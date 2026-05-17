"""设置路由 — 提取字段自定义管理"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.database import get_session
from backend.models.extraction_field import ExtractionField
from backend.schemas.settings import (
    ExtractionFieldCreate,
    ExtractionFieldUpdate,
    ExtractionFieldResponse,
)
from backend.services.prompt_builder import clear_prompt_cache

router = APIRouter(prefix="/api/settings", tags=["Settings"])

# 默认字段
DEFAULT_FIELDS = [
    ("姓名", "姓名", ""),
    ("性别", "性别", "男/女"),
    ("出生年月", "出生年月", "YYYY-MM"),
    ("手机号码", "手机号码", "11位"),
    ("最高学历", "最高学历", "大专/本科/硕士/博士"),
    ("毕业学校", "毕业学校", ""),
    ("毕业年份", "毕业年份", "YYYY"),
    ("地区", "地区", "省/市"),
    ("专业名称", "专业名称", ""),
    ("应聘职位", "应聘职位", ""),
]


async def _init_default_fields(session: AsyncSession):
    """初始化默认字段（如果表为空）"""
    count = await session.scalar(select(func.count(ExtractionField.id)))
    if count == 0:
        for i, (key, label, hint) in enumerate(DEFAULT_FIELDS):
            session.add(ExtractionField(
                field_key=key, field_label=label,
                field_hint=hint, sort_order=i,
            ))
        await session.commit()


@router.get("/fields", response_model=list[ExtractionFieldResponse])
async def list_fields(session: AsyncSession = Depends(get_session)):
    """获取所有提取字段"""
    await _init_default_fields(session)
    result = await session.execute(
        select(ExtractionField).order_by(ExtractionField.sort_order)
    )
    return result.scalars().all()


@router.post("/fields", response_model=ExtractionFieldResponse)
async def create_field(
    data: ExtractionFieldCreate,
    session: AsyncSession = Depends(get_session),
):
    """添加提取字段"""
    # 获取最大排序
    max_order = await session.scalar(select(func.max(ExtractionField.sort_order))) or 0

    field = ExtractionField(
        field_key=data.field_key,
        field_label=data.field_label,
        field_hint=data.field_hint,
        sort_order=max_order + 1,
    )
    session.add(field)
    await session.commit()
    await session.refresh(field)
    clear_prompt_cache()
    return field


@router.put("/fields/{field_id}", response_model=ExtractionFieldResponse)
async def update_field(
    field_id: int,
    data: ExtractionFieldUpdate,
    session: AsyncSession = Depends(get_session),
):
    """更新提取字段"""
    result = await session.execute(
        select(ExtractionField).where(ExtractionField.id == field_id)
    )
    field = result.scalar_one_or_none()
    if not field:
        raise HTTPException(status_code=404, detail="字段不存在")

    if data.field_label is not None:
        field.field_label = data.field_label
    if data.field_hint is not None:
        field.field_hint = data.field_hint
    if data.sort_order is not None:
        field.sort_order = data.sort_order

    await session.commit()
    await session.refresh(field)
    clear_prompt_cache()
    return field


@router.delete("/fields/{field_id}")
async def delete_field(field_id: int, session: AsyncSession = Depends(get_session)):
    """删除提取字段"""
    result = await session.execute(
        select(ExtractionField).where(ExtractionField.id == field_id)
    )
    field = result.scalar_one_or_none()
    if not field:
        raise HTTPException(status_code=404, detail="字段不存在")

    # 至少保留一个字段
    count = await session.scalar(select(func.count(ExtractionField.id)))
    if count <= 1:
        raise HTTPException(status_code=400, detail="至少保留一个提取字段")

    await session.delete(field)
    await session.commit()
    clear_prompt_cache()
    return {"message": "已删除"}


@router.post("/fields/reset")
async def reset_fields(session: AsyncSession = Depends(get_session)):
    """重置为默认提取字段"""
    # 删除所有现有字段
    fields = (await session.execute(select(ExtractionField))).scalars().all()
    for f in fields:
        await session.delete(f)
    await session.commit()

    # 重新初始化
    await _init_default_fields(session)
    clear_prompt_cache()

    return {"message": "已重置为默认字段", "count": len(DEFAULT_FIELDS)}
