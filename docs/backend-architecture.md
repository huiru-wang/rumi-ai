# RumiAI 后端架构设计文档

> 本文档面向 AI 及开发者，旨在帮助快速理解 RumiAI 后端的整体设计、模块职责与数据流转。

---

## 一、系统总览

RumiAI 后端由 **两个独立进程** 组成，共享同一份代码库：

| 进程 | 框架 | 端口 | 职责 |
|------|------|-----:|------|
| **FastAPI 服务** | FastAPI + Uvicorn | 8000 | REST API：工作区/文档/任务/消息/PPT风格 CRUD、文件上传与下载、风格提取 |
| **LangGraph 服务** | LangGraph Server | 2024 | Agent 运行时：流式对话、工具调用、中断恢复 |

两个进程共享底层存储（SQLite + ChromaDB HTTP Server + 文件系统），但各自独立初始化依赖实例。

```
┌─────────────────────────────────────────────────────────────────┐
│                        前端 (Next.js :3000)                      │
│                                                                 │
│   REST API 调用 ──────────┐     LangGraph Stream ──────────┐    │
└───────────────────────────┼─────────────────────────────────┼────┘
                            ▼                                 ▼
                 ┌─────────────────┐              ┌──────────────────┐
                 │  FastAPI (:8000) │              │ LangGraph (:2024)│
                 │                 │              │                  │
                 │  routes.py      │              │  graph.py        │
                 │  deps.py        │              │  state.py        │
                 │  managers/*     │              │  prompt_manager  │
                 └────────┬────────┘              │  skill_manager   │
                          │                       │  middlewares/*   │
                          │                       │  tools/*         │
                          │                       └────────┬─────────┘
                          │                                │
                          ▼                                ▼
                 ┌─────────────────────────────────────────────────┐
                 │              共享存储层                           │
                 │                                                 │
                 │  SQLite (database.py)   ← 元数据: workspace,    │
                 │                            document, task,      │
                 │                            message, ppt_style   │
                 │  ChromaDB HTTP Server      ← 向量索引           │
                 │  FileStore (file_store.py)  ← 原始文件 + 产出    │
                 │    └ providers.py          ← Local/OSS 抽象     │
                 └─────────────────────────────────────────────────┘
```

---

## 二、技术栈

| 类别 | 技术 | 版本要求 | 说明 |
|------|------|---------|------|
| **语言** | Python | ≥ 3.12 | 使用 `match` 等新语法特性 |
| **Web 框架** | FastAPI | ≥ 0.115 | 异步 REST API |
| **Agent 框架** | LangChain + LangGraph | LangChain ≥ 1.2, LangGraph ≥ 1.1 | Agent 编排、中间件、工具注册 |
| **LLM 接入** | langchain-openai + DeepSeek | — | 通过 OpenAI 兼容接口调用 DeepSeek (deepseek-v4-flash) |
| **TTS** | Dashscope qwen3-tts-flash | — | 口播稿音频合成，非流式调用 |
| **向量数据库** | ChromaDB HTTP Server | ≥ 1.0 | 独立 HTTP 服务，两进程共享，按 workspace 隔离 collection |
| **关系数据库** | SQLite (aiosqlite) | — | 轻量异步，存储 workspace/document/task/message/ppt_style 元数据 |
| **Embedding** | Dashscope text-embedding-v2 | — | 通过 Dashscope SDK 直接调用 |
| **文档解析** | PyMuPDF (PDF), python-docx (DOCX) | — | 结构化解析为章节 |
| **文档去重** | MD5 content_hash | — | 上传时基于文件名 + 内容哈希检测重复 |
| **PPTX 解析** | python-pptx + Pillow | — | 风格提取：解析幻灯片结构、主题色、字体等 |
| **文本分块** | langchain-text-splitters | — | RecursiveCharacterTextSplitter |
| **可观测性** | LangSmith | — | Agent 调用链追踪 |
| **包管理** | uv + hatchling | — | 现代 Python 包管理 |

---

## 三、目录结构

```
backend/
├── langgraph.json          # LangGraph Server 配置（入口、依赖、环境）
├── pyproject.toml           # Python 项目配置 + 依赖声明
├── .env                     # 环境变量（不提交）
├── data/                    # 运行时数据目录（不提交）
│   ├── rumi_ai.db       #   SQLite 数据库文件
│   ├── chroma/              #   ChromaDB 持久化目录
│   └── files/               #   用户上传文件 + Agent 产出文件
│       └── {workspace_id}/  #     按工作区隔离
│           ├── 原始文件.pdf
│           ├── 原始文件.md   #     解析后的 Markdown 导出
│           └── outputs/     #     Agent 产出物（PPT HTML、口播稿、音频、风格预览等）
│               └── {task_id}/  #    产出按任务 ID 隔离
├── skills/                  # Agent 技能目录
│   ├── ppt/                 #   PPT 生成技能
│   │   ├── SKILL.md         #     技能主提示（YAML frontmatter + Markdown）
│   │   ├── assets/          #     静态资源（viewport-base.css）
│   │   └── references/      #     参考文件（style-presets, html-template, animation-patterns）
│   └── narration/           #   口播稿生成技能
│       └── SKILL.md
├── static/                  # 静态资源
│   ├── ppt-styles/          #   系统预设 PPT 风格 HTML 文件（5 种）
│   ├── ppt-assets/          #   PPT 技能静态资产（挂载到 /ppt-assets）
│   └── ppt-templates/       #   PPT 模板文件（挂载到 /ppt-templates）
├── scripts/                 # 辅助脚本
│   └── parse_pptx.py        #     PPTX 结构化解析脚本
├── src/                     # 源代码根目录
│   ├── app_context.py       #   统一依赖注入数据类 (AppContext)
│   ├── api/                 #   REST API 层
│   │   ├── routes.py        #     FastAPI 路由定义
│   │   └── deps.py          #     依赖注入（单例初始化）
│   ├── agent/               #   Agent 层
│   │   ├── graph.py         #     LangGraph Agent 图构建
│   │   ├── state.py         #     Agent 状态定义
│   │   └── message_history.py #   消息历史持久化回调 + 中间件
│   ├── managers/            #   业务管理器层
│   │   ├── doc_manager.py   #     文档上传/解析/分块/摘要编排 (DocManager)
│   │   ├── tts_manager.py   #     TTS 音频生成 (TTSManager)
│   │   ├── prompt_manager.py #    系统提示词 + 风格提取提示词
│   │   ├── prompts/         #     Prompt 模板文件目录
│   │   │   ├── system_prompt.md           # Agent 系统提示词
│   │   │   ├── style_extract_prompt.md    # 风格描述生成提示词
│   │   │   └── generate_cover_html_prompt.md # 封面 HTML 生成提示词
│   │   ├── skill_manager.py #     技能扫描与加载
│   │   └── style_extract_manager.py # PPTX 风格提取工作流 (StyleExtractManager)
│   ├── middlewares/         #   Agent 中间件
│   │   ├── context_inject_middleware.py # 动态注入文档摘要 + PPT元信息 + 风格描述
│   │   ├── summarization.py #     长对话摘要压缩
│   │   ├── model_message_sanitizer.py # 模型请求清洗
│   │   └── logging_middlewares.py #    日志中间件
│   ├── storage/             #   存储层
│   │   ├── database.py      #     SQLite 封装（异步）
│   │   ├── vector_store.py  #     ChromaDB HTTP Client 封装
│   │   ├── file_store.py    #     文件系统封装（委托 Provider）
│   │   └── providers.py     #     存储提供者抽象（LocalProvider / OSSProvider）
│   ├── parsers/             #   文档解析器
│   │   ├── base.py          #     基础数据结构 + 分块逻辑
│   │   ├── pdf_parser.py    #     PDF 解析
│   │   ├── docx_parser.py   #     DOCX 解析
│   │   └── markdown_parser.py #   Markdown/纯文本解析
│   └── tools/               #   Agent 工具
│       ├── __init__.py      #     create_tools() 统一注册
│       ├── rag_search.py    #     知识库检索
│       ├── load_skill.py    #     技能加载
│       ├── save_ppt.py      #     PPT 产出物保存
│       ├── save_narration.py #    口播稿 + TTS 音频保存
│       ├── get_ppt_detail.py #    获取 PPT 任务详情
│       ├── get_style_template.py # 获取当前风格模板完整内容
│       ├── clarify_form.py  #     表单中断收集用户输入
│       ├── run_skill_script.py #  技能脚本执行
│       └── terminal_tool.py #     Shell 命令执行（备用）
└── tests/                   # 单元测试
```

---

## 四、分层架构详解

后端采用 **四层架构**，自上而下依次为：

```
┌──────────────────────────────────────────┐
│  API 层 (routes.py / LangGraph Server)   │  ← 接收外部请求
├──────────────────────────────────────────┤
│  Agent 层 (graph.py + middlewares + tools)│  ← AI 推理与工具调用
├──────────────────────────────────────────┤
│  Manager 层 (doc + tts + style_extract)  │  ← 业务编排
├──────────────────────────────────────────┤
│  Storage 层 (database / vector / file)   │  ← 数据持久化
└──────────────────────────────────────────┘
```

### 4.1 API 层

**文件**: `src/api/routes.py`, `src/api/deps.py`

#### 4.1.1 FastAPI 服务 (`routes.py`)

提供 RESTful API，所有路由前缀 `/api/`：

| 方法 | 路径 | 功能 | 关键行为 |
|------|------|------|---------|
| `POST` | `/api/workspaces` | 创建工作区 | 同名检测（409），初始化 ext_data |
| `GET` | `/api/workspaces` | 列出用户工作区 | 按 `user_id` 过滤 |
| `GET` | `/api/workspaces/{id}` | 获取工作区详情 | 含 ext_data 配置 |
| `PATCH` | `/api/workspaces/{id}/thread` | 绑定 LangGraph thread_id | 前端持久化会话 |
| `PATCH` | `/api/workspaces/{id}/config` | 更新工作区配置 | ppt_style / voice_id 等 |
| `DELETE` | `/api/workspaces/{id}` | 删除工作区 | 级联删除文档+向量+文件 |
| `GET` | `/api/threads/{thread_id}/messages` | 获取聊天消息历史 | turn-based 分页 |
| `GET` | `/api/threads/{thread_id}/messages/{id}` | 获取单条消息详情 | 用于消息恢复 |
| `POST` | `/api/workspaces/{id}/documents` | 上传文档 | **异步后台处理** |
| `GET` | `/api/workspaces/{id}/documents` | 列出文档 | 含状态轮询支持 |
| `DELETE` | `/api/workspaces/{id}/documents/{doc_id}` | 删除文档 | 清理文件+向量 |
| `GET` | `/api/workspaces/{id}/tasks` | 列出任务/产出 | 顶层任务+嵌套子任务 |
| `GET` | `/api/workspaces/{id}/tasks/{task_id}` | 获取单个任务详情 | 用于风格提取进度轮询 |
| `DELETE` | `/api/workspaces/{id}/tasks/{task_id}` | 删除任务 | 级联删除子任务+文件 |
| `PUT` | `/api/workspaces/{id}/tasks/{task_id}/file` | 保存任务文件内容 | PPT HTML 编辑回写 |
| `POST` | `/api/workspaces/{id}/style-extraction` | 上传 PPTX 启动风格提取 | **异步后台处理** |
| `DELETE` | `/api/workspaces/{id}/style-extraction/{task_id}` | 取消并删除风格提取 | 取消+文件清理 |
| `POST` | `/api/style-extraction/{task_id}/save` | 将提取结果保存为自定义风格 | 写入 ppt_style 表 |
| `GET` | `/api/ppt-styles` | 列出 PPT 风格 | 系统预设 + 用户自定义 |
| `GET` | `/api/voices` | 列出 TTS 音色 | 内置种子数据 |
| `DELETE` | `/api/ppt-styles/{style_id}` | 删除自定义风格 | 系统风格不可删 |
| `GET` | `/api/ppt-style-preview/{path}` | 风格预览 HTML | 系统/自定义统一端点，支持 `thumb=1` |
| `GET` | `/api/tasks/{task_id}/download` | 下载任务产出文件 | 后端从 task.result_data 解析路径 |
| `GET` | `/api/files/{path}` | 下载文件 | 通用文件服务，attachment 模式 |
| `GET` | `/api/file-view/{path}` | 内联预览文件 | inline 模式，支持 `thumb=1` 剥离外部字体 |

**关键设计决策**：
- **文档上传采用异步后台处理**：`upload_document` 接口立即返回 `uploaded` 状态，解析/分块/索引/摘要在 `BackgroundTasks` 中异步执行
- **风格提取采用异步后台处理**：上传 PPTX 后立即返回 task，前端轮询进度
- **父子任务层级**：`list_tasks` 仅返回顶层任务（PPT），子任务（口播稿、音频）通过 `children` 字段嵌套返回
- **PPT 风格数据库化**：系统预设风格在 DB 初始化时 seed（5 种，ID 前缀 `sys-`），自定义风格通过风格提取工作流生成
- **任务文件回写**：`save_task_file` 支持 PPT HTML 的在线编辑保存
- **CORS 全开放**：开发阶段 `allow_origins=["*"]`
- **静态资源挂载**：PPT 技能的资产和模板通过 `StaticFiles` 挂载到 `/ppt-assets` 和 `/ppt-templates`

#### 4.1.2 依赖注入 (`deps.py`)

通过 `AppContext.from_env()` 创建统一上下文，再暴露向后兼容的单例：

```python
app_ctx = AppContext.from_env()
db = app_ctx.db
vector_store = app_ctx.vector_store
file_store = app_ctx.file_store
skill_manager = app_ctx.skill_manager
doc_service = DocManager(db=db, vector_store=vector_store, file_store=file_store)
style_extract_manager = StyleExtractManager(db=db, file_store=file_store)
```

> 注意：`DocManager` 和 `StyleExtractManager` 内部各自创建独立的 LLM 实例（`SUMMARIZATION_MODEL`），不再从外部传入。

> 注意：FastAPI 进程使用 `deps.py` 的实例，LangGraph 进程在 `graph.py._make_default_graph()` 中独立创建自己的实例。

---

### 4.2 Agent 层

**文件**: `src/agent/graph.py`, `src/agent/state.py`, `src/agent/message_history.py`

这是 RumiAI 的核心智能层，基于 **LangChain Agent + LangGraph** 构建。

#### 4.2.1 Agent 图 (`graph.py`)

使用 `langchain.agents.create_agent()` 创建标准的 ReAct Agent：

```
用户消息 → [中间件链] → LLM 推理 → 工具调用 → LLM 继续推理 → 最终回复
                              ↑                ↓
                         middlewares/*    tools/*
```

**核心组件**：

- **Model**: `ChatOpenAI`，通过 OpenAI 兼容接口调用 DeepSeek（`MAIN_MODEL`），开启 `streaming` 和 `enable_thinking`
- **State**: `MainAgentState`，继承 `AgentState`，扩展 workspace/config 字段
- **Tools**: 8 个注册工具（见 4.3 节）
- **Middlewares**: 见 4.2.4 节

#### 4.2.2 Agent 状态 (`state.py`)

```python
class MainAgentState(AgentState):
    workspace_id: str           # 当前工作区 ID
    ppt_style: str              # PPT 风格（如 "swiss-modern"）
    voice_id: str               # TTS 音色 ID（如 "Cherry"）
    current_ppt_task_id: str    # 当前 PPT 任务 ID（口播稿生成时使用）
```

`workspace_id` 贯穿整个 Agent 调用链，工具通过 `runtime.state.get("workspace_id")` 获取。`ppt_style` 和 `voice_id` 由前端通过 workspace 配置传入，工具读取后用于产出定制化的 PPT 和音频。

#### 4.2.3 系统提示词 (`prompt_manager.py`)

`PromptManager` 类定义 Agent 的角色为 **文档驱动的 AI 工作台助手**，系统提示词从 `managers/prompts/system_prompt.md` 文件加载，核心约束包括：
- 结构化 Markdown 输出
- 基于文档事实，禁止捏造
- 引用规范（`{{ref:文档名|章节}}`）
- 技能使用（`/ppt`、`/narrate` 命令触发）
- 文档边界（回答基于工作区文档）
- 动态注入当前 PPT 产出元信息（含 topic/summary）

此外，`PromptManager` 还提供风格提取相关的提示词构建方法（模板文件位于 `managers/prompts/`）：
- `build_style_description_prompt()` — 基于 `style_extract_prompt.md` 构建风格描述生成提示词
- `build_preview_html_prompt()` — 基于 `generate_cover_html_prompt.md` 构建预览 HTML 生成提示词，支持资源清单注入

运行时通过 `ContextInjectMiddleware` 动态追加文档摘要、PPT 产出元信息和风格描述。

#### 4.2.4 中间件 (`middlewares/`)

中间件按执行顺序注册，覆盖 Agent 生命周期各阶段。所有中间件均采用 **类模式**（继承 `AgentMiddleware`）：

| 中间件 | 阶段 | 职责 |
|--------|------|------|
| `ContextInjectMiddleware` | before_model | 动态注入文档摘要 + PPT 产出元信息 + 用户风格偏好描述 |
| `MessageHistoryMiddleware` | before/after_agent | 持久化消息历史到 SQLite |
| `ModelMessageSanitizerMiddleware` | before_model | 清洗模型请求（移除无效字段） |
| `SummarizationMiddleware` | after_agent | 长对话摘要压缩（token 超 40000 时触发） |
| `LoggingMiddleware` | before/after_agent/model | 全生命周期日志 |

**ContextInjectMiddleware 注入内容**：
- 当前 workspace 的文档摘要列表
- 用户配置的 PPT 风格完整描述（从 `ppt_style` 表查询 `style_description`）
- 当前 workspace 已完成 PPT 任务的元信息表（含 topic、summary、子任务状态）

**消息历史持久化**：
- `MessageHistoryCallback` 将每条消息（human/ai/tool）写入 `message` 表
- 自动过滤摘要生成的中间消息（`lc_source=summarization`）
- 通过 `MessageHistoryMiddleware` 在 Agent 执行前后触发

**长对话摘要**：
- `SummarizationMiddleware` 监控消息 token 总量
- 超过阈值（40000 tokens）时，保留最近 8 条消息，将更早的消息压缩为摘要
- 使用独立的 LLM 实例生成摘要（`MAIN_MODEL`）

---

### 4.3 工具层 (Tools)

Agent 注册了 **8 个工具**，通过 `create_tools(ctx)` 统一注册：

#### 4.3.1 `rag_search` — 知识库检索

- **触发时机**：用户提出与文档内容相关的问题
- **实现**：调用 `VectorStore.search()`，在当前 workspace 的 ChromaDB collection 中做余弦相似度检索
- **输出格式**：带结构化位置信息的检索片段（文件名 | 章节 > 小节 | 页码）
- **workspace 隔离**：通过 `runtime.state["workspace_id"]` 自动定位 collection

#### 4.3.2 `load_skill` — 技能加载

- **触发时机**：用户使用 `/ppt`、`/narrate` 等命令，或 Agent 判断需要特定技能
- **两种调用模式**：
  - 不带 `file_paths`：返回技能主提示 + `linked_files` 列表
  - 带 `file_paths`：批量加载技能目录下的文件（最多 5 个）
- **动态 docstring**：工具描述中列出所有可用技能的名称和描述

#### 4.3.3 `save_ppt` — PPT 产出物保存

- **触发时机**：Agent 完成 PPT 生成后
- **流程**：创建 Task 记录（type=ppt）→ 保存 HTML 文件到 `ppt/{task_id}/` → 更新 Task 状态为 completed
- **前端联动**：保存后前端通过轮询 Task 列表自动展示新产出

#### 4.3.4 `save_narration` — 口播稿 + TTS 音频保存

- **触发时机**：Agent 完成口播稿生成后
- **流程**：创建 Task 记录（type=narration, parent_task_id=ppt_task_id）→ 保存口播稿文本 → 逐页生成 TTS 音频 → 更新 Task 状态
- **TTS 调用**：通过 `TTSManager` 调用 Dashscope qwen3-tts-flash
- **文件命名**：`{narration_task_id}_narration.md`（文本），`{narration_task_id}_{slide_number}.wav`（音频），存储在 `ppt/{ppt_task_id}/` 目录

#### 4.3.5 `get_ppt_detail` — 获取 PPT 任务详情

- **触发时机**：Agent 需要了解已有 PPT 的结构信息（如幻灯片数量、大纲等）
- **实现**：从 DB 读取 PPT 任务的 result_data

#### 4.3.6 `clarify_form` — 表单中断

- **触发时机**：Agent 需要用户澄清意图或提供参数
- **实现**：使用 LangGraph 的 `interrupt()` 机制暂停 Agent 执行，发送表单定义到前端
- **表单字段类型**：`text`、`select`、`multiselect`
- **恢复**：前端提交表单后通过 LangGraph `resume` API 恢复 Agent 执行

#### 4.3.7 `get_style_template` — 获取风格模板

- **触发时机**：生成 PPT 前必须调用，获取当前配置的完整风格规范
- **实现**：从 `ppt_style` 表查询当前 `ppt_style` ID 对应的风格记录，拼接风格描述 + 资源清单
- **输出**：包含颜色体系、字体规范、布局规则、背景图片使用方式等详细描述，以及可用的视觉资产资源清单（含 URL 和使用建议）
- **兼容处理**：支持 legacy `name_en` 值的回退查询

#### 4.3.8 `run_skill_script` — 技能脚本执行

- **触发时机**：技能中定义的辅助脚本需要执行
- **安全措施**：workdir 必须是绝对路径，校验 shell 元字符，支持超时和后台执行

---

### 4.4 Manager 层

#### 4.4.1 DocManager (`managers/doc_manager.py`)

`DocManager` 是文档处理的业务编排器，协调解析器、存储层和 LLM：

#### 文档处理流水线

```
上传文件 (bytes)
    │
    ▼
┌─ create_document_upload ─────────────────────────┐
│  1. 检测文件类型 (pdf/docx/markdown/text)         │
│  2. FileStore.save() → 保存原始文件                │
│  3. Database.create_document() → 创建元数据记录    │
│  4. 返回 status="uploaded"                        │
└──────────────────────────────────────────────────┘
    │ (BackgroundTasks 异步执行)
    ▼
┌─ process_document ───────────────────────────────┐
│  ① status="parsing"                              │
│     → 结构化解析为 DocumentSection 列表            │
│     → 导出 Markdown 文件                          │
│                                                  │
│  ② status="parsed" → "chunking"                  │
│     → split_sections_into_chunks()               │
│     → RecursiveCharacterTextSplitter             │
│     → 生成 ChunkWithMetadata 列表                 │
│                                                  │
│  ③ status="indexing"                             │
│     → VectorStore.add_structured_chunks()        │
│     → 写入 ChromaDB（按 workspace 隔离 collection）│
│                                                  │
│  ④ status="summarizing"                          │
│     → LLM 生成 200 字摘要（失败则截断 fallback）   │
│                                                  │
│  ⑤ status="ready"                                │
│     → 文档就绪，可供 RAG 检索                      │
└──────────────────────────────────────────────────┘
```

**状态机**：`uploaded → parsing → parsed → chunking → indexing → summarizing → ready`（任意阶段失败进入 `error`）

**删除操作**：
- `delete_document()`：删除文件 + 解析的 Markdown + 向量数据 + DB 记录
- `delete_workspace()`：遍历所有文档执行删除 + 删除 collection + 删除文件目录

#### 4.4.2 TTSManager (`managers/tts_manager.py`)

`TTSManager` 封装 Dashscope TTS 调用，用于口播稿音频生成：

- **模型**：qwen3-tts-flash
- **调用模式**：非流式，逐页合成
- **输入**：口播稿文本 + 音色 ID
- **输出**：WAV 音频文件保存到 `ppt/{ppt_task_id}/` 目录

#### 4.4.3 StyleExtractManager (`managers/style_extract_manager.py`)

`StyleExtractManager` 管理 PPTX 风格提取的完整异步工作流：

```
上传 PPTX 文件
    │
    ▼
┌─ run_extraction (异步) ────────────────────────────┐
│                                                     │
│  ① status="generating", step="parsing"             │
│     → parse_pptx() 解析 PPTX 结构                   │
│     → 提取主题色、字体、布局、形状等结构化数据        │
│                                                     │
│  ② step="analyzing_style"                          │
│     → LLM 生成风格描述 JSON                         │
│     → 解析为 {name, name_en, description,           │
│              style_description}                      │
│                                                     │
│  ③ step="generating_preview"                       │
│     → LLM 生成预览 HTML 文件                        │
│     → 清理 markdown code fence                      │
│                                                     │
│  ④ status="completed"                              │
│     → 保存预览 HTML 到 style/{task_id}/           │
│     → 更新 task result_data                         │
│                                                     │
└─────────────────────────────────────────────────────┘
    │
    ▼ (用户确认保存)
┌─ save_as_custom_style ─────────────────────────────┐
│  → 从 task.result_data 提取风格数据                 │
│  → 写入 ppt_style 表 (category="custom")            │
│  → 返回 PptStyleInfo                                │
└─────────────────────────────────────────────────────┘
```

**状态机**：`generating(parsing → analyzing_style → generating_preview) → completed | failed | cancelled`

**关键能力**：
- 支持中途取消（`cancel_extraction()`）
- 自动命名（中英文风格名，英文名为 kebab-case）
- 预览 HTML 的 markdown code fence 清理
- 将完成结果保存为自定义 PPT 风格

#### 4.4.4 SkillManager (`managers/skill_manager.py`)

实现 **LangChain Skills 模式（渐进式披露）**：

```
skills/
├── ppt/
│   ├── SKILL.md              ← YAML frontmatter (name + description)
│   ├── assets/               ← viewport-base.css
│   └── references/           ← style-presets, html-template, animation-patterns
└── narration/
    └── SKILL.md              ← 口播稿生成技能
```

- **启动时扫描** `skills/` 目录，解析所有 `SKILL.md` 的 YAML frontmatter，提取 `name` + `description`
- **Agent 仅看到名称和描述**（通过 `load_skill` 工具的 docstring 注入）
- **按需加载**：Agent 调用 `load_skill(skill_name)` 时才读取完整技能内容
- **文件加载**：支持 `load_skill(skill_name, file_paths=[...])` 批量加载技能目录下的关联文件
- **安全约束**：`load_file()` 通过路径校验防止目录逃逸

---

### 4.5 Storage 层

#### 4.5.1 Database (`database.py`)

- **引擎**：aiosqlite（异步 SQLite）
- **五张表**：
  - `workspace(id, user_id, name, thread_id, ext_data, created_at)` — 工作区，`ext_data` 存储 JSON 配置（`ppt_style` 为风格 ID 如 `sys-swiss-modern`，`voice_info` 为 `{id, name, trait, gender}`）
  - `document(id, workspace_id, filename, file_type, summary, storage_path, status, error_message, content_hash, created_at, updated_at)` — 文档，`content_hash` 用于去重
  - `task(id, workspace_id, type, title, status, result_data, parent_task_id, created_at, updated_at)` — 任务/产出，支持父子层级。类型：`ppt`、`narration`、`ppt_style_extraction`
  - `message(id, thread_id, workspace_id, message_id, role, type, content, tool_calls, tool_call_id, name, additional_kwargs, response_metadata, created_at, updated_at)` — 聊天消息历史
  - `ppt_style(id, user_id, category, name, name_en, description, style_description, resource_manifest, preview_path, created_at)` — PPT 风格预设与自定义，`resource_manifest` 存储视觉资产 JSON
- **外键**：document/task → workspace（ON DELETE CASCADE），task.parent_task_id → task（ON DELETE SET NULL）
- **ppt_style 初始化**：DB 初始化时自动 seed 5 种系统预设风格（`user_id="system"`，ID 前缀 `sys-`，`category` 为 `dark`/`light`）
- **自动迁移**：`_migrate_tables()` 处理新增列的兼容，包括 `content_hash`、`ext_data`、`resource_manifest`、`parent_task_id` 等，并执行 `voice_id` → `voice_info` 和 `ppt_style name_en` → style ID 的数据迁移

**消息历史查询**：
- `list_thread_messages()` 实现 turn-based 分页：以 human 消息为 turn 边界，`limit` 控制 turn 数量，`before` 支持游标翻页
- 返回 `{messages: [...], next_cursor: id | null}`

**任务层级查询**：
- `list_tasks()` 仅返回顶层任务（`parent_task_id IS NULL`），子任务通过 `children` 字段嵌套
- `delete_task()` 对 PPT 类型任务级联删除所有子任务

**PPT 风格查询**：
- `list_all_ppt_styles(user_ids)` — 查询系统 + 用户自定义风格
- `get_ppt_style_by_name_en(name_en, user_id)` — 按英文名查询（用于中间件注入完整风格描述）
- `create_ppt_style()` — 创建自定义风格（来自风格提取）
- `delete_ppt_style()` — 删除自定义风格（系统风格不可删）

#### 4.5.2 VectorStore (`vector_store.py`)

- **引擎**：ChromaDB **HTTP Server**（`chromadb.HttpClient`），两进程共享同一个 ChromaDB HTTP 服务
- **配置**：`CHROMA_HOST`（默认 `localhost`）、`CHROMA_PORT`（默认 `8001`）环境变量
- **Embedding**：`DashscopeEmbeddingFunction`，封装 Dashscope text-embedding-v2 SDK
- **Collection 策略**：每个 workspace 一个 collection，名称为 `ws_{workspace_id}`
- **元数据**：每个 chunk 携带 `doc_id, filename, chunk_index, section_title, chapter_title, page_start, page_end, section_level`
- **检索**：余弦相似度（`hnsw:space=cosine`），支持按 `doc_id` 过滤
- **批量写入**：默认 batch_size=20

#### 4.5.3 FileStore (`file_store.py`)

- **存储提供者**：委托 `StorageProvider` 实现，支持 `LocalProvider`（本地文件系统）和 `OSSProvider`（阿里云 OSS），通过 `OSS_ENABLE` 环境变量切换
- **新路径结构**：
  - `user/{user_id}/workspace/{workspace_id}/docs/{filename}` — 文档
  - `user/{user_id}/workspace/{workspace_id}/ppt/{task_id}/{...}` — PPT 及口播稿
  - `user/{user_id}/workspace/{workspace_id}/style/{task_id}/...` — 风格提取产出
  - `user/{user_id}/style/{style_id}/{filename}` — 自定义风格
- **智能路由**：接受绝对路径（legacy DB 记录）或相对 key，自动路由到对应 Provider
- **功能**：同步/异步写入、单文件删除、目录删除、工作区级清理、用户风格管理

#### 4.5.4 StorageProvider (`providers.py`)

- **`StorageProvider`** ABC：定义 `save`, `save_async`, `read`, `exists`, `delete`, `delete_prefix`, `get_url`, `get_public_url` 统一接口
- **`LocalProvider`**：本地文件系统实现，支持绝对/相对路径解析
- **`OSSProvider`**：阿里云 OSS 实现，所有阻塞调用通过 `asyncio.to_thread` 包装。`get_url()` 返回预签名 URL（1h 有效），`get_public_url()` 返回永久公开 URL

---

### 4.6 解析器层 (Parsers)

#### 基础数据结构 (`base.py`)

- **`DocumentSection`**：解析产出的结构化单元（title, level, content, page_start/end, parent_title）
- **`ChunkWithMetadata`**：向量存储的 chunk 单元，携带章节/页码元数据
- **`split_sections_into_chunks()`**：使用 `RecursiveCharacterTextSplitter`，chunk_size=2000，overlap=200

#### 解析器实现

| 解析器 | 文件类型 | 库 | 结构化能力 |
|--------|---------|-----|-----------|
| `PdfParser` | .pdf | PyMuPDF | 按页解析，识别标题层级 |
| `DocxParser` | .docx/.doc | python-docx | 按段落解析，利用 Word 标题样式 |
| `MarkdownParser` | .md/.txt | 内置 | 按标题层级拆分 |

#### PPTX 解析脚本 (`scripts/parse_pptx.py`)

- **用途**：为风格提取提供 PPTX 结构化数据
- **输出**：文件基本信息、主题色方案、字体方案、文字色/填充色频率、字号分布、形状类型、布局分布、背景图分析、每页摘要

---

## 五、核心数据流

### 5.1 文档上传与索引

```
前端 → POST /api/workspaces/{id}/documents (multipart file)
  → routes.py: 读取文件内容
  → doc_service.create_document_upload(): 保存文件 + 创建 DB 记录
  → BackgroundTasks: doc_service.process_document()
    → Parser: 结构化解析
    → Splitter: 分块
    → VectorStore: 写入向量
    → LLM: 生成摘要
    → Database: 更新状态为 ready
前端 ← 轮询 GET /api/workspaces/{id}/documents 追踪状态
```

### 5.2 智能问答

```
前端 → LangGraph Stream API (:2024) 发送消息 + workspace_id + ppt_style + voice_id
  → graph.py: 中间件链处理
    → ContextInjectMiddleware: 注入文档摘要 + PPT元信息 + 风格描述
    → MessageHistoryMiddleware: 持久化消息
    → ModelMessageSanitizerMiddleware: 清洗请求
  → LLM 推理 → 决定调用 rag_search
  → rag_search: ChromaDB 检索 → 返回带位置信息的片段
  → LLM 基于检索结果生成带引用标记的回答
  → SummarizationMiddleware: 检查是否需要摘要压缩
前端 ← 流式接收 AI 回复
```

### 5.3 PPT 生成

```
前端 → 用户发送 "/ppt 产品规划"
  → LLM 识别 /ppt 命令 → 调用 load_skill("html-ppt")
  → 获取 PPT 技能完整提示 + linked_files 列表
  → (可选) 调用 clarify_form → 前端展示表单 → 用户填写 → resume
  → (可选) 调用 rag_search 检索相关文档
  → (可选) 调用 load_skill("html-ppt", file_paths=[...]) 加载参考文件
  → LLM 生成完整 PPT HTML
  → 调用 save_ppt(type="ppt", title=..., content=HTML, ppt_style=...)
    → 创建 Task + 保存文件到 ppt/{task_id}/
前端 ← 产出面板展示新 PPT，可预览、编辑和下载
```

### 5.4 口播稿生成

```
前端 → 用户在 PPT 任务菜单中点击"生成口播稿"
  → workspace page 设置 current_ppt_task_id + 发送 /narrate 命令
  → LLM 识别 /narrate 命令 → 调用 load_skill("narration")
  → Agent 检查 current_ppt_task_id，获取 PPT 大纲
  → (可选) 调用 rag_search 检索文档增强内容
  → LLM 生成逐页口播稿文本
  → 调用 save_narration(ppt_task_id=..., content=..., voice_id=...)
    → 创建子 Task (parent_task_id=ppt_task_id)
    → 保存口播稿文本文件
    → 逐页调用 TTSManager 生成音频
    → 更新 Task 状态为 completed
前端 ← 产出面板在 PPT 下方展示口播稿子任务，可播放
```

### 5.5 PPT 风格提取

```
前端 → 用户点击"提取风格" → 上传 PPTX 文件
  → POST /api/workspaces/{id}/style-extraction
  → file_store 保存 PPTX → 创建 Task (type=ppt_style_extraction)
  → BackgroundTasks: style_extract_manager.run_extraction()
    → Step 1 (parsing): parse_pptx() 解析 PPTX 结构
    → Step 2 (analyzing_style): LLM 生成风格描述 JSON
    → Step 3 (generating_preview): LLM 生成预览 HTML
    → Step 4 (completed): 保存产出到 style/{task_id}/ → 更新 Task
前端 ← StyleExtractionDialog 轮询进度，展示步骤状态

用户确认 → POST /api/style-extraction/{task_id}/save
  → 写入 ppt_style 表 (category="custom")
  → 新风格出现在 StylePickerDialog 的"自定义主题"分类中
```

### 5.6 消息历史恢复

```
前端 → 打开工作区聊天面板
  → 检查 workspace.thread_id
  → 如有 thread_id → GET /api/threads/{thread_id}/messages
    → 返回按 turn 分组的消息列表 + next_cursor
  → 前端加载历史消息渲染到 Thread 组件
  → 用户滚动到顶部 → 使用 next_cursor 加载更多
  → useStream 接管后续实时通信
```

---

## 六、配置与环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `OPENAI_API_KEY` | 必填 | DeepSeek API 密钥 |
| `OPENAI_API_BASE` | `https://api.deepseek.com` | DeepSeek API 地址 |
| `MAIN_MODEL` | `deepseek-v4-flash` | Agent 图使用的 LLM 模型 |
| `SUMMARIZATION_API_KEY` | — | 摘要生成 API 密钥 |
| `SUMMARIZATION_API_BASE` | `https://api.deepseek.com` | 摘要生成 API 地址 |
| `SUMMARIZATION_MODEL` | `deepseek-v4-flash` | 摘要/文档处理/风格提取用 LLM |
| `EMBEDDING_API_KEY` | 必填 | Embedding API 密钥 |
| `EMBEDDING_API_BASE` | `https://dashscope.aliyuncs.com/compatible-mode/v1` | Embedding API 地址 |
| `EMBEDDING_MODEL` | `text-embedding-v2` | Embedding 模型名 |
| `TTS_API_KEY` | 必填 | TTS API 密钥 |
| `TTS_API_BASE` | Dashscope 多模态接口 | TTS API 地址 |
| `TTS_MODEL` | `qwen3-tts-flash` | TTS 模型名 |
| `DATA_DIR` | `./data` | 数据存储根目录 |
| `CHROMA_HOST` | `localhost` | ChromaDB HTTP Server 地址 |
| `CHROMA_PORT` | `8001` | ChromaDB HTTP Server 端口 |
| `OSS_ENABLE` | `false` | 是否启用 OSS 存储 |
| `OSS_ENDPOINT` | — | OSS 服务端点 |
| `OSS_BUCKET` | — | OSS Bucket 名称 |
| `OSS_ACCESS_KEY_ID` | — | OSS AccessKey ID |
| `OSS_ACCESS_KEY_SECRET` | — | OSS AccessKey Secret |
| `LANGSMITH_TRACING` | `true` | 是否启用 LangSmith 追踪 |
| `LANGSMITH_API_KEY` | — | LangSmith API 密钥 |

**LangGraph Server 配置** (`langgraph.json`)：
```json
{
  "python_version": "3.12",
  "dependencies": ["."],
  "graphs": {
    "main_agent": "src.agent.graph:graph"
  },
  "env": ".env"
}
```

---

## 七、关键设计决策

1. **双进程架构**：FastAPI 处理 CRUD、文件操作和风格提取，LangGraph 专注 Agent 流式推理，职责分离
2. **AppContext 统一入口**：所有存储实例通过 `AppContext` 数据类捆绑，两个进程各自创建独立实例
3. **Workspace 隔离**：所有数据（文件、向量、元数据）以 workspace_id 为维度隔离
4. **异步文档处理**：上传立即返回，后台异步完成解析→分块→索引→摘要的流水线
5. **渐进式技能披露**：Agent 启动时只看到技能名称和描述，按需加载完整技能内容，减少 token 消耗
6. **父子任务层级**：PPT 任务为顶层任务，口播稿/音频任务通过 `parent_task_id` 挂载，支持级联删除
7. **消息历史持久化**：所有对话消息独立存储在 SQLite 的 message 表中，支持 turn-based 分页和恢复
8. **长对话摘要压缩**：超过 token 阈值（40000）时自动压缩历史消息为摘要，保持 Agent 上下文窗口可控
9. **中断式交互**：`clarify_form` 利用 LangGraph interrupt 机制实现 Agent-用户的多轮表单交互
10. **动态提示注入**：`ContextInjectMiddleware` 在每次模型请求前注入文档摘要、PPT 产出元信息和用户风格偏好完整描述
11. **ExternalCommand 机制**：前端通过 slash command 胶囊 UI 触发复杂技能（如 /narrate），降低用户输入门槛
12. **PPT 风格数据库化**：系统预设风格（5 种）和用户自定义风格统一存储在 `ppt_style` 表，支持动态查询和中间件注入，风格 ID 前缀 `sys-`
13. **PPTX 风格提取工作流**：通过 LLM 分析 PPTX 结构化数据，自动生成风格描述和预览 HTML，保存为可复用的自定义风格
14. **中间件类化**：所有中间件采用类模式（继承 `AgentMiddleware`），统一生命周期管理
15. **存储提供者抽象**：`StorageProvider` 抽象层支持本地文件系统和阿里云 OSS 无缝切换，通过环境变量配置
16. **ChromaDB HTTP Server**：两进程共享同一个 ChromaDB HTTP 服务，消除 SQLite 文件锁和 Rust FFI 生命周期问题
17. **文档去重**：上传时基于文件名 + MD5 内容哈希检测重复文档
18. **TTS 音色种子数据**：音色列表从 `_BUILTIN_VOICES` 种子数据提供，通过 `GET /api/voices` 接口返回
19. **Prompt 模板文件化**：系统提示词和风格提取提示词从 `managers/prompts/` 目录的 Markdown 文件加载，便于独立维护
20. **文件路径结构升级**：从扁平 `{workspace_id}/` 迁移到 `user/{user_id}/workspace/{workspace_id}/` 结构化路径，支持 OSS 存储
