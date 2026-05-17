"""简历信息提取核心逻辑 - 多模型支持

支持 6 种 AI 提供商：
  - OpenAI-compatible: Moonshot, OpenAI, DeepSeek, Custom
  - Anthropic native: Claude
  - Gemini native: Google Gemini
"""

import json
import asyncio
import logging
import httpx
from openai import OpenAI

from backend.config import settings

logger = logging.getLogger(__name__)

# ==================== 提供商配置 ====================
PROVIDER_CONFIGS = {
    "moonshot": {
        "api_type": "openai",
        "base_url": "https://api.moonshot.cn/v1",
        "model": "moonshot-v1-8k-vision-preview",
    },
    "openai": {
        "api_type": "openai",
        "base_url": "https://api.openai.com/v1",
        "model": "gpt-4o",
    },
    "deepseek": {
        "api_type": "openai",
        "base_url": "https://api.deepseek.com/v1",
        "model": "deepseek-chat",
    },
    "anthropic": {
        "api_type": "anthropic",
        "base_url": "https://api.anthropic.com/v1",
        "model": "claude-3-5-sonnet-20241022",
    },
    "gemini": {
        "api_type": "gemini",
        "base_url": "https://generativelanguage.googleapis.com/v1beta",
        "model": "gemini-2.0-flash",
    },
    "custom": {
        "api_type": "openai",
        "base_url": None,
        "model": None,
    },
}

# 默认 prompt（占位，实际运行时由 prompt_builder 动态生成）
SYSTEM_PROMPT = (
    "你是一个专业的简历信息提取系统。请严格按以下要求及格式从简历中提取信息并以JSON格式返回:\n"
    "1. 姓名\n2. 性别(男/女)\n3. 出生年月(YYYY-MM)\n4. 手机号码(11位)\n"
    "5. 最高学历(大专/本科/硕士/博士)\n6. 毕业学校\n7. 毕业年份(YYYY)\n8. 地区(省/市)\n9. 专业名称\n10. 应聘职位\n"
    "示例: {'姓名':'张三','性别':'男','出生年月':'1990-05','手机号码':'11111111111'...}\n"
    "只返回JSON数据，不要任何解释！"
)


def _parse_response(content: str) -> dict:
    """清理并解析 AI 返回的 JSON"""
    content = content.strip()
    if content.startswith("```"):
        parts = content.split("```")
        if len(parts) >= 2:
            content = parts[1]
            if content.startswith("json"):
                content = content[4:]
    content = content.strip()
    return json.loads(content)


def _get_system_prompt(session_factory) -> str:
    """获取 System Prompt（优先使用用户自定义字段）"""
    import asyncio
    from backend.services.prompt_builder import build_extraction_prompt

    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # 在异步上下文中，在线程中运行
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                return pool.submit(lambda: asyncio.run(build_extraction_prompt(session_factory))).result(timeout=5)
        else:
            return asyncio.run(build_extraction_prompt(session_factory))
    except Exception:
        return SYSTEM_PROMPT


# ==================== OpenAI-compatible 提供商 ====================
def _extract_openai_sync(base64_image: str, api_key: str, base_url: str, model: str,
                         session_factory=None) -> tuple[dict, int]:
    """OpenAI-compatible API 调用 (Moonshot, OpenAI, DeepSeek, Custom)"""
    client = OpenAI(api_key=api_key, base_url=base_url)
    prompt = _get_system_prompt(session_factory) if session_factory else SYSTEM_PROMPT

    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": prompt},
            {
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}},
                    {"type": "text", "text": "请从这份简历中提取上述要求的个人信息。"},
                ],
            },
        ],
        temperature=0.1,
    )

    content = response.choices[0].message.content
    tokens_used = response.usage.total_tokens if response.usage else 0
    return _parse_response(content), tokens_used


# ==================== Anthropic Claude ====================
def _extract_anthropic_sync(base64_image: str, api_key: str,
                            session_factory=None) -> tuple[dict, int]:
    """Anthropic Claude 原生 API 调用"""
    prompt = _get_system_prompt(session_factory) if session_factory else SYSTEM_PROMPT
    url = "https://api.anthropic.com/v1/messages"
    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }
    body = {
        "model": PROVIDER_CONFIGS["anthropic"]["model"],
        "max_tokens": 4096,
        "system": prompt,
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": "image/jpeg",
                            "data": base64_image,
                        },
                    },
                    {"type": "text", "text": "请从这份简历中提取上述要求的个人信息。"},
                ],
            }
        ],
    }

    response = httpx.post(url, headers=headers, json=body, timeout=120)
    response.raise_for_status()
    data = response.json()

    content = data["content"][0]["text"]
    tokens_used = data.get("usage", {}).get("input_tokens", 0) + data.get("usage", {}).get("output_tokens", 0)
    return _parse_response(content), tokens_used


# ==================== Google Gemini ====================
def _extract_gemini_sync(base64_image: str, api_key: str,
                         session_factory=None) -> tuple[dict, int]:
    """Google Gemini 原生 API 调用"""
    prompt = _get_system_prompt(session_factory) if session_factory else SYSTEM_PROMPT
    model = PROVIDER_CONFIGS["gemini"]["model"]
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"

    body = {
        "system_instruction": {"parts": [{"text": prompt}]},
        "contents": [
            {
                "parts": [
                    {
                        "inline_data": {
                            "mime_type": "image/jpeg",
                            "data": base64_image,
                        }
                    },
                    {"text": "请从这份简历中提取上述要求的个人信息。"},
                ]
            }
        ],
    }

    response = httpx.post(url, json=body, timeout=120)
    response.raise_for_status()
    data = response.json()

    content = data["candidates"][0]["content"]["parts"][0]["text"]
    tokens_used = (
        data.get("usageMetadata", {}).get("promptTokenCount", 0)
        + data.get("usageMetadata", {}).get("candidatesTokenCount", 0)
    )
    return _parse_response(content), tokens_used


# ==================== 调度入口 ====================
async def extract_resume_info(
    base64_image: str,
    api_key: str,
    provider: str = "moonshot",
    base_url_override: str | None = None,
    model_override: str | None = None,
    max_retries: int | None = None,
    session_factory=None,
) -> tuple[dict, int]:
    """异步提取简历信息（带重试，多模型分发）

    Args:
        base64_image: 图片的 base64 编码
        api_key: 已解密的 API Key
        provider: 提供商标识 (moonshot/openai/deepseek/anthropic/gemini/custom)
        base_url_override: 自定义 Base URL (仅 custom 提供商)
        model_override: 自定义模型 (仅 custom 提供商)
        max_retries: 最大重试次数
        session_factory: 数据库 session factory（用于获取自定义字段）

    Returns:
        (extracted_data_dict, tokens_used)
    """
    if max_retries is None:
        max_retries = settings.RETRY_MAX_ATTEMPTS

    config = PROVIDER_CONFIGS.get(provider)
    if not config:
        raise ValueError(f"不支持的提供商: {provider}")

    api_type = config["api_type"]
    base_url = base_url_override or config["base_url"]
    model = model_override or config["model"]

    if provider == "custom" and (not base_url or not model):
        raise ValueError("Custom 提供商必须提供 base_url 和 model")

    last_error = None
    for attempt in range(max_retries):
        try:
            if api_type == "openai":
                info, tokens = await asyncio.to_thread(
                    _extract_openai_sync, base64_image, api_key, base_url, model, session_factory
                )
            elif api_type == "anthropic":
                info, tokens = await asyncio.to_thread(
                    _extract_anthropic_sync, base64_image, api_key, session_factory
                )
            elif api_type == "gemini":
                info, tokens = await asyncio.to_thread(
                    _extract_gemini_sync, base64_image, api_key, session_factory
                )
            else:
                raise ValueError(f"未知 API 类型: {api_type}")

            return info, tokens
        except Exception as e:
            last_error = e
            logger.warning(f"提取失败 [{provider} 尝试 {attempt + 1}/{max_retries}]: {e}")
            if attempt < max_retries - 1:
                wait_time = min(5 * (attempt + 1), 30)
                await asyncio.sleep(wait_time)

    raise last_error if last_error else Exception("未知错误")
