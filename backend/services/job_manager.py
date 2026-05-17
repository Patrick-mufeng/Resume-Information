"""任务管理器

编排简历处理流水线：并发控制、WebSocket 推送、暂停/恢复。
"""

import asyncio
import logging
from pathlib import Path
from typing import Callable

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from backend.config import settings
from backend.models.resume import Resume, ResumeStatus
from backend.models.job import ProcessingJob, JobStatus
from backend.services.key_rotator import key_rotator
from backend.services.resume_processor import extract_resume_info
from backend.services.file_manager import image_to_base64, get_upload_path

logger = logging.getLogger(__name__)


class JobManager:
    """处理任务编排器"""

    def __init__(self):
        self._running_jobs: dict[int, asyncio.Task] = {}  # job_id -> task
        self._pause_flags: dict[int, asyncio.Event] = {}  # job_id -> pause event
        self._ws_callbacks: dict[int, list[Callable]] = {}  # job_id -> [callback]
        self._ws_message_buffer: dict[int, list[dict]] = {}  # job_id -> [messages] 缓冲给新连接重放
        self._semaphore: asyncio.Semaphore | None = None
        self._sessionmaker: async_sessionmaker[AsyncSession] | None = None

    def set_sessionmaker(self, sm: async_sessionmaker[AsyncSession]):
        self._sessionmaker = sm

    async def register_ws_callback(self, job_id: int, callback: Callable):
        """注册 WebSocket 回调（用于推送进度消息），并重放历史消息"""
        if job_id not in self._ws_callbacks:
            self._ws_callbacks[job_id] = []
        self._ws_callbacks[job_id].append(callback)
        # 新客户端连接后重放已缓存的消息
        await self._replay_to_client(job_id, callback)

    def unregister_ws_callback(self, job_id: int, callback: Callable):
        """移除 WebSocket 回调"""
        if job_id in self._ws_callbacks:
            self._ws_callbacks[job_id] = [
                cb for cb in self._ws_callbacks[job_id] if cb is not callback
            ]

    async def _push_progress(self, job_id: int, message: dict):
        """向所有注册的 WebSocket 客户端推送进度消息，并缓存供新连接重放"""
        # 缓存消息（job_completed 是最终消息，之后不再缓存）
        if job_id not in self._ws_message_buffer:
            self._ws_message_buffer[job_id] = []
        self._ws_message_buffer[job_id].append(message)

        # 推送
        if job_id in self._ws_callbacks:
            for cb in self._ws_callbacks[job_id]:
                try:
                    await cb(message)
                except Exception as e:
                    logger.error(f"WebSocket 推送失败: {e}")

    async def _replay_to_client(self, job_id: int, callback: Callable):
        """将已缓存的消息重放给新连接的客户端"""
        if job_id in self._ws_message_buffer:
            for msg in self._ws_message_buffer[job_id]:
                try:
                    await callback(msg)
                except Exception as e:
                    logger.error(f"重放消息失败: {e}")

    async def start_job(self, job_id: int):
        """启动处理任务"""
        if not self._sessionmaker:
            raise RuntimeError("sessionmaker 未初始化")

        if job_id in self._running_jobs:
            raise RuntimeError(f"任务 {job_id} 已在运行中")

        self._semaphore = asyncio.Semaphore(settings.MAX_CONCURRENT_PROCESSING)
        self._pause_flags[job_id] = asyncio.Event()
        self._pause_flags[job_id].set()  # 初始为不暂停状态

        task = asyncio.create_task(self._process_job(job_id))
        self._running_jobs[job_id] = task

        # 更新 job 状态
        async with self._sessionmaker() as session:
            await session.execute(
                update(ProcessingJob)
                .where(ProcessingJob.id == job_id)
                .values(status=JobStatus.RUNNING)
            )
            await session.commit()

        logger.info(f"任务 {job_id} 已启动")

    async def pause_job(self, job_id: int):
        """暂停处理任务"""
        if job_id in self._pause_flags:
            self._pause_flags[job_id].clear()
            async with self._sessionmaker() as session:
                await session.execute(
                    update(ProcessingJob)
                    .where(ProcessingJob.id == job_id)
                    .values(status=JobStatus.PAUSED)
                )
                await session.commit()
            await self._push_progress(job_id, {"type": "job_paused"})
            logger.info(f"任务 {job_id} 已暂停")

    async def resume_job(self, job_id: int):
        """恢复处理任务"""
        if job_id in self._pause_flags:
            self._pause_flags[job_id].set()
            async with self._sessionmaker() as session:
                await session.execute(
                    update(ProcessingJob)
                    .where(ProcessingJob.id == job_id)
                    .values(status=JobStatus.RUNNING)
                )
                await session.commit()
            await self._push_progress(job_id, {"type": "job_resumed"})
            logger.info(f"任务 {job_id} 已恢复")

    async def _process_job(self, job_id: int):
        """核心处理循环"""
        try:
            await self._push_progress(job_id, {"type": "job_started"})

            while True:
                # 检查暂停
                if job_id in self._pause_flags:
                    await self._pause_flags[job_id].wait()

                # 获取下一个待处理的简历
                async with self._sessionmaker() as session:
                    result = await session.execute(
                        select(Resume)
                        .where(
                            Resume.job_id == job_id,
                            Resume.status == ResumeStatus.PENDING,
                        )
                        .limit(1)
                    )
                    resume = result.scalar_one_or_none()

                    if resume is None:
                        break  # 没有待处理的了

                    resume.status = ResumeStatus.PROCESSING
                    await session.commit()

                # 并发控制
                async with self._semaphore:
                    await self._process_single_resume(resume, job_id)

            # 标记 job 完成
            await self._finalize_job(job_id)

        except asyncio.CancelledError:
            logger.info(f"任务 {job_id} 被取消")
            async with self._sessionmaker() as session:
                await session.execute(
                    update(ProcessingJob)
                    .where(ProcessingJob.id == job_id)
                    .values(status=JobStatus.FAILED)
                )
                await session.commit()
        except Exception as e:
            logger.error(f"任务 {job_id} 处理异常: {e}")
            async with self._sessionmaker() as session:
                await session.execute(
                    update(ProcessingJob)
                    .where(ProcessingJob.id == job_id)
                    .values(status=JobStatus.FAILED)
                )
                await session.commit()
            await self._push_progress(job_id, {"type": "job_error", "error": str(e)})
        finally:
            self._running_jobs.pop(job_id, None)

    async def _process_single_resume(self, resume: Resume, job_id: int):
        """处理单份简历"""
        filename = resume.original_filename
        await self._push_progress(job_id, {
            "type": "file_started",
            "resume_id": resume.id,
            "filename": filename,
        })

        start_time = asyncio.get_event_loop().time()

        try:
            # 读取图片
            image_path = get_upload_path(resume.stored_filename)
            base64_img = await asyncio.to_thread(image_to_base64, image_path)

            # 获取 Key 并调用 API
            key_id, key_info = await key_rotator.get_available_key()
            info, tokens_used = await extract_resume_info(
                base64_img,
                api_key=key_info["key"],
                provider=key_info.get("provider", "moonshot"),
                base_url_override=key_info.get("base_url_override"),
                model_override=key_info.get("model_override"),
                session_factory=self._sessionmaker,
            )

            elapsed_ms = (asyncio.get_event_loop().time() - start_time) * 1000

            # 持久化结果
            async with self._sessionmaker() as session:
                await session.execute(
                    update(Resume)
                    .where(Resume.id == resume.id)
                    .values(
                        status=ResumeStatus.COMPLETED,
                        extracted_data=info,
                        api_key_id=key_id,
                        tokens_used=tokens_used,
                        processing_time_ms=elapsed_ms,
                    )
                )
                await session.execute(
                    update(ProcessingJob)
                    .where(ProcessingJob.id == job_id)
                    .values(processed_count=ProcessingJob.processed_count + 1)
                )
                await session.commit()

            await key_rotator.update_key_stats(key_id, tokens_used)

            await self._push_progress(job_id, {
                "type": "file_completed",
                "resume_id": resume.id,
                "filename": filename,
                "name": info.get("姓名", ""),
                "duration_ms": elapsed_ms,
            })

        except Exception as e:
            elapsed_ms = (asyncio.get_event_loop().time() - start_time) * 1000
            error_msg = str(e)

            async with self._sessionmaker() as session:
                new_retry = resume.retry_count + 1
                new_status = ResumeStatus.FAILED if new_retry >= settings.RETRY_MAX_ATTEMPTS else ResumeStatus.PENDING

                await session.execute(
                    update(Resume)
                    .where(Resume.id == resume.id)
                    .values(
                        status=new_status,
                        error_message=error_msg,
                        retry_count=new_retry,
                        processing_time_ms=elapsed_ms,
                    )
                )
                if new_status == ResumeStatus.FAILED:
                    await session.execute(
                        update(ProcessingJob)
                        .where(ProcessingJob.id == job_id)
                        .values(failed_count=ProcessingJob.failed_count + 1)
                    )
                await session.commit()

            await self._push_progress(job_id, {
                "type": "file_failed",
                "resume_id": resume.id,
                "filename": filename,
                "error": error_msg,
                "retry": new_retry,
            })

    async def _finalize_job(self, job_id: int):
        """完成任务并更新状态"""
        async with self._sessionmaker() as session:
            result = await session.execute(
                select(ProcessingJob).where(ProcessingJob.id == job_id)
            )
            job = result.scalar_one_or_none()
            if job:
                # 检查是否有失败项
                failed_result = await session.execute(
                    select(Resume).where(
                        Resume.job_id == job_id,
                        Resume.status == ResumeStatus.FAILED,
                    )
                )
                failed_count = len(failed_result.scalars().all())
                status = JobStatus.FAILED if failed_count > 0 else JobStatus.COMPLETED
                await session.execute(
                    update(ProcessingJob)
                    .where(ProcessingJob.id == job_id)
                    .values(status=status)
                )
                await session.commit()

                await self._push_progress(job_id, {
                    "type": "job_completed",
                    "status": status.value,
                    "processed": job.processed_count,
                    "failed": failed_count,
                })


# 全局单例
job_manager = JobManager()
