import logging
from collections.abc import Awaitable, Callable
from typing import Any

from langchain.agents.middleware import AgentMiddleware
from langchain_core.callbacks import AsyncCallbackHandler
from langchain_core.messages import AIMessage, BaseMessage, ToolMessage

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
        run_id: str | None,
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
                run_id=run_id,
                **record,
            )

    def _message_to_record(self, message: Any, *, fallback_id: str) -> dict | None:
        role = self._message_role(message)
        if role not in {"human", "ai", "tool"}:
            return None

        tool_call_id = getattr(message, "tool_call_id", None) or self._dict_get(
            message, "tool_call_id"
        )
        message_id = (
            f"tool:{tool_call_id}"
            if role == "tool" and tool_call_id
            else getattr(message, "id", None) or self._dict_get(message, "id") or fallback_id
        )
        content = getattr(message, "content", None)
        if content is None:
            content = self._dict_get(message, "content", "")

        return {
            "message_id": str(message_id),
            "role": role,
            "type": role,
            "content": content,
            "tool_calls": self._message_tool_calls(message),
            "tool_call_id": tool_call_id,
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
        await self._record_messages(state, runtime, self._current_user_messages(state))

    async def aafter_model(self, state: dict, runtime) -> None:
        await self._record_messages(state, runtime, self._current_ai_messages(state))

    async def awrap_tool_call(
        self,
        request,
        handler: Callable[[Any], Awaitable[ToolMessage | Any]],
    ) -> ToolMessage | Any:
        result = await handler(request)
        if isinstance(result, ToolMessage):
            await self._record_messages(request.state, request.runtime, [result])
        return result

    async def aafter_agent(self, state: dict, runtime) -> None:
        await self._record_state_messages(state, runtime)

    async def _record_state_messages(self, state: dict, runtime) -> None:
        await self._record_messages(state, runtime, state.get("messages", []))

    async def _record_messages(self, state: dict, runtime, messages: list[Any]) -> None:
        try:
            await self.callback.record_messages(
                thread_id=self._thread_id(runtime),
                workspace_id=state.get("workspace_id"),
                run_id=self._run_id(runtime),
                messages=messages,
            )
        except Exception:
            logger.exception("Failed to persist message history")

    def _current_user_messages(self, state: dict) -> list[Any]:
        messages = state.get("messages", [])
        if not messages:
            return []
        last = messages[-1]
        return [last] if self.callback._message_role(last) == "human" else []

    def _current_ai_messages(self, state: dict) -> list[Any]:
        messages = state.get("messages", [])
        if not messages:
            return []
        last = messages[-1]
        if isinstance(last, AIMessage):
            return [last]
        if isinstance(last, dict) and self.callback._message_role(last) == "ai":
            return [last]
        return []

    def _run_id(self, runtime) -> str | None:
        execution_info = getattr(runtime, "execution_info", None)
        run_id = getattr(execution_info, "run_id", None)
        return str(run_id) if run_id else None

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
