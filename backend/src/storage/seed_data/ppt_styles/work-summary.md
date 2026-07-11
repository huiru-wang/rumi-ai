# 橙红渐变商务工作总结 PPT 风格模板

## 1. Vibe — 整体气质

现代、简洁、稳重、有企业汇报感。以浅灰白背景建立干净办公氛围，以橙红渐变几何块形成强识别度，通过左上角统一装饰、章节大色块、卡片化信息和流程图形保持整套 PPT 的连续性。

关键词：商务汇报 / 浅灰留白 / 橙红渐变 / 几何块面 / 轻阴影 / 清晰层级 / 稳定版式

核心原则：

- 内容优先，装饰只承担品牌识别和层级引导。
- 每页只设置一个主视觉中心。
- 橙红渐变用于强调，不大面积铺满普通内容页。
- 页面保持宽松，不把正文塞满画布。
- 遇到内容数量变化时，优先切换版式或拆页，而不是压缩字号。

## 2. Color System — 色彩系统

本风格固定使用“浅灰白 + 橙红渐变 + 深灰文字”的商务配色，不建议引入额外高饱和主色。

```css
:root {
  --bg-primary: #f2f2f2;
  --bg-soft: #f5f5f5;
  --surface: #ffffff;
  --text-primary: #3f3f3f;
  --text-secondary: #666666;
  --text-muted: #999999;
  --line-muted: #c9c9c9;
  --accent-orange: #fa8d27;
  --accent-red: #d83818;
  --accent-red-strong: #df2123;
}
```

### 渐变

主渐变用于圆角矩形、章节块、指标标签、流程节点和底部总结条。

```css
linear-gradient(135deg, #fa8d27 0%, #d83818 100%)
```

横向强调条可使用：

```css
linear-gradient(90deg, #fa8d27 0%, #df2123 100%)
```

### 使用比例

- 浅灰白背景：75%–85%
- 橙红渐变：10%–18%
- 深灰文字：5%–10%
- 图片、线条、辅助色：少量

不要使用蓝、绿、紫作为主要装饰色。若图表需要多色，只允许低饱和辅助色，并确保橙红仍是主强调色。

## 2.1 HTML-PPT Canvas Rules — HTML 实现画布规则

本模板用于 HTML-PPT 生成时，必须使用固定 16:9 逻辑画布。不要直接把页面内容铺满任意浏览器窗口。

推荐结构：

```html
<section class="slide">
  <div class="slide-frame">
    <!-- all visible content -->
  </div>
</section>
```

推荐 CSS：

```css
.slide {
  width: 100vw;
  height: 100vh;
  display: grid;
  place-items: center;
  overflow: hidden;
  background: #111;
}

.slide-frame {
  position: relative;
  width: min(100vw, calc(100vh * 16 / 9));
  aspect-ratio: 16 / 9;
  height: auto;
  overflow: hidden;
  background: var(--bg-primary);
}

@media (min-aspect-ratio: 16/9) {
  .slide-frame {
    width: auto;
    height: 100vh;
  }
}
```

实现约束：

- 所有可见元素都必须放在 `.slide-frame` 内。
- 所有绝对定位都相对 `.slide-frame`，不能相对浏览器 viewport。
- 不使用 `height: 100dvh` 作为内部布局基准。
- 不使用 `justify-content: center` 包裹整页内容页；内容页标题必须固定在顶部区域。
- 字号、间距、装饰块尺寸优先使用相对 `.slide-frame` 的百分比或稳定 token，不要混用大量 `vh` 和 `vw`。
- 如果需要滚动演示，可滚动的是外层 `.slide`，不是内部画布。

## 3. Typography — 字体系统

| 用途 | 中文字体 | 西文字体 | 字重 | 推荐尺寸 |
|---|---|---|---|---|
| 封面主标题 | 思源黑体 / 微软雅黑 / 等线 | Arial / Helvetica | 500–700 | 52–76px |
| 章节大标题 | 思源黑体 / 微软雅黑 / 等线 | Arial / Helvetica | 500–700 | 72–96px |
| 内容页标题 | 思源黑体 / 微软雅黑 / 等线 | Arial / Helvetica | 500–700 | 34–46px |
| 模块标题 | 思源黑体 / 微软雅黑 | Arial | 500–700 | 20–28px |
| 正文说明 | 思源黑体 / 微软雅黑 | Arial | 400 | 14–18px |
| 英文装饰 | Arial / Helvetica | Arial / Helvetica | 400–600 | 10–18px |
| 数据数字 | Arial / Helvetica | Arial / Helvetica | 600–700 | 34–72px |

文字颜色：

- 主标题：`--text-primary`
- 正文：`--text-secondary`
- 弱说明：`--text-muted`
- 橙红块中文字：`#ffffff`

排版规则：

- 标题不使用过度字距；保持商务清晰感。
- 内容页标题尽量一行，最长不超过两行。
- 正文行高 1.45–1.7。
- 色块内标题不超过 12 个中文字符；超过时换成外置标题。

## 4. Layout Grammar — 布局语法

PPT 规划时先识别页面类型：`cover -> agenda -> section -> content -> closing`，再从对应 `variants` 中选择版式。禁止创建未定义的页面类型。普通内容页必须从 `content.*` 中选择。

```yaml
page_layouts:
  cover:
    enabled: true
    display_name: 封面页
    variants:
      - id: cover.business_geometry
        name: 商务几何封面
        best_for: 工作总结、年度汇报、项目汇报开场
        structure: 左侧/左上几何块群 + 右中主标题 + 副标题/说明 + 汇报人信息 + 底部小字
        capacity: 1 个主标题、1 个副标题或说明、1 行汇报人/日期信息

  agenda:
    enabled: true
    display_name: 目录页
    variants:
      - id: agenda.vertical_sections
        name: 纵向章节目录
        best_for: 3-5 个章节的标准工作汇报
        structure: 左侧几何装饰和目录块 + 右侧纵向编号章节列表
        capacity: 3-5 个章节，每个章节 1 个标题 + 1 行短说明
      - id: agenda.grid_sections
        name: 双列章节目录
        best_for: 6-8 个章节或主题入口
        structure: 左侧目录标识 + 右侧 2 列编号章节卡片
        capacity: 6-8 个章节，每个章节 1 个短标题

  section:
    enabled: true
    display_name: 章节页
    variants:
      - id: section.part_geometry
        name: PART 几何章节页
        best_for: 汇报分章、阶段切换、内容转场
        structure: 左侧橙红 PART 编号块 + 右侧超大章节标题 + 简短说明 + 底部几何背景
        capacity: 1 个章节标题、1 个 PART 编号、1 段 1-2 行说明

  content:
    enabled: true
    display_name: 内容页
    variants:
      - id: content.point_matrix
        name: 多观点矩阵
        best_for: 工作总结、问题归纳、措施拆解、多观点并列
        structure: 页眉标题 + 2x2 / 3x2 观点块 + 可选中心主题或淡灰圆形辅助线
        capacity: 2-6 个观点，每个观点 1 个短标题 + 1 段 30-60 字说明

      - id: content.metric_image
        name: 图文指标页
        best_for: 成果展示、KPI、百分比、关键数据说明
        structure: 页眉标题 + 左侧/下方图片 + 右侧 3-4 个指标卡
        capacity: 1 张图片、3-4 个指标，每个指标 1 个数字 + 1 个标题 + 1 行说明

      - id: content.metric_banner
        name: 横幅数据页
        best_for: 3 个核心数据、阶段成果、关键数字总览
        structure: 顶部标题 + 左/中大面积橙红横幅 + 3 个数据列 + 辅助图片或说明
        capacity: 3 个核心数字、1 张辅助图片、1 个补充结论

      - id: content.timeline
        name: 时间轴阶段页
        best_for: 年度计划、项目里程碑、阶段成果、路线图
        structure: 页眉标题 + 横向时间轴/梯形条 + 节点卡片 + 阶段说明
        capacity: 3-5 个阶段，每阶段 1 个时间点 + 1 个标题 + 1 行说明

      - id: content.comparison
        name: 左右对比页
        best_for: 问题与措施、现状与目标、前后对比、方案权衡
        structure: 页眉标题 + 左右对称橙红箭头/色块 + 中央主题或年份
        capacity: 2 个对比对象，每侧 1 个标题 + 2-4 条要点

      - id: content.table_cards
        name: 表格卡片页
        best_for: 项目清单、问题清单、成果列表、计划列表
        structure: 页眉标题 + 3 列或 3x2 白色卡片表格 + 底部橙红总结条
        capacity: 3-6 张卡片，每张 3-5 行短数据

      - id: content.process_steps
        name: 流程步骤页
        best_for: 下一步计划、执行路径、行动方案、工作流程
        structure: 页眉标题 + 横向流程/环形流程/错位步骤块 + 步骤说明
        capacity: 3-6 个步骤，每步 1 个编号 + 1 个标题 + 1 段 20-40 字说明

      - id: content.summary_text
        name: 重点说明页
        best_for: 单一结论、较长说明、综合分析
        structure: 页眉标题 + 左侧重点色块/数字 + 右侧正文分组
        capacity: 1 个核心结论、3-5 条说明或 1 段 120 字以内正文

  closing:
    enabled: true
    display_name: 结束页
    variants:
      - id: closing.business_geometry_end
        name: 商务几何结束页
        best_for: 感谢观看、汇报收束、结束语
        structure: 左侧/左上几何块群 + 右中结束标题 + 汇报人信息 + 底部小字
        capacity: 1 个结束标题、1 行说明、1 行汇报人/日期信息
```

## 5. Page Type Rules — 页面类型规则

### Cover / 封面页

固定使用 `cover.business_geometry`。

结构：

- 左侧和左上区域使用大面积橙红、白色、灰色几何块叠加。
- 主标题位于画面右中部，是第一视觉中心。
- 主标题上方可放一个很大的半透明英文装饰词，如 `BUSINESS`，透明度 8%–15%。
- 主标题下方放简短说明文字。
- 汇报人信息放在小描边按钮或细线框内。
- 底部可放小号系列说明文字。

限制：

- 不放目录、长列表、复杂图表。
- 主标题最多两行。
- 装饰块可以出血到画布外，但不能遮挡标题。

### Agenda / 目录页

优先使用 `agenda.vertical_sections`。

选择规则：

- 3-5 个章节：使用 `agenda.vertical_sections`。
- 6-8 个章节：使用 `agenda.grid_sections`。
- 超过 8 个章节：合并章节或拆为“上篇/下篇”，不要在一页中堆满。

结构：

- 左侧保留封面风格几何装饰。
- 左下或左中放橙色目录块，写 `目录 / CONTENTS`。
- 右侧为编号章节列表。
- 编号使用圆形或细线圆，标题使用深灰。

HTML 坐标规则：

- 目录页使用固定两区布局，不允许仅用 `align-items: center` 自动居中。
- 左侧目录标识区占画布宽度 30%–38%，右侧列表区占 52%–60%。
- 3 个目录项时，纵向锚点固定在 30%、50%、70%。
- 4 个目录项时，纵向锚点固定在 24%、40%、56%、72%。
- 5 个目录项时，纵向锚点固定在 20%、35%、50%、65%、80%。
- 6-8 个目录项必须切换到 `agenda.grid_sections`，不要继续纵向拉长。
- 目录项说明文字可省略，但不能因为说明少而让列表整体只占中间一小块。

### Section / 章节页

章节页固定使用 `section.part_geometry`。

使用条件：

- Deck 有 2 个以上清晰内容组。
- 每个章节后至少跟随 2 页内容页。
- 如果某一级主题使用章节页，同级主题必须都使用章节页。

避免使用：

- 总页数很短，只有一个连续主题。
- 某个章节后只有 1 页内容。

结构：

- 左侧橙红渐变大圆角矩形显示 `PART 01`。
- 右侧超大中文章节标题。
- 标题下方放 1-2 行说明。
- 背景底部和边缘使用橙色、白色、灰色块面叠加。

### Content / 内容页

所有内容页必须包含：

- 左上角统一几何页眉装饰。
- 页眉标题，位置在左上装饰右侧。
- 浅灰白背景。
- 一个主要内容区。

HTML 坐标规则：

- 内容页标题区固定在画布顶部 5%–13% 范围内。
- 主内容区固定在画布顶部 18% 到底部 88% 范围内。
- `.page-header` 不参与主体内容垂直居中。
- `.page-header` 建议绝对定位或独立 grid row，不要作为 flex 内容和主体一起 `justify-content: center`。
- 主体内容可居中，但只能在主内容区内部居中。

左上角装饰组件：

- 2-3 个叠放圆角矩形。
- 包含橙红渐变块、白色或浅灰块。
- 可部分超出画布边缘。
- 带轻阴影。
- 可放一个简单白色线性图标或符号。

左上角装饰 HTML 实现必须使用固定组件，不允许每页重新自由生成：

```html
<div class="corner-deco" aria-hidden="true">
  <div class="corner-block corner-block-orange"></div>
  <div class="corner-block corner-block-light"></div>
  <div class="corner-block corner-block-dot"></div>
</div>
```

推荐坐标：

```css
.corner-deco {
  position: absolute;
  left: 0;
  top: 0;
  width: 13%;
  height: 15%;
  pointer-events: none;
  z-index: 1;
}

.corner-block-orange {
  position: absolute;
  left: -1.5%;
  top: -1.5%;
  width: 8%;
  height: 10%;
  border-radius: 10px;
  background: var(--gradient-main);
  box-shadow: 0 6px 16px rgba(0, 0, 0, 0.12);
}

.corner-block-light {
  position: absolute;
  left: 2.2%;
  top: 1.8%;
  width: 6%;
  height: 5%;
  border-radius: 8px;
  background: var(--surface);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08);
}

.corner-block-dot {
  position: absolute;
  left: 5.8%;
  top: 6.5%;
  width: 2.2%;
  aspect-ratio: 1;
  border-radius: 50%;
  background: var(--accent-orange);
}
```

限制：

- 普通内容页左上角装饰最多 3 个图形。
- 普通内容页装饰块旋转角度为 0 度；不要随机旋转。
- 装饰块不得进入标题文字区域。
- 内容页不允许额外添加大面积背景几何块，除非该 variant 明确要求。

### Closing / 结束页

固定使用 `closing.business_geometry_end`。

结构：

- 与封面保持同源几何装饰。
- 右中部放大标题，如“感谢观看”。
- 可放半透明英文装饰词 `BUSINESS`。
- 下方放汇报人、日期或公司信息。

限制：

- 不放复杂内容。
- 不放二维码、广告、水印，除非用户明确要求。

## 6. Variant Selection Rules — 内容页版式选择规则

根据内容语义选择版式：

| 内容类型 | 首选版式 | 备选版式 |
|---|---|---|
| 2-6 个观点 / 问题 / 措施 | `content.point_matrix` | `content.summary_text` |
| 关键数据 + 图片 | `content.metric_image` | `content.metric_banner` |
| 3 个核心数据总览 | `content.metric_banner` | `content.metric_image` |
| 阶段、年份、路线图 | `content.timeline` | `content.process_steps` |
| 前后、左右、优劣对比 | `content.comparison` | `content.table_cards` |
| 项目清单、表格、列表 | `content.table_cards` | `content.summary_text` |
| 执行步骤、计划路径 | `content.process_steps` | `content.timeline` |
| 单一重点结论或长说明 | `content.summary_text` | `content.point_matrix` |

禁止规则：

- 不要把 7 个以上观点硬塞进 `content.point_matrix`。
- 不要把长正文放进橙红色块。
- 不要在同一页同时使用时间轴、表格、图片和多观点矩阵。
- 不要为了凑版式添加无意义英文装饰词。

## 7. Capacity & Overflow — 容量和拆页规则

### 通用容量

- 一页最多承载 1 个主标题、1 个主视觉结构、6 个信息单元。
- 普通正文总量建议不超过 180 个中文字符。
- 色块内正文不超过 40 个中文字符。
- 数据卡片单张不超过 1 个数字、1 个标题、1 行说明。

### 超载处理

当内容超出容量时，按以下顺序处理：

1. 合并相近观点。
2. 将长句改为短标题 + 简短说明。
3. 从矩阵版切换到表格卡片版。
4. 拆成两页，保持同一版式连续。
5. 增加章节页或小结页，而不是缩小字号。

### 数量适配

观点数量：

- 2 个：左右对称。
- 3 个：三列或上二下一。
- 4 个：2 x 2。
- 5 个：中心重点 + 四周辅助，或上二中一下二。
- 6 个：2 x 3。
- 7 个以上：拆页或改为表格卡片。

阶段数量：

- 3 个：横向三段。
- 4-5 个：横向时间轴。
- 6 个：上下两行错位流程。
- 7 个以上：拆页。

表格卡片数量：

- 1-3 张：横向等分。
- 4-6 张：3 x 2。
- 超过 6 张：拆页。

## 8. Visual Components — 视觉组件

### 几何块

常用元素：

- 圆角矩形
- 矩形
- 圆形
- 菱形
- 梯形
- 半透明叠层

组件规则：

- 圆角半径 8-18px。
- 大装饰块可带 10%-25% 透明叠层。
- 阴影柔和，不使用硬边黑影。
- HTML 实现时，几何块必须来自预定义组件或当前 variant 的明确结构，不允许为了“更有设计感”自由添加额外旋转块。
- 普通内容页所有装饰几何面积总和不超过画布面积 12%；封面、章节页、结束页不超过 35%。
- 除封面、章节页、结束页外，不使用超过 15 度的旋转几何块。
- 同一页几何装饰的 z-index 必须低于正文内容，不能遮挡文字。

```css
box-shadow: 0 12px 28px rgba(0, 0, 0, 0.18);
```

小卡片阴影：

```css
box-shadow: 0 6px 16px rgba(0, 0, 0, 0.10);
```

### 图片

- 图片仅作为辅助内容，不压过橙红主视觉。
- 推荐商务办公、会议、数据分析、团队协作主题。
- 图片使用矩形裁切，比例优先 16:10、4:3 或横向长图。
- 可叠加橙红半透明遮罩，透明度不超过 20%。
- 图片页仍保留左上角页眉装饰。

### 图标

- 图标使用简单线性白色图标。
- 图标通常放在橙红渐变块内。
- 图标只辅助识别，不作为主视觉。
- 不使用彩色扁平插画图标或复杂 3D 图标。

## 9. Consistency Policy — 一致性策略

整套 PPT 必须保持：

- 同一套背景色、橙红渐变、标题颜色。
- 内容页统一左上角页眉装饰。
- 同级章节页使用同一种 `section.part_geometry`。
- 同类内容尽量使用同一版式。例如所有“问题分析”页都用 `content.point_matrix` 或 `content.table_cards`，不要频繁切换。
- 页眉标题位置、字号、颜色保持一致。
- 图片裁切风格保持一致。

节奏建议：

- 封面和结束页互相呼应。
- 章节页使用大装饰、强视觉。
- 内容页降低装饰密度，突出信息。
- 每 3-5 页内容后可用章节页或总结页调整节奏。

## 10. Anti-patterns — 禁止事项

不要复用以下来源模板元素：

- 下载站网址
- `第一PPT`
- `包图网`
- 素材授权页
- 模板来源说明页
- 原模板占位英文长句
- 与实际内容无关的 `PPT 模板` 字样

不要出现以下排版问题：

- 大段正文塞进橙红渐变块。
- 一页超过 6 个并列信息单元。
- 多种复杂结构叠加在同一页。
- 缩小字号来容纳过量内容。
- 标题被装饰图形遮挡。
- 橙红色块面积超过普通内容页 25%。
- 每页都使用大面积背景装饰，导致内容页过重。
- HTML slide 直接使用 `100vw/100vh` 作为内容坐标系，导致非 16:9 窗口下布局漂移。
- 内容页 `.slide-content` 使用 `justify-content: center`，导致页眉标题和主体一起垂直漂移。
- 几何装饰使用大量 `absolute + rotate + vw/vh` 自由摆放。
- 目录页 3 个章节仍使用居中 flex 布局，造成上下大面积空白。
- 每页重新定义不同的装饰块坐标，而不是复用同一组件。

## 11. Recommended Deck Structure — 推荐整套结构

标准工作总结：

1. `cover.business_geometry`：封面
2. `agenda.vertical_sections`：目录
3. `section.part_geometry`：工作汇报总结
4. `content.point_matrix` / `content.summary_text`：总结内容
5. `section.part_geometry`：取得成果展示
6. `content.metric_image` / `content.metric_banner`：成果数据
7. `section.part_geometry`：问题不足分析
8. `content.point_matrix` / `content.table_cards`：问题分析
9. `section.part_geometry`：下步工作计划
10. `content.timeline` / `content.process_steps`：计划路径
11. `closing.business_geometry_end`：结束页

简短汇报：

1. 封面
2. 目录，可选
3. 3-5 页内容页
4. 结束页

总页数少于 6 页时，可以不使用章节页。

## 12. Generation Checklist — 生成检查清单

生成前：

- 是否识别了页面类型？
- 是否为每个内容页选择了合法 `variant id`？
- 是否检查了每页容量？
- 是否需要章节页，且同级章节是否一致？
- HTML-PPT 是否使用固定 16:9 `.slide-frame` 作为内部坐标系？
- 内容页页眉是否固定在顶部，而不是参与主体垂直居中？
- 几何装饰是否来自预定义组件，而不是逐页自由生成？

生成后：

- 标题是否保持统一位置和字号？
- 内容页是否都有左上角装饰？
- 橙红渐变是否只用于强调？
- 是否有水印、模板站信息或无关占位文本？
- 是否有内容拥挤、文字过小、图形遮挡？
- 是否有超过容量但未拆页的页面？
- 在 16:9、宽屏、窄屏三种浏览器窗口下截图，几何装饰是否仍然稳定？
- 目录页 3/4/5 项是否按固定纵向锚点分布，没有异常留白？
- 内容页标题、主内容区、装饰块是否互不重叠？

## 13. HTML-PPT Implementation Contract — HTML-PPT 实现契约

后续用本模板生成 HTML PPT 时，必须遵守以下契约。该契约优先级高于自由审美发挥。

### 13.1 固定画布

- 每页必须有 `.slide-frame`。
- `.slide-frame` 必须保持 16:9。
- 所有定位和尺寸都以 `.slide-frame` 为参照。
- 不允许使用浏览器窗口高度直接决定页面内部布局。

### 13.2 固定页面骨架

内容页推荐骨架：

```html
<section class="slide">
  <div class="slide-frame content-frame">
    <div class="corner-deco" aria-hidden="true">...</div>
    <header class="page-header">
      <div class="page-tag">01 · 标签</div>
      <h2>页面标题</h2>
    </header>
    <main class="page-main variant-point-matrix">
      <!-- variant content -->
    </main>
  </div>
</section>
```

推荐 CSS：

```css
.content-frame {
  position: relative;
  background: var(--bg-primary);
}

.page-header {
  position: absolute;
  left: 9%;
  right: 7%;
  top: 6%;
  height: 10%;
  z-index: 3;
}

.page-main {
  position: absolute;
  left: 7%;
  right: 7%;
  top: 19%;
  bottom: 9%;
  z-index: 2;
}
```

### 13.3 固定装饰策略

- 封面、章节页、结束页可以使用较大几何块，但必须锚定在固定边角或底部区域。
- 内容页只使用左上角装饰组件，不添加额外背景装饰。
- 普通内容页不使用随机旋转、随机透明度、随机偏移。
- 装饰块不能承担正文容器职责，正文优先放在白色卡片、表格、说明区或主内容区。

### 13.4 固定目录策略

目录页不要让列表自然居中后留下大空白。必须按章节数量使用明确布局：

```text
3 项：纵向锚点 30% / 50% / 70%
4 项：纵向锚点 24% / 40% / 56% / 72%
5 项：纵向锚点 20% / 35% / 50% / 65% / 80%
6-8 项：切换 2 列网格
```

### 13.5 验证要求

生成 HTML 后至少检查：

- 16:9 桌面视口：1600 x 900。
- 宽屏视口：1920 x 900。
- 较窄视口：1200 x 900。

三个视口下都必须满足：

- `.slide-frame` 保持 16:9。
- 几何装饰不漂移、不遮挡标题。
- 内容页标题固定在顶部。
- 目录页无异常留白。
- 文本没有溢出卡片或互相重叠。
