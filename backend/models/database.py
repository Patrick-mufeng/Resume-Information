"""SQLAlchemy 异步引擎和会话管理"""

import logging
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase
from backend.config import settings

logger = logging.getLogger(__name__)

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    connect_args={"check_same_thread": False},
)

async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def init_db():
    """创建所有表并按需迁移"""
    # 确保所有模型已导入
    import backend.models.api_key  # noqa
    import backend.models.resume  # noqa
    import backend.models.job  # noqa
    import backend.models.extraction_field  # noqa

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

        # 迁移：为已有数据库添加新列
        migrations = [
            "ALTER TABLE api_keys ADD COLUMN provider VARCHAR(50) NOT NULL DEFAULT 'moonshot'",
            "ALTER TABLE api_keys ADD COLUMN base_url_override VARCHAR(512)",
            "ALTER TABLE api_keys ADD COLUMN model_override VARCHAR(100)",
            "ALTER TABLE api_keys ADD COLUMN is_validated BOOLEAN",
            "ALTER TABLE api_keys ADD COLUMN last_check_at DATETIME",
            "ALTER TABLE api_keys ADD COLUMN last_check_error VARCHAR(500)",
            # 为常用查询添加索引
            "CREATE INDEX IF NOT EXISTS idx_resumes_job_id ON resumes(job_id)",
            "CREATE INDEX IF NOT EXISTS idx_resumes_status ON resumes(status)",
            "CREATE INDEX IF NOT EXISTS idx_resumes_original_filename ON resumes(original_filename)",
        ]
        from sqlalchemy import text as sa_text

        for sql in migrations:
            try:
                await conn.run_sync(lambda c, s=sql: c.execute(sa_text(s)))
            except Exception:
                pass  # 列/索引已存在，跳过


async def get_session() -> AsyncSession:
    """获取数据库会话（依赖注入用）"""
    async with async_session() as session:
        yield session
