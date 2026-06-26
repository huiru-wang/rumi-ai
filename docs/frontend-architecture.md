# RumiAI 前端架构设计文档

> 本文档面向 AI 及开发者，旨在帮助快速理解 RumiAI 前端的整体设计、模块职责与交互流程。

---

## 一、系统总览

RumiAI 前端是一个基于 **Next.js (App Router)** 的单页应用，提供文档知识管理和 AI 对话交互界面。

### 核心交互模型

```
┌─────────────────────────────────────────────────────────────────────┐
│                        浏览器 (localhost:3000)                       │
│                                                                     │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │                    工作区页面（三栏布局）                       │   │
│  │                                                              │   │
│  │  ┌──────────┐  ┌────────────────────┐  ┌──────────────────┐ │   │
│  │  │ 文档面板  │  │     聊天面板        │  │  配置 + 产出面板 │ │   │
│  │  │          │  │                    │  │                  │ │   │
│  │  │ 上传文档  │  │  流式对话          │  │  PPT 风格选择    │ │   │
│  │  │ 文档列表  │  │  工具调用展示      │  │  风格提取        │ │   │
│  │  │ 状态追踪  │  │  表单中断交互      │  │  音色选择        │ │   │
│  │  │          │  │  Markdown 渲染     │  │  PPT / 口播稿    │ │   │
│  │  │          │  │  消息历史分页       │  │  预览 / 播放     │ │   │
│  │  │          │  │                    │  │  父子层级展示    │ │   │
│  │  └──────────┘  └────────────────────┘  └──────────────────┘ │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                                                                     │
│  弹窗层: PPTPreviewDialog | PPTPlayerDialog | StyleExtractionDialog │
│                                                                     │
│        REST API (:8000)                LangGraph Stream (:2024)      │
│        ↕ 工作区/文档/任务/消息/风格    ↕ Agent 流式对话              │
└─────────────────────────────────────────────────────────────────────┘
```

**前端同时与两个后端服务通信**：
- **FastAPI (:8000)**：通过 REST API 管理工作区、文档上传/删除、任务查询、消息历史、配置更新、PPT 风格管理、风格提取、TTS 音色列表、文件下载/预览
- **LangGraph (:2024)**：通过 `@langchain/react` 的 `useStream` hook 进行流式 Agent 对话

---

## 二、技术栈

| 类别 | 技术 | 说明 |
|------|------|------|
| **框架** | Next.js 16 (App Router) | React Server Components + Client Components |
| **UI 库** | React 19 | 最新版 React |
| **样式** | Tailwind CSS 4 | 原子化 CSS，暗色主题 |
| **Agent 通信** | @langchain/langgraph-sdk/react (`useStream`) | LangGraph 流式对话 hook |
| **文件下载** | fetch + Blob URL | 跨域文件下载 |
| **图标** | lucide-react | 一致的图标风格 |
| **Markdown** | react-markdown + remark-gfm | GFM 扩展 Markdown 渲染 |
| **代码高亮** | react-syntax-highlighter (Prism) | oneDark 主题 |
| **字体** | Geist + Geist Mono | 现代等宽/无衬线字体 |
| **包管理** | pnpm | 高效依赖管理 |
| **语言** | TypeScript | 严格类型检查 |

---

## 三、目录结构

```
frontend/
├── package.json                 # 项目配置与依赖
├── next.config.ts               # Next.js 配置
├── tsconfig.json                # TypeScript 配置
├── postcss.config.mjs           # PostCSS 配置
├── public/                      # 静态资源
│   └── ppt-styles/              #   PPT 风格预设 HTML 文件
└── src/
    ├── app/                     # Next.js App Router 路由
    │   ├── layout.tsx           #   根布局（字体、全局样式）
    │   ├── globals.css          #   全局 CSS + Tailwind 导入
    │   ├── page.tsx             #   首页（工作区列表）
    │   └── workspace/
    │       └── [id]/
    │           └── page.tsx     #   工作区详情页（三栏布局 + 弹窗）
    ├── components/              # UI 组件
    │   ├── chat/                #   聊天相关组件
    │   │   ├── assistant.tsx    #     Agent 连接 & 流上下文 Provider
    │   │   ├── chat-panel.tsx   #     聊天面板容器
    │   │   ├── thread.tsx       #     对话线程（消息渲染 + 输入框）
    │   │   └── clarify-form.tsx #     Agent 表单中断 UI
    │   ├── config/              #   配置组件
    │   │   ├── config-panel.tsx #     配置面板（风格 + 音色 + 风格提取入口）
    │   │   ├── style-picker-dialog.tsx       # PPT 风格选择弹窗（API 加载，分类展示）
    │   │   ├── style-extraction-dialog.tsx   # 风格提取进度弹窗（步骤可视化）
    │   │   ├── style-extraction-upload-dialog.tsx # PPTX 上传入口弹窗
    │   │   └── voice-picker-dialog.tsx       # TTS 音色选择弹窗（含试听）
    │   ├── document/            #   文档管理组件
    │   │   └── document-panel.tsx #   文档面板（上传 + 列表 + 状态）
    │   ├── layout/              #   布局组件
    │   │   └── three-panel.tsx  #     三栏可拖拽布局
    │   ├── player/              #   PPT 播放/预览组件
    │   │   ├── ppt-preview-dialog.tsx # PPT 预览 + 编辑（iframe srcDoc）
    │   │   └── ppt-player-dialog.tsx  # PPT 播放（幻灯片 + 音频同步）
    │   ├── task/                #   任务/产出组件
    │   │   └── task-panel.tsx   #     产出面板（父子层级 + 口播稿 + 播放）
    │   └── workspace/           #   工作区组件
    │       ├── workspace-card.tsx #   工作区卡片
    │       └── create-dialog.tsx  #   创建工作区弹窗
    └── lib/                     # 工具库
        ├── api.ts               #   REST API 封装（类型定义 + 请求方法）
        └── user.ts              #   用户 ID 管理（localStorage）
```

---

## 四、页面与路由

前端只有 **2 个页面**，采用 Next.js App Router：

| 路由 | 文件 | 功能 |
|------|------|------|
| `/` | `app/page.tsx` | **首页** — 工作区列表、新建、删除 |
| `/workspace/[id]` | `app/workspace/[id]/page.tsx` | **工作区详情** — 三栏布局 + 弹窗层 |

### 4.1 首页 (`app/page.tsx`)

**职责**：展示当前用户的所有工作区，支持新建和删除。

**数据流**：
```
页面加载 → getUserId() 获取/生成用户 ID
         → listWorkspaces(userId) 获取列表
         → 渲染 WorkspaceCard 网格

用户操作：
  点击"新建"  → 打开 CreateDialog → createWorkspace() → 刷新列表
  点击卡片    → router.push(`/workspace/${id}`)
  点击删除    → deleteWorkspace(id) → 刷新列表
```

**用户 ID 策略**（`lib/user.ts`）：
- 首次访问时生成 `crypto.randomUUID()` 并存入 `localStorage`
- 后续访问复用，Key 为 `rumi-ai-user-id`
- SSR 场景返回 `"anonymous"` 兜底

### 4.2 工作区详情页 (`app/workspace/[id]/page.tsx`)

**职责**：三栏布局的主工作页面，组合文档管理、AI 对话、配置、产出管理，并管理弹窗层。

**组件组合**：
```tsx
<header>...</header>
<ThreePanel
  left={<DocumentPanel workspaceId={id} />}
  center={<ChatPanel workspaceId={id} pptStyle voiceId currentPptTaskId externalCommand ... />}
  right={
    <div>
      <ConfigPanel workspaceId pptStyle voiceId onConfigChange />
      <TaskPanel workspaceId onNarrate onPlayNarration onPreview />
    </div>
  }
/>
{playerData && <PPTPlayerDialog ... />}
{previewTask && <PPTPreviewDialog ... />}
{extractionTaskId && <StyleExtractionDialog ... />}
```

**关键状态**：
- `pptStyle` / `voiceId`：从 workspace.ext_data 读取，传递给 ChatPanel 和 ConfigPanel
- `currentPptTaskId`：触发口播稿生成时设置，ChatPanel 将其注入 Agent state
- `externalCommand`：通过 ExternalCommand 机制向聊天面板注入 slash command（如 `/narrate`）
- `playerData`：打开 PPT 播放器弹窗
- `previewTask`：打开 PPT 预览/编辑弹窗
- `extractionTaskId`：打开风格提取进度弹窗

---

## 五、组件架构详解

### 5.1 布局组件

#### `ThreePanel` (`components/layout/three-panel.tsx`)

三栏可拖拽布局组件，是工作区页面的骨架：

```
┌──────────────┬──┬────────────────────┬──┬────────────────┐
│   Left       │░░│     Center         │░░│    Right       │
│   (文档)     │░░│     (聊天)          │░░│  (配置+产出)   │
│              │░░│                    │░░│                │
│  width:      │  │   flex: 1          │  │  width:        │
│  280px       │  │                    │  │  300px         │
│  (可拖拽)    │  │                    │  │  (可拖拽)       │
└──────────────┴──┴────────────────────┴──┴────────────────┘
                ↑                        ↑
           左侧拖拽手柄              右侧拖拽手柄
```

**核心参数**：
- `MIN_SIDE_WIDTH = 240px`，`MAX_SIDE_WIDTH = 400px`
- 默认左侧 280px，右侧 300px
- 中间区域弹性伸缩 (`flex: 1`)
- 右侧支持折叠（`rightCollapsed`），折叠后显示为 8px 宽的展开按钮

---

### 5.2 聊天组件

聊天系统是前端最复杂的模块，由三个组件分层协作：

```
┌─ Assistant (Provider) ──────────────────────────────┐
│                                                     │
│  useStream() → 管理 LangGraph 流式连接               │
│  listThreadMessages() → 加载历史消息                  │
│  StreamContext → 向下传递 messages/submit/stop        │
│  ResumeContext → 向下传递 interrupt resume 回调       │
│                                                     │
│  ┌─ ChatPanel (容器) ─────────────────────────────┐ │
│  │                                                │ │
│  │  ┌─ Thread (渲染) ─────────────────────────┐  │ │
│  │  │                                          │  │ │
│  │  │  "加载更早消息" 按钮                       │  │ │
│  │  │  消息列表渲染                             │  │ │
│  │  │  - AI 消息: Markdown + 工具调用折叠       │  │ │
│  │  │  - 用户消息: 纯文本 / 胶囊命令            │  │ │
│  │  │  - 中断表单: ClarifyForm                 │  │ │
│  │  │  输入框 + 发送/停止按钮                   │  │ │
│  │  │                                          │  │ │
│  │  └──────────────────────────────────────────┘  │ │
│  └────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────┘
```

#### 5.2.1 `Assistant` (`components/chat/assistant.tsx`)

**角色**：Agent 连接管理器 + Context Provider + 消息历史管理

**核心机制**：

1. **Thread ID 管理**：
   - 页面加载时从后端获取已保存的 `thread_id`
   - 新 `thread_id` 自动通过 `updateWorkspaceThreadId()` 持久化到后端
   - Stream 报 404 时自动清空 `thread_id` 触发新会话

2. **消息历史加载**：
   - 初始化时通过 `listThreadMessages()` 加载最近 3 个 turn 的历史消息
   - 支持 `loadOlderMessages()` 使用 `next_cursor` 翻页加载更多
   - 历史消息与实时流消息合并渲染

3. **`useStream` Hook**：
   ```typescript
   useStream({
     apiUrl: "http://localhost:2024",
     assistantId: "main_agent",
     threadId,
   })
   ```
   管理与 LangGraph Server 的流式通信。

4. **ExternalCommand 机制**：
   - 父组件（workspace page）可通过 `externalCommand` prop 注入 slash command
   - 命令以胶囊 UI 形式显示在输入框上方，用户点击即发送
   - 支持 `metadata` 传递额外信息（如 `pptTaskId`）

5. **Context 传递**：
   - `StreamContext`：`messages`, `isLoading`, `interrupt`, `submit`, `stop`, `error`, `loadOlderMessages`, `hasOlderMessages`, `externalCommand`
   - `ResumeContext`：`resume` 回调，供 `ClarifyForm` 提交表单结果

6. **消息发送**：
   ```
   submit() → stream.submit({
     messages: [{ role: "human", content }],
     workspace_id, ppt_style, voice_id, current_ppt_task_id
   })
   ```

#### 5.2.2 `ChatPanel` (`components/chat/chat-panel.tsx`)

容器组件，组合 `Assistant` Provider 和 `Thread` 渲染，传递配置参数（pptStyle, voiceId, currentPptTaskId, externalCommand）。

#### 5.2.3 `Thread` (`components/chat/thread.tsx`)

**角色**：消息渲染引擎 + 输入界面

**消息渲染规则**：

| 消息类型 | 渲染方式 |
|---------|---------|
| `human` 消息 | 右对齐气泡，纯文本 |
| `ai` 消息（文本） | 左对齐，ReactMarkdown 渲染（GFM + 代码高亮） |
| `ai` 消息（工具调用） | 可折叠的工具调用卡片（显示工具名 + 参数摘要） |
| `tool` 消息 | 隐藏不显示（工具结果已被 AI 消化） |
| `interrupt` 状态 | 渲染 `ClarifyForm` 交互表单 |

**关键功能**：
- **消息历史分页**：顶部"加载更早消息"按钮，点击触发 `loadOlderMessages()`
- **自动滚动**：新消息到达时自动滚动到底部
- **代码块**：语法高亮 + 复制按钮
- **引用标记**：解析 `{{ref:文档名|章节}}` 格式并渲染为引用标签
- **思考过程**：`<think>` 标签内容渲染为可折叠的 "思考过程" 区域
- **停止生成**：加载中显示停止按钮

**工具调用去重**：
- 使用 `toolCallFingerprint()` 对工具调用做指纹去重

#### 5.2.4 `ClarifyForm` (`components/chat/clarify-form.tsx`)

**角色**：Agent 表单中断的前端 UI

**支持的字段类型**：
- `text`：文本输入框
- `select`：单选下拉
- `multiselect`：多选复选框组

**交互流程**：
```
Agent 调用 clarify_form 工具
  → LangGraph interrupt → 前端收到 interrupt 数据
  → 渲染 ClarifyForm（title + description + fields）
  → 用户填写并提交
  → resume(values) → LangGraph 恢复 Agent 执行
  → 表单变为 "✓ 已提交" 状态
```

---

### 5.3 配置组件

#### `ConfigPanel` (`components/config/config-panel.tsx`)

**角色**：工作区配置入口面板，提供 PPT 风格、TTS 音色和风格提取三个配置项。

**功能**：
- 显示当前选中的风格和音色摘要
- 点击打开对应的选择弹窗
- 提供"提取风格"入口，打开风格提取上传弹窗
- 选择后通过 `updateWorkspaceConfig()` API 持久化到 workspace.ext_data

#### `StylePickerDialog` (`components/config/style-picker-dialog.tsx`)

**角色**：PPT 风格选择弹窗

**数据来源**：通过 `listPptStyles()` API 从后端加载风格列表（系统预设 + 用户自定义）

**风格分类**：
- **深色主题 (dark)**：Bold Signal, Electric Studio, Creative Voltage, Dark Botanical 等
- **浅色主题 (light)**：Notebook Tabs, Pastel Geometry, Split Pastel, Vintage Editorial 等
- **自定义主题 (custom)**：通过风格提取工作流生成的用户自定义风格

**功能**：
- 网格布局展示所有风格，按分类分组
- 每种风格显示中文名、英文名、视觉描述
- 支持点击预览（加载风格预览 HTML 到 iframe）
- 选中后持久化到 workspace config
- 自定义风格支持删除（二次确认）

#### `StyleExtractionUploadDialog` (`components/config/style-extraction-upload-dialog.tsx`)

**角色**：PPTX 文件上传入口弹窗

**功能**：
- 选择 .pptx 文件
- 调用 `submitStyleExtraction()` API 上传并启动风格提取
- 上传成功后关闭弹窗，打开 StyleExtractionDialog 展示进度

#### `StyleExtractionDialog` (`components/config/style-extraction-dialog.tsx`)

**角色**：风格提取进度可视化弹窗

**步骤可视化**：
1. 上传文件
2. 解析 PPTX 结构
3. 分析风格特征
4. 生成预览页面
5. 完成

**功能**：
- 轮询 `getTask()` API 获取任务进度
- 每步显示 done/active/pending/error 状态
- 完成后可预览生成的风格预览 HTML
- 确认后调用 `saveStyleFromExtraction()` 保存为自定义风格
- 保存成功后通知 ConfigPanel 刷新风格列表

#### `VoicePickerDialog` (`components/config/voice-picker-dialog.tsx`)

**角色**：TTS 音色选择弹窗

**功能**：
- 展示可用音色列表（通过 `listVoices()` API 从后端加载，包含名称、性别、特质描述）
- 支持在线试听（播放预置音频样本 URL）
- 选择后持久化到 workspace config（存储完整 `voice_info` 结构体）

---

### 5.4 文档组件

#### `DocumentPanel` (`components/document/document-panel.tsx`)

**角色**：文档上传和管理面板

**功能**：
- **上传**：支持多文件选择，通过 `FormData` 上传到 FastAPI
- **列表**：展示文档名、类型标签、状态图标
- **状态轮询**：当有文档处于处理中状态时，每 1.5 秒自动轮询刷新
- **删除**：点击删除按钮移除文档

**文档状态展示**：

| 状态 | 图标 | 颜色 | 标签 |
|------|------|------|------|
| `uploaded` | Loader2 (旋转) | 蓝色 | 已上传 |
| `parsing` | Loader2 (旋转) | 黄色 | 正在解析 |
| `parsed` | Loader2 (旋转) | 黄色 | 已解析 |
| `chunking` | Loader2 (旋转) | 黄色 | 正在分块 |
| `indexing` | Loader2 (旋转) | 黄色 | 正在入库 |
| `summarizing` | Loader2 (旋转) | 黄色 | 正在理解文档 |
| `ready` | CheckCircle | 绿色 | 就绪 |
| `error` | AlertCircle | 红色 | 失败 |

**轮询优化**：仅当文档列表中存在 `ACTIVE_STATUSES` 状态时才启动定时器。

---

### 5.5 产出组件

#### `TaskPanel` (`components/task/task-panel.tsx`)

**角色**：展示 Agent 生成的产出物，支持父子任务层级

**功能**：
- **父子层级展示**：顶层任务（PPT）可展开/折叠，子任务（口播稿）嵌套显示
- **预览**：PPT 完成后可打开预览/编辑弹窗
- **播放**：口播稿完成后与 PPT 联动播放
- **生成口播稿**：PPT 完成后可触发口播稿生成（通过 onNarrate 回调）
- **下载**：通过 `downloadTaskFile(taskId, filename)` 触发浏览器下载（fetch + Blob URL 跨域方案）
- **删除**：PPT 删除时二次确认（提示将删除关联口播稿和音频）
- **折叠**：整个面板可折叠为窄条
- **自动刷新**：每 5 秒轮询任务列表

**任务类型**：

| 类型 | 图标 | 关系 | 文件格式 |
|------|------|------|---------|
| `ppt` | Presentation | 顶层 | `.html`（自包含 HTML） |
| `narration` | Mic | PPT 子任务 | `.md`（文本）+ `.wav`（音频） |
| `ppt_style_extraction` | Palette | 顶层（独立管理） | `preview.html` |

**任务状态**：

| 状态 | 图标 | 颜色 | 说明 |
|------|------|------|------|
| `generating` | Loader2 (旋转) | 黄色 | 生成中 |
| `completed` | CheckCircle | 绿色 | 已完成 |
| `failed` | Package | 红色 | 失败 |
| `narrating` | Loader2 (旋转) | 黄色 | 口播稿文本生成中 |
| `tts_generating` | Loader2 (旋转) | 蓝色 | 音频生成中（显示进度） |
| `tts_failed` | AlertCircle | 橙色 | 音频生成失败 |
| `cancelled` | XCircle | 灰色 | 已取消（风格提取） |

---

### 5.6 PPT 播放/预览组件

#### `PPTPreviewDialog` (`components/player/ppt-preview-dialog.tsx`)

**角色**：PPT 预览 + 在线编辑

**核心功能**：
- **iframe srcDoc 渲染**：将 PPT HTML 通过 `srcDoc` 注入 iframe 展示
- **编辑模式**：按 E 键或点击按钮切换 `contentEditable`，支持在 iframe 内直接编辑
- **保存**：编辑后通过 `postMessage` 获取修改后的 HTML，调用 `saveTaskFile()` API 回写
- **样式信息显示**：展示当前 PPT 使用的风格预设名称

#### `PPTPlayerDialog` (`components/player/ppt-player-dialog.tsx`)

**角色**：PPT 幻灯片播放 + 音频同步

**核心功能**：
- **逐页播放**：解析 PPT HTML 中的 `.slide` 元素，逐页切换显示
- **音频同步**：每页幻灯片对应一段音频，音频播完自动翻页
- **进度条**：显示当前页/总页数，支持点击跳转
- **全屏模式**：支持进入全屏播放
- **音量控制**：静音/取消静音切换
- **交互锁定**：注入脚本禁用 iframe 内的所有用户交互（滚动、点击、键盘）

---

### 5.7 工作区组件

#### `WorkspaceCard` (`components/workspace/workspace-card.tsx`)

工作区卡片，展示名称 + 创建时间 + 删除按钮，点击进入工作区。

#### `CreateDialog` (`components/workspace/create-dialog.tsx`)

创建工作区的模态弹窗，包含名称输入 + 提交/取消按钮 + 重名错误提示。

---

## 六、数据层

### 6.1 API 封装 (`lib/api.ts`)

统一的 HTTP 请求封装，所有与 FastAPI 的通信通过此模块。

**设计特点**：
- `request<T>()` 泛型方法，自动 JSON 解析 + 错误处理
- `ApiError` 自定义错误类，携带 `status` + `detail`
- 所有方法都有详细的 console.log 调试日志
- `API_BASE` 通过 `NEXT_PUBLIC_API_BASE` 环境变量配置

**API 方法清单**：

| 方法 | 端点 | 说明 |
|------|------|------|
| `createWorkspace()` | `POST /api/workspaces` | 创建工作区 |
| `listWorkspaces()` | `GET /api/workspaces` | 列出用户工作区 |
| `getWorkspace()` | `GET /api/workspaces/{id}` | 获取工作区详情（含 ext_data） |
| `deleteWorkspace()` | `DELETE /api/workspaces/{id}` | 删除工作区 |
| `updateWorkspaceThreadId()` | `PATCH /api/workspaces/{id}/thread` | 绑定 thread_id |
| `updateWorkspaceConfig()` | `PATCH /api/workspaces/{id}/config` | 更新配置（ppt_style/voice_id） |
| `listThreadMessages()` | `GET /api/threads/{id}/messages` | 获取消息历史（turn-based 分页） |
| `getMessageDetail()` | `GET /api/threads/{id}/messages/{mid}` | 获取单条消息详情 |
| `listDocuments()` | `GET /api/workspaces/{id}/documents` | 列出文档 |
| `uploadDocument()` | `POST /api/workspaces/{id}/documents` | 上传文档（FormData，409 去重） |
| `deleteDocument()` | `DELETE /api/workspaces/{id}/documents/{doc_id}` | 删除文档 |
| `listTasks()` | `GET /api/workspaces/{id}/tasks` | 列出任务（顶层+嵌套子任务） |
| `getTask()` | `GET /api/workspaces/{id}/tasks/{task_id}` | 获取单个任务详情 |
| `deleteTask()` | `DELETE /api/workspaces/{id}/tasks/{task_id}` | 删除任务 |
| `saveTaskFile()` | `PUT /api/workspaces/{id}/tasks/{task_id}/file` | 保存 PPT HTML 编辑 |
| `listPptStyles()` | `GET /api/ppt-styles` | 列出 PPT 风格（系统+自定义） |
| `deletePptStyle()` | `DELETE /api/ppt-styles/{id}` | 删除自定义风格 |
| `listVoices()` | `GET /api/voices` | 列出可用 TTS 音色 |
| `submitStyleExtraction()` | `POST /api/workspaces/{id}/style-extraction` | 上传 PPTX 启动风格提取 |
| `deleteStyleExtraction()` | `DELETE /api/workspaces/{id}/style-extraction/{task_id}` | 取消并删除风格提取 |
| `saveStyleFromExtraction()` | `POST /api/style-extraction/{task_id}/save` | 保存提取结果为自定义风格 |
| `getFileViewUrl()` | 构建 URL | 生成内联预览 URL（支持 thumb） |
| `downloadTaskFile()` | `GET /api/tasks/{id}/download` | 触发浏览器下载任务文件 |
| `fetchFileContent()` | 直接 fetch | 获取文件文本内容 |

**类型定义**：
- `Workspace`：`id, user_id, name, thread_id, ext_data, created_at`（`ext_data` 含 `ppt_style` 风格 ID + `voice_info` 结构体）
- `Document`：`id, workspace_id, filename, file_type, summary, status, error_message, created_at, updated_at`
- `DocumentStatus`：`uploaded | processing | parsing | parsed | chunking | indexing | summarizing | ready | error`
- `Task`：`id, workspace_id, type, title, status, result_data, parent_task_id, children, created_at`
- `ThreadMessage`：`id, thread_id, workspace_id, message_id, role, type, content, tool_calls, ...`
- `ThreadMessagesPage`：`messages, next_cursor`
- `PptStyleInfo`：`id, user_id, category, name, name_en, description, preview_path, created_at`
- `VoiceInfo`：`id, name, gender, trait, audio_url`

### 6.2 状态管理

前端 **不使用全局状态管理库**，采用以下策略：

| 状态类型 | 管理方式 | 说明 |
|---------|---------|------|
| 工作区列表 | `useState` + `useCallback` | 页面级，fetchWorkspaces 刷新 |
| 文档列表 | `useState` + 轮询 | 面板级，有活跃状态时 1.5s 轮询，重复上传 toast 提示 |
| 任务列表 | `useState` + 轮询 | 面板级，固定 5s 轮询 |
| 对话流 | `useStream` (LangGraph) | 由 @langchain/langgraph-sdk/react 管理 |
| 消息历史 | `listThreadMessages` | turn-based 分页，按需加载更多 |
| Thread ID | `useState` + 后端持久化 | Assistant 组件管理，跨会话持久 |
| 工作区配置 | `useState` + 后端持久化 | ppt_style / voice_id，通过 updateWorkspaceConfig 同步 |
| PPT 风格列表 | `useState` + API 加载 | ConfigPanel 管理，通过 listPptStyles 获取 |
| 风格提取进度 | `useState` + 轮询 | StyleExtractionDialog 管理，通过 getTask 轮询 |
| 用户 ID | `localStorage` | `lib/user.ts` 管理，浏览器级持久 |
| 面板宽度 | `useState` | ThreePanel 组件局部状态 |
| PPT 播放 | `useState` | workspace page 管理 playerData/previewTask |
| ExternalCommand | `useState` | workspace page → ChatPanel，一次性消费 |

---

## 七、核心交互流程

### 7.1 首次访问

```
用户打开 localhost:3000
  → layout.tsx 渲染根布局
  → page.tsx (首页)
    → getUserId() → localStorage 无值 → 生成 UUID 并存储
    → listWorkspaces(userId) → 空列表
    → 展示 "还没有工作区，创建一个开始吧"
```

### 7.2 创建工作区并进入

```
用户点击"新建工作区" → 打开 CreateDialog
  → 输入名称 → 提交
  → createWorkspace(userId, name)
    → 成功: 刷新列表，关闭弹窗
    → 409: 显示 "工作区名称已存在"

用户点击工作区卡片
  → router.push(`/workspace/${id}`)
  → workspace/[id]/page.tsx
    → getWorkspace(id) 验证工作区存在，读取 ext_data 配置
    → 渲染 header + ThreePanel 三栏布局
```

### 7.3 上传文档

```
用户在文档面板点击上传 → 选择文件
  → uploadDocument(workspaceId, file) [FormData]
  → 重复文档返回 409，前端 toast 提示
  → 文档立即出现在列表（status=uploaded）
  → 轮询开始（1.5s 间隔）
  → 状态变化: uploaded → parsing → parsed → chunking → indexing → summarizing → ready
  → ready 后轮询自动停止
```

### 7.4 AI 对话

```
用户在聊天面板输入消息 → 提交
  → Assistant.submit(content)
    → useStream.submit({
        messages: [{role:"human", content}],
        workspace_id, ppt_style, voice_id, current_ppt_task_id
      })
    → LangGraph Server 创建/复用 thread
    → 流式返回 AI 消息

  Thread 实时渲染:
    → 文本内容: ReactMarkdown 渲染
    → 工具调用: 显示可折叠的工具卡片
    → 思考过程: <think> 标签折叠展示
    → 引用标记: {{ref:...}} 渲染为标签

  如果 Agent 调用 clarify_form:
    → interrupt 事件 → 渲染 ClarifyForm
    → 用户填写提交 → resume(values)
    → Agent 继续执行
```

### 7.5 配置切换

```
用户在右侧配置面板点击风格/音色入口
  → 打开 StylePickerDialog / VoicePickerDialog
  → StylePickerDialog 从 API 加载风格列表（listPptStyles）
  → 风格按分类展示（深色/浅色/自定义）
  → 选择后:
    → onConfigChange("ppt_style", styleNameEn) → 更新本地状态
    → updateWorkspaceConfig(workspaceId, "ppt_style", styleNameEn) → 持久化到后端
    → 后续聊天消息自动携带新的 ppt_style
```

### 7.6 PPT 风格提取

```
用户在配置面板点击"提取风格"
  → 打开 StyleExtractionUploadDialog
  → 选择 .pptx 文件 → submitStyleExtraction(workspaceId, file)
  → 后端创建 Task (type=ppt_style_extraction) 并启动异步工作流
  → 关闭上传弹窗 → 打开 StyleExtractionDialog

StyleExtractionDialog 轮询进度:
  → getTask(workspaceId, taskId) 每 2s 轮询
  → 步骤可视化: 上传文件 → 解析PPTX → 分析风格 → 生成预览 → 完成
  → 每步显示 done/active/pending/error 状态

完成后:
  → 展示风格预览 HTML（iframe 加载 preview.html）
  → 展示风格名称（中英文）、描述
  → 用户点击"保存为自定义风格"
  → saveStyleFromExtraction(taskId, userId)
  → 新风格写入 ppt_style 表 → 出现在风格选择弹窗的"自定义主题"中
  → 刷新风格列表
```

### 7.7 PPT 生成与查看

```
Agent 调用 save_ppt → 后端创建 Task + 保存文件
  → 产出面板轮询（5s）检测到新 Task
  → PPT 显示在产出列表
  → 用户点击预览按钮 → 打开 PPTPreviewDialog
    → iframe srcDoc 加载 PPT HTML
    → 可按 E 键进入编辑模式 → 修改后保存
  → 用户点击下载 → GET /api/files/{path} → 浏览器下载
```

### 7.8 口播稿生成与播放

```
用户在 PPT 任务菜单中点击"生成口播稿"
  → workspace page 设置 currentPptTaskId
  → 创建 ExternalCommand { command: "/narrate", metadata: { pptTaskId } }
  → ChatPanel 接收 → 显示胶囊 UI → 用户确认发送
  → Agent 执行 narration 技能
    → 生成口播稿文本 + TTS 音频
    → 创建子 Task (parent_task_id = ppt_task_id)
  → 产出面板: PPT 任务下出现口播稿子任务
  → 口播稿完成后，点击播放按钮
    → 打开 PPTPlayerDialog
    → 逐页幻灯片 + 音频同步播放
```

### 7.9 消息历史恢复

```
用户重新打开工作区
  → Assistant 获取 workspace.thread_id
  → 如有 thread_id:
    → listThreadMessages(threadId, { limit: 3 })
    → 渲染最近 3 个 turn 的历史消息
    → 用户滚动到顶部 → 点击"加载更早消息"
    → loadOlderMessages() 使用 next_cursor 翻页
  → useStream 接管后续实时通信
```

---

## 八、通信架构

前端与两个后端服务的通信职责明确分离：

```
┌─────────────────────────────────────────────────────────────┐
│                    前端 (Next.js)                             │
│                                                             │
│  lib/api.ts ──── REST (fetch) ────→ FastAPI (:8000)         │
│    工作区 CRUD                        文档/任务管理            │
│    文档上传/删除                      消息历史查询              │
│    工作区配置更新                     任务文件回写              │
│    Thread ID 持久化                   PPT 风格管理             │
│    风格提取提交/轮询/保存              TTS 音色列表             │
│    文件下载/内联预览                                         │
│                                                             │
│  assistant.tsx ── Stream (useStream) → LangGraph (:2024)    │
│    (via @langchain/langgraph-sdk/react)                      │
│    对话消息发送                         Agent 推理             │
│    流式消息接收                         工具调用               │
│    Interrupt 处理                       会话管理              │
│    Resume 提交                                                │
│    workspace_id + ppt_style + voice_id + current_ppt_task_id │
└─────────────────────────────────────────────────────────────┘
```

**环境变量**：
| 变量 | 默认值 | 说明 |
|------|--------|------|
| `NEXT_PUBLIC_API_BASE` | `http://localhost:8000` | FastAPI 服务地址 |
| `NEXT_PUBLIC_LANGGRAPH_API_URL` | `http://localhost:2024` | LangGraph 服务地址 |

---

## 九、UI 设计系统

### 9.1 主题

采用 **暗色主题**，通过 CSS 变量定义：

| 变量 | 用途 | 说明 |
|------|------|
| `--foreground` | 主文本色 | — |
| `--background` | 页面背景 | — |
| `--muted` / `--muted-foreground` | 次要内容 | — |
| `--accent` / `--accent-foreground` | 强调色（按钮、高亮） | — |
| `--border` | 边框 | — |
| `--destructive` | 危险操作（删除） | — |

### 9.2 设计模式

- **卡片式布局**：工作区列表使用网格卡片
- **面板式布局**：工作区内三栏分屏，右侧面板上部配置、下部产出
- **气泡式对话**：用户消息右对齐，AI 消息左对齐
- **渐进披露**：工具调用默认折叠，思考过程可展开
- **状态可视化**：文档/任务/风格提取进度通过图标+颜色+文字三重提示
- **父子层级**：产出面板中 PPT 任务可展开查看关联的口播稿子任务
- **弹窗式预览/播放**：PPT 预览和播放均以全屏弹窗形式呈现
- **弹窗式风格提取**：步骤进度可视化 + 完成后可预览 + 一键保存
- **胶囊命令**：ExternalCommand 以胶囊 UI 注入聊天输入框，降低技能触发门槛
- **分类风格选择**：PPT 风格按深色/浅色/自定义分类展示，支持预览和删除
- **文档去重**：上传时后端基于文件名 + 内容哈希检测重复，409 状态码前端 toast 提示
- **文件下载跨域方案**：通过 fetch + Blob URL + 临时 `<a>` 元素实现跨域文件下载，避免浏览器同源策略限制
- **响应式**：工作区列表 1-3 列自适应

---

## 十、关键设计决策

1. **双通道通信**：REST API 处理 CRUD 和风格管理，LangGraph Stream 处理 AI 对话，职责清晰
2. **Context Provider 模式**：`Assistant` 组件作为 Provider 管理 Agent 连接和消息历史，子组件通过 `useStreamContext()` 消费
3. **无全局状态库**：数据流简单（列表+详情），每个面板独立管理自己的数据，通过 React 原生 `useState` + `useCallback` 足够
4. **轮询而非 WebSocket**：文档状态、任务列表和风格提取进度通过轮询同步，实现简单且场景契合
5. **LangGraph SDK 接管对话**：不自行实现流式通信协议，完全依赖 `@langchain/langgraph-sdk/react` 的 `useStream` hook
6. **Thread ID 双向持久化**：前端通过 `useStream` 获取 `threadId`，再通过 REST API 持久化到后端 workspace 记录
7. **消息历史 turn-based 分页**：以 human 消息为 turn 边界，按需加载更多历史，避免一次性加载全部消息
8. **ExternalCommand 机制**：复杂技能（如 /narrate）通过父组件注入胶囊命令，而非要求用户手动输入 slash command
9. **父子任务层级**：Task 面板以树形结构展示 PPT 及其关联的口播稿子任务，支持级联操作
10. **PPT 预览/编辑一体化**：通过 iframe srcDoc + contentEditable 实现在线编辑，postMessage 获取修改后的 HTML 回写
11. **所有组件 "use client"**：由于强依赖浏览器 API（localStorage、DOM 事件、流式通信），所有组件均为 Client Components
12. **可拖拽三栏布局**：使用原生 DOM 事件实现拖拽，避免引入额外布局库
13. **PPT 风格 API 化**：风格列表从后端 API 动态加载（系统预设 + 用户自定义），而非前端硬编码
14. **风格提取工作流前端可视化**：通过轮询 Task 进度，将后端异步工作流的每个步骤实时展示给用户
15. **TTS 音色 API 化**：音色列表从后端 `GET /api/voices` 接口加载，不在前端硬编码
16. **文件下载抽象**：前端通过 `downloadTaskFile(taskId)` 下载，后端解析文件路径，存储细节对前端透明
17. **文档去重**：上传时后端检测重复（文件名 + 内容哈希），409 状态码前端友好提示
