import pytest

from src.managers.vision_manager import VisionManager
from src.parsers.base import DocumentBlock


@pytest.mark.asyncio
async def test_vision_manager_skips_when_not_configured(monkeypatch):
    monkeypatch.delenv("VISION_API_KEY", raising=False)
    monkeypatch.delenv("VISION_MODEL", raising=False)

    manager = VisionManager(file_store=None)
    block = DocumentBlock(
        id="img-1",
        type="image",
        caption="图1",
        asset_path="user/u/workspace/ws/docs/assets/image.png",
    )

    result = await manager.enrich_block(block)

    assert result.summary == ""

