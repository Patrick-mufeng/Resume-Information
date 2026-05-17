"""API Key ORM 模型"""

from datetime import datetime
from sqlalchemy import String, Boolean, DateTime, JSON, func
from sqlalchemy.orm import Mapped, mapped_column
from backend.models.database import Base


class APIKey(Base):
    __tablename__ = "api_keys"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    key_value: Mapped[str] = mapped_column(String(512), nullable=False)  # Fernet 加密存储
    label: Mapped[str] = mapped_column(String(100), default="", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    requests_today: Mapped[int] = mapped_column(default=0)
    tokens_today: Mapped[int] = mapped_column(default=0)
    tpm_used: Mapped[int] = mapped_column(default=0)
    tpm_reset_time: Mapped[float] = mapped_column(default=0.0)
    daily_reset_time: Mapped[float] = mapped_column(default=0.0)
    consecutive_errors: Mapped[int] = mapped_column(default=0)
    next_available_time: Mapped[float] = mapped_column(default=0.0)
    provider: Mapped[str] = mapped_column(String(50), default="moonshot", nullable=False)
    base_url_override: Mapped[str | None] = mapped_column(String(512), nullable=True)
    model_override: Mapped[str | None] = mapped_column(String(100), nullable=True)
    is_validated: Mapped[bool | None] = mapped_column(Boolean, nullable=True, default=None)  # None=未检查, True=有效, False=无效
    last_check_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_check_error: Mapped[str | None] = mapped_column(String(500), nullable=True)
