@echo off
chcp 65001 >nul
title ResumeAI - 简历信息提取系统

cd /d "%~dp0"

echo.
echo   ========================================
echo     ResumeAI  v2.0  简历信息提取系统
echo   ========================================
echo.

:: ── 检查 Python ──
python --version >nul 2>&1
if errorlevel 1 (
    echo   [错误] 未找到 Python，请先安装 Python 3.10+
    pause
    exit /b 1
)

:: ── 检查 .env ──
if not exist ".env" (
    echo   [!] .env 文件不存在，正在从 .env.example 创建...
    if exist ".env.example" (
        copy .env.example .env >nul
        echo   [提示] 请编辑 .env 文件，填入 API Key 等配置
    ) else (
        echo   [警告] .env.example 也不存在，请手动创建 .env 文件
    )
    echo.
)

:: ── 检查依赖 ──
python -c "import uvicorn" >nul 2>&1
if errorlevel 1 (
    echo   [!] 正在安装依赖...
    pip install -r requirements.txt -q
    if errorlevel 1 (
        echo   [错误] 依赖安装失败，请手动执行: pip install -r requirements.txt
        pause
        exit /b 1
    )
    echo   [OK] 依赖安装完成
    echo.
)

:: ── 创建必要目录 ──
if not exist "data\uploads" mkdir data\uploads

:: ── 启动 ──
echo   前端界面 : http://localhost:8000
echo   API 文档  : http://localhost:8000/docs
echo   按 Ctrl+C 停止服务
echo   ========================================
echo.

python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000

pause
