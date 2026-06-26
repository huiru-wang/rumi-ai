import logging
from typing import Any

from langchain.agents.middleware import AgentMiddleware
from langchain_core.callbacks import AsyncCallbackHandler
from langchain_core.messages import BaseMessage

from src.storage.database import Database

logger = logging.getLogger(__name__)


class MessageHistoryCallback(AsyncCallbackHandler):
    """Persist full chat messages outside LangGraph state."""

    def __init__(self, db: Database):
        self.db = db

    async def record_messages(
        self,
        *,
        thread_id: str | None,
        workspace_id: str | None,
        messages: list[Any],
    ) -> None:
        if not thread_id:
            logger.debug("Skip message history without thread_id")
            return

        for index, message in enumerate(messages):
            if self._is_summarization_message(message):
                continue
            record = self._message_to_record(message, fallback_id=f"{thread_id}-{index}")
            if record is None:
                continue
            await self.db.record_message(
                thread_id=thread_id,
                workspace_id=workspace_id,
                **record,
            )

    def _message_to_record(self, message: Any, *, fallback_id: str) -> dict | None:
        role = self._message_role(message)
        if role not in {"human", "ai", "tool"}:
            return None

        message_id = getattr(message, "id", None) or self._dict_get(message, "id") or fallback_id
        content = getattr(message, "content", None)
        if content is None:
            content = self._dict_get(message, "content", "")

        return {
            "message_id": str(message_id),
            "role": role,
            "type": role,
            "content": content,
            "tool_calls": self._message_tool_calls(message),
            "tool_call_id": getattr(message, "tool_call_id", None) or self._dict_get(message, "tool_call_id"),
            "name": getattr(message, "name", None) or self._dict_get(message, "name"),
            "additional_kwargs": getattr(message, "additional_kwargs", None)
            or self._dict_get(message, "additional_kwargs", {}),
            "response_metadata": getattr(message, "response_metadata", None)
            or self._dict_get(message, "response_metadata", {}),
        }

    @staticmethod
    def _dict_get(message: Any, key: str, default: Any = None) -> Any:
        return message.get(key, default) if isinstance(message, dict) else default

    def _message_role(self, message: Any) -> str:
        if isinstance(message, BaseMessage):
            return message.type
        raw_type = self._dict_get(message, "type") or self._dict_get(message, "role")
        if raw_type == "user":
            return "human"
        if raw_type == "assistant":
            return "ai"
        return str(raw_type or "")

    def _message_tool_calls(self, message: Any) -> list:
        tool_calls = getattr(message, "tool_calls", None)
        if tool_calls is None:
            tool_calls = self._dict_get(message, "tool_calls")
        if not isinstance(tool_calls, list):
            return []
        normalized = []
        for tool_call in tool_calls:
            if not isinstance(tool_call, dict):
                continue
            normalized.append(
                {
                    "id": tool_call.get("id"),
                    "name": tool_call.get("name"),
                    "args": tool_call.get("args", {}),
                }
            )
        return normalized

    def _is_summarization_message(self, message: Any) -> bool:
        additional_kwargs = getattr(message, "additional_kwargs", None)
        if additional_kwargs is None:
            additional_kwargs = self._dict_get(message, "additional_kwargs", {})
        return (
            isinstance(additional_kwargs, dict)
            and additional_kwargs.get("lc_source") == "summarization"
        )


class MessageHistoryMiddleware(AgentMiddleware):
    def __init__(self, callback: MessageHistoryCallback):
        self.callback = callback

    async def abefore_agent(self, state: dict, runtime) -> None:
        await self._record_state_messages(state, runtime)

    async def aafter_agent(self, state: dict, runtime) -> None:
        await self._record_state_messages(state, runtime)

    async def _record_state_messages(self, state: dict, runtime) -> None:
        try:
            await self.callback.record_messages(
                thread_id=self._thread_id(runtime),
                workspace_id=state.get("workspace_id"),
                messages=state.get("messages", []),
            )
        except Exception:
            logger.exception("Failed to persist message history")

    def _thread_id(self, runtime) -> str | None:
        execution_info = getattr(runtime, "execution_info", None)
        thread_id = getattr(execution_info, "thread_id", None)
        if thread_id:
            return str(thread_id)

        context = getattr(runtime, "context", None)
        if isinstance(context, dict) and context.get("thread_id"):
            return str(context["thread_id"])

        config = getattr(runtime, "config", None) or {}
        configurable = config.get("configurable", {}) if isinstance(config, dict) else {}
        thread_id = configurable.get("thread_id")
        return str(thread_id) if thread_id else None
