<div align="center">

# ResumeAI 🧠📄

**简历信息批量提取系统** — 基于多模型 AI 视觉 API，一键批量提取简历字段，输出结构化 JSON / CSV

![Python](https://img.shields.io/badge/Python-3.10+-3776AB?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688?logo=fastapi&logoColor=white)
![SQLite](https://img.shields.io/badge/SQLite-003B57?logo=sqlite&logoColor=white)
[![License](https://img.shields.io/badge/License-MIT-yellow?logo=opensourceinitiative)](#)

</div>

---

## 📋 目录

- [概述](#概述)
- [功能特性](#功能特性)
- [快速开始](#快速开始)
- [使用指南](#使用指南)
- [项目结构](#项目结构)
- [环境变量](#环境变量)
- [AI 提供商](#ai-提供商)
- [Word 转图片说明](#word-转图片说明)
- [技术栈](#技术栈)

---

## 概述

ResumeAI 是一个面向 HR / 招聘团队的简历信息批量提取工具，支持 **6 大 AI 提供商**、**多 Key 轮询**、**PDF/Word 自动转图片**、**自定义提取字段**。上传文件夹即可全自动处理，结果实时可查，支持 CSV 导出。

---

## 功能特性

| 类别 | 功能 |
|------|------|
| 🤖 **AI 提供商** | Moonshot / OpenAI / DeepSeek / Anthropic Claude / Google Gemini / 自定义端点 |
| 🔄 **Key 轮询** | 添加多个 API Key，自动交替使用突破速率限制 |
| ✅ **Key 检测** | 添加 Key 自动验证 — 🟢 有效 / 🔴 无效 / ⚪ 无法验证 |
| 📂 **文件处理** | PDF/Word 自动转图片，跳过空白页，支持 JPG/PNG 直接识别 |
| 📁 **批量处理** | 输入文件夹路径一键扫描 → 转换 → 识别 → 结构化输出 |
| ✏️ **自定义字段** | 自由增删提取字段，AI 严格按字段列表输出 JSON |
| 📊 **实时进度** | WebSocket 推送日志流 + 进度条 + 统计卡片 |
| ⏸️ **暂停/恢复** | 处理中途可随时暂停，随时恢复 |
| 📤 **CSV 导出** | 动态字段表头，兼容 Excel 打开 |
| 💾 **数据持久化** | SQLite 存储所有历史记录，失败项支持重试 |

---

## 快速开始

### 安装

```bash
pip install -r requirements.txt
```

### 配置

复制 `.env.example` 为 `.env`，生成加密密钥后填入：

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

```env
# .env
MAX_CONCURRENT_PROCESSING=3
ENCRYPTION_KEY=上面命令输出的密钥
```

### 启动

```bash
# Windows
start.bat

# Linux / macOS
chmod +x start.sh && ./start.sh
```

打开 **http://localhost:8000**

---

## 使用指南

### 1️⃣ 添加 API Key

进入 **API Key 管理** → 选择提供商 → 填入 Key → 系统自动检测可用性（🟢 亮起即可用）。建议添加 **2 个以上 Key** 实现轮询加速。

### 2️⃣ 批量处理简历

**方式一：文件夹扫描（推荐）**
进入 **上传处理** → 输入简历文件夹路径（如 `D:/简历文件夹`）→ 点击扫描并处理。系统自动：扫描文件 → PDF/Word 转图片 → 去空白页 → 创建任务 → AI 识别。

**方式二：手动上传**
点击 **新建任务** → 拖拽文件（支持 JPG/PNG/PDF/DOCX）→ 开始处理。

### 3️⃣ 自定义提取字段（可选）

进入 **提取设置**，自由增删字段。修改后 AI 提取和 CSV 导出自动适配。

**默认字段：** 姓名、性别、出生年月、手机号码、最高学历、毕业学校、毕业年份、地区、专业名称、应聘职位

### 4️⃣ 查看与导出

进入 **结果查看** → 搜索 / 筛选 / 查看详情 / 重试失败项 / **导出 CSV**。

---

## 项目结构

```
Resume Information/
├── backend/
│   ├── main.py                   # FastAPI 入口
│   ├── config.py                 # 配置管理
│   ├── models/                   # SQLAlchemy ORM 模型
│   │   ├── database.py           # 引擎 + 迁移
│   │   ├── api_key.py            # API Key 模型
│   │   ├── resume.py             # 简历记录模型
│   │   ├── job.py                # 处理任务模型
│   │   └── extraction_field.py   # 自定义字段模型
│   ├── schemas/                  # Pydantic 校验
│   ├── services/                 # 核心业务逻辑
│   │   ├── key_rotator.py        # 多 Key 轮转
│   │   ├── resume_processor.py   # AI 提取（6 提供商）
│   │   ├── file_converter.py     # PDF/Word → 图片
│   │   ├── file_manager.py       # 文件上传管理
│   │   ├── job_manager.py        # 任务编排 + 并发
│   │   ├── key_validator.py      # Key 可用性检测
│   │   ├── prompt_builder.py     # 动态 Prompt
│   │   └── encryption.py         # Key 加密存储
│   └── routes/                   # API 路由
├── frontend/
│   ├── index.html                # SPA 入口
│   ├── css/styles.css            # 深蓝科技主题
│   └── js/                       # 前端模块
├── data/                         # 运行时数据（DB + 上传）
├── requirements.txt
├── .env
├── start.bat / start.sh
└── Resume Information.py         # 原始 CLI 脚本（参考）
```

---

## 环境变量

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `HOST` | 监听地址（`0.0.0.0` 允许局域网访问） | `0.0.0.0` |
| `PORT` | 服务端口 | `8000` |
| `DEBUG` | 调试模式，输出详细日志 | `true` |
| `DATABASE_URL` | SQLite 数据库路径 | `./data/resume_processor.db` |
| `UPLOAD_DIR` | 文件上传目录 | `./data/uploads` |
| `MAX_UPLOAD_SIZE_MB` | 单文件大小上限 | `10` |
| `RATE_LIMIT_TPM` | 每 Key 每分钟 Token 上限 | `32000` |
| `RATE_LIMIT_RPM` | 每 Key 每分钟请求上限 | `3` |
| `RATE_LIMIT_TPD` | 每 Key 每日 Token 上限 | `1500000` |
| `MAX_CONCURRENT_PROCESSING` | 并行处理数 | `3` |
| `RETRY_MAX_ATTEMPTS` | 失败重试次数 | `3` |
| `ENCRYPTION_KEY` | API Key 加密密钥 **（必填）** | — |
| `WEB_PASSWORD` | Web 访问密码（空=不启用） | — |

---

## AI 提供商

| 提供商 | 获取地址 | Key 格式 |
|--------|---------|---------|
| Moonshot | https://platform.moonshot.cn | `sk-...` |
| OpenAI | https://platform.openai.com/api-keys | `sk-...` |
| DeepSeek | https://platform.deepseek.com/api_keys | `sk-...` |
| Anthropic | https://console.anthropic.com | `sk-ant-...` |
| Google Gemini | https://aistudio.google.com/apikey | `AIza...` |

---

## Word 转图片说明

Word 文件需先转为 PDF 再转图片，系统按优先级自动尝试：

1. **docx2pdf** — 需 Microsoft Word + `pip install docx2pdf pywin32`
2. **win32com** — 需 Microsoft Word + `pip install pywin32`
3. **LibreOffice** — headless 模式（免费，推荐安装）

无以上工具时，可将 Word **另存为 PDF** 后上传。

---

## 技术栈

| 层 | 技术 |
|----|------|
| 🖥️ **后端** | Python FastAPI + SQLAlchemy + SQLite + WebSocket |
| 🌐 **前端** | 原生 HTML / CSS / JS（ES Modules），深蓝科技主题 |
| 🤖 **AI 集成** | OpenAI SDK + httpx（Anthropic / Gemini 原生 API） |
| 📄 **文件处理** | PyMuPDF（PDF→图片）、python-docx（Word 读取）、Pillow |
