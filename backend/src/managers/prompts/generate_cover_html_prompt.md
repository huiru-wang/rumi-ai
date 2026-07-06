# 生成 PPT 风格完整预览 HTML

根据提供的风格模版，生成一个**独立、完整、只读、多页**的 PPT 风格预览 HTML。

该预览不是最终 PPT 产物，而是用于让用户判断该风格在不同页面类型下的整体表现。必须覆盖风格模板 `page_layouts` 中所有 `enabled: true` 的页面类型和主要布局变体。

---

## 输出要求

- 输出纯 HTML，不要用 ```html 或任何代码块包裹。
- 自包含文件，CSS/JS 全部内联，不依赖外部文件（字体 CDN 和资源清单图片除外）。
- 页面比例为 16:9，每页全屏展示，支持滚轮、键盘、触摸和导航点翻页。
- 必须是只读预览：禁止 `contenteditable`、编辑按钮、导出按钮、localStorage 自动保存、`InlineEditor` 或任何编辑热区。
- `<body>` 必须包含 `data-preview-mode="readonly"`。
- 每个幻灯片 section 必须有 `.slide` 类，并用 `data-page-type="cover|agenda|section|content|closing"` 标记页面类型。
- 每个启用页面类型至少生成一页；如果某个页面类型有多个关键布局变体，可以各生成一页。
- 使用占位符文本，禁止还原原始 PPT 业务文本和行业专有内容。

---

## 页面类型覆盖

如果风格模版包含标准化 `page_layouts`，必须优先读取：

- `page_layouts.cover`
- `page_layouts.agenda`
- `page_layouts.section`
- `page_layouts.content`
- `page_layouts.closing`

只生成 `enabled: true` 的页面类型。`enabled: false` 的页面类型不要生成，但可以在 JS 导航中自然跳过。

布局变体规则：

- 每页的结构必须来自对应 `page_layouts.<page_type>.variants[*]`。
- `layout_variant` 的视觉结构必须体现在 HTML class 或 `data-layout` 中，例如 `data-layout="content.split_text_visual"`。
- 封面页用封面占位符，目录页用目录占位符，章节页用章节占位符，内容页用图文/卡片/图表/引用等占位符，封底页用结尾占位符。

---

## HTML 骨架

必须使用以下结构思想，可以扩展样式和页面，但不能删掉只读、翻页和动画能力：

```html
<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>[风格名称] - 风格预览</title>
  <link rel="preconnect" href="https://fonts.loli.net">
  <link rel="stylesheet" href="https://fonts.loli.net/css2?family=...">
  <style>
    :root { /* CSS 变量：颜色、字体、字号，从风格模版提取 */ }
    /* 完整页面、动画、导航、每种 page_type 的布局样式 */
  </style>
</head>
<body data-preview-mode="readonly">
  <main class="deck" aria-label="PPT 风格预览">
    <section class="slide" data-page-type="cover" data-layout="cover.xxx">...</section>
    <section class="slide" data-page-type="content" data-layout="content.xxx">...</section>
  </main>
  <nav class="nav-dots" aria-label="幻灯片导航">...</nav>
  <script>
    /* 只读保护、翻页控制、visible 入场动画 */
  </script>
</body>
</html>
```

---

## 必须包含的基础 CSS

```css
* { box-sizing: border-box; }
html, body { margin: 0; min-height: 100%; overflow: hidden; }
body { width: 100vw; height: 100vh; height: 100dvh; }
.deck { width: 100%; height: 100%; position: relative; overflow: hidden; }
.slide {
  position: absolute; inset: 0;
  width: 100vw; height: 100vh; height: 100dvh;
  opacity: 0; pointer-events: none;
  transform: translateY(18px) scale(0.985);
  transition: opacity 480ms ease, transform 520ms ease;
  overflow: hidden;
}
.slide.active { opacity: 1; pointer-events: auto; transform: translateY(0) scale(1); }
.slide-content {
  position: relative; z-index: 2;
  width: 100%; height: 100%;
  padding: var(--slide-padding);
  overflow: hidden;
}
.reveal {
  opacity: 0;
  transform: translateY(28px);
  transition: opacity 640ms ease, transform 640ms ease;
}
.slide.visible .reveal { opacity: 1; transform: translateY(0); }
.reveal:nth-child(2) { transition-delay: 80ms; }
.reveal:nth-child(3) { transition-delay: 160ms; }
.reveal:nth-child(4) { transition-delay: 240ms; }
.nav-dots {
  position: fixed; right: 22px; top: 50%; transform: translateY(-50%);
  display: flex; flex-direction: column; gap: 10px; z-index: 20;
}
.nav-dot {
  width: 9px; height: 9px; border-radius: 999px;
  border: 1px solid currentColor; background: transparent; cursor: pointer;
}
.nav-dot.active { background: currentColor; }
:root {
  --title-size: clamp(2rem, 5vw, 5rem);
  --h2-size: clamp(1.35rem, 3vw, 3rem);
  --h3-size: clamp(1rem, 2vw, 1.6rem);
  --body-size: clamp(0.78rem, 1.25vw, 1.08rem);
  --small-size: clamp(0.68rem, 0.9vw, 0.88rem);
  --slide-padding: clamp(1.5rem, 4.5vw, 5rem);
  --content-gap: clamp(0.8rem, 2vw, 2rem);
}
@media (max-height: 620px) {
  :root { --slide-padding: clamp(0.8rem, 3vw, 2rem); --title-size: clamp(1.4rem, 4vw, 3rem); }
}
@media (max-width: 720px) {
  .nav-dots { right: 12px; }
  :root { --slide-padding: clamp(1rem, 5vw, 2rem); }
}
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after { animation-duration: 0.01ms !important; transition-duration: 0.2s !important; }
}
```

---

## 必须包含的基础 JS

```js
document.addEventListener('DOMContentLoaded', () => {
  document.querySelectorAll('[contenteditable]').forEach((el) => el.setAttribute('contenteditable', 'false'));
  const slides = Array.from(document.querySelectorAll('.slide'));
  const dots = Array.from(document.querySelectorAll('.nav-dot'));
  let current = 0;
  let locked = false;

  function show(index) {
    current = Math.max(0, Math.min(index, slides.length - 1));
    slides.forEach((slide, i) => {
      slide.classList.toggle('active', i === current);
      slide.classList.remove('visible');
      if (i === current) requestAnimationFrame(() => slide.classList.add('visible'));
    });
    dots.forEach((dot, i) => dot.classList.toggle('active', i === current));
  }

  dots.forEach((dot, i) => dot.addEventListener('click', () => show(i)));
  window.addEventListener('keydown', (event) => {
    if (['ArrowDown', 'ArrowRight', 'PageDown', ' '].includes(event.key)) show(current + 1);
    if (['ArrowUp', 'ArrowLeft', 'PageUp'].includes(event.key)) show(current - 1);
  });
  window.addEventListener('wheel', (event) => {
    if (locked || Math.abs(event.deltaY) < 20) return;
    locked = true;
    show(current + (event.deltaY > 0 ? 1 : -1));
    setTimeout(() => { locked = false; }, 520);
  }, { passive: true });
  let touchStartY = 0;
  window.addEventListener('touchstart', (event) => { touchStartY = event.touches[0].clientY; }, { passive: true });
  window.addEventListener('touchend', (event) => {
    const diff = touchStartY - event.changedTouches[0].clientY;
    if (Math.abs(diff) > 40) show(current + (diff > 0 ? 1 : -1));
  }, { passive: true });
  show(0);
});
```

---

## 视觉资产规则

如果资源清单不为空：

- 优先使用 `usage_type=background` 的资源作为对应页面类型的背景图。
- 普通图片、图标、装饰图形可以用于内容页或章节页，但必须符合风格模板的 Visual Assets 使用建议。
- 资源 URL 必须原样使用，不要改写路径。
- 不要为了展示所有资源而堆砌图片；预览应体现“该风格如何使用资产”，不是资源图库。

如果资源清单为空：

- 使用 CSS 渐变、几何图形、线条、纹理构建风格，不要引入外部图片或图标。

---

## 占位符内容

使用中性占位符，避免业务泄漏：

- 封面页：`封面主标题`、`封面副标题`、`机构名称`、`日期信息`
- 目录页：`核心议题 01`、`核心议题 02`、`核心议题 03`
- 章节页：`章节标题`、`过渡说明`
- 内容页：`页面主标题`、`关键观点`、`要点说明`、`数据指标`、`图表标题`
- 封底页：`谢谢观看`、`结尾说明`、`联系信息`

---

## 禁止事项

- 禁止生成单页封面预览，除非 `page_layouts` 只有封面页启用。
- 禁止加入任何编辑能力。
- 禁止还原原 PPT 的业务文本。
- 禁止引入资源清单外的图片。
- 禁止让页面产生内部滚动条或内容溢出。
- 禁止输出代码块。
