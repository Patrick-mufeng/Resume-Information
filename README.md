<div align="center">

# ResumeAI 🧠📄

**简历信息批量提取系统** — 基于多模型 AI 视觉 API 的简历信息批量提取工具，支持 **6 大 AI 提供商** + **多 Key 轮询** + **PDF/Word 自动转图片** + **自定义提取字段**，一键批量提取简历字段，输出结构化 JSON / CSV。

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
  - [1. 安装依赖](#1-安装依赖)
  - [2. 配置](#2-配置)
  - [3. 启动](#3-启动)
- [使用指南](#使用指南)
  - [第一步：添加 API Key](#第一步添加-api-key)
  - [第二步：批量处理简历](#第二步批量处理简历)
  - [第三步：自定义提取字段（可选）](#第三步自定义提取字段可选)
  - [第四步：查看和导出结果](#第四步查看和导出结果)
- [项目结构](#项目结构)
- [环境变量说明](#环境变量说明)
- [各提供商 Key 获取地址](#各提供商-key-获取地址)
- [Word 转图片说明](#word-转图片说明)
- [技术栈](#技术栈)

---

## 概述

ResumeAI 是一个面向 HR / 招聘团队的简历信息批量提取工具。基于多模型 AI 视觉 API，无需繁琐的模板配置，上传简历文件夹即可全自动批量提取关键信息，结果结构化输出，支持实时查看和 CSV 导出。

---

## 功能特性

- **🤖 6 大 AI 提供商**：Moonshot / OpenAI / DeepSeek / Anthropic Claude / Google Gemini / 自定义端点
- **🔄 多 Key 轮询**：添加多个 API Key，自动交替使用突破速率限制，大幅提升处理吞吐量
- **✅ Key 可用性检测**：添加 Key 时自动验证——🟢 绿灯有效 / 🔴 红灯无效 / ⚪ 灰灯无法验证
- **📂 PDF/Word 自动转图片**：上传或扫描文件夹时自动转换为图片格式，智能跳过空白页
- **📁 文件夹批量处理**：输入文件夹路径一键扫描 → 转换 → 识别，全程自动化
- **✏️ 自定义提取字段**：自由增删提取字段，AI 严格按字段列表输出 JSON，灵活适配不同业务需求
- **📊 实时进度监控**：WebSocket 推送日志流 + 进度条 + 统计卡片，处理状态一目了然
- **⏸️ 暂停/恢复**：处理中途可随时暂停，需要时恢复继续，灵活控制处理节奏
- **📤 CSV 导出**：动态字段表头，兼容 Excel 直接打开查看
- **💾 数据持久化**：SQLite 存储所有历史记录，支持对失败项单独重试

---

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置

复制 `.env.example` 为 `.env`，按需修改配置：

```bash
# 首先生成加密密钥（用于 API Key 加密存储）
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

将输出的密钥填入 `.env`：

```env
# 并行处理数（建议不超过 Key 数量）
MAX_CONCURRENT_PROCESSING=3

# 加密密钥（必填，首次使用请运行上面的生成命令）
ENCRYPTION_KEY=上面命令输出的密钥
```

### 3. 启动

```bash
# Windows：双击 start.bat 或在命令行运行
start.bat

# Linux / macOS：
chmod +x start.sh && ./start.sh
```

启动后访问 **http://localhost:8000** 即可进入 Web 界面。

---

## 使用指南

### 第一步：添加 API Key

1. 进入 **API Key 管理** 页面
2. 选择 AI 提供商（Moonshot / OpenAI / DeepSeek / Claude / Gemini / Custom）
3. 填入 API Key，点击添加
4. 系统**自动检测 Key 可用性**，🟢 绿灯亮起即可使用
5. 建议添加 **2 个以上 Key** 以实现轮询加速，有效突破单 Key 速率限制

### 第二步：批量处理简历

**方式一：文件夹批量处理（推荐）**

1. 进入 **上传处理** 页面
2. 输入简历文件夹路径（如 `D:/简历文件夹`）
3. 点击 **扫描并处理**，系统自动完成以下流程：
   - 扫描文件夹内所有 PDF / Word / JPG / PNG 文件
   - 将 PDF 和 Word 文件转为图片格式（已有图片则跳过）
   - 智能识别并删除空白页
   - 创建处理任务 + 自动启动 AI 识别
   - 实时推送处理进度和日志

**方式二：手动上传**

1. 点击 **新建任务**
2. 拖拽文件到上传区（支持 JPG / PNG / PDF / DOCX 格式）
3. 点击 **开始处理**

### 第三步：自定义提取字段（可选）

进入 **提取设置** 页面，自由增删提取字段。修改后 AI 提取结果和 CSV 导出将自动适配更新，无需修改任何代码。

**默认字段：**

| 字段 | 说明 |
|------|------|
| 姓名 | 候选人姓名 |
| 性别 | 男 / 女 |
| 出生年月 | 出生日期 |
| 手机号码 | 联系电话 |
| 最高学历 | 最高教育程度 |
| 毕业学校 | 毕业院校名称 |
| 毕业年份 | 毕业年份 |
| 地区 | 所在城市 / 地区 |
| 专业名称 | 所学专业 |
| 应聘职位 | 目标岗位 |

### 第四步：查看和导出结果

进入 **结果查看** 页面：
- 🔍 搜索和筛选提取数据
- 📄 点击 **详情** 查看每条简历的完整提取结果
- 🔄 失败的记录可单独 **重试**
- 📥 点击 **导出 CSV** 下载结构化数据，兼容 Excel 打开

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
├── data/                         # 运行时数据（DB + 上传文件）
├── requirements.txt
├── .env                          # 环境配置
├── start.bat / start.sh          # 启动脚本
└── Resume Information.py         # 原始 CLI 脚本（参考）
```

---

## 环境变量说明

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `HOST` | 监听地址，`0.0.0.0` 允许局域网访问 | `0.0.0.0` |
| `PORT` | 服务端口 | `8000` |
| `DEBUG` | 调试模式，`true` 输出详细日志 | `true` |
| `DATABASE_URL` | SQLite 数据库路径 | `./data/resume_processor.db` |
| `UPLOAD_DIR` | 文件上传目录 | `./data/uploads` |
| `MAX_UPLOAD_SIZE_MB` | 单文件大小上限（MB） | `10` |
| `RATE_LIMIT_TPM` | 每 Key 每分钟 Token 上限 | `32000` |
| `RATE_LIMIT_RPM` | 每 Key 每分钟请求上限 | `3` |
| `RATE_LIMIT_TPD` | 每 Key 每日 Token 上限 | `1500000` |
| `MAX_CONCURRENT_PROCESSING` | 并行处理数 | `3` |
| `RETRY_MAX_ATTEMPTS` | 失败重试次数 | `3` |
| `ENCRYPTION_KEY` | API Key 加密密钥 **（必填）** | — |
| `WEB_PASSWORD` | Web 访问密码（留空=不启用） | — |

---

## 各提供商 Key 获取地址

| 提供商 | 注册地址 | Key 格式 |
|--------|---------|---------|
| Moonshot | https://platform.moonshot.cn | `sk-...` |
| OpenAI | https://platform.openai.com/api-keys | `sk-...` |
| DeepSeek | https://platform.deepseek.com/api_keys | `sk-...` |
| Anthropic | https://console.anthropic.com | `sk-ant-...` |
| Google Gemini | https://aistudio.google.com/apikey | `AIza...` |

---

## Word 转图片说明

Word 文件需要先转为 PDF 再转为图片，系统按优先级自动尝试以下方式：

1. **docx2pdf** — 需安装 Microsoft Word + `pip install docx2pdf pywin32`
2. **win32com** — 需安装 Microsoft Word + `pip install pywin32`
3. **LibreOffice** — headless 模式转换（免费开源，推荐安装）

> 💡 如果以上工具均无法使用，可以手动将 Word 文件**另存为 PDF** 后再上传。

---

## 技术栈

- **🖥️ 后端**：Python FastAPI + SQLAlchemy + SQLite + WebSocket
- **🌐 前端**：原生 HTML / CSS / JS（ES Modules），深蓝科技主题
- **🤖 AI 集成**：OpenAI SDK + httpx（Anthropic / Gemini 原生 API）
- **📄 文件处理**：PyMuPDF（PDF → 图片）、python-docx（Word 读取）、Pillow（图片处理）
