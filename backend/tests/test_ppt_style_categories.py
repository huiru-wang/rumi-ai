from src.storage.seeds import _BUILTIN_PPT_STYLES


def test_builtin_ppt_styles_use_usage_categories():
    categories_by_id = {style["id"]: style["category"] for style in _BUILTIN_PPT_STYLES}

    assert categories_by_id == {
        "sys-magazine-ink": "creative",
        "sys-cream-pastel-infographic": "data",
        "sys-dark-soft-glow": "creative",
        "sys-swiss-modern": "business",
        "sys-peach-lavender-split": "product",
    }


def test_builtin_ppt_styles_do_not_use_color_categories():
    categories = {style["category"] for style in _BUILTIN_PPT_STYLES}

    assert "dark" not in categories
    assert "light" not in categories
