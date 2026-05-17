"""DB 驱动的 API Key 轮转管理器（异步版本）

从原 CLI 脚本的 APIKeyRotator 迁移，改为从数据库加载 Key，
使用 asyncio.Lock 保证协程安全。支持多模型提供商。
"""

import asyncio
import time
import logging
from collections import deque
from typing import Callable

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import settings
from backend.models.api_key import APIKey
from backend.services.encryption import decrypt_key

logger = logging.getLogger(__name__)


class KeyRotator:
    """异步安全的多 API Key 轮转管理器"""

    def __init__(self):
        self._keys: list[dict] = []
        self._stats: dict[int, dict] = {}
        self._available: deque[int] = deque()
        self._lock = asyncio.Lock()
        self._session_factory: Callable | None = None

    def set_session_factory(self, factory: Callable):
        self._session_factory = factory

    async def load_keys(self):
        """从数据库加载所有活跃 Key"""
        if not self._session_factory:
            return

        async with self._session_factory() as session:
            result = await session.execute(
                select(APIKey).where(APIKey.is_active == True)
            )
            keys = result.scalars().all()

        self._keys = []
        self._stats = {}
        self._available.clear()
        now = time.time()

        for k in keys:
            key_safe = k.key_value[:6] + "..." + k.key_value[-4:] if len(k.key_value) > 10 else "***"
            self._keys.append({
                "id": k.id,
                "key_value": k.key_value,
                "label": k.label,
                "provider": k.provider,
                "base_url_override": k.base_url_override,
                "model_override": k.model_override,
                "key_safe": key_safe,
            })
            self._stats[k.id] = {
                "requests_today": k.requests_today,
                "tokens_today": k.tokens_today,
                "tpm_used": k.tpm_used,
                "tpm_reset_time": k.tpm_reset_time or now + 60,
                "daily_reset_time": k.daily_reset_time or now + 86400,
                "consecutive_errors": k.consecutive_errors,
                "next_available_time": k.next_available_time or 0,
                "last_used": k.last_used_at.timestamp() if k.last_used_at else 0,
            }
            self._available.append(k.id)

        logger.info(f"已从数据库加载 {len(self._keys)} 个 API Key")

    async def reload_keys(self):
        """重新加载所有 Key（增删后调用）"""
        await self.load_keys()

    @property
    def key_count(self) -> int:
        return len(self._keys)

    def _get_key_info(self, key_id: int) -> dict | None:
        for k in self._keys:
            if k["id"] == key_id:
                return k
        return None

    async def get_available_key(self) -> tuple[int, dict]:
        """获取当前可用的 API Key，返回 (key_id, key_info)

        key_info = {"key": decrypted_value, "provider": "...", "base_url_override": ..., "model_override": ...}
        """
        async with self._lock:
            if not self._keys:
                raise RuntimeError("没有可用的 API Key，请先添加 Key")

            now = time.time()
            best_key_id = None
            min_wait_time = float("inf")

            for key_id in list(self._available):
                stats = self._stats[key_id]

                if now > stats["daily_reset_time"]:
                    stats.update({
                        "requests_today": 0,
                        "tokens_today": 0,
                        "daily_reset_time": now + 86400,
                        "consecutive_errors": 0,
                    })

                if now > stats["tpm_reset_time"]:
                    stats["tpm_used"] = 0
                    stats["tpm_reset_time"] = now + 60

                if (stats["tokens_today"] >= settings.RATE_LIMIT_TPD or
                        stats["tpm_used"] >= settings.RATE_LIMIT_TPM or
                        stats["consecutive_errors"] >= 3):
                    continue

                wait_time = max(0, stats["next_available_time"] - now)
                if wait_time < min_wait_time:
                    min_wait_time = wait_time
                    best_key_id = key_id

            if best_key_id is None:
                raise RuntimeError("所有 API Key 都已达到速率限制，请稍后再试")

            request_interval = 60 / settings.RATE_LIMIT_RPM
            self._stats[best_key_id]["next_available_time"] = now + min_wait_time + request_interval

            if min_wait_time > 0:
                await asyncio.sleep(min_wait_time)

            key_data = self._get_key_info(best_key_id)
            key_info = {
                "key": decrypt_key(key_data["key_value"]),
                "provider": key_data.get("provider", "moonshot"),
                "base_url_override": key_data.get("base_url_override"),
                "model_override": key_data.get("model_override"),
            }
            return best_key_id, key_info

    async def update_key_stats(self, key_id: int, tokens_used: int = 0, error: bool = False):
        """更新 Key 使用统计"""
        async with self._lock:
            if key_id not in self._stats:
                return

            stats = self._stats[key_id]
            now = time.time()
            stats["last_used"] = now

            if error:
                stats["consecutive_errors"] += 1
            else:
                stats["consecutive_errors"] = 0
                stats["requests_today"] += 1
                stats["tokens_today"] += tokens_used
                stats["tpm_used"] += tokens_used

            if self._session_factory:
                try:
                    async with self._session_factory() as session:
                        await session.execute(
                            update(APIKey)
                            .where(APIKey.id == key_id)
                            .values(
                                requests_today=stats["requests_today"],
                                tokens_today=stats["tokens_today"],
                                tpm_used=stats["tpm_used"],
                                tpm_reset_time=stats["tpm_reset_time"],
                                daily_reset_time=stats["daily_reset_time"],
                                consecutive_errors=stats["consecutive_errors"],
                                next_available_time=stats["next_available_time"],
                                last_used_at=now,
                            )
                        )
                        await session.commit()
                except Exception as e:
                    logger.error(f"持久化 Key 统计失败: {e}")

    def get_key_stats(self, key_id: int) -> dict | None:
        return self._stats.get(key_id)

    def get_all_stats(self) -> list[dict]:
        """获取所有 Key 的统计信息"""
        result = []
        for k in self._keys:
            stats = self._stats.get(k["id"], {})
            masked = k["key_safe"]
            result.append({
                "id": k["id"],
                "label": k["label"],
                "key_masked": masked,
                "provider": k.get("provider", "moonshot"),
                "requests_today": stats.get("requests_today", 0),
                "tokens_today": stats.get("tokens_today", 0),
                "tpm_used": stats.get("tpm_used", 0),
                "consecutive_errors": stats.get("consecutive_errors", 0),
            })
        return result


# 全局单例
key_rotator = KeyRotator()
