export const STYLE_PREVIEW_NAV_SCRIPT = `
(function () {
  function getSlides() {
    var slides = Array.prototype.slice.call(document.querySelectorAll('.slide'));
    if (slides.length === 0) {
      slides = Array.prototype.slice.call(document.querySelectorAll('section'));
    }
    return slides;
  }

  function setReadOnly() {
    document.querySelectorAll('[contenteditable]').forEach(function (el) {
      el.removeAttribute('contenteditable');
    });
    document.documentElement.style.overflow = 'hidden';
    document.body.style.overflow = 'hidden';
    document.body.style.pointerEvents = 'none';
  }

  function postState(index) {
    var slides = getSlides();
    window.parent.postMessage({
      type: 'style-preview-state',
      index: index,
      total: Math.max(slides.length, 1)
    }, '*');
  }

  function navigate(index) {
    var slides = getSlides();
    if (slides.length <= 1) {
      postState(0);
      return;
    }
    var next = Math.max(0, Math.min(index, slides.length - 1));
    slides.forEach(function (slide, i) {
      slide.classList.add('visible');
      slide.style.display = i === next ? '' : 'none';
    });
    postState(next);
  }

  window.addEventListener('message', function (event) {
    var data = event.data || {};
    if (data.type === 'style-preview:navigate' || data.type === 'navigate-slide') {
      navigate(Number(data.index) || 0);
    }
  });

  window.addEventListener('DOMContentLoaded', function () {
    setReadOnly();
    navigate(0);
  });

  setTimeout(function () {
    setReadOnly();
    navigate(0);
  }, 0);
})();
`;

export function prepareStylePreviewHtml(html: string): string {
  const script = `<script>${STYLE_PREVIEW_NAV_SCRIPT}</script>`;
  if (/<\/body>/i.test(html)) {
    return html.replace(/<\/body>/i, `${script}</body>`);
  }
  return `${html}${script}`;
}
