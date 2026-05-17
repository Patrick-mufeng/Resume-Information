"""ProcessingJob 相关 Pydantic 模型"""

from datetime import datetime
from pydantic import BaseModel, Field


class JobCreate(BaseModel):
    name: str = Field(default="", max_length=200)


class JobResponse(BaseModel):
    id: int
    name: str
    status: str
    total_files: int
    processed_count: int
    failed_count: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class JobStatusResponse(JobResponse):
    pending_count: int = 0
    processing_count: int = 0
