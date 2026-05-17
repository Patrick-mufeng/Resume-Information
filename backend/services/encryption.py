"""API Key 加密/解密工具

使用 Fernet 对称加密保护存储的 API Key。
"""

from cryptography.fernet import Fernet
from backend.config import settings


def _get_fernet() -> Fernet:
    """获取 Fernet 实例"""
    key = settings.ENCRYPTION_KEY
    if not key:
        # 开发环境生成临时 key（重启后失效）
        import warnings
        warnings.warn("ENCRYPTION_KEY 未设置，使用临时密钥（重启后 Key 将无法解密）")
        return Fernet(Fernet.generate_key())
    return Fernet(key.encode() if isinstance(key, str) else key)


def encrypt_key(raw_key: str) -> str:
    """加密 API Key"""
    f = _get_fernet()
    return f.encrypt(raw_key.encode()).decode()


def decrypt_key(encrypted_key: str) -> str:
    """解密 API Key"""
    f = _get_fernet()
    return f.decrypt(encrypted_key.encode()).decode()
