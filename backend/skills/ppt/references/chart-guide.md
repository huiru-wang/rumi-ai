# Chart Guide — Data Visualization for HTML Presentations

This guide governs how and when to include data visualizations in an HTML presentation.

All charts MUST be built with inline SVG and CSS only. No external charting libraries are allowed.

---

## 1. When to Use a Chart

Charts are not decorations. They are tools for revealing structure in data. Use a chart only when the source document contains quantifiable relationships that are harder to understand as text.

### 1.1 Automatic Chart Decision Matrix

During Phase 2 outline generation, inspect the source content for each slide. If a slide matches one of the patterns below, automatically recommend a chart in the "视觉建议" column.

| Content Pattern | Recommended Chart | Why |
|-----------------|-------------------|-----|
| Multiple values compared side-by-side, ranking | Bar, Lollipop, Radial Bar | Length is the easiest visual comparison |
| Values changing over time or sequence | Line, Area | Shows direction, rate, and trend |
| Parts of a whole, percentages, market share | Donut, Treemap, Waffle | Emphasizes proportion without misleading angles |
| Flow from one stage to another, conversions | Sankey, Flow Diagram | Preserves magnitude through stages |
| Multi-dimensional scores or capability ratings | Radar | Compares several attributes at once |
| A few KPIs with recent trend | Sparkline + Big Number | Compact, dashboard-like impact |
| Hierarchical breakdown or nested categories | Treemap, Sunburst, Icicle | Shows nested proportions |
| Geographic distribution or regional comparison | Symbol Map / Dot Map (only if regions are few) | Avoids complex map projections |

### 1.2 When NOT to Use a Chart

| Situation | Better Approach |
|-----------|-----------------|
| Only 1-2 isolated numbers | Large numeral + one-sentence insight |
| Pure concept comparison without numbers | Card grid, two-column comparison, or diagram |
| Data has too many categories (>12) | Aggregate into groups, or use a ranked table |
| Data dimensions exceed 3-4 | Split into multiple slides, each with one clear relationship |
| Source text has no concrete figures | Illustration, process diagram, or icon-based explanation |
| The chart would duplicate what a single sentence already says | Use the sentence |

### 1.3 Decision Heuristic

For each slide, ask:

1. Does the source material contain 3 or more related numbers?
2. Is the relationship among those numbers part of the story (bigger, faster, growing, share)?
3. Would a visual shape make the pattern obvious within 2 seconds?

If all three are true, use a chart. Otherwise, prefer text, numbers, or diagrams.

---

## 2. Chart Design Rules

### 2.1 Style Integration

Charts must look like they were designed for the current slide, not pasted from a spreadsheet.

- **Colors**: Derive every color from the theme CSS variables:
  - Primary data: `var(--accent)`
  - Secondary data: `var(--text-secondary)` or a transparent variant
  - Background fills: `var(--bg-secondary)` with low opacity
  - Text labels: `var(--text-primary)` / `var(--text-secondary)`
- **Typography**: Use the slide's body font for labels. Use the display font for big numbers inside donut centers.
- **Shapes**: Prefer rounded corners on bars, smooth curves on lines, and generous inner radius on donuts.
- **Texture**: Subtle gradients and opacity layering are allowed; drop shadows on chart elements are discouraged.

### 2.2 Data-Ink Ratio

Remove everything that does not carry information:

- No full chart borders
- No 3D effects, no exploded pie slices
- Gridlines, if present, must be extremely faint (`opacity: 0.1`-`0.2`)
- Axis ticks should be minimal or omitted when labels are self-evident
- Legends should be avoided when direct labeling is possible

### 2.3 Direct Labeling

Whenever possible, place values or category names directly on or next to the data mark instead of using a separate legend.

### 2.4 Viewport Budget

- A chart should occupy at most 60% of a slide's height.
- Every chart slide must include:
  - A clear slide title
  - The chart itself
  - 1-2 concise insights explaining what the chart shows
- Charts must never cause slide scrolling. If the chart is too complex, simplify the data or split into multiple slides.

---

## 3. Chart Types in Detail

### 3.1 Bar / Lollipop

Use for: ranking, comparing magnitudes

- Limit to 3-8 categories
- Use horizontal bars when labels are long
- Round bar ends for a refined look
- Sort bars by value unless the natural order is meaningful
- Lollipop reduces ink while preserving comparability

### 3.2 Line / Area

Use for: trends over time

- 2-6 series maximum
- Use area with gradient fill for single-series emphasis
- Highlight peaks, valleys, or inflection points with annotations
- Avoid jagged lines; prefer smooth curves unless precision is required

### 3.3 Donut

Use for: parts of a whole

- Limit to 2-6 slices
- Always show percentages or values directly on/near slices
- Use the center for the total or a key insight
- Never use 3D or exploded variants

### 3.4 Radar

Use for: multi-dimensional comparison

- 4-7 axes works best
- Keep scales identical across axes
- Compare at most 2-3 entities to avoid clutter
- Use filled polygons with low opacity

### 3.5 Sankey

Use for: flow between stages

- 3-5 stages recommended
- Label flows with values or percentages
- Keep node widths proportional to flow magnitude
- Use curved paths, not straight lines

### 3.6 Waffle / Isotype

Use for: intuitive percentages

- 10x10 grid = 100 units
- Use icons or filled cells
- Great for single percentages like market share or completion rate

---

## 4. Animation Rules

Charts must tell a story as the slide enters the viewport. Use CSS animations triggered by the slide's `.visible` class.

### 4.1 Animation Patterns

| Chart Type | Animation | CSS Approach |
|------------|-----------|--------------|
| Bar / Lollipop | Grow from baseline | `scaleY(0)` → `scaleY(1)`, `transform-origin: bottom` |
| Line / Area | Draw the line | `stroke-dasharray` + `stroke-dashoffset` |
| Donut | Expand slices | `stroke-dasharray` animated per slice |
| Radar | Expand web + fade data | Scale polygon from center, fade in |
| Sankey | Flow along path | `stroke-dashoffset` on flow paths |
| Counter | Number increments | JS requestAnimationFrame updating `textContent` |

### 4.2 Timing

- Total animation duration: 0.8s - 1.5s
- Stagger multiple elements by 80-150ms
- Use `cubic-bezier(0.16, 1, 0.3, 1)` (ease-out-expo) for growing elements
- Respect `prefers-reduced-motion`: disable animations when requested

### 4.3 Trigger

All chart animations must be triggered when the parent `.slide` receives the `.visible` class from the existing Intersection Observer. Do not use independent scroll triggers or autoplay.

---

## 5. Anti-Patterns

Avoid these generic or misleading chart choices:

- Default library styling (gray grid, blue bars, default tooltips)
- 3D pie or donut charts
- Exploded pie slices
- Dual Y-axes that distort comparison
- Truncated Y-axis that exaggerates differences
- Pie charts with more than 6 slices
- Decorative charts that do not clarify data
- Charts without titles or without any written insight

---

## 6. Inline Editing

Charts must remain editable in the browser.

- Make `text` and `tspan` elements inside SVG editable when edit mode is active
- Do NOT make shapes (`rect`, `path`, `circle`) contenteditable
- For simple charts, expose key data values as `data-value` attributes on text elements so users can see what to edit
- The overall SVG structure, scales, and paths should be regenerated by the agent; manual path editing by the user is not required

---

## 7. Implementation Checklist

Before calling `save_ppt`, verify every chart slide:

- [ ] Chart type matches the data relationship
- [ ] Colors come from theme CSS variables only
- [ ] No 3D effects, no default library styling
- [ ] Animation triggers on `.slide.visible`
- [ ] Chart height does not exceed 60% of slide
- [ ] Title and 1-2 insights are present
- [ ] Labels are directly readable without legend decoding
- [ ] Inline editing works for text labels and big numbers
- [ ] `prefers-reduced-motion` is respected
