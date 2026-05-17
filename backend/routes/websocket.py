"""WebSocket 路由 - 实时进度推送"""

import json
import logging
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from backend.services.job_manager import job_manager

logger = logging.getLogger(__name__)

router = APIRouter()


@router.websocket("/ws/progress/{job_id}")
async def progress_websocket(websocket: WebSocket, job_id: int):
    """WebSocket 端点：实时推送任务处理进度"""
    await websocket.accept()
    logger.info(f"WebSocket 已连接: job_id={job_id}")

    async def send_message(message: dict):
        try:
            await websocket.send_json(message)
        except Exception:
            pass

    # 注册回调并重放历史消息
    await job_manager.register_ws_callback(job_id, send_message)

    try:
        # 保持连接
        while True:
            data = await websocket.receive_text()
            # 客户端可以发送控制命令
            try:
                cmd = json.loads(data)
                if cmd.get("action") == "ping":
                    await websocket.send_json({"type": "pong"})
            except json.JSONDecodeError:
                pass
    except WebSocketDisconnect:
        logger.info(f"WebSocket 已断开: job_id={job_id}")
    finally:
        job_manager.unregister_ws_callback(job_id, send_message)
