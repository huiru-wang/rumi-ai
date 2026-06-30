# 文档解析架构设计

## 目标

将任意类型文档（PDF、DOCX、Markdown/TXT）解析为两项最终输出：

1. **Summary** — 文档级摘要（200字以内）
2. **Vector Chunks** — 带原文档位置索引的向量数据

Markdown 仅作为结构化中间表示，不作为最终交付产物。

---

## 整体管线

```
          ┌─────────────────────────────────────────────┐
          │        Stage 1: 分类 + 适配器选择              │
          └──────────────────┬──────────────────────────┘
                             ▼
          ┌─────────────────────────────────────────────┐
          │        Stage 2: 多模态结构提取                 │
          │        输出 → Block[] (统一中间表示)           │
          └──────────────────┬──────────────────────────┘
                             ▼
          ┌─────────────────────────────────────────────┐
          │        Stage 3: 图片理解（Vision LLM）         │
          │        image block → caption 文本             │
          └──────────────────┬──────────────────────────┘
                             ▼
          ┌─────────────────────────────────────────────┐
          │        Stage 4: 语义分块                       │
          │        Block[] → Chunk[]（带 locator）         │
          └──────────────────┬──────────────────────────┘
                             ▼
          ┌─────────────┬────┴───────────────────────────┐
          ▼             ▼                                 │
   ┌────────────┐  ┌──────────────┐                      │
   │ Stage 5a   │  │ Stage 5b     │                      │
   │ Embedding  │  │ Summarization│                      │
   │ → 向量入库  │  │ → 文档摘要    │                      │
   └────────────┘  └──────────────┘                      │
```

---

## Stage 1: 文档分类与策略路由

```
输入: file_bytes + filename

判断逻辑:
  .docx       → DocxExtractor
  .md / .txt  → MarkdownExtractor
  .pdf        → PDF 子分类:
                 ├── 文本型（可提取字符密度 > 阈值）→ TextPdfExtractor
                 ├── 扫描型（字符稀疏/字体异常）    → VisionPdfExtractor
                 └── 混合型（部分页文本，部分页扫描）→ HybridPdfExtractor
```

### PDF 子分类信号

- 采样页（最多 10 页）的平均可提取字符数（阈值：50 字符/页）
- CID 字体使用占比（嵌入字体映射异常）
- Unicode 映射错误率
- 图片覆盖面积比（> 80% 判定为扫描）
- 异常长宽比页面检测

---

## Stage 2: 多模态结构提取

所有提取器输出统一的 `Block[]` 中间表示。

### Block 数据结构

```
Block:
  type: "heading" | "text" | "image" | "table" | "formula" | "code" | "list"
  content: str              # 文本内容 / LaTeX / HTML table / ""(图片无文本)
  image_data: bytes?        # 图片原始数据（仅 image 类型）
  level: int?               # heading 级别（1-3）
  locator:                  # 原文档定位
    page: int?              # PDF 页码
    paragraph_index: int?   # DOCX 段落序号
    line_range: [int, int]? # Markdown 行号范围
    bbox: [x0, y0, x1, y1]?# PDF 页面坐标（归一化 0~1）
```

### 各文档类型提取策略

#### TextPdf（文本型 PDF）

```
每页:
  → get_text("dict") 提取文本 span（附带字体大小/粗体信息）
  → get_images() 提取嵌入图片
  → find_tables() 提取表格结构
  → 按阅读顺序排列所有 block
  → 每个 block 携带 page + bbox 定位
  → 标题检测: 字体大小启发式 + 编号模式匹配
```

#### VisionPdf（扫描型 PDF）

```
每页:
  → 渲染为 200dpi PIL Image
  → Vision LLM 整页理解 → 输出结构化 Markdown
  → 解析 Markdown 为 Block[]
  → locator 为 page 级定位（无精确 bbox）
```

#### HybridPdf（混合型 PDF）

```
逐页判断:
  文本页（字符密度 > 阈值）→ TextPdf 策略
  扫描页（字符密度 < 阈值）→ VisionPdf 策略
合并为统一 Block[]，保持页面顺序
```

#### DOCX

```
遍历 document.body 所有元素（保持文档顺序）:
  paragraph (heading style) → heading block, locator = paragraph_index
  paragraph (normal)        → text block, locator = paragraph_index
  table                     → table block (保留 HTML 结构), locator = paragraph_index
  inline_shape / image      → image block, locator = paragraph_index
```

#### Markdown / TXT

```
逐行解析:
  # heading       → heading block, locator = line_range
  正文段落         → text block, locator = line_range
  ![alt](url)     → image block (下载或保留 URL), locator = line_range
  | table |       → table block, locator = line_range
  ```code```      → code block, locator = line_range
```

---

## Stage 3: 图片理解

```
遍历 Block[] 中 type == "image" 的 block:

  1. 过滤: 尺寸 < 50x50px 或 < 5KB → 标记为装饰，跳过
  2. 存储: image_data → FileStore/OSS → 得到 storage_path
  3. 描述: image_data → Vision LLM → caption（200字以内）
  4. 回写: block.content = caption, block.image_ref = storage_path
```

经过此阶段，所有 block 都具有文本化的 `content`，可统一参与后续分块。

---

## Stage 4: 语义分块

将有序的 `Block[]` 切分为适合向量检索的 `Chunk[]`。

### 分块策略

1. 以 heading 为天然分界线，形成 Section 组
2. 每个 Section 内的 blocks 按顺序合并为连续文本
3. 图片 caption 以 `[图: ...]` 标记融入文本流
4. 表格以简化文本或 HTML 形式保留
5. 超长 Section → RecursiveTextSplitter 切分（保持 overlap）
6. 每个 chunk 继承其来源 blocks 的 locator 范围（取并集）

### Chunk 数据结构

```
Chunk:
  text: str                      # 用于 embedding 的完整文本（含 caption）
  section_title: str             # 所属章节标题
  chapter_title: str             # 所属上级章节标题
  chunk_index: int               # 全文顺序编号
  image_refs: [storage_path]     # 关联的图片路径列表
  locator:                       # 聚合后的定位信息
    pages: [int]                 # 跨页范围 (PDF)
    paragraph_range: [int, int]  # 段落范围 (DOCX)
    line_range: [int, int]       # 行号范围 (Markdown)
    bbox_page_map: {page: [x0, y0, x1, y1]}  # 各页的区域（可选）
```

### 分块参数

- 目标 chunk 大小: 800 ~ 1500 字符
- overlap: 150 ~ 200 字符
- 分隔符优先级: `\n\n` > `\n` > `。` > `；` > ` `

---

## Stage 5a: Embedding 入库

```
对每个 Chunk:
  1. embedding = embed_model(chunk.text)
  2. 写入向量库 (pgvector):
     - embedding: vector(1536)
     - metadata:
         doc_id, workspace_id
         section_title, chapter_title
         chunk_index
         locator (JSONB)
         image_refs (JSONB)
         source_filename
```

### 向量存储 Schema (pgvector)

```sql
CREATE TABLE document_chunk (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id UUID NOT NULL,
    document_id UUID NOT NULL,
    chunk_index INT NOT NULL,
    embedding_text TEXT NOT NULL,
    embedding vector(1536),
    section_title TEXT DEFAULT '',
    chapter_title TEXT DEFAULT '',
    locator JSONB DEFAULT '{}',
    image_refs JSONB DEFAULT '[]',
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_chunk_embedding ON document_chunk
    USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
CREATE INDEX idx_chunk_workspace ON document_chunk(workspace_id);
CREATE INDEX idx_chunk_document ON document_chunk(document_id);
```

---

## Stage 5b: Summary 生成

```
短文档（< 8000 字）:
  全文拼接 → LLM → 200字摘要

长文档（> 8000 字）:
  前 N 个 section 各自生成段落摘要
  → 拼接段落摘要 → LLM → 200字全文摘要
```

---

## RAG 检索流程

```
用户提问
  → text embedding → 向量检索 top-k chunks
  → 组装上下文:
       text_context = chunk.text 拼接
       image_urls = chunk.image_refs 收集
  → 送入 LLM:
       若有图片且 LLM 支持 vision → 多模态消息（文本 + 图片）
       否则 → 纯文本消息（caption 已包含在 text 中）
  → 生成回答
```

---

## 设计原则

1. **一切皆 Block** — 统一中间表示，隔离上游文档类型差异
2. **位置不丢** — 从提取到入库全链路保留 locator，支持回溯原文
3. **图片文本化** — Vision LLM 将图片转为 caption，参与文本 embedding
4. **策略自适应** — 自动判断文档特征，选择最优解析路径
5. **最终产物极简** — 只输出 Summary + Vector Chunks，不保留冗余中间文件

---

## 流程示例

### 30 页混合型 PDF（含扫描图表）

```
1. [分类] 采样 10 页 → 第 1-20 页文本丰富，21-30 页为扫描图表
   → 路由到 HybridPdfExtractor

2. [提取]
   Page 1-20: PyMuPDF 文本提取 → 120 个 text/heading blocks + 5 个 image blocks + 3 个 table blocks
   Page 21-30: 渲染为图片 → Vision LLM → 产出 40 个 blocks
   合计: 168 个 blocks

3. [图片理解]
   8 张有意义的图片 → Vision LLM caption
   例: "柱状图显示 2023 年 Q1-Q4 营收趋势，Q3 达到峰值 2.4 亿元"

4. [分块]
   168 blocks → 按 heading 分组为 12 sections → 切分为 28 chunks
   每个 chunk 携带 locator: {pages: [5, 6], bbox_page_map: {...}}

5. [输出]
   28 chunks → embedding → pgvector
   全文 → LLM → Summary: "本报告分析了xxx公司2023年度经营状况..."
```
