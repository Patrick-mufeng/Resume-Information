"""应用配置管理，从环境变量加载"""

import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


class Settings:
    # Server
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "8000"))
    DEBUG: bool = os.getenv("DEBUG", "false").lower() == "true"

    # Database
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        f"sqlite+aiosqlite:///{BASE_DIR / 'data' / 'resume_processor.db'}"
    )

    # File Storage
    UPLOAD_DIR: Path = Path(os.getenv("UPLOAD_DIR", str(BASE_DIR / "data" / "uploads")))
    MAX_UPLOAD_SIZE_MB: int = int(os.getenv("MAX_UPLOAD_SIZE_MB", "10"))

    # Rate Limits (per API key)
    RATE_LIMIT_TPM: int = int(os.getenv("RATE_LIMIT_TPM", "32000"))
    RATE_LIMIT_RPM: int = int(os.getenv("RATE_LIMIT_RPM", "3"))
    RATE_LIMIT_TPD: int = int(os.getenv("RATE_LIMIT_TPD", "1500000"))

    # Processing
    MAX_CONCURRENT_PROCESSING: int = int(os.getenv("MAX_CONCURRENT_PROCESSING", "3"))
    RETRY_MAX_ATTEMPTS: int = int(os.getenv("RETRY_MAX_ATTEMPTS", "3"))

    # Encryption (API key at rest)
    ENCRYPTION_KEY: str = os.getenv("ENCRYPTION_KEY", "")

    # Auth
    WEB_PASSWORD: str = os.getenv("WEB_PASSWORD", "")

    @property
    def max_upload_size_bytes(self) -> int:
        return self.MAX_UPLOAD_SIZE_MB * 1024 * 1024


settings = Settings()
