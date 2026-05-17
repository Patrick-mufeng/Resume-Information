"""设置相关 Pydantic 模型"""

from pydantic import BaseModel, Field


class ExtractionFieldCreate(BaseModel):
    field_key: str = Field(..., min_length=1, max_length=50, description="JSON 键名如 姓名")
    field_label: str = Field(..., min_length=1, max_length=100, description="字段说明如 姓名")
    field_hint: str = Field(default="", max_length=200, description="格式提示如 11位")


class ExtractionFieldUpdate(BaseModel):
    field_label: str | None = None
    field_hint: str | None = None
    sort_order: int | None = None


class ExtractionFieldResponse(BaseModel):
    id: int
    field_key: str
    field_label: str
    field_hint: str
    sort_order: int

    model_config = {"from_attributes": True}
