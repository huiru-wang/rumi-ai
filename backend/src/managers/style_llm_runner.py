"""Lightweight LLM calls for the PPT style extraction workflow."""

from __future__ import annotations

import json
import logging
import os
import time
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from src.exceptions import BusinessError, BusinessErrorCode

logger = logging.getLogger(__name__)


def strip_code_fence(text: str) -> str:
    stripped = text.strip()
    if not stripped.startswith("```"):
        return stripped
    first_newline = stripped.find("\n")
    if first_newline == -1:
        return stripped.strip("`").strip()
    stripped = stripped[first_newline + 1 :]
    if stripped.rstrip().endswith("```"):
        stripped = stripped.rstrip()[:-3]
    return stripped.strip()


def _message_text(response: Any) -> str:
    content = response.content if isinstance(response, AIMessage) else getattr(response, "content", response)
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(
            part.get("text", "") if isinstance(part, dict) else str(part)
            for part in content
        )
    return str(content)


def _extract_json_object(text: str) -> str:
    start = text.find("{")
    if start == -1:
        raise BusinessError(BusinessErrorCode.STYLE_EXTRACTION_OUTPUT_INVALID)
    depth = 0
    in_string = False
    escaped = False
    for index, char in enumerate(text[start:], start=start):
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[start : index + 1]
    raise BusinessError(BusinessErrorCode.STYLE_EXTRACTION_OUTPUT_INVALID)


def _model_error(exc: BaseException, purpose: str) -> BusinessError:
    status_code = getattr(exc, "status_code", None)
    text = f"{type(exc).__name__}: {exc}".lower()
    if status_code == 401 or "authentication" in text or "api key" in text:
        code = BusinessErrorCode.STYLE_EXTRACTION_MODEL_AUTH
    elif status_code == 402 or "quota" in text or "billing" in text or "insufficient" in text:
        code = BusinessErrorCode.STYLE_EXTRACTION_MODEL_QUOTA
    elif status_code == 429 or "rate limit" in text or "ratelimit" in text:
        code = BusinessErrorCode.STYLE_EXTRACTION_MODEL_RATE_LIMIT
    elif "timeout" in text or "timed out" in text:
        code = BusinessErrorCode.STYLE_EXTRACTION_MODEL_TIMEOUT
    elif "connection" in text or "network" in text or "dns" in text or status_code in {502, 503, 504}:
        code = BusinessErrorCode.STYLE_EXTRACTION_MODEL_CONNECTION
    else:
        code = BusinessErrorCode.STYLE_EXTRACTION_UNKNOWN
    return BusinessError(code, stage=purpose)


class StyleLLMRunner:
    """Invoke the text model without agent tools, state, or middleware."""

    def __init__(self, llm: ChatOpenAI | None = None):
        self.llm = llm or ChatOpenAI(
            model=os.getenv("SUMMARIZATION_MODEL"),
            api_key=os.getenv("SUMMARIZATION_API_KEY"),
            base_url=os.getenv("SUMMARIZATION_API_BASE"),
        )

    async def invoke_text(self, *, system_prompt: str, user_prompt: str, purpose: str) -> str:
        started = time.monotonic()
        try:
            response = await self.llm.ainvoke([
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_prompt),
            ])
            output = _message_text(response).strip()
        except BusinessError:
            raise
        except Exception as exc:
            raise _model_error(exc, purpose) from exc
        logger.info(
            "[StyleLLMRunner] purpose=%s input_chars=%d output_chars=%d duration_ms=%d",
            purpose,
            len(system_prompt) + len(user_prompt),
            len(output),
            int((time.monotonic() - started) * 1000),
        )
        return output

    async def invoke_json(self, *, system_prompt: str, user_prompt: str, purpose: str) -> dict:
        raw = await self.invoke_text(system_prompt=system_prompt, user_prompt=user_prompt, purpose=purpose)
        try:
            value = json.loads(_extract_json_object(strip_code_fence(raw)))
        except BusinessError:
            raise
        except json.JSONDecodeError as exc:
            raise BusinessError(
                BusinessErrorCode.STYLE_EXTRACTION_OUTPUT_INVALID,
                stage=purpose,
            ) from exc
        if not isinstance(value, dict):
            raise BusinessError(BusinessErrorCode.STYLE_EXTRACTION_OUTPUT_INVALID, stage=purpose)
        return value

    async def invoke_html(self, *, system_prompt: str, user_prompt: str, purpose: str) -> str:
        raw = await self.invoke_text(system_prompt=system_prompt, user_prompt=user_prompt, purpose=purpose)
        return strip_code_fence(raw)
