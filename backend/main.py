"""FastAPI 应用入口

组装路由、中间件、静态文件、生命周期事件。
"""

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

from backend.config import settings as config_settings
from backend.models.database import init_db, async_session
from backend.services.key_rotator import key_rotator
from backend.services.job_manager import job_manager
from backend.routes import api_keys, resumes, jobs, websocket, settings as settings_router

# 日志配置
logging.basicConfig(
    level=logging.DEBUG if config_settings.DEBUG else logging.INFO,
    format="%(asctime)s | %(name)-20s | %(levelname)-8s | %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动时
    logger.info("正在初始化数据库...")
    await init_db()

    logger.info("正在加载 API Key...")
    key_rotator.set_session_factory(async_session)
    await key_rotator.load_keys()

    logger.info("正在初始化任务管理器...")
    job_manager.set_sessionmaker(async_session)

    logger.info(f"服务已启动: http://{config_settings.HOST}:{config_settings.PORT}")
    yield
    # 关闭时
    logger.info("服务已关闭")


app = FastAPI(
    title="简历信息提取系统",
    description="多模型AI视觉API的多账号轮询简历信息提取工具（Moonshot/OpenAI/DeepSeek/Claude/Gemini）",
    version="2.0.0",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/api/health")
async def health_check():
    """健康检查"""
    return {
        "status": "ok",
        "key_count": key_rotator.key_count,
    }


# 注册路由
app.include_router(api_keys.router)
app.include_router(resumes.router)
app.include_router(jobs.router)
app.include_router(websocket.router)
app.include_router(settings_router.router)

# 静态文件（前端）
frontend_dir = Path(__file__).resolve().parent.parent / "frontend"
if frontend_dir.exists():
    app.mount("/", StaticFiles(directory=str(frontend_dir), html=True), name="frontend")
    logger.info(f"前端静态文件已挂载: {frontend_dir}")
