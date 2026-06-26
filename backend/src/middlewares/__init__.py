import os

from src.agent.message_history import MessageHistoryCallback, MessageHistoryMiddleware
from src.app_context import AppContext
from langchain_openai import ChatOpenAI
from src.middlewares.context_inject_middleware import ContextInjectMiddleware
from src.middlewares.logging_middlewares import LoggingMiddleware
from src.middlewares.model_message_sanitizer import ModelMessageSanitizerMiddleware
from src.middlewares.summarization import SummarizationMiddleware

__all__ = ["create_middlewares"]


def create_middlewares(
    ctx: AppContext,
    message_history_callback: MessageHistoryCallback,
) -> list:
    """中间件统一注册, 注意顺序, 遵循洋葱模型"""
    summary_model = ChatOpenAI(
        model=os.getenv("SUMMARIZATION_MODEL"),
        api_key=os.getenv("SUMMARIZATION_API_KEY"),
        base_url=os.getenv("SUMMARIZATION_API_BASE"),
    )
    return [
        ContextInjectMiddleware(ctx.db),
        MessageHistoryMiddleware(message_history_callback),
        ModelMessageSanitizerMiddleware(),
        SummarizationMiddleware(
            model=summary_model,
            trigger=("tokens", 40000),
            keep=("messages", 8),
            trim_tokens_to_summarize=12000,
            min_messages_since_summary=8,
        ),
        LoggingMiddleware(),
    ]
