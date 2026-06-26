import logging
from collections.abc import Awaitable, Callable

from langchain.agents.middleware import AgentMiddleware, ModelRequest, ModelResponse
from langchain_core.messages import AIMessage, BaseMessage, ToolMessage

logger = logging.getLogger(__name__)


UNSUPPORTED_CONTENT_PART_TYPES = {
    "invalid_tool_call",
    "tool_call",
    "tool_use",
}


def _following_tool_message_ids(
    messages: list[BaseMessage],
    start_index: int,
) -> set[str]:
    tool_message_ids: set[str] = set()
    for message in messages[start_index + 1 :]:
        if not isinstance(message, ToolMessage):
            break
        if message.tool_call_id:
            tool_message_ids.add(message.tool_call_id)
    return tool_message_ids


def _message_tool_call_ids(message: AIMessage) -> set[str]:
    ids = {
        tool_call.get("id")
        for tool_call in message.tool_calls
        if isinstance(tool_call, dict) and tool_call.get("id")
    }

    raw_tool_calls = message.additional_kwargs.get("tool_calls")
    if isinstance(raw_tool_calls, list):
        ids.update(
            raw_tool_call.get("id")
            for raw_tool_call in raw_tool_calls
            if isinstance(raw_tool_call, dict) and raw_tool_call.get("id")
        )

    return {tool_call_id for tool_call_id in ids if isinstance(tool_call_id, str)}


def _clear_tool_calls(message: AIMessage) -> AIMessage:
    return message.model_copy(
        update={
            "tool_calls": [],
            "invalid_tool_calls": [],
            "additional_kwargs": {
                key: value
                for key, value in message.additional_kwargs.items()
                if key != "tool_calls"
            },
        }
    )


def sanitize_model_messages(messages: list[BaseMessage]) -> list[BaseMessage]:
    """Remove history parts that OpenAI-compatible APIs reject."""
    sanitized: list[BaseMessage] = []
    pending_tool_call_ids: set[str] = set()

    for index, message in enumerate(messages):
        if isinstance(message, AIMessage) and isinstance(message.content, list):
            cleaned = [
                part
                for part in message.content
                if not (
                    isinstance(part, dict)
                    and part.get("type") in UNSUPPORTED_CONTENT_PART_TYPES
                )
            ]
            if len(cleaned) != len(message.content):
                message = message.model_copy(
                    update={"content": cleaned if cleaned else ""}
                )

        if isinstance(message, AIMessage):
            expected_ids = _message_tool_call_ids(message)
            actual_ids = _following_tool_message_ids(messages, index)
            if expected_ids and expected_ids.issubset(actual_ids):
                pending_tool_call_ids = set(expected_ids)
            else:
                pending_tool_call_ids = set()
                if expected_ids or message.invalid_tool_calls:
                    message = _clear_tool_calls(message)

        elif isinstance(message, ToolMessage):
            if message.tool_call_id not in pending_tool_call_ids:
                continue
            pending_tool_call_ids.remove(message.tool_call_id)

        else:
            pending_tool_call_ids = set()

        sanitized.append(message)

    return sanitized


class ModelMessageSanitizerMiddleware(AgentMiddleware):
    """Keep persisted history compatible with the configured chat model."""

    async def awrap_model_call(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], Awaitable[ModelResponse]],
    ) -> ModelResponse:
        sanitized = sanitize_model_messages(request.messages)

        if any(before is not after for before, after in zip(request.messages, sanitized)):
            logger.info(
                "[Middleware] sanitize_model_request | workspace=%s | message_count=%d",
                request.state.get("workspace_id", "default"),
                len(request.messages),
            )
            request = request.override(messages=sanitized)

        return await handler(request)
