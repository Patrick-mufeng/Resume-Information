"""API Key 管理路由"""

import logging
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.database import get_session
from backend.models.api_key import APIKey
from backend.schemas.api_key import APIKeyCreate, APIKeyUpdate, APIKeyResponse, KeyCheckResponse
from backend.services.key_rotator import key_rotator
from backend.services.encryption import encrypt_key, decrypt_key
from backend.services.key_validator import validate_key

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/keys", tags=["API Keys"])


def mask_key(key_value: str) -> str:
    """脱敏显示 Key"""
    if len(key_value) > 10:
        return key_value[:6] + "..." + key_value[-4:]
    return "***"


def _key_to_response(k: APIKey) -> APIKeyResponse:
    return APIKeyResponse(
        id=k.id,
        key_masked=mask_key(decrypt_key(k.key_value)),
        label=k.label,
        is_active=k.is_active,
        provider=k.provider,
        base_url_override=k.base_url_override,
        model_override=k.model_override,
        is_validated=k.is_validated,
        last_check_at=k.last_check_at,
        last_check_error=k.last_check_error,
        created_at=k.created_at,
        last_used_at=k.last_used_at,
        requests_today=k.requests_today,
        tokens_today=k.tokens_today,
        tpm_used=k.tpm_used,
        consecutive_errors=k.consecutive_errors,
    )


@router.get("", response_model=list[APIKeyResponse])
async def list_keys(session: AsyncSession = Depends(get_session)):
    """获取所有 API Key（脱敏显示）"""
    result = await session.execute(select(APIKey).order_by(APIKey.created_at.desc()))
    return [_key_to_response(k) for k in result.scalars().all()]


@router.post("", response_model=APIKeyResponse)
async def create_key(data: APIKeyCreate, session: AsyncSession = Depends(get_session)):
    """添加新的 API Key"""
    # Custom provider 校验
    if data.provider == "custom" and (not data.base_url_override or not data.model_override):
        raise HTTPException(status_code=400, detail="Custom 提供商必须提供 base_url_override 和 model_override")

    encrypted = encrypt_key(data.key_value)
    api_key = APIKey(
        key_value=encrypted,
        label=data.label,
        provider=data.provider,
        base_url_override=data.base_url_override,
        model_override=data.model_override,
    )
    session.add(api_key)
    await session.commit()
    await session.refresh(api_key)
    await key_rotator.reload_keys()

    return _key_to_response(api_key)


@router.delete("/{key_id}")
async def delete_key(key_id: int, session: AsyncSession = Depends(get_session)):
    """删除 API Key"""
    result = await session.execute(select(APIKey).where(APIKey.id == key_id))
    api_key = result.scalar_one_or_none()
    if not api_key:
        raise HTTPException(status_code=404, detail="Key 不存在")

    await session.delete(api_key)
    await session.commit()
    await key_rotator.reload_keys()

    return {"message": "已删除"}


@router.patch("/{key_id}/toggle")
async def toggle_key(key_id: int, session: AsyncSession = Depends(get_session)):
    """启用/禁用 API Key"""
    result = await session.execute(select(APIKey).where(APIKey.id == key_id))
    api_key = result.scalar_one_or_none()
    if not api_key:
        raise HTTPException(status_code=404, detail="Key 不存在")

    api_key.is_active = not api_key.is_active
    await session.commit()
    await key_rotator.reload_keys()

    return {"message": "已切换", "is_active": api_key.is_active}


@router.post("/{key_id}/check", response_model=KeyCheckResponse)
async def check_key(key_id: int, session: AsyncSession = Depends(get_session)):
    """验证 API Key 可用性"""
    result = await session.execute(select(APIKey).where(APIKey.id == key_id))
    api_key = result.scalar_one_or_none()
    if not api_key:
        raise HTTPException(status_code=404, detail="Key 不存在")

    decrypted = decrypt_key(api_key.key_value)
    is_valid, error = validate_key(
        provider=api_key.provider,
        api_key=decrypted,
        base_url_override=api_key.base_url_override,
        model_override=api_key.model_override,
    )

    api_key.is_validated = is_valid
    api_key.last_check_at = datetime.now()
    api_key.last_check_error = error
    await session.commit()

    logger.info(f"Key {key_id} 检查结果: valid={is_valid}" + (f" error={error}" if error else ""))
    return KeyCheckResponse(id=key_id, is_valid=is_valid, error=error)


@router.post("/check-all")
async def check_all_keys(session: AsyncSession = Depends(get_session)):
    """批量检查所有 Key 的可用性"""
    result = await session.execute(select(APIKey))
    keys = result.scalars().all()

    results = []
    for k in keys:
        decrypted = decrypt_key(k.key_value)
        is_valid, error = validate_key(
            provider=k.provider,
            api_key=decrypted,
            base_url_override=k.base_url_override,
            model_override=k.model_override,
        )
        k.is_validated = is_valid
        k.last_check_at = datetime.now()
        k.last_check_error = error
        results.append({"id": k.id, "is_valid": is_valid, "error": error})

    await session.commit()
    return {"results": results}
