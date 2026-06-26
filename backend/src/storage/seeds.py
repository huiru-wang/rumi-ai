"""System builtin seed data for PPT styles and voices."""

from __future__ import annotations

from pathlib import Path


def _load_style_description(name_en: str) -> str:
    """Load style_description from the prompt .md file (strip YAML frontmatter)."""
    md_path = Path(__file__).resolve().parent / "seed_data" / "ppt_styles" / f"{name_en}.md"
    if not md_path.exists():
        return ""
    text = md_path.read_text(encoding="utf-8")
    # Strip YAML frontmatter (--- ... ---)
    if text.startswith("---"):
        end = text.find("---", 3)
        if end != -1:
            text = text[end + 3:].lstrip("\n")
    return text


# System builtin PPT style seed data
_BUILTIN_PPT_STYLES = [
    {
        "id": "sys-magazine-ink",
        "user_id": "system",
        "category": "dark",
        "name": "墨纸杂志",
        "name_en": "magazine-ink",
        "description": "纯墨黑与暖米白的高对比纸媒美学，衬线大字与等宽标签营造编辑感，适合深度内容与品牌发布。",
        "preview_path": "magazine-ink.html",
        "style_description": _load_style_description("magazine-ink"),
    },
    {
        "id": "sys-cream-brutalism",
        "user_id": "system",
        "category": "light",
        "name": "奶油粗野主义",
        "name_en": "cream-brutalism",
        "description": "奶白底黑框的粗野主义信息图，糖果色卡片与大号数据，适合趋势解读与知识分享。",
        "preview_path": "cream-brutalism.html",
        "style_description": _load_style_description("cream-brutalism"),
    },
    {
        "id": "sys-dark-soft-glow",
        "user_id": "system",
        "category": "dark",
        "name": "暗色柔光",
        "name_en": "dark-soft-glow",
        "description": "深黑底搭配柔焦暖色光晕，衬线标题与极简几何线条，适合高端宣讲与品牌发布会。",
        "preview_path": "dark-soft-glow.html",
        "style_description": _load_style_description("dark-soft-glow"),
    },
    {
        "id": "sys-swiss-modern",
        "user_id": "system",
        "category": "light",
        "name": "瑞士国际风",
        "name_en": "swiss-modern",
        "description": "以安全橙为单一强调色的瑞士国际主义风格，强调网格秩序、无衬线大字重对比与几何抽象装饰，适用于企业宣讲、安全宣贯类演示。",
        "preview_path": "swiss-modern.html",
        "style_description": _load_style_description("swiss-modern"),
    },
    {
        "id": "sys-peach-lavender-split",
        "user_id": "system",
        "category": "light",
        "name": "桃紫分境",
        "name_en": "peach-lavender-split",
        "description": "桃粉与薰衣草紫左右分屏，糖果色标签卡片，适合轻松宣讲与知识分享。",
        "preview_path": "peach-lavender-split.html",
        "style_description": _load_style_description("peach-lavender-split"),
    },
]


# Builtin voice seed data (mirrors frontend VOICES constant)
_BUILTIN_VOICES = [
    {
        "id": "Cherry",
        "name": "芊悦",
        "trait": "阳光积极、亲切自然小姐姐",
        "gender": "female",
        "audio_url": "https://help-static-aliyun-doc.aliyuncs.com/file-manage-files/zh-CN/20250211/tixcef/cherry.wav",
    },
    {
        "id": "Ethan",
        "name": "晨煦",
        "trait": "阳光、温暖、活力、朝气的男生",
        "gender": "male",
        "audio_url": "https://help-static-aliyun-doc.aliyuncs.com/file-manage-files/zh-CN/20250211/emaqdp/ethan.wav",
    },
    {
        "id": "Chelsie",
        "name": "千雪",
        "trait": "二次元虚拟女友",
        "gender": "female",
        "audio_url": "https://help-static-aliyun-doc.aliyuncs.com/file-manage-files/zh-CN/20250211/vnpxgw/chelsie.wav",
    },
    {
        "id": "Vivian",
        "name": "十三",
        "trait": "拽拽的、可爱的小暴躁",
        "gender": "female",
        "audio_url": "https://help-static-aliyun-doc.aliyuncs.com/file-manage-files/zh-CN/20251120/eetwkj/Vivian.wav",
    },
    {
        "id": "Eldric Sage",
        "name": "沧明子",
        "trait": "沉稳睿智的老者",
        "gender": "male",
        "audio_url": "https://help-static-aliyun-doc.aliyuncs.com/file-manage-files/zh-CN/20251120/hbvhwj/Eldric+Sage.wav",
    },
    {
        "id": "Neil",
        "name": "阿闻",
        "trait": "专业的新闻主持人",
        "gender": "male",
        "audio_url": "https://help-static-aliyun-doc.aliyuncs.com/file-manage-files/zh-CN/20251120/ucmfkt/Neil.wav",
    },
    {
        "id": "Vincent",
        "name": "田叔",
        "trait": "沙哑烟嗓",
        "gender": "male",
        "audio_url": "https://help-static-aliyun-doc.aliyuncs.com/file-manage-files/zh-CN/20251120/skfrkq/Vincent.wav",
    },
    {
        "id": "Bellona",
        "name": "燕铮莺",
        "trait": "声音洪亮、字正腔圆江湖",
        "gender": "female",
        "audio_url": "https://help-static-aliyun-doc.aliyuncs.com/file-manage-files/zh-CN/20251120/wztwli/Bellona.wav",
    },
]


def get_default_voice_info(voice_id: str) -> dict:
    """Look up voice info from builtin seed data. Returns {id, name, trait, gender} or empty dict."""
    voice = next((v for v in _BUILTIN_VOICES if v["id"] == voice_id), None)
    if voice:
        return {"id": voice["id"], "name": voice["name"], "trait": voice["trait"], "gender": voice["gender"]}
    return {}
