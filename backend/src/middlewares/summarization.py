from typing import Any

from langchain.agents.middleware import SummarizationMiddleware
from langchain_core.messages import AnyMessage, HumanMessage
from langchain_core.messages.utils import get_buffer_string
from langgraph.constants import TAG_NOSTREAM


class SummarizationMiddleware(SummarizationMiddleware):
    """Summarization with UI-safe markers and a simple cooldown."""

    def __init__(
        self,
        *args,
        min_messages_since_summary: int = 8,
        **kwargs,
    ) -> None:
        super().__init__(*args, **kwargs)
        self.min_messages_since_summary = min_messages_since_summary
        # Create a summary model with TAG_NOSTREAM to prevent streaming tokens to UI
        existing_tags = list(
            (getattr(self.model, "config", None) or {}).get("tags") or []
        )
        merged_tags = (
            [*existing_tags, TAG_NOSTREAM]
            if TAG_NOSTREAM not in existing_tags
            else existing_tags
        )
        self._summary_model = self.model.with_config(tags=merged_tags)

    def _should_summarize(self, messages: list[AnyMessage], total_tokens: int) -> bool:
        if not super()._should_summarize(messages, total_tokens):
            return False

        last_summary_index = self._last_summary_index(messages)
        if last_summary_index is None:
            return True

        messages_since_summary = len(messages) - last_summary_index - 1
        return messages_since_summary >= self.min_messages_since_summary

    @staticmethod
    def _build_new_messages(summary: str) -> list[HumanMessage]:
        return [
            HumanMessage(
                content=f"Here is a summary of the conversation to date:\n\n{summary}",
                name="summary",
                additional_kwargs={
                    "lc_source": "summarization",
                    "message_hidden": True,
                },
            )
        ]

    def _create_summary(self, messages_to_summarize: list[AnyMessage]) -> str:
        """Generate summary using _summary_model with TAG_NOSTREAM."""
        if not messages_to_summarize:
            return "No previous conversation history."

        trimmed_messages = self._trim_messages_for_summary(messages_to_summarize)
        if not trimmed_messages:
            return "Previous conversation was too long to summarize."

        formatted_messages = get_buffer_string(trimmed_messages)

        try:
            response = self._summary_model.invoke(
                self.summary_prompt.format(messages=formatted_messages).rstrip(),
                config={"metadata": {"lc_source": "summarization"}},
            )
            return response.text.strip()
        except Exception as e:
            return f"Error generating summary: {e!s}"

    async def _acreate_summary(self, messages_to_summarize: list[AnyMessage]) -> str:
        """Generate summary using _summary_model with TAG_NOSTREAM (async)."""
        if not messages_to_summarize:
            return "No previous conversation history."

        trimmed_messages = self._trim_messages_for_summary(messages_to_summarize)
        if not trimmed_messages:
            return "Previous conversation was too long to summarize."

        formatted_messages = get_buffer_string(trimmed_messages)

        try:
            response = await self._summary_model.ainvoke(
                self.summary_prompt.format(messages=formatted_messages).rstrip(),
                config={"metadata": {"lc_source": "summarization"}},
            )
            return response.text.strip()
        except Exception as e:
            return f"Error generating summary: {e!s}"

    @staticmethod
    def _last_summary_index(messages: list[AnyMessage]) -> int | None:
        for index in range(len(messages) - 1, -1, -1):
            if _is_summary_message(messages[index]):
                return index
        return None


def _is_summary_message(message: Any) -> bool:
    # 1. name field check (most reliable, first-class field)
    if getattr(message, "name", None) == "summary":
        return True
    if isinstance(message, dict) and message.get("name") == "summary":
        return True
    # 2. additional_kwargs fallback
    additional_kwargs = getattr(message, "additional_kwargs", None)
    if additional_kwargs is None and isinstance(message, dict):
        additional_kwargs = message.get("additional_kwargs")
    return (
        isinstance(additional_kwargs, dict)
        and additional_kwargs.get("lc_source") == "summarization"
    )
