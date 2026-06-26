# RumiAI

RumiAI 是一个文档驱动的 AI 工作台，帮助用户基于上传的文档进行知识问答、PPT 生成、口播稿生成、TTS 音频合成和 PPT 风格提取。

## 架构概览

本地开发栈由 4 个服务组成：

| 服务 | 端口 | 说明 |
|------|-----:|------|
| FastAPI Backend | 8000 | REST API，管理工作区/文档/任务/消息/PPT风格 |
| LangGraph Server | 2024 | Agent 流式运行时，对话+工具调用 |
| ChromaDB | 8001 | 向量数据库，文档 Embedding 存储与检索 |
| Next.js Frontend | 3000 | 工作台 UI（文档、聊天、任务、配置、播放面板） |

后端采用**双进程架构**：FastAPI 负责 CRUD，LangGraph 负责 Agent 推理，两者共享 SQLite + ChromaDB + 文件存储，但各自维护独立的依赖实例。

## 快速开始

### 前置条件

在开始之前，确保系统已安装：

| 工具 | 最低版本 | 说明 |
|------|---------|------|
| Python | >= 3.12 | 后端运行时 |
| Node.js | >= 22 | 前端运行时（pnpm 10+ 要求） |

> Python 和 Node.js 的安装由用户自行处理（推荐 pyenv / nvm）。

### 一键初始化

```bash
./scripts/init.sh
```

该脚本会自动完成以下操作：

1. 检查并安装系统工具：`uv`、`pnpm`（或 npm）、`perl`、`lsof`
2. 创建 `backend/.env`（从模板复制）
3. 创建数据目录 `backend/data/{chroma,files}`
4. 安装 Python 依赖（`uv sync`）
5. 安装前端依赖（`pnpm install`）

### 配置环境变量

编辑 `backend/.env`，填入必要的 API Key：

| 变量 | 用途 | 是否必须 |
|------|------|---------|
| `OPENAI_API_KEY` | Agent LLM 推理 + 文档摘要 | **必须** |
| `OPENAI_API_BASE` | DeepSeek API 地址 | 默认 `https://api.deepseek.com` |
| `MAIN_MODEL` | Agent 主模型 | 默认 `deepseek-v4-flash` |
| `EMBEDDING_API_KEY` | 向量 Embedding（Dashscope） | **必须** |
| `EMBEDDING_API_BASE` | Embedding API 地址 | 默认 Dashscope |
| `EMBEDDING_MODEL` | Embedding 模型 | 默认 `text-embedding-v2` |
| `TTS_API_KEY` | TTS 语音合成（Dashscope） | 可选 |
| `TTS_MODEL` | TTS 模型 | 默认 `qwen3-tts-flash` |
| `VISION_API_KEY` | 视觉模型（PPT 风格提取） | 可选 |
| `VISION_MODEL` | 视觉模型 | 默认 `qwen3.5-flash` |
| `LANGSMITH_API_KEY` | 链路追踪 | 可选 |
| `OSS_ACCESS_KEY_ID/SECRET` | 阿里云 OSS 存储 | 可选（默认本地存储） |

### 启动服务

```bash
./scripts/start.sh
```

启动后访问 **http://localhost:3000** 即可使用。

### 验证

```bash
./scripts/doctor.sh   # 健康检查，确认所有依赖和端口就绪
```

## 依赖清单

### 系统工具

| 工具 | 用途 | 安装方式 |
|------|------|---------|
| Python >= 3.12 | 后端运行时 | pyenv / brew / apt |
| Node.js >= 22 | 前端运行时 | nvm / brew |
| uv | Python 包管理器 | `curl -LsSf https://astral.sh/uv/install.sh \| sh` |
| pnpm（或 npm） | 前端包管理器 | `npm install -g pnpm` |
| perl | 日志时间戳转换 | macOS 自带 / `apt install perl` |
| lsof | 端口检测 | macOS 自带 / `apt install lsof` |

### Python 依赖（后端）

通过 `uv sync` 安装，定义在 `backend/pyproject.toml`：

**核心框架**
- `langchain >= 1.2.3` — Agent 框架
- `langgraph >= 1.1.9` — Agent 图运行时
- `langgraph-api >= 0.10.0` / `langgraph-cli >= 0.4.27` — LangGraph 开发服务器
- `langchain-openai >= 0.3` — OpenAI 兼容 LLM 集成
- `langchain-community >= 0.3` — 社区组件
- `langchain-text-splitters >= 0.3` — 文本分块
- `langchain-deepseek >= 1.1.0` — DeepSeek 模型适配

**Web 框架**
- `fastapi >= 0.115` / `uvicorn >= 0.34` — REST API 服务器

**存储**
- `chromadb >= 1.0` — 向量数据库
- `aiosqlite >= 0.21` — 异步 SQLite

**文档处理**
- `python-docx >= 1.1` — Word 文档解析
- `pymupdf >= 1.25` — PDF 解析
- `python-pptx >= 1.0` — PPTX 解析
- `Pillow >= 10.0` — 图片处理

**AI 服务**
- `dashscope >= 1.20` — 阿里云 Dashscope SDK（Embedding + TTS + Vision）

**工具库**
- `httpx >= 0.28` — HTTP 客户端
- `python-dotenv >= 1.1` — 环境变量加载
- `pyyaml >= 6.0` — YAML 解析
- `python-multipart >= 0.0.20` — 文件上传

**可选依赖**
- `oss2 >= 2.18` — 阿里云 OSS 存储（`uv sync --extra oss`）
- `pytest >= 8` / `pytest-asyncio >= 0.25` / `ruff >= 0.11` — 开发工具（`uv sync --extra dev`）

### Node 依赖（前端）

通过 `pnpm install` 安装，定义在 `frontend/package.json`：

**框架**
- `next 16` — React 全栈框架（App Router）
- `react 19` / `react-dom 19` — UI 库

**AI 通信**
- `@langchain/core ^1.1` — LangChain 核心类型
- `@langchain/langgraph-sdk ^1.9` — LangGraph 客户端 SDK
- `@langchain/react ^1.0` — React 流式 Hook

**UI 组件**
- `@assistant-ui/react ^0.14` / `@assistant-ui/react-langchain` / `@assistant-ui/react-markdown` — 聊天 UI
- `react-markdown ^10.1` / `remark-gfm ^4.0` — Markdown 渲染
- `react-syntax-highlighter ^16.1` — 代码高亮
- `lucide-react ^1.16` — 图标库
- `zustand ^5.0` — 轻量状态管理

**开发工具**
- `tailwindcss ^4` / `@tailwindcss/postcss` — CSS 框架
- `typescript ^5` — 类型系统
- `eslint ^9` / `eslint-config-next` — 代码检查

### 外部 API 服务

| 服务 | 用途 | 申请地址 |
|------|------|---------|
| DeepSeek API | Agent LLM + 文档摘要 | https://platform.deepseek.com |
| Dashscope | Embedding + TTS + Vision | https://dashscope.console.aliyun.com |
| LangSmith（可选） | 链路追踪 | https://smith.langchain.com |

## 日常开发命令

```bash
# 启动所有服务
./scripts/start.sh

# 停止所有服务
./scripts/stop.sh

# 重启所有服务
./scripts/restart.sh

# 健康检查
./scripts/doctor.sh

# 后端测试
cd backend && uv run pytest tests/

# 前端 lint + build
cd frontend && pnpm lint && pnpm build
```

## 项目结构

```
rumi-ai/
├── backend/
│   ├── skills/             # Agent 技能（ppt、narration）
│   ├── src/
│   │   ├── api/            # FastAPI 路由 + 依赖注入
│   │   ├── agent/          # LangGraph Agent 入口 + 状态管理
│   │   ├── managers/       # 业务管理器（文档、TTS、提示词、技能、风格提取）
│   │   ├── middlewares/    # Agent 中间件（上下文注入、上下文摘要、日志等）
│   │   ├── tools/          # Agent 工具（rag_search、save_ppt 等）
│   │   ├── parsers/        # 文档解析器（PDF、DOCX、Markdown）
│   │   ├── storage/        # 存储抽象层（SQLite、ChromaDB、FileStore）
│   │   └── app_context.py  # 统一依赖入口
│   ├── data/               # 运行时数据（SQLite、ChromaDB、文件）
│   ├── tests/              # 后端测试
│   ├── pyproject.toml      # Python 依赖定义
│   ├── langgraph.json      # LangGraph 配置
│   └── .env                # 环境变量（不提交）
├── frontend/
│   ├── src/
│   │   ├── app/            # Next.js 路由（首页、工作区页）
│   │   ├── components/     # UI 组件（chat、config、player、document、task）
│   │   └── lib/            # API 客户端
│   ├── package.json        # Node 依赖定义
│   └── .next/              # 构建产物
├── scripts/                # 开发运维脚本
│   ├── init.sh             # 从零初始化
│   ├── start.sh            # 启动所有服务
│   ├── stop.sh             # 停止所有服务
│   ├── restart.sh          # 重启所有服务
│   └── doctor.sh           # 健康检查
├── docs/                   # 架构文档
├── AGENTS.md               # AI 协作规范
└── README.md               # 本文档
```

## 开发规范

- 详细开发规范、模块职责和代码约定见 `AGENTS.md`
- 架构设计文档见 `docs/backend-architecture.md` 和 `docs/frontend-architecture.md`
