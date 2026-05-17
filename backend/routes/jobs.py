"""处理任务管理路由"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func, update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.database import get_session
from backend.models.job import ProcessingJob, JobStatus
from backend.models.resume import Resume, ResumeStatus
from backend.schemas.job import JobCreate, JobResponse, JobStatusResponse
from backend.services.job_manager import job_manager

router = APIRouter(prefix="/api/jobs", tags=["Jobs"])


@router.get("", response_model=list[JobResponse])
async def list_jobs(session: AsyncSession = Depends(get_session)):
    """获取所有任务列表"""
    result = await session.execute(
        select(ProcessingJob).order_by(ProcessingJob.created_at.desc())
    )
    jobs = result.scalars().all()
    return [
        JobResponse(
            id=j.id,
            name=j.name,
            status=j.status.value,
            total_files=j.total_files,
            processed_count=j.processed_count,
            failed_count=j.failed_count,
            created_at=j.created_at,
            updated_at=j.updated_at,
        )
        for j in jobs
    ]


@router.post("", response_model=JobResponse)
async def create_job(data: JobCreate, session: AsyncSession = Depends(get_session)):
    """创建新的处理任务"""
    job = ProcessingJob(name=data.name or "新任务")
    session.add(job)
    await session.commit()
    await session.refresh(job)

    return JobResponse(
        id=job.id,
        name=job.name,
        status=job.status.value,
        total_files=job.total_files,
        processed_count=job.processed_count,
        failed_count=job.failed_count,
        created_at=job.created_at,
        updated_at=job.updated_at,
    )


@router.get("/{job_id}", response_model=JobStatusResponse)
async def get_job_status(job_id: int, session: AsyncSession = Depends(get_session)):
    """获取任务详情（含各状态简历数量）"""
    result = await session.execute(
        select(ProcessingJob).where(ProcessingJob.id == job_id)
    )
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="任务不存在")

    # 统计各状态数量
    pending = await session.execute(
        select(func.count(Resume.id)).where(
            Resume.job_id == job_id,
            Resume.status == ResumeStatus.PENDING,
        )
    )
    processing = await session.execute(
        select(func.count(Resume.id)).where(
            Resume.job_id == job_id,
            Resume.status == ResumeStatus.PROCESSING,
        )
    )

    return JobStatusResponse(
        id=job.id,
        name=job.name,
        status=job.status.value,
        total_files=job.total_files,
        processed_count=job.processed_count,
        failed_count=job.failed_count,
        created_at=job.created_at,
        updated_at=job.updated_at,
        pending_count=pending.scalar() or 0,
        processing_count=processing.scalar() or 0,
    )


@router.post("/{job_id}/start")
async def start_job(job_id: int, session: AsyncSession = Depends(get_session)):
    """启动处理任务"""
    result = await session.execute(
        select(ProcessingJob).where(ProcessingJob.id == job_id)
    )
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="任务不存在")

    if job.status in (JobStatus.RUNNING,):
        raise HTTPException(status_code=400, detail="任务已在运行中")

    try:
        await job_manager.start_job(job_id)
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return {"message": "任务已启动"}


@router.post("/{job_id}/pause")
async def pause_job(job_id: int):
    """暂停处理任务"""
    await job_manager.pause_job(job_id)
    return {"message": "任务已暂停"}


@router.post("/{job_id}/resume")
async def resume_job(job_id: int):
    """恢复处理任务"""
    await job_manager.resume_job(job_id)
    return {"message": "任务已恢复"}


@router.delete("/{job_id}")
async def delete_job(job_id: int, session: AsyncSession = Depends(get_session)):
    """删除任务及其所有关联简历"""
    result = await session.execute(
        select(ProcessingJob).where(ProcessingJob.id == job_id)
    )
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="任务不存在")

    # 删除关联简历
    await session.execute(
        update(Resume)
        .where(Resume.job_id == job_id)
        .values(job_id=None)
    )
    await session.delete(job)
    await session.commit()

    return {"message": "已删除"}
