"""API Key 可用性验证

针对不同提供商发送最小化认证测试请求，验证 Key 是否有效。
用 /models 端点检查，不消耗 token，只验证认证是否通过。
"""

import httpx
import logging

logger = logging.getLogger(__name__)

TIMEOUT = 15  # 检查超时（秒）


def check_openai_compatible(base_url: str, api_key: str) -> tuple[bool | None, str | None]:
    """检查 OpenAI-compatible Key — 用 /models 端点验证认证

    Returns:
        (True, None)       — Key 有效
        (False, error_msg)  — Key 无效（401/403）
        (None, error_msg)   — 无法判断（网络/服务异常）
    """
    try:
        resp = httpx.get(
            f"{base_url.rstrip('/')}/models",
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=TIMEOUT,
        )
        if resp.status_code == 200:
            return True, None
        if resp.status_code in (401, 403):
            return False, _extract_http_error(resp)
        # 429/500/etc — 服务端问题，无法判断
        logger.warning(f"/models 返回 {resp.status_code}: {resp.text[:200]}")
        return None, f"服务异常 HTTP {resp.status_code}，请稍后重试"
    except httpx.TimeoutException:
        return None, "网络超时，无法验证"
    except httpx.ConnectError as e:
        return None, f"无法连接: {str(e)[:80]}"
    except Exception as e:
        logger.warning(f"检查 Key 异常: {e}")
        return None, f"网络异常: {str(e)[:80]}"


def check_anthropic(api_key: str) -> tuple[bool | None, str | None]:
    """检查 Anthropic Key"""
    try:
        resp = httpx.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": "claude-3-5-sonnet-20241022",
                "max_tokens": 1,
                "messages": [{"role": "user", "content": "hi"}],
            },
            timeout=TIMEOUT,
        )
        if resp.status_code in (401, 403):
            return False, _extract_http_error(resp)
        if resp.status_code == 200:
            return True, None
        return None, f"服务异常 HTTP {resp.status_code}，请稍后重试"
    except httpx.TimeoutException:
        return None, "网络超时，无法验证"
    except Exception as e:
        return None, f"网络异常: {str(e)[:80]}"


def check_gemini(api_key: str) -> tuple[bool | None, str | None]:
    """检查 Gemini Key — 请求模型列表"""
    try:
        resp = httpx.get(
            f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}",
            timeout=TIMEOUT,
        )
        if resp.status_code in (400, 401, 403):
            return False, _extract_http_error(resp)
        if resp.status_code == 200:
            return True, None
        return None, f"服务异常 HTTP {resp.status_code}，请稍后重试"
    except httpx.TimeoutException:
        return None, "网络超时，无法验证"
    except Exception as e:
        return None, f"网络异常: {str(e)[:80]}"


def validate_key(provider: str, api_key: str, base_url_override: str | None = None,
                 model_override: str | None = None) -> tuple[bool, str | None]:
    """验证 API Key 可用性

    Args:
        provider: 提供商
        api_key: 已解密的 Key
        base_url_override: 自定义 Base URL
        model_override: 自定义模型

    Returns:
        (is_valid, message_or_None)
    """
    from .resume_processor import PROVIDER_CONFIGS

    config = PROVIDER_CONFIGS.get(provider)
    if not config:
        return False, f"不支持的提供商: {provider}"

    api_type = config["api_type"]
    base_url = base_url_override or config["base_url"]

    if not base_url:
        return False, "缺少 Base URL"

    logger.info(f"检查 Key 可用性: provider={provider}")

    if api_type == "openai":
        return check_openai_compatible(base_url, api_key)
    elif api_type == "anthropic":
        return check_anthropic(api_key)
    elif api_type == "gemini":
        return check_gemini(api_key)
    else:
        return False, f"未知 API 类型: {api_type}"


def _extract_http_error(resp) -> str:
    """从 HTTP 响应中提取错误信息"""
    try:
        data = resp.json()
        if isinstance(data, dict):
            err = data.get("error", {})
            if isinstance(err, dict):
                return str(err.get("message", resp.text[:200]))
            return str(err)
    except Exception:
        pass
    return resp.text[:200]
