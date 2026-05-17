"""文件管理服务

处理简历图片的上传、存储、验证。
最终所有文件都转为图片后再进行 AI 识别。
"""

import os
import uuid
import base64
import logging
from pathlib import Path

from backend.config import settings

logger = logging.getLogger(__name__)

ALLOWED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".pdf", ".docx", ".doc"}


def ensure_upload_dir():
    """确保上传目录存在"""
    settings.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


def validate_file(filename: str, file_size: int) -> str | None:
    """验证文件是否合法"""
    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        return f"不支持的文件格式: {ext}，仅支持 {', '.join(sorted(ALLOWED_EXTENSIONS))}"
    if file_size > settings.max_upload_size_bytes:
        return f"文件过大: {file_size / 1024 / 1024:.1f}MB，最大 {settings.MAX_UPLOAD_SIZE_MB}MB"
    return None


def generate_stored_filename(original_filename: str) -> str:
    """生成唯一的存储文件名"""
    ext = Path(original_filename).suffix.lower()
    return f"{uuid.uuid4().hex}{ext}"


def get_upload_path(stored_filename: str) -> Path:
    """获取文件存储的完整路径"""
    return settings.UPLOAD_DIR / stored_filename


async def save_upload_file(file_content: bytes, stored_filename: str) -> Path:
    """保存上传文件到磁盘"""
    ensure_upload_dir()
    file_path = get_upload_path(stored_filename)
    file_path.write_bytes(file_content)
    logger.info(f"文件已保存: {file_path}")
    return file_path


def image_to_base64(file_path: Path) -> str:
    """将图片文件转换为 base64 编码"""
    with open(file_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def delete_uploaded_file(stored_filename: str) -> bool:
    """删除上传的文件"""
    file_path = get_upload_path(stored_filename)
    if file_path.exists():
        os.remove(file_path)
        return True
    return False
