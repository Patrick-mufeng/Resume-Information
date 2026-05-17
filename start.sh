#!/bin/bash

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

echo "============================================"
echo "  简历信息提取系统 ResumeAI v2.0"
echo "============================================"
echo ""

# 检查 .env 文件
if [ ! -f ".env" ]; then
    echo "[警告] .env 文件不存在，正在从 .env.example 创建..."
    cp .env.example .env
    echo "[提示] 请编辑 .env 文件，设置 ENCRYPTION_KEY 和其他配置"
    echo ""
fi

# 创建必要目录
mkdir -p data/uploads

# 启动服务
echo "正在启动服务..."
echo "前端界面: http://localhost:8000"
echo "API 文档: http://localhost:8000/docs"
echo "按 Ctrl+C 停止服务"
echo "============================================"

python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000
