"""Lightweight visual understanding for extracted document images."""

from __future__ import annotations

import base64
import logging
import os
from mimetypes import guess_type

from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI

from src.parsers.base import DocumentBlock
from src.storage.file_store import FileStore

logger = logging.getLogger(__name__)


class VisionManager:
    """Generate short RAG-oriented summaries for image/chart blocks."""

    def __init__(self, file_store: FileStore | None):
        self.file_store = file_store
        self.model_name = os.getenv("VISION_MODEL", "")
        self.api_key = os.getenv("VISION_API_KEY", "")
        self.api_base = os.getenv("VISION_API_BASE", "")
        self.max_bytes = int(os.getenv("VISION_MAX_IMAGE_BYTES", str(4 * 1024 * 1024)))
        self._model = None
        if self.model_name and self.api_key:
            self._model = ChatOpenAI(
                model=self.model_name,
                api_key=self.api_key,
                base_url=self.api_base or None,
            )

    @property
    def enabled(self) -> bool:
        return self._model is not None and self.file_store is not None

    async def enrich_block(self, block: DocumentBlock) -> DocumentBlock:
        """Return block with visual summary when possible."""
        if block.type not in ("image", "chart") or not block.asset_path:
            return block
        if not self.enabled:
            logger.info(
                "[VisionManager] disabled: missing VISION_API_KEY/VISION_MODEL or file_store"
            )
            return block

        logger.info(
            "[VisionManager] analyze start: block_id=%s asset_path=%s",
            block.id,
            block.asset_path,
        )
        try:
            image_bytes = await self.file_store.read(block.asset_path)  # type: ignore[union-attr]
            if len(image_bytes) > self.max_bytes:
                logger.info(
                    "[VisionManager] skip large image: block_id=%s size=%d max=%d",
                    block.id,
                    len(image_bytes),
                    self.max_bytes,
                )
                return block
            mime = guess_type(block.asset_path)[0] or "image/png"
            encoded = base64.b64encode(image_bytes).decode("ascii")
            prompt = (
                "请用中文简洁描述这张文档图片，服务于知识库检索。"
                "包括：图片类型、核心内容、可见文字、图表趋势或流程关系。"
                "不要编造不可见信息。150字以内。"
            )
            if block.caption:
                prompt += f"\n图片标题或上下文：{block.caption}"
            response = await self._model.ainvoke(  # type: ignore[union-attr]
                [
                    HumanMessage(
                        content=[
                            {"type": "text", "text": prompt},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:{mime};base64,{encoded}",
                                },
                            },
                        ]
                    )
                ]
            )
            summary = str(response.content).strip()
            block.summary = summary
            logger.info(
                "[VisionManager] analyze success: block_id=%s summary_len=%d",
                block.id,
                len(summary),
            )
        except Exception as exc:
            logger.warning(
                "[VisionManager] analyze failed: block_id=%s error=%s",
                block.id,
                exc,
            )
        return block
