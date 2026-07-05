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

### Layout Balance Rule

Viewport fitting means the slide fits cleanly, not that every content block must expand to fill the slide.

For normal content slides, keep visible breathing room around the main content. Avoid stretching cards, columns, or bullet containers to fill all remaining vertical space unless the slide is intentionally designed as a full-bleed poster, KPI page, chart, or immersive visual layout.

When using cards or columns, prefer content-sized blocks with balanced spacing. If the slide starts to look like stacked blocks from top to bottom, reduce text, split the slide, or vary the layout.

Decorative headers, footers, tags, and bottom notes must never overlap the main content. On dense slides, remove non-essential decorative text or bottom notes before shrinking content into an unreadable layout.

### Content-Driven Layout Choice

Let the content shape choose the layout. Cards work well for categories, comparisons, and independent points; diagrams, flows, timelines, maps, or state branches often explain mechanisms, processes, relationships, dependencies, and lifecycle changes better.

Match visual weight to information density. A large visual block should carry enough structure, insight, or hierarchy to justify its size. If a point is short, use a smaller module, inline annotation, or combine it into a richer visual structure.

Technical slides should add explanatory value beyond definitions. Prefer including one or two of: mechanism, boundary condition, cause/effect, concrete example, contrast, common pitfall, or decision rule.

Avoid repeating the same meaning across decorative tags, headings, and card titles. Each visible element should either orient, explain, compare, or emphasize.

These are judgment guidelines, not fixed templates. Use large cards, grids, bars, or minimal layouts when the content genuinely benefits from them.

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
- Type: `select`, `allow_custom: true`
- Options: Dynamically generate 4–6 purpose options from the user's message, selected topic, and knowledge-base document summaries. Options should be concrete presentation scenarios, not generic labels.
- If the user's message clearly states a purpose, include that purpose as an option and set `recommended: ["<user's purpose>"]`.
- If the user did not provide a purpose, infer the most likely purpose from the topic and document content, then set it as the single recommended option.
- Prefer domain-specific options over the old generic defaults. Examples:
  - Product/business content → `客户提案`, `产品介绍`, `售前演示`, `市场宣讲`, `投资人路演`
  - Technical/API/architecture/spec content → `技术培训`, `方案评审`, `团队内部宣贯`, `实施落地说明`, `技术分享`
  - Project/progress/metrics content → `项目汇报`, `管理层汇报`, `阶段复盘`, `计划评审`
  - Process/SOP/manual content → `操作培训`, `流程宣贯`, `制度解读`, `新员工培训`
  - Research/analysis/report content → `研究汇报`, `洞察分享`, `决策建议`, `专题研讨`
- Only use generic fallbacks such as `产品路演`, `教学培训`, `会议演讲`, `内部汇报` when the available context is too thin to infer a more specific scenario.
- **Never add placeholder options like "其他" or "自定义用途" to the `options` array** — the custom input field (rendered automatically when `allow_custom=true`) already handles free-text input.

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

**Question 5 — Content Density（内容密度）** (header: "Density")
- Type: `select`
- Options:
  - `轻量：少文字、多留白、适合演讲展示`
  - `标准：图文平衡、适合汇报讲解`
  - `高密度：信息完整、适合培训/复盘/资料留存`
- If the user explicitly asks for a concise, visual, spacious, or keynote-style deck, set `recommended` to `轻量：少文字、多留白、适合演讲展示`.
- If the user explicitly asks for a detailed training deck, manual, review document, or leave-behind material, set `recommended` to `高密度：信息完整、适合培训/复盘/资料留存`.
- Otherwise set `recommended` to `标准：图文平衡、适合汇报讲解`.

Content density affects planning and layout:

| Density | Per-slide content | Layout implication |
|---------|-------------------|--------------------|
| 轻量 | 1 main idea + 2-3 short points | Larger visuals, more whitespace, fewer cards |
| 标准 | 1 main idea + 3-5 points | Balanced text, diagrams, images, and charts |
| 高密度 | 1 topic + 4-6 points, steps, or examples | Prefer split slides, tables, flows, and structured modules |

Density never overrides viewport fitting. If content does not fit cleanly, split slides instead of shrinking or scrolling.

**When no documents are available and the user has not provided a topic**, the Topic question's custom input is required. Do not proceed with generation until the user provides a concrete topic, outline, or source content.

### Form Cancellation

If the user cancels the form (the tool returns `cancelled: true`), **immediately stop the entire PPT generation flow**. Do not proceed to Phase 2 or any subsequent step. Politely acknowledge the cancellation and wait for the user's next instruction.

### Default capability — Inline Editing
Do not ask whether inline editing is needed. Generated HTML presentations must support editing text directly in the browser by default, including edit mode, localStorage auto-save, and export/save functionality.

Only disable inline editing when the user explicitly asks for a presentation-only file, a smaller file, or no editing controls.

---

## Phase 1.5: Full Content & Asset Gathering

Before you generate the outline, collect the full content and visual materials needed for the whole presentation.

The goal is to collect enough material for the whole presentation, not to perform a later per-slide verification pass. Use the selected topic, purpose, length, content density, and source documents to decide what to retrieve and how deeply to retrieve it.

When source documents are selected:

- Use `rag_search` to gather the content needed to support the full deck before writing the outline.
- If the user selected specific documents, use the corresponding `doc_id` when searching those documents.
- Do not prescribe a fixed number of `rag_search` calls. Retrieval depth depends on document count, topic complexity, expected length, and content density.
- Higher density requires more complete facts, examples, steps, tables, and edge cases; lighter density requires stronger synthesis and fewer points.
- Prefer document-grounded content over general model knowledge. Do not invent professional facts, data, laws, or case examples that are not in the selected sources or directly provided by the user.

Collect material across these categories:

- Core definitions, background, conclusions, and key arguments
- Facts, metrics, percentages, dates, timelines, and comparisons
- Cases, workflows, procedures, risks, tradeoffs, and before/after states
- Tables, charts, diagrams, screenshots, document images, and other visual assets
- Source locations that explain where each important fact or asset came from

When no source documents are selected or available, base the deck only on the user's provided topic, outline, or source text. If the user has not provided enough content for a reliable deck, ask for more material before continuing.

### Content & Asset Inventory

Internally organize the gathered material before drafting the outline. You may summarize this inventory in the outline when it helps the user understand scope, but do not turn it into a separate user confirmation gate.

Use this structure:

| Type | Source | Available material | Best use |
|------|--------|--------------------|----------|
| text | Document/page/section or user input | Key fact, conclusion, example, or process | Slide topic or supporting point |
| table | Document/page/section | Important rows, columns, values, or categories | Simplified table, comparison, or chart |
| chart | Document/page/section | Existing chart or chartable numbers | Recreate as inline SVG chart |
| image | Document/page/section | Image Markdown/URL, screenshot, diagram, or photo | Use directly if relevant, otherwise create `.img-slot` placeholder |

Image and chart rules:

- Prefer relevant document images, screenshots, and diagrams over generic placeholders.
- Use a document image only when it directly supports the slide's message.
- If no suitable image exists, use the standard `.img-slot[data-img-slot]` placeholder with a clear description.
- If a table or numeric text can be understood faster as a chart, plan an inline SVG chart using the chart rules.
- Never copy citation markers, source headers, or `来源索引` text into the final HTML.

---

## Phase 2: Outline Confirmation

Before generating the final HTML presentation, create a text-only Markdown outline and ask the user to confirm it.

**Hard gate:** Do not generate the full HTML presentation and do not call `save_ppt` until the user explicitly confirms the outline.

The outline must be based on the material gathered in Phase 1.5. Do not draft the outline only from document summaries when ready source documents exist.

Use the selected source documents as the generation scope:

- "All documents" means synthesize across all available knowledge-base documents
- Specific document selections mean use gathered material from only those selected documents
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

内容密度：...

视觉风格：...

内容来源：...

### 幻灯片结构

| # | 标题 | 核心内容 | 关键词 | 内容密度 | 可用素材 | 视觉建议 | 依据/来源 |
|---|------|----------|--------|----------|----------|----------|-----------|
| 1 | ... | ... | 关键词1,关键词2,关键词3 | 轻量/标准/高密度 | 图片/图表/表格/案例/无 | ... | ... |
| 2 | ... | ... | 关键词1,关键词2,关键词3 | 轻量/标准/高密度 | 图片/图表/表格/案例/无 | ... | ... |

### 内容取舍说明

- 会重点展开：...
- 会简略处理：...
- 暂不纳入：...
- 素材不足或需用户补充：...

### 请确认

如果这个大纲方向没问题，请回复“确认”。
如果需要调整，请直接说明希望修改的部分，例如：增加/删除章节、调整页数、更换顺序、加强案例、加强代码、加强图解或总结。
```

#### Keywords 生成规则（重要）

`keywords` are preserved in the structured outline for later narration generation, follow-up retrieval, and user-facing traceability. Generate them from the material gathered in Phase 1.5 and follow these rules:

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

Keep the outline concise but concrete enough for the user to judge scope, order, emphasis, density, and visual material usage.

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

## Phase 2.5: Slide Design Briefs

After the user explicitly confirms the outline, create internal slide design briefs before writing HTML.

These briefs translate the confirmed outline and Phase 1.5 material inventory into page-level layout decisions. Do not add another user confirmation gate unless the briefs change the major structure, page count, or section order that the user already approved.

Use this structure:

| # | Slide Goal | Material Used | Layout | Image/Chart Handling | Density Handling |
|---|------------|---------------|--------|----------------------|------------------|
| 1 | What the audience should remember | Facts/assets from gathered inventory | Cover / split / flow / comparison / chart / case | Use document image / recreate chart / image slot / none | How selected density is applied |

Brief rules:

- Each slide must have one clear communication goal.
- Map gathered facts, cases, tables, images, or charts to the slide where they are most useful.
- Choose layouts from the content shape: process, comparison, timeline, chart, case, table, diagram, or sparse keynote slide.
- Make image/chart decisions before HTML generation.
- Use density to decide whether to simplify, split, or structure content; never use density as a reason to cram content.

Do not perform a per-slide RAG verification pass after briefs are written. If you discover that the confirmed outline lacks enough gathered material for a slide, adapt the slide using the existing gathered material or explain the gap before generation if it changes the user's approved scope.

---

## Phase 3: Build Final Presentation

Generate the final presentation using the last outline explicitly confirmed by the user.

The final presentation must follow the confirmed outline and the slide design briefs. You may split an overloaded slide into multiple slides for viewport fitting, but do not add or remove major sections without asking the user to confirm an updated outline.

Use only:

- The user's explicit instructions and provided source content
- The material gathered during Phase 1.5
- The confirmed outline
- The slide design briefs
- The current style template

Do not perform a per-slide RAG verification pass in this phase. Do not add a separate second-pass quality-check phase. Generate directly from the gathered material, confirmed outline, and briefs.

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
- **Image containers MUST use the standard Image Slot System**: use `.img-slot` class + `data-img-slot` attribute + `data-ratio` attribute for all image placeholder areas. Never invent custom class names (e.g. `.visual-placeholder`, `.img-grid-figure`). For image grids, wrap items in `.img-slot-grid[data-columns="N"]`. Include the Image Upload Module JS and CSS from `html-template.md` when inline editing is enabled. Add `<input type="file" id="imgUploader" accept="image/*" style="display:none" />` at the start of `<body>`.
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
  "density": "standard",
  "total_slides": 12,
  "style": "swiss-modern",
  "material_inventory_summary": "本次PPT使用的主要事实、数据、图片、图表、表格或案例素材摘要",
  "slides": [
    {
      "number": 1,
      "title": "幻灯片标题",
      "key_points": ["要点1", "要点2"],
      "keywords": ["关键词1", "关键词2", "关键词3"],
      "density": "standard",
      "source_refs": ["doc_id:xxx"],
      "asset_refs": [
        {
          "type": "image",
          "source": "文档名 p.12",
          "usage": "作为案例截图"
        }
      ],
      "design_brief": {
        "goal": "本页要让观众记住的核心信息",
        "layout": "分栏/流程/对比/图表/案例/封面等",
        "image_or_chart": "document-image / svg-chart / image-slot / none",
        "density_handling": "轻量/标准/高密度在本页的处理方式"
      },
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

Summarize in a structured way:

- PPT title
- Style name
- Slide count
- Content density
- Content sources used
- Main structure or sections
- Materials used: document images, recreated charts, tables, cases, or image placeholders
- Inline editing: Hover top-left corner or press E to enter edit mode, click any text to edit, click image slots to upload/replace images, Ctrl+S to save

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
