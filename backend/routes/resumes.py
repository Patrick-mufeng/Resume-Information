"""简历管理路由"""

import csv
import io
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File
from fastapi.responses import StreamingResponse
from sqlalchemy import select, func, update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.database import get_session
from backend.models.resume import Resume, ResumeStatus
from backend.models.job import ProcessingJob, JobStatus
from backend.schemas.resume import ResumeResponse, ResumeListResponse
from backend.services.file_manager import (
    validate_file, generate_stored_filename, save_upload_file,
    delete_uploaded_file, get_upload_path,
)

router = APIRouter(prefix="/api/resumes", tags=["Resumes"])


@router.get("", response_model=ResumeListResponse)
async def list_resumes(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    status: str | None = Query(None),
    search: str | None = Query(None),
    session: AsyncSession = Depends(get_session),
):
    """获取简历列表（分页、筛选、搜索）"""
    query = select(Resume)
    count_query = select(func.count(Resume.id))

    if status:
        query = query.where(Resume.status == status)
        count_query = count_query.where(Resume.status == status)

    if search:
        search_filter = Resume.original_filename.contains(search)
        query = query.where(search_filter)
        count_query = count_query.where(search_filter)

    total_result = await session.execute(count_query)
    total = total_result.scalar()

    query = query.order_by(Resume.created_at.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)
    result = await session.execute(query)
    resumes = result.scalars().all()

    return ResumeListResponse(
        items=[
            ResumeResponse(
                id=r.id,
                job_id=r.job_id,
                original_filename=r.original_filename,
                stored_filename=r.stored_filename,
                file_size=r.file_size,
                status=r.status.value,
                extracted_data=r.extracted_data,
                error_message=r.error_message,
                api_key_id=r.api_key_id,
                tokens_used=r.tokens_used,
                processing_time_ms=r.processing_time_ms,
                retry_count=r.retry_count,
                created_at=r.created_at,
                updated_at=r.updated_at,
            )
            for r in resumes
        ],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{resume_id}", response_model=ResumeResponse)
async def get_resume(resume_id: int, session: AsyncSession = Depends(get_session)):
    """获取单条简历详情"""
    result = await session.execute(select(Resume).where(Resume.id == resume_id))
    resume = result.scalar_one_or_none()
    if not resume:
        raise HTTPException(status_code=404, detail="简历不存在")

    return ResumeResponse(
        id=resume.id,
        job_id=resume.job_id,
        original_filename=resume.original_filename,
        stored_filename=resume.stored_filename,
        file_size=resume.file_size,
        status=resume.status.value,
        extracted_data=resume.extracted_data,
        error_message=resume.error_message,
        api_key_id=resume.api_key_id,
        tokens_used=resume.tokens_used,
        processing_time_ms=resume.processing_time_ms,
        retry_count=resume.retry_count,
        created_at=resume.created_at,
        updated_at=resume.updated_at,
    )


@router.delete("/{resume_id}")
async def delete_resume(resume_id: int, session: AsyncSession = Depends(get_session)):
    """删除单条简历记录及其文件"""
    result = await session.execute(select(Resume).where(Resume.id == resume_id))
    resume = result.scalar_one_or_none()
    if not resume:
        raise HTTPException(status_code=404, detail="简历不存在")

    # 删除磁盘文件
    delete_uploaded_file(resume.stored_filename)
    await session.delete(resume)
    await session.commit()

    return {"message": "已删除"}


@router.post("/{resume_id}/retry")
async def retry_resume(resume_id: int, session: AsyncSession = Depends(get_session)):
    """重试失败的简历"""
    result = await session.execute(select(Resume).where(Resume.id == resume_id))
    resume = result.scalar_one_or_none()
    if not resume:
        raise HTTPException(status_code=404, detail="简历不存在")

    if resume.status != ResumeStatus.FAILED:
        raise HTTPException(status_code=400, detail="只能重试失败的简历")

    await session.execute(
        update(Resume)
        .where(Resume.id == resume_id)
        .values(status=ResumeStatus.PENDING, error_message=None, retry_count=0)
    )
    await session.commit()

    return {"message": "已加入重试队列"}


@router.post("/process-folder")
async def process_folder(
    folder_path: str = Query(..., description="简历文件夹路径"),
    session: AsyncSession = Depends(get_session),
):
    """扫描文件夹 → 转换 PDF/Word → 自动识别

    1. 扫描文件夹中的 PDF/Word/图片
    2. PDF/Word 转为图片（已有对应图片则跳过）
    3. 删除空白页
    4. 复制到上传目录
    5. 创建任务并自动启动处理
    """
    import shutil
    from pathlib import Path
    from backend.services.file_converter import scan_and_convert
    from backend.services.job_manager import job_manager
    from backend.services.file_manager import generate_stored_filename, get_upload_path

    src_folder = Path(folder_path)
    if not src_folder.exists():
        raise HTTPException(status_code=400, detail=f"文件夹不存在: {folder_path}")

    # 扫描并转换
    images = scan_and_convert(folder_path)

    if not images:
        raise HTTPException(status_code=400, detail="文件夹中未找到简历文件（支持 PDF/Word/JPG/PNG）")

    # 创建任务
    job = ProcessingJob(name=src_folder.name, status=JobStatus.PENDING)
    session.add(job)
    await session.commit()
    await session.refresh(job)

    # 复制图片到上传目录并注册（批量添加，一次 flush + commit）
    resumes = []
    for img in images:
        stored_name = generate_stored_filename(img.name)
        dest = get_upload_path(stored_name)
        shutil.copy2(str(img), str(dest))

        resume = Resume(
            job_id=job.id,
            original_filename=img.name,
            stored_filename=stored_name,
            file_size=img.stat().st_size,
            status=ResumeStatus.PENDING,
        )
        session.add(resume)
        resumes.append(resume)

    await session.flush()  # 批量分配 ID
    resume_ids = [r.id for r in resumes]

    # 更新任务文件数
    job.total_files = len(resume_ids)
    await session.commit()

    return {
        "message": f"扫描完成，共 {len(resume_ids)} 份简历",
        "job_id": job.id,
        "total": len(resume_ids),
        "resume_ids": resume_ids,
    }


@router.post("/process-folder/start")
async def process_folder_start(
    folder_path: str = Query(..., description="简历文件夹路径"),
    session: AsyncSession = Depends(get_session),
):
    """扫描 + 转换 + 直接启动处理（合并接口）"""
    from backend.services.job_manager import job_manager

    # 先调用 process_folder 的逻辑
    result = await process_folder(folder_path, session)

    # 立即启动
    try:
        await job_manager.start_job(result["job_id"])
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return {**result, "status": "started"}


@router.post("/upload")
async def upload_files(
    files: list[UploadFile] = File(...),
    job_id: int | None = None,
    session: AsyncSession = Depends(get_session),
):
    """上传简历文件，关联到指定任务"""
    uploaded = []
    errors = []
    pending_resumes = []  # 批量 flush 用

    import shutil
    from pathlib import Path as FilePath
    from backend.services.file_converter import convert_pdf_to_images, convert_docx_to_images

    for file in files:
        content = await file.read()

        # 验证文件
        err = validate_file(file.filename, len(content))
        if err:
            errors.append({"filename": file.filename, "error": err})
            continue

        # 保存原始文件
        stored_name = generate_stored_filename(file.filename)
        stored_path = await save_upload_file(content, stored_name)

        ext = FilePath(file.filename).suffix.lower()

        if ext in (".pdf", ".docx", ".doc"):
            # PDF/Word → 转换为图片
            try:
                if ext == ".pdf":
                    images = convert_pdf_to_images(stored_path, stored_path.parent)
                else:
                    images = convert_docx_to_images(stored_path, stored_path.parent)

                # 删除原始文件
                stored_path.unlink()

                # 每个图片页注册为一份简历
                for img_path in images:
                    resume = Resume(
                        job_id=job_id,
                        original_filename=f"{file.filename} (第{img_path.stem[-3:]}页)",
                        stored_filename=img_path.name,
                        file_size=img_path.stat().st_size,
                        status=ResumeStatus.PENDING,
                    )
                    session.add(resume)
                    pending_resumes.append((resume, img_path.stat().st_size))
            except Exception as e:
                errors.append({"filename": file.filename, "error": f"转换失败: {e}"})
        else:
            # 图片直接保存
            resume = Resume(
                job_id=job_id,
                original_filename=file.filename,
                stored_filename=stored_name,
                file_size=len(content),
                status=ResumeStatus.PENDING,
            )
            session.add(resume)
            pending_resumes.append((resume, len(content)))

    # 批量 flush 获取 ID
    await session.flush()
    for resume, size in pending_resumes:
        uploaded.append({
            "id": resume.id,
            "filename": resume.original_filename,
            "size": size,
        })

    # 更新 job 的 total_files
    if job_id:
        count_result = await session.execute(
            select(func.count(Resume.id)).where(Resume.job_id == job_id)
        )
        total = count_result.scalar()
        await session.execute(
            update(ProcessingJob)
            .where(ProcessingJob.id == job_id)
            .values(total_files=total)
        )
    await session.commit()

    return {"uploaded": uploaded, "errors": errors}


@router.get("/export/csv")
async def export_csv(
    job_id: int | None = Query(None),
    session: AsyncSession = Depends(get_session),
):
    """导出结果为 CSV 文件（使用自定义字段）"""
    from backend.models.extraction_field import ExtractionField

    # 获取自定义字段
    field_result = await session.execute(
        select(ExtractionField).order_by(ExtractionField.sort_order)
    )
    fields = field_result.scalars().all()
    if not fields:
        fields = [
            type('F', (), {'field_key': k, 'field_label': v})()
            for k, v in [("姓名", "姓名"), ("性别", "性别"), ("出生年月", "出生年月"),
                         ("手机号码", "手机号码"), ("最高学历", "最高学历"), ("毕业学校", "毕业学校"),
                         ("毕业年份", "毕业年份"), ("地区", "地区"), ("专业名称", "专业名称"),
                         ("应聘职位", "应聘职位")]
        ]

    query = select(Resume).where(
        Resume.status == ResumeStatus.COMPLETED,
        Resume.extracted_data.isnot(None),
    )
    if job_id:
        query = query.where(Resume.job_id == job_id)
    query = query.order_by(Resume.created_at.desc())

    result = await session.execute(query)
    resumes = result.scalars().all()

    output = io.StringIO()
    writer = csv.writer(output)

    # 动态表头
    headers = ["文件名"] + [f.field_label for f in fields]
    writer.writerow(headers)

    # 动态数据
    for r in resumes:
        data = r.extracted_data or {}
        row = [r.original_filename] + [data.get(f.field_key, "") for f in fields]
        writer.writerow(row)

    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=resume_results.csv"},
    )
