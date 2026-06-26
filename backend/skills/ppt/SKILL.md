---
name: html-ppt
description: Create stunning, animation-rich HTML presentations from scratch or by converting PowerPoint files. Use when the user wants to build a presentation, convert a PPT/PPTX to web, or create slides for a talk/pitch. Helps non-designers discover their aesthetic through visual exploration rather than abstract choices.
---

# html-ppt

Create zero-dependency, animation-rich HTML presentations that run entirely in the browser.

## Core Principles

1. **Zero Dependencies** — Single HTML files with inline CSS/JS. No npm, no build tools.
2. **Single-step choices** — Collect concrete choices up front, then generate the final deliverable directly. Do not create intermediate style preview files.
3. **Distinctive Design** — No generic "AI slop." Every presentation must feel custom-crafted.
4. **Viewport Fitting (NON-NEGOTIABLE)** — Every slide MUST fit exactly within 100vh. No scrolling within slides, ever. Content overflows? Split into multiple slides.

## Design Aesthetics

You tend to converge toward generic, "on distribution" outputs. In frontend design, this creates what users call the "AI slop" aesthetic. Avoid this: make creative, distinctive frontends that surprise and delight.

Focus on:

- Typography: Choose fonts that are beautiful, unique, and interesting. Avoid generic fonts like Arial and Inter; opt instead for distinctive choices that elevate the frontend's aesthetics.
- Color & Theme: Commit to a cohesive aesthetic. Use CSS variables for consistency. Dominant colors with sharp accents outperform timid, evenly-distributed palettes. Draw from IDE themes and cultural aesthetics for inspiration.
- Motion: Use animations for effects and micro-interactions. Prioritize CSS-only solutions for HTML. Use Motion library for React when available. Focus on high-impact moments: one well-orchestrated page load with staggered reveals (animation-delay) creates more delight than scattered micro-interactions.
- Backgrounds: Create atmosphere and depth rather than defaulting to solid colors. Layer CSS gradients, use geometric patterns, or add contextual effects that match the overall aesthetic.

Avoid generic AI-generated aesthetics:

- Overused font families (Inter, Roboto, Arial, system fonts)
- Cliched color schemes (particularly purple gradients on white backgrounds)
- Predictable layouts and component patterns
- Cookie-cutter design that lacks context-specific character

Interpret creatively and make unexpected choices that feel genuinely designed for the context. Vary between light and dark themes, different fonts, different aesthetics. You still tend to converge on common choices (Space Grotesk, for example) across generations. Avoid this: it is critical that you think outside the box!

## Viewport Fitting Rules

These invariants apply to EVERY slide in EVERY presentation:

- Every `.slide` must have `height: 100vh; height: 100dvh; overflow: hidden;`
- ALL font sizes and spacing must use `clamp(min, preferred, max)` — never fixed px/rem
- Content containers need `max-height` constraints
- Images: `max-height: min(50vh, 400px)`
- Breakpoints required for heights: 700px, 600px, 500px
- Include `prefers-reduced-motion` support
- Never negate CSS functions directly (`-clamp()`, `-min()`, `-max()` are silently ignored) — use `calc(-1 * clamp(...))` instead
- **Background images from style template**: When the style template provides background image resources, you **MUST** use them on the cover slide and key transition slides. **NEVER** overlay background images with semi-transparent solid color layers (e.g., `rgba(255,255,255,0.9)`) — this destroys the visual identity. For text readability over background images, use local text background blocks (semi-transparent card behind text only, not full-slide overlay) or text shadows. Background images use `.bg-image` class with `background-image` on a `<div>`, never `<img>`.

**When generating, read `viewport-base.css` and include its full contents in every presentation.**

### Content Density Limits Per Slide

| Slide Type    | Maximum Content                                           |
| ------------- | --------------------------------------------------------- |
| Title slide   | 1 heading + 1 subtitle + optional tagline                 |
| Content slide | 1 heading + 4-6 bullet points OR 1 heading + 2 paragraphs |
| Feature grid  | 1 heading + 6 cards maximum (2x3 or 3x2)                  |
| Code slide    | 1 heading + 8-10 lines of code                            |
| Chart slide   | 1 heading + 1 chart (max 60% height) + 1-2 insights       |
| Quote slide   | 1 quote (max 3 lines) + attribution                       |

**Content exceeds limits? Split into multiple slides. Never cram, never scroll.**

---

## Phase 1: Content Discovery

**Before building the form**, analyze the user's original message to extract explicitly provided information (topic, purpose, page count, document scope). Set matched values as `recommended` for the corresponding fields. `recommended` will be auto-preselected by the frontend and shown with a "推荐" badge. **The form always displays all questions** — let the user confirm or adjust.

**Ask ALL questions in a single `clarify_form` call** so the user fills everything out at once.

### Language Rule
All form `label` and `options` **must match the user's language**. When the user speaks Chinese, use 简体中文; when English, use English. The fixed options below are provided in Chinese as default — translate them only if the user is clearly using another language.

### Form Fields

**Question 1 — Topic（主题确认）** (header: "Topic")
- Type: `select`, `allow_custom: true`
- Options: Based on knowledge-base document summaries, recommend 2–3 topic directions as options. If the user's message clearly mentions a topic, include it as an option and put it in `recommended`.
- If no knowledge-base documents are available and the user hasn't provided a topic, set `options` to an empty list `[]` — the user will use the custom input field.
- **Never add placeholder options like "自定义主题" to the `options` array** — the custom input field (rendered automatically when `allow_custom=true`) already handles free-text input.
- If the user provided a topic, set `recommended: ["<user's topic>"]`.
- If the user did not provide a topic, set `recommended` to the most relevant topic from the document options.

**Question 2 — Purpose（用途）** (header: "Purpose")
- Type: `select`
- Options: `产品路演` / `教学培训` / `会议演讲` / `内部汇报`
- If the user's message clearly states a purpose, set `recommended: ["<matched option>"]`.
- Otherwise, recommend based on Topic context (e.g., product-related topic → "产品路演", teaching-related topic → "教学培训").

**Question 3 — Length（页数）** (header: "Length")
- Type: `select`
- Options: `精简 5-10页` / `适中 10-20页` / `详尽 20+页`
- If the user's message clearly states a page range, set `recommended: ["<matched option>"]`.
- Otherwise, recommend based on Purpose (e.g., 产品路演 → "精简 5-10页", 教学培训 → "适中 10-20页").

**Question 4 — Source Documents（内容来源）** (header: "Sources")
- Type: `multiselect`
- **Only include this field when knowledge-base documents are available.** If no documents, omit this field.
- Options: List every available document by filename or clear title. **Do NOT include a "全部文档" option** — since this is a multiselect field, users can simply select all documents individually if needed.
- If the user's message specifies documents, set `recommended: ["<specified docs>"]`.
- Otherwise, set `recommended` to all available document names (so they are all preselected by default).
- If the user selects specific documents, use only those as the generation scope.
- If the user selects all documents, use every available knowledge-base document.

**When no documents are available and the user has not provided a topic**, the Topic question's custom input is required. Do not proceed with generation until the user provides a concrete topic, outline, or source content.

### Form Cancellation

If the user cancels the form (the tool returns `cancelled: true`), **immediately stop the entire PPT generation flow**. Do not proceed to Phase 2 or any subsequent step. Politely acknowledge the cancellation and wait for the user's next instruction.

### Default capability — Inline Editing
Do not ask whether inline editing is needed. Generated HTML presentations must support editing text directly in the browser by default, including edit mode, localStorage auto-save, and export/save functionality.

Only disable inline editing when the user explicitly asks for a presentation-only file, a smaller file, or no editing controls.

---

## Phase 2: Outline Confirmation

Before generating the final HTML presentation, create a text-only Markdown outline and ask the user to confirm it.

**Hard gate:** Do not generate the full HTML presentation and do not call `save_ppt` until the user explicitly confirms the outline.

Use the selected source documents as the retrieval and generation scope:

- "All documents" means synthesize across all available knowledge-base documents
- Specific document selections mean retrieve from and cite only those selected documents
- If no documents are selected, rely on the user's provided topic, outline, or source content
- Do not imply that unselected documents were used

### Step 2.1: Draft Outline

Output the outline as Markdown in this structure:

```md
## PPT 大纲确认

主题：...

目标受众：...

用途：...

预计页数：...

视觉风格：...

内容来源：...

### 幻灯片结构

| # | 标题 | 核心内容 | 关键词 | 视觉建议 | 依据/来源 |
|---|------|----------|--------|----------|-----------|
| 1 | ... | ... | 关键词1,关键词2,关键词3 | ... | ... |
| 2 | ... | ... | 关键词1,关键词2,关键词3 | ... | ... |

### 内容取舍说明

- 会重点展开：...
- 会简略处理：...
- 暂不纳入：...

### 请确认

如果这个大纲方向没问题，请回复“确认”。
如果需要调整，请直接说明希望修改的部分，例如：增加/删除章节、调整页数、更换顺序、加强案例、加强代码、加强图解或总结。
```

#### Keywords 生成规则（重要）

`keywords` 的唯一用途是作为 RAG 检索查询词，从知识库原始文档中召回与该幻灯片相关的段落。生成时必须遵守以下规则：

**✅ 必须包含：**
- 该幻灯片涉及的**具体技术术语、专有名词、API/类名**（如 `ThreadPoolExecutor`、`volatile`、`CountDownLatch`）
- 该幻灯片涉及的**具体业务场景或操作名称**（如 "加锁顺序"、"死锁预防"、"线程池配置参数"）
- 优先选择**在源文档原文中出现过的词汇**，以提高向量检索的召回率

**❌ 禁止包含：**
- **文档来源/出版方名称**：如 "阿里巴巴"、"Oracle"、"IBM"（这些不是文档内容本身，检索不到有用段落）
- **元描述词/篇章结构词**：如 "总结"、"回顾"、"概述"、"最佳实践"、"要点"（这些词不出现在原文中，检索结果为空）
- **过于宽泛的通用词**：如 "Java"、"规范"、"编程"、"并发"（单独使用区分度太低，检索噪声大）

**示例对比：**

| 幻灯片 | ❌ 错误 keywords | ✅ 正确 keywords |
|--------|----------------|----------------|
| 封面/标题 | 阿里巴巴, Java, 并发, 规范 | 并发处理, 编程规约, 线程安全规范 |
| 核心要点回顾 | 总结, 回顾, 最佳实践 | ThreadPoolExecutor, 锁粒度, volatile, ConcurrentHashMap |

Keep the outline concise but concrete enough for the user to judge scope, order, and emphasis. Do not call tools in the same assistant message as the outline unless retrieval is needed before writing it.

### Step 2.15: Automatic Chart Decision

When drafting the outline, inspect the source content for each slide and decide whether a chart would clarify the data relationship better than text. Do NOT ask the user whether they want charts; this is an agent design decision.

**Add a chart in the "视觉建议" column when the slide content matches any of these patterns:**

| Content Pattern | Recommended Chart |
|-----------------|-------------------|
| Multiple values compared or ranked | Bar / Lollipop / Radial Bar |
| Values changing over time or sequence | Line / Area |
| Parts of a whole, percentages, share | Donut / Treemap / Waffle |
| Flow from one stage to another | Sankey / Flow Diagram |
| Multi-dimensional scores or ratings | Radar |
| A few KPIs with a short trend | Sparkline + Big Number |

**Do NOT use a chart when:**

- Only 1-2 isolated numbers exist (use a large numeral instead)
- The comparison is purely conceptual with no figures (use cards or a diagram)
- There are more than 12 categories (aggregate or use a table)
- The data has more than 3-4 dimensions (split into multiple slides)
- The source text contains no concrete figures

**Writing rule for the outline:** When you choose a chart, write the exact chart type in the "视觉建议" column, for example:

- "Lollipop chart showing Q3 revenue by team"
- "Area chart with gradient fill for user growth trend"
- "Donut chart + center counter for market share breakdown"

Never write vague suggestions like "配图" or "可视化".

### Step 2.2: Multi-turn Revision Loop

After presenting the outline, wait for the user's reply.

- If the user explicitly confirms, proceed to Phase 3.
- If the user asks for changes, revise the outline and ask for confirmation again.
- If the user reply is ambiguous, ask one short confirmation question before proceeding.
- If the requested change conflicts with selected documents or available evidence, explain the tradeoff and propose a revised outline for confirmation.

Explicit confirmations include: "确认", "可以", "没问题", "按这个来", "开始生成", "Looks good", "Approved", or equivalent clear approval.

During this loop:

- Do not generate the full HTML presentation.
- Do not call `save_ppt`.
- Do not claim the PPT is complete.
- Preserve the latest confirmed outline as the source of truth for final generation.

---

## Phase 3: Build Final Presentation

Generate the final presentation using the last outline explicitly confirmed by the user.

The final presentation must follow the confirmed outline. You may split an overloaded slide into multiple slides for viewport fitting, but do not add or remove major sections without asking the user to confirm an updated outline.

**Before generating, read these supporting files and call the style template tool:**

- **Call `get_style_template` tool** to fetch the complete style specification (style description + resource manifest with background image URLs). This is **MANDATORY** — you must use the returned style template as the authoritative design reference and strictly follow its color scheme, typography, layout rules, and background image usage.
- [html-template.md](references/html-template.md) — HTML architecture and JS features
- [style-guide.md](references/style-guide.md) — CSS rules, anti-patterns, font reference
- [viewport-base.css](assets/viewport-base.css) — Mandatory CSS (include in full)
- [animation-patterns.md](references/animation-patterns.md) — Animation reference for the selected style and presentation tone
- [chart-guide.md](references/chart-guide.md) — When the outline contains chart slides: chart selection, design rules, anti-patterns
- [chart-patterns.css](assets/chart-patterns.css) — When the outline contains chart slides: reusable SVG chart CSS classes and keyframes
- [chart-templates.md](references/chart-templates.md) — When the outline contains chart slides: copy-ready SVG chart skeletons

**Key requirements:**

- Single self-contained HTML file, all CSS/JS inline
- Include the FULL contents of viewport-base.css in the `<style>` block
- Use fonts from fonts.loli.net (China-accessible Google Fonts mirror) — never system fonts, never api.fontshare.com
- Add detailed comments explaining each section
- Every section needs a clear `/* === SECTION NAME === */` comment block
- **严禁在幻灯片内容中出现任何来源引用标记**：包括 `{{ref:...}}`、`ref:文档名|章节`、`📄 文件名 | 位置`、`[片段N]` 等一切形式。RAG 检索返回的来源标注仅供你理解内容出处，绝不能写入最终 HTML。

---

## Phase 4: Delivery

### Step 4.1: Save Output

**You MUST call `save_ppt` to deliver the presentation, but only after the user has explicitly confirmed the outline and the final HTML is complete.** This is the only way the user can access the result in their output panel.

Never call `save_ppt` during outline drafting, outline revision, or before explicit user approval.

```
save_ppt(
  title="<presentation title, 不超过20个字>",
  content="<full self-contained HTML>",
  filename="<safe-filename>.html",
  outline=<JSON string of structured outline>
)
```

**`title` 命名规则**：标题必须简洁，**不超过 20 个字**。超出时应精简为核心主题（如"并发编程规范精讲"而非"阿里巴巴Java开发手册之并发编程规范精讲"）。

**`title` 去重规则**：调用 `save_ppt` 前，必须检查系统提示中「当前PPT产出」表格已有的标题。
- 如果不存在相同标题，则不需要关注增加标识
- 如果已存在相同的标题，必须在主标题后用中文括号追加区分标识，优先级如下：
1. **风格区分**：追加当前风格中文名，如 `产品规划（瑞士国际风）`、`产品规划（墨纸杂志）`
2. **内容侧重区分**：追加内容差异点，如 `数据安全（管理篇）`、`并发编程（实战案例版）`
3. **用途区分**：追加用途标签，如 `产品路演（精简版）`、`内部汇报（详细版）`

确保同一工作区内每个 PPT 标题唯一可辨识。如果没有重复风险，则不需要追加括号后缀。

The `outline` parameter must be a JSON string matching this schema:
```json
{
  "title": "PPT主题",
  "topic": "PPT的核心主题（简短，如：并发编程规范、数据安全管理）",
  "summary": "PPT的全局摘要（2-3句话概括整个PPT的核心内容和目标）",
  "audience": "目标受众",
  "purpose": "用途",
  "total_slides": 12,
  "style": "swiss-modern",
  "slides": [
    {
      "number": 1,
      "title": "幻灯片标题",
      "key_points": ["要点1", "要点2"],
      "keywords": ["关键词1", "关键词2", "关键词3"],
      "source_refs": ["doc_id:xxx"],
      "notes": "补充说明（可选）"
    }
  ]
}
```

**`topic`** 是 PPT 的核心主题，简短明了（如"并发编程规范"、"数据安全管理"）。
**`summary`** 用 2-3 句话概括整个 PPT 的核心内容、目标和价值，用于后续口播稿生成和系统提示展示。

This outline is used later for narration generation and RAG retrieval.

**`keywords` 规则（强制执行）：**
- 每张幻灯片填写 **3-6 个关键词**
- 关键词必须能作为 RAG 查询词，从知识库原文中召回与该页相关的段落
- 只填写**具体的技术术语、专有名词、API/类名、业务场景词**，且优先使用源文档原文中出现过的词汇
- **禁止**填写：文档来源/出版方名（如"阿里巴巴"）、元描述词（如"总结"、"回顾"、"概述"、"最佳实践"）、过于宽泛的通用词（如单独写"Java"、"规范"）
- 封面页和总结页同样需要填写与该页实际内容对应的具体术语，不得使用篇章结构词

The HTML must be fully self-contained (all CSS/JS inline). Do NOT use terminal commands or scripts to save — `save_ppt` is the only delivery mechanism.

### Step 4.2: Confirm to User

Summarize — Tell the user:
   - style name, slide count
   - Inline editing: Hover top-left corner or press E to enter edit mode, click any text to edit, Ctrl+S to save

---

## Supporting Files

| File                                               | Purpose                                                              | When to Read              |
| -------------------------------------------------- | -------------------------------------------------------------------- | ------------------------- |
| [style-guide.md](references/style-guide.md)                   | CSS rules, anti-patterns, font pairing reference                     | Phase 3      |
| [viewport-base.css](assets/viewport-base.css)             | Mandatory responsive CSS — copy into every presentation              | Phase 3      |
| [html-template.md](references/html-template.md)               | HTML structure, JS features, code quality standards                  | Phase 3      |
| [animation-patterns.md](references/animation-patterns.md)     | CSS/JS animation snippets and effect-to-feeling guide                | Phase 3      |
| [chart-guide.md](references/chart-guide.md)                 | Chart selection, design rules, anti-patterns                         | Phase 3 (when outline has charts) |
| [chart-patterns.css](assets/chart-patterns.css)           | Reusable SVG chart CSS classes and keyframes                         | Phase 3 (when outline has charts) |
| [chart-templates.md](references/chart-templates.md)         | Copy-ready SVG chart skeletons                                       | Phase 3 (when outline has charts) |
