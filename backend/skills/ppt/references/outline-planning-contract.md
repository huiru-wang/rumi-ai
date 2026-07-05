# Outline Planning Contract

Use this contract after content and asset collection and after reading the selected style template.

## Content Grouping First

先识别内容分组, then decide whether section pages are useful. A section page is not decorative; it must introduce a coherent group of following content slides.

Recommended internal grouping structure:

| Group | Scope | Candidate slides | Needs section? | Reason |
|-------|-------|------------------|----------------|--------|
| ... | ... | ... | yes/no | ... |

## Section Page Rules

- If the deck has one continuous topic, do not force a section page.
- If the deck is compact, usually under 8 slides, prefer skipping section pages unless there are 2+ strong groups.
- If a section page is used, it must introduce at least 2 following content slides.
- 禁止只给一个并列主题插入章节页 while another peer topic has no matching section page.
- For dual-core topics such as "数组与切片", choose one of two patterns:
  - Symmetric sections: one section for each peer topic.
  - No sections: use content pages to explain positioning and comparison.

## User Outline Display

The Markdown outline shown to the user must use Chinese page type labels and Chinese layout names:

```md
| # | 页面类型 | 布局 | 标题 | 内容意图 | 核心内容 | 关键词 | 可用素材 | 视觉建议 | 依据/来源 |
|---|----------|------|------|----------|----------|--------|----------|----------|-----------|
| 1 | 封面页 | 杂志封面英雄页 | ... | 开场定位 | ... | ... | ... | ... | ... |
| 2 | 内容页 | 左文右图型 | ... | 解释机制 | ... | ... | ... | ... | ... |
```

The saved JSON must keep machine-readable fields:

```json
{
  "page_type": "content",
  "page_type_label": "内容页",
  "layout_variant": "content.split_text_visual",
  "layout_name": "左文右图型"
}
```

