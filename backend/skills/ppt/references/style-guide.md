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

## Image Implementation Rules

- **Content images** (screenshots, logos, inline visuals) must use the `.slide-image` class. They are constrained by `max-height: min(50vh, 400px)` from `viewport-base.css`.
- **Full-bleed slide backgrounds** must use `.bg-image` with `background-image` on a `<div>`. Never implement them as `<img>`, or the `viewport-base.css` image constraint will truncate them to the top half.

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
