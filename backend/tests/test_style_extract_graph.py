from langchain_core.messages import AIMessage

from src.agent.style_extract_graph import create_style_extract_graph
from src.managers.style_extract_manager import _extract_visual_resources


class FakePromptManager:
    def build_style_description_prompt(self, markdown_text: str) -> str:
        return f"STYLE::{markdown_text}"

    def build_preview_html_prompt(
        self,
        style_description: str,
        resource_base_url: str,
        resource_manifest: list[dict],
    ) -> str:
        return f"PREVIEW::{style_description}::{resource_base_url}::{len(resource_manifest)}"


class FakeLLM:
    def __init__(self):
        self.prompts: list[str] = []

    async def ainvoke(self, messages):
        system_prompt = messages[0].content
        self.prompts.append(system_prompt)
        if system_prompt.startswith("STYLE::"):
            return AIMessage(content="""---
name: 赤焰警戒
name_en: red-alert-style
description: 红灰安全培训风格
---

# 赤焰警戒

## 1. Vibe — 整体气质
严肃、清晰。

## 2. Color System — 色彩系统

## 3. Typography — 字体系统

## 4. Layout Grammar — 布局语法

page_layouts:
  cover:
    enabled: true
    display_name: 封面页
    variants:
      - id: cover.hero
        name: 主视觉封面
        best_for: 开场
        structure: 居中标题
        capacity: 低
  agenda:
    enabled: false
    display_name: 目录页
    variants: []
  section:
    enabled: false
    display_name: 章节页
    variants: []
  content:
    enabled: true
    display_name: 内容页
    variants:
      - id: content.cards
        name: 卡片阵列
        best_for: 要点说明
        structure: 三列卡片
        capacity: 中
  closing:
    enabled: true
    display_name: 封底页
    variants:
      - id: closing.end
        name: 结尾页
        best_for: 结束
        structure: 居中收束
        capacity: 低
section_policy:
  use_when: []
  avoid_when: []
  consistency: []

## 5. Signature Elements — 标志性元素

## 6. Visual Assets — 视觉资产

## 7. Usage Guidelines — 生成新 PPT 时的使用说明""")
        return AIMessage(content="""```html
<!DOCTYPE html><html><body data-preview-mode="readonly"><section class="slide" data-page-type="cover"><div class="reveal">Cover</div></section><section class="slide" data-page-type="content"><div class="reveal">Content</div></section><section class="slide" data-page-type="closing"><div class="reveal">End</div></section><style>.slide.visible .reveal{opacity:1}</style></body></html>
```""")


async def test_style_extract_graph_generates_template_and_preview():
    llm = FakeLLM()
    callback_states = []

    async def before_preview(state):
        callback_states.append(dict(state))

    graph = create_style_extract_graph(
        llm,  # type: ignore[arg-type]
        FakePromptManager(),  # type: ignore[arg-type]
        on_before_preview=before_preview,
    )

    result = await graph.ainvoke({
        "markdown_text": "PPTX markdown",
        "resource_base_url": "",
        "resource_manifest": [{"filename": "image1.png"}],
    })

    assert result["style_name"] == "赤焰警戒"
    assert result["style_name_en"] == "red-alert-style"
    assert result["description"] == "红灰安全培训风格"
    assert result["preview_html"].startswith("<!DOCTYPE html>")
    assert result["preview_html"].endswith("</html>")
    assert callback_states[0]["style_description"].startswith("# 赤焰警戒")
    assert len(llm.prompts) == 2
    assert llm.prompts[0].startswith("STYLE::PPTX markdown")
    assert "## 视觉资产盘点" in llm.prompts[0]
    assert "## 页面布局盘点" in llm.prompts[0]
    assert llm.prompts[1].startswith("PREVIEW::# 赤焰警戒")
    assert llm.prompts[1].endswith("::::1")


def test_extract_visual_resources_only_includes_background_images():
    markdown = """
## 第 1 页

### 背景

背景图片： `../media/bg.png`

### 形状

| kind | x | y | width | height | fill | text | textColor |
|------|---|---|-------|--------|------|------|-----------|
| pic | 10 | 10 | 100 | 100 | 图片 `../media/icon.png` |  |  |
"""

    resources = _extract_visual_resources(
        markdown,
        {"bg.png": "/tmp/bg.png", "icon.png": "/tmp/icon.png", "unused.png": "/tmp/unused.png"},
    )

    by_name = {item["filename"]: item for item in resources}
    assert by_name["bg.png"]["usage_type"] == "background"
    assert by_name["bg.png"]["slides"] == [1]
    assert "icon.png" not in by_name
    assert "unused.png" not in by_name
