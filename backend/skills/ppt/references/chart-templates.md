# Chart Templates

Copy-ready SVG skeletons for common chart types. All templates assume `chart-patterns.css` is included in the presentation.

Replace placeholder values, labels, and dimensions to match your data. Keep data points minimal (3-8 categories, 2-6 time points).

---

## 1. Vertical Lollipop Chart

Best for: ranking 4-6 categories

```html
<svg class="chart-wrap" viewBox="0 0 500 320" preserveAspectRatio="xMidYMid meet">
  <g transform="translate(60, 40)">
    <!-- faint baseline grid -->
    <line class="chart-grid" x1="0" y1="200" x2="360" y2="200" />
    <line class="chart-grid" x1="0" y1="150" x2="360" y2="150" />
    <line class="chart-grid" x1="0" y1="100" x2="360" y2="100" />
    <line class="chart-grid" x1="0" y1="50" x2="360" y2="50" />

    <!-- Category 1: value 80% -->
    <text class="chart-label" x="30" y="225" text-anchor="middle">Alpha</text>
    <line class="chart-lollipop-line" x1="30" y1="200" x2="30" y2="40" />
    <circle class="chart-lollipop-head" cx="30" cy="40" r="7" />
    <text class="chart-value" x="30" y="30" text-anchor="middle">80%</text>

    <!-- Category 2: value 55% -->
    <text class="chart-label" x="110" y="225" text-anchor="middle">Beta</text>
    <line class="chart-lollipop-line" x1="110" y1="200" x2="110" y2="90" />
    <circle class="chart-lollipop-head" cx="110" cy="90" r="7" />
    <text class="chart-value" x="110" y="80" text-anchor="middle">55%</text>

    <!-- Category 3: value 92% -->
    <text class="chart-label" x="190" y="225" text-anchor="middle">Gamma</text>
    <line class="chart-lollipop-line" x1="190" y1="200" x2="190" y2="16" />
    <circle class="chart-lollipop-head" cx="190" cy="16" r="7" />
    <text class="chart-value" x="190" y="6" text-anchor="middle">92%</text>

    <!-- Category 4: value 67% -->
    <text class="chart-label" x="270" y="225" text-anchor="middle">Delta</text>
    <line class="chart-lollipop-line" x1="270" y1="200" x2="270" y2="66" />
    <circle class="chart-lollipop-head" cx="270" cy="66" r="7" />
    <text class="chart-value" x="270" y="56" text-anchor="middle">67%</text>
  </g>
</svg>
```

**Replace:** category labels, `y2` positions (top of line), circle `cy`, and value text.

---

## 2. Area Chart

Best for: trends over 4-7 time periods

```html
<svg class="chart-wrap" viewBox="0 0 540 280" preserveAspectRatio="xMidYMid meet">
  <defs>
    <linearGradient id="areaGradient" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="var(--accent)" stop-opacity="0.35" />
      <stop offset="100%" stop-color="var(--accent)" stop-opacity="0" />
    </linearGradient>
  </defs>

  <g transform="translate(50, 30)">
    <!-- grid -->
    <line class="chart-grid" x1="0" y1="180" x2="440" y2="180" />
    <line class="chart-grid" x1="0" y1="120" x2="440" y2="120" />
    <line class="chart-grid" x1="0" y1="60" x2="440" y2="60" />

    <!-- area fill -->
    <path class="chart-area" d="M0,180 L0,120 L110,90 L220,100 L330,40 L440,60 L440,180 Z" fill="url(#areaGradient)" />

    <!-- line -->
    <path class="chart-line" d="M0,120 L110,90 L220,100 L330,40 L440,60" />

    <!-- points -->
    <circle class="chart-point" cx="0" cy="120" r="5" />
    <circle class="chart-point" cx="110" cy="90" r="5" />
    <circle class="chart-point" cx="220" cy="100" r="5" />
    <circle class="chart-point" cx="330" cy="40" r="5" />
    <circle class="chart-point" cx="440" cy="60" r="5" />

    <!-- x-axis labels -->
    <text class="chart-label" x="0" y="205" text-anchor="middle">Q1</text>
    <text class="chart-label" x="110" y="205" text-anchor="middle">Q2</text>
    <text class="chart-label" x="220" y="205" text-anchor="middle">Q3</text>
    <text class="chart-label" x="330" y="205" text-anchor="middle">Q4</text>
    <text class="chart-label" x="440" y="205" text-anchor="middle">Q5</text>
  </g>
</svg>
```

**Replace:** points in the `d` attributes, point `cx`/`cy`, and labels.

---

## 3. Donut Chart

Best for: 2-5 parts of a whole

```html
<svg class="chart-wrap" viewBox="0 0 400 300" preserveAspectRatio="xMidYMid meet">
  <g transform="translate(150, 150)">
    <!-- background ring -->
    <circle class="chart-donut-bg" r="80" cx="0" cy="0" />

    <!-- segment 1: 45% -->
    <circle class="chart-donut-segment" r="80" cx="0" cy="0"
            stroke-dasharray="226 502" stroke-dashoffset="0" />

    <!-- segment 2: 30% -->
    <circle class="chart-donut-segment" r="80" cx="0" cy="0"
            stroke-dasharray="151 502" stroke-dashoffset="-226" />

    <!-- segment 3: 25% -->
    <circle class="chart-donut-segment" r="80" cx="0" cy="0"
            stroke-dasharray="126 502" stroke-dashoffset="-377" />

    <!-- center text -->
    <text class="chart-donut-label" x="0" y="-8">100%</text>
    <text class="chart-donut-sublabel" x="0" y="18">Total Share</text>
  </g>

  <!-- legend / labels on the right -->
  <g transform="translate(260, 90)">
    <circle r="6" cx="0" cy="0" fill="var(--accent)" />
    <text class="chart-label" x="16" y="5">Segment A — 45%</text>

    <circle r="6" cx="0" cy="40" fill="var(--text-secondary)" />
    <text class="chart-label" x="16" y="45">Segment B — 30%</text>

    <circle r="6" cx="0" cy="80" fill="var(--bg-secondary)" />
    <text class="chart-label" x="16" y="85">Segment C — 25%</text>
  </g>
</svg>
```

**Math:** Circumference = `2 * π * 80 ≈ 502`. For a segment of `P%`, dash length = `502 * P / 100`. `stroke-dashoffset` accumulates previous segments.

---

## 4. Radar Chart

Best for: 5-6 dimensional comparison

```html
<svg class="chart-wrap" viewBox="0 0 400 360" preserveAspectRatio="xMidYMid meet">
  <g transform="translate(200, 180)">
    <!-- web background -->
    <polygon class="chart-radar-web" points="0,-120 104,-60 104,60 0,120 -104,60 -104,-60" />
    <polygon class="chart-radar-web" points="0,-90 78,-45 78,45 0,90 -78,45 -78,-45" />
    <polygon class="chart-radar-web" points="0,-60 52,-30 52,30 0,60 -52,30 -52,-30" />
    <polygon class="chart-radar-web" points="0,-30 26,-15 26,15 0,30 -26,15 -26,-15" />

    <!-- axes -->
    <line class="chart-radar-axis" x1="0" y1="0" x2="0" y2="-120" />
    <line class="chart-radar-axis" x1="0" y1="0" x2="104" y2="-60" />
    <line class="chart-radar-axis" x1="0" y1="0" x2="104" y2="60" />
    <line class="chart-radar-axis" x1="0" y1="0" x2="0" y2="120" />
    <line class="chart-radar-axis" x1="0" y1="0" x2="-104" y2="60" />
    <line class="chart-radar-axis" x1="0" y1="0" x2="-104" y2="-60" />

    <!-- data shape: values 80, 65, 90, 75, 60, 85 out of 100 -->
    <polygon class="chart-radar-shape" points="0,-96 68,-39 94,54 0,90 -63,36 -88,-51" />

    <!-- labels -->
    <text class="chart-radar-label" x="0" y="-140">Speed</text>
    <text class="chart-radar-label" x="130" y="-70">Quality</text>
    <text class="chart-radar-label" x="130" y="80">Scale</text>
    <text class="chart-radar-label" x="0" y="150">Cost</text>
    <text class="chart-radar-label" x="-130" y="80">UX</text>
    <text class="chart-radar-label" x="-130" y="-70">Reliability</text>
  </g>
</svg>
```

**Replace:** polygon points according to each dimension's score. Maximum radius is 120.

---

## 5. Sankey Diagram

Best for: 3-4 stage flow

```html
<svg class="chart-wrap" viewBox="0 0 540 260" preserveAspectRatio="xMidYMid meet">
  <defs>
    <linearGradient id="flowGradient" x1="0" y1="0" x2="1" y2="0">
      <stop offset="0%" stop-color="var(--accent)" stop-opacity="0.6" />
      <stop offset="100%" stop-color="var(--accent)" stop-opacity="0.3" />
    </linearGradient>
  </defs>

  <g transform="translate(40, 30)">
    <!-- stage 1 node -->
    <rect class="chart-node" x="0" y="20" width="20" height="160" rx="4" />
    <text class="chart-value" x="10" y="-10" text-anchor="middle">1,000</text>
    <text class="chart-label" x="10" y="205" text-anchor="middle">Visitors</text>

    <!-- stage 2 node -->
    <rect class="chart-node" x="220" y="50" width="20" height="100" rx="4" />
    <text class="chart-value" x="230" y="-10" text-anchor="middle">600</text>
    <text class="chart-label" x="230" y="205" text-anchor="middle">Signups</text>

    <!-- stage 3 node -->
    <rect class="chart-node" x="440" y="90" width="20" height="40" rx="4" />
    <text class="chart-value" x="450" y="-10" text-anchor="middle">200</text>
    <text class="chart-label" x="450" y="205" text-anchor="middle">Paid</text>

    <!-- flow paths -->
    <path class="chart-flow" d="M20,100 C100,100 140,100 220,100" stroke="url(#flowGradient)" stroke-width="80" />
    <path class="chart-flow secondary" d="M240,100 C320,100 360,110 440,110" stroke-width="40" />
  </g>
</svg>
```

**Replace:** node heights, flow path `d` control points, and stroke widths to represent magnitudes.

---

## 6. Sparkline + Big Number

Best for: KPI slides

```html
<svg class="chart-wrap" viewBox="0 0 400 160" preserveAspectRatio="xMidYMid meet">
  <g transform="translate(0, 40)">
    <path class="chart-sparkline" d="M0,60 L60,45 L120,55 L180,20 L240,35 L300,10 L360,25 L400,5" />
  </g>
  <text class="chart-donut-label" x="20" y="130">+42%</text>
  <text class="chart-donut-sublabel" x="20" y="155">MoM growth</text>
</svg>
```

**Replace:** sparkline path and big number text.
