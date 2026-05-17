"""动态 Prompt 构建器 — 根据用户自定义字段生成提取提示词"""

import logging
from sqlalchemy import select

logger = logging.getLogger(__name__)

# 缓存：避免每次请求都查库
_cached_prompt: str | None = None
_cached_model: str | None = None


def clear_prompt_cache():
    """清除 Prompt 缓存（字段变更时调用）"""
    global _cached_prompt
    _cached_prompt = None
    logger.info("Prompt 缓存已清除")


async def build_extraction_prompt(session_factory) -> str:
    """根据数据库中的自定义字段动态生成 System Prompt

    Args:
        session_factory: async_session factory

    Returns:
        完整的 system prompt 字符串
    """
    global _cached_prompt

    if _cached_prompt is not None:
        return _cached_prompt

    from backend.models.extraction_field import ExtractionField

    async with session_factory() as session:
        result = await session.execute(
            select(ExtractionField).order_by(ExtractionField.sort_order)
        )
        fields = result.scalars().all()

    if not fields:
        # 降级到硬编码默认
        _cached_prompt = (
            "你是一个专业的简历信息提取系统。请严格按以下要求及格式从简历中提取信息并以JSON格式返回:\n"
            "1. 姓名\n2. 性别(男/女)\n3. 出生年月(YYYY-MM)\n4. 手机号码(11位)\n"
            "5. 最高学历(大专/本科/硕士/博士)\n6. 毕业学校\n7. 毕业年份(YYYY)\n8. 地区(省/市)\n9. 专业名称\n10. 应聘职位\n"
            "示例: {'姓名':'张三','性别':'男','出生年月':'1990-05','手机号码':'11111111111'...}\n"
            "只返回JSON数据，不要任何解释！"
        )
        return _cached_prompt

    # 构建字段列表
    field_lines = []
    example_parts = []
    for i, f in enumerate(fields, 1):
        hint = f"({f.field_hint})" if f.field_hint else ""
        field_lines.append(f"{i}. {f.field_label}{hint}")
        example_parts.append(f"'{f.field_key}':'...'")

    field_list = "\n".join(field_lines)
    example = "{" + ", ".join(example_parts) + "}"

    _cached_prompt = (
        f"你是一个专业的简历信息提取系统。请严格按以下要求及格式从简历中提取信息并以JSON格式返回:\n"
        f"{field_list}\n"
        f"示例: {example}\n"
        f"只返回JSON数据，不要任何解释！"
    )
    return _cached_prompt
