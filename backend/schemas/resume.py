"""Resume 相关 Pydantic 模型"""

from datetime import datetime
from pydantic import BaseModel, Field


class ResumeResponse(BaseModel):
    id: int
    job_id: int | None
    original_filename: str
    stored_filename: str
    file_size: int
    status: str
    extracted_data: dict | None
    error_message: str | None
    api_key_id: int | None
    tokens_used: int
    processing_time_ms: float
    retry_count: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ResumeListResponse(BaseModel):
    items: list[ResumeResponse]
    total: int
    page: int
    page_size: int
