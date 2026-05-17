"""提取字段 ORM 模型 — 用户可自定义"""

from sqlalchemy import String, Integer
from sqlalchemy.orm import Mapped, mapped_column
from backend.models.database import Base


class ExtractionField(Base):
    __tablename__ = "extraction_fields"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    field_key: Mapped[str] = mapped_column(String(50), nullable=False)  # JSON key
    field_label: Mapped[str] = mapped_column(String(100), nullable=False)  # 显示名
    field_hint: Mapped[str] = mapped_column(String(200), default="", nullable=False)  # 提示如 "11位"
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
