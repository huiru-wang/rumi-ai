# Page Layout Contract

This contract is shared by PPT generation and PPT style extraction. Keep it stable unless both flows are updated together.

## Fixed Page Types

Internal `page_type` values are business-independent:

| page_type | 用户可见页面类型 | Purpose |
|-----------|------------------|---------|
| `cover` | 封面页 | Opening title, hook, and metadata |
| `agenda` | 目录页 | Navigation and deck structure |
| `section` | 章节页 | Chapter divider, title page, or transition |
| `content` | 内容页 | Main explanation, comparison, chart, image, quote, or case |
| `closing` | 封底页 | Ending statement, call to action, or final summary |

Default order: `cover -> agenda -> section -> content -> closing`.

用户可见大纲必须使用中文页面类型。Do not expose raw enum values such as `cover`, `section`, or `content` in the Markdown outline shown to the user. Use raw enum values only in internal briefs and saved JSON.

## Style Template Requirement

Every reusable style template should include a normalized capability map under `## 4. Layout Grammar`:

```yaml
page_layouts:
  cover:
    enabled: true
    display_name: 封面页
    variants:
      - id: cover.variant_name
        name: 中文布局名
        best_for: ...
        structure: ...
        capacity: ...
  agenda:
    enabled: true
    display_name: 目录页
    variants: []
    fallback: ...
  section:
    enabled: true
    display_name: 章节页
    variants: []
  content:
    enabled: true
    display_name: 内容页
    variants: []
  closing:
    enabled: true
    display_name: 封底页
    variants: []
section_policy:
  use_when:
    - deck has 2+ clear content groups
    - each section introduces at least 2 following content slides
  avoid_when:
    - compact deck has one continuous topic
    - the section title only covers one isolated subtopic
  consistency:
    - if section is used for one peer topic, use it for all peer topics
    - do not create a section page for one peer topic while another peer topic has no section page
```

`layout_variant` is style-specific and must be selected from `page_layouts.<page_type>.variants`. Do not invent unsupported layouts during generation.

## Naming Rules

- Variant IDs use `<page_type>.<semantic_name>`, for example `content.split_text_visual`.
- Variant names are Chinese and user-readable, for example `左文右图型`.
- `display_name` is Chinese and can be used in user-facing outline tables.
- `capacity` describes practical content limits; it replaces any separate content-density question.

