# Style Guide — Cross-Style Universal Rules

These rules apply to **every** presentation regardless of the selected visual style.

---

## Viewport Base CSS

For mandatory base styles, see [viewport-base.css](../assets/viewport-base.css). Include its full contents in every presentation's `<style>` block.

---

## Image Implementation Rules

- **Content images** (screenshots, logos, inline visuals) must use the `.slide-image` class. They are constrained by `max-height: min(50vh, 400px)` from `viewport-base.css`.
- **Full-bleed slide backgrounds** must use `.bg-image` with `background-image` on a `<div>`. Never implement them as `<img>`, or the `viewport-base.css` image constraint will truncate them to the top half.

---

## Image Container Convention (Mandatory)

All image placeholder areas in generated HTML presentations **must** follow this standard structure. This ensures the editing system can reliably detect and enable image upload on any image slot, regardless of the visual style.

### Required Class & Attributes

| Element | Class | Required Attribute | Purpose |
|---------|-------|-------------------|---------|
| Single image slot | `.img-slot` | `data-img-slot`, `data-ratio` | Editable image placeholder |
| Grid container | `.img-slot-grid` | `data-columns` | Multi-image grid wrapper |
| Grid item caption | `.img-slot-caption` | — | Caption below image |
| Full-bleed background | `.bg-image` | — | CSS background-image |

### Supported Ratios

`data-ratio` accepts: `16:10`, `4:3`, `3:4`, `1:1`, `auto`

### Standard HTML Structures

**Type A — Single image in a split/mixed layout:**

```html
<div class="img-slot" data-img-slot data-ratio="16:10">[描述文字]</div>
```

**Type B — Image grid (3 columns):**

```html
<div class="img-slot-grid" data-columns="3">
  <figure>
    <div class="img-slot" data-img-slot data-ratio="4:3">[图片描述]</div>
    <figcaption class="img-slot-caption">说明文字</figcaption>
  </figure>
  <!-- more figures... -->
</div>
```

### Style Customization via CSS Variables

Styles **must not** override `.img-slot` structural properties directly. Instead, override these variables in `:root`:

| Variable | Default | What it controls |
|----------|---------|------------------|
| `--img-slot-radius` | `0` | Border radius |
| `--img-slot-border` | `1px solid rgba(128,128,128,0.2)` | Border |
| `--img-slot-bg` | `rgba(128,128,128,0.05)` | Empty-state background |
| `--img-slot-caption-font` | `var(--font-mono)` | Caption font |
| `--img-slot-caption-size` | `var(--small-size)` | Caption size |

### Prohibited

- ❌ Custom class names for image placeholders (e.g. `.visual-placeholder`, `.img-grid-figure`)
- ❌ Defining image containers without `data-img-slot` attribute
- ❌ Using `<img>` tags for empty placeholders (only use when actual image data is loaded)
- ❌ Overriding `.img-slot` structural CSS (aspect-ratio, max-height, display) in style-specific rules

---

## Image Implementation Rules

- **Content images** (screenshots, logos, inline visuals) must use the `.slide-image` class. They are constrained by `max-height: min(50vh, 400px)` from `viewport-base.css`.
- **Full-bleed slide backgrounds** must use `.bg-image` with `background-image` on a `<div>`. Never implement them as `<img>`, or the `viewport-base.css` image constraint will truncate them to the top half.

## Layout Anti-Pattern

Avoid content slides that read as a wall of oversized blocks. A common cause is combining full-height flex containers with stretched cards or columns.

Use full-height blocks only when they are part of the intended visual concept, such as a poster slide, KPI slide, comparison hero, chart, or full-slide diagram. Otherwise, let cards size to their content and leave intentional whitespace.

Avoid stretching sparse cards to fill the slide. If cards contain only short labels and one-line explanations, reduce their visual weight or replace them with a richer structure such as a process, comparison, relationship map, or annotated example.

## Layout Quality Checks

Before finalizing a slide, check:

- Does the main visual form match the content type?
- Are large surfaces justified by enough information, structure, or visual hierarchy?
- Could a diagram, flow, or relationship layout explain the idea better than independent cards?
- Is the slide adding insight beyond restating the title?
- Are decorative labels, subtitles, and card headings doing different jobs instead of repeating one another?

---

## CSS Gotchas

### Negating CSS Functions

**WRONG — silently ignored by browsers (no console error):**
```css
right: -clamp(28px, 3.5vw, 44px);   /* Browser ignores this */
margin-left: -min(10vw, 100px);      /* Browser ignores this */
```

**CORRECT — wrap in `calc()`:**
```css
right: calc(-1 * clamp(28px, 3.5vw, 44px));  /* Works */
margin-left: calc(-1 * min(10vw, 100px));     /* Works */
```

CSS does not allow a leading `-` before function names. The browser silently discards the entire declaration — no error, the element just appears in the wrong position. **Always use `calc(-1 * ...)` to negate CSS function values.**

---

### Grid Column Count Must Match All Direct Children

**WRONG — decorative elements (dividers, arrows) are also grid children:**
```css
/* Intent: 2 content panels with a divider between them */
.split-layout {
  grid-template-columns: 1fr 1fr; /* BUG: 3 children, only 2 columns */
}

/* Intent: 3 layers with arrows between them */
.arch-grid {
  grid-template-columns: repeat(3, 1fr); /* BUG: 5 children, only 3 columns */
}
```

**CORRECT — account for every direct child element:**
```css
/* 3 children: panel + divider + panel */
.split-layout {
  grid-template-columns: 1fr auto 1fr;
}

/* 5 children: layer + arrow + layer + arrow + layer */
.arch-grid {
  grid-template-columns: 1fr auto 1fr auto 1fr;
}
```

CSS Grid places ALL direct children into the column template sequentially. When `grid-template-columns` has fewer slots than children, extra items wrap to implicit rows — causing broken layouts with no console error. **Always count every direct child (including decorative separators, arrows, dividers) and set columns accordingly.** Use `auto` for decorative elements so they only take their intrinsic width.

---

## DO NOT USE (Generic AI Patterns)

**Fonts:** Inter, Roboto, Arial, system fonts as display

**Colors:** `#6366f1` (generic indigo), purple gradients on white

**Layouts:** Everything centered, generic hero sections, identical card grids

**Decorations:** Realistic illustrations, gratuitous glassmorphism, drop shadows without purpose
---

## Chart Color Integration

Charts must feel native to the current theme. Follow these rules for every SVG chart:

- **Never hard-code chart colors**. Always derive them from the theme CSS variables defined in `:root`.
- Use these mappings:
  - Primary data marks: `var(--accent)`
  - Secondary / muted data: `var(--text-secondary)` or a transparent variant such as `rgba(var(--accent-rgb), 0.5)`
  - Chart background fills: `var(--bg-secondary)` with low opacity
  - Labels and axis text: `var(--text-primary)` for values, `var(--text-secondary)` for category labels
- If a chart needs more than one color, generate harmonious variants by adjusting opacity or mixing the accent color with `--bg-secondary`, not by introducing new hues.
- Avoid library defaults: no gray grids, no blue bars, no default tooltip chrome.
