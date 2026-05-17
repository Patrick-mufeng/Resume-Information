"""Resume ORM 模型"""

import enum
from datetime import datetime
from sqlalchemy import String, Integer, Float, Text, DateTime, Enum, JSON, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column
from backend.models.database import Base


class ResumeStatus(str, enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class Resume(Base):
    __tablename__ = "resumes"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    job_id: Mapped[int | None] = mapped_column(ForeignKey("processing_jobs.id"), nullable=True, index=True)
    original_filename: Mapped[str] = mapped_column(String(500), nullable=False, index=True)
    stored_filename: Mapped[str] = mapped_column(String(500), nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[ResumeStatus] = mapped_column(
        Enum(ResumeStatus), default=ResumeStatus.PENDING, index=True
    )
    extracted_data: Mapped[str | None] = mapped_column(JSON, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    api_key_id: Mapped[int | None] = mapped_column(ForeignKey("api_keys.id"), nullable=True)
    tokens_used: Mapped[int] = mapped_column(Integer, default=0)
    processing_time_ms: Mapped[float] = mapped_column(Float, default=0.0)
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )
