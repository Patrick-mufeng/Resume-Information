"""API Key 相关 Pydantic 模型"""

from datetime import datetime
from pydantic import BaseModel, Field, field_validator


VALID_PROVIDERS = {"moonshot", "openai", "deepseek", "anthropic", "gemini", "custom"}


class APIKeyCreate(BaseModel):
    key_value: str = Field(..., min_length=10, description="API Key")
    label: str = Field(default="", max_length=100, description="Key 备注标签")
    provider: str = Field(default="moonshot", description="API 提供商")
    base_url_override: str | None = Field(default=None, description="自定义 Base URL")
    model_override: str | None = Field(default=None, description="自定义模型名")

    @field_validator("provider")
    @classmethod
    def validate_provider(cls, v):
        if v not in VALID_PROVIDERS:
            raise ValueError(f"不支持的提供商: {v}，可选: {', '.join(sorted(VALID_PROVIDERS))}")
        return v


class APIKeyUpdate(BaseModel):
    label: str | None = None
    is_active: bool | None = None


class KeyCheckResponse(BaseModel):
    id: int
    is_valid: bool | None  # True=有效, False=无效, None=无法确定（网络问题）
    error: str | None = None


class APIKeyResponse(BaseModel):
    id: int
    key_masked: str
    label: str
    is_active: bool
    provider: str
    base_url_override: str | None = None
    model_override: str | None = None
    is_validated: bool | None = None  # None=未检查, True=有效, False=无效
    last_check_at: datetime | None = None
    last_check_error: str | None = None
    created_at: datetime
    last_used_at: datetime | None
    requests_today: int
    tokens_today: int
    tpm_used: int
    consecutive_errors: int

    model_config = {"from_attributes": True}
