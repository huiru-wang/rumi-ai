import asyncio
import inspect
import logging
import uuid
from contextvars import ContextVar, Token, copy_context
from typing import Any, Awaitable, Callable


DEFAULT_CONTEXT_VALUE = "-"

trace_id_var: ContextVar[str] = ContextVar("trace_id", default=DEFAULT_CONTEXT_VALUE)
request_id_var: ContextVar[str] = ContextVar("request_id", default=DEFAULT_CONTEXT_VALUE)
user_id_var: ContextVar[str] = ContextVar("user_id", default=DEFAULT_CONTEXT_VALUE)
workspace_id_var: ContextVar[str] = ContextVar("workspace_id", default=DEFAULT_CONTEXT_VALUE)

_LOG_RECORD_FACTORY_INSTALLED = False


def new_trace_id() -> str:
    return f"trc_{uuid.uuid4().hex}"


def new_request_id() -> str:
    return f"req_{uuid.uuid4().hex}"


def get_log_context() -> dict[str, str]:
    return {
        "trace_id": trace_id_var.get(),
        "request_id": request_id_var.get(),
        "user_id": user_id_var.get(),
        "workspace_id": workspace_id_var.get(),
    }


def set_log_context(
    *,
    trace_id: str | None = None,
    request_id: str | None = None,
    user_id: str | None = None,
    workspace_id: str | None = None,
) -> list[tuple[ContextVar[str], Token[str]]]:
    tokens: list[tuple[ContextVar[str], Token[str]]] = []
    if trace_id is not None:
        tokens.append((trace_id_var, trace_id_var.set(trace_id or DEFAULT_CONTEXT_VALUE)))
    if request_id is not None:
        tokens.append((request_id_var, request_id_var.set(request_id or DEFAULT_CONTEXT_VALUE)))
    if user_id is not None:
        tokens.append((user_id_var, user_id_var.set(user_id or DEFAULT_CONTEXT_VALUE)))
    if workspace_id is not None:
        tokens.append((workspace_id_var, workspace_id_var.set(workspace_id or DEFAULT_CONTEXT_VALUE)))
    return tokens


def reset_log_context(tokens: list[tuple[ContextVar[str], Token[str]]]) -> None:
    for var, token in reversed(tokens):
        var.reset(token)


def configure_log_record_context() -> None:
    """Inject request/trace context into every LogRecord.

    This keeps business code low-intrusion: modules can keep using normal
    ``logger.info(...)`` calls while formatters can reference these fields.
    """
    global _LOG_RECORD_FACTORY_INSTALLED
    if _LOG_RECORD_FACTORY_INSTALLED:
        return

    old_factory = logging.getLogRecordFactory()

    def record_factory(*args: Any, **kwargs: Any) -> logging.LogRecord:
        record = old_factory(*args, **kwargs)
        context = get_log_context()
        record.trace_id = context["trace_id"]
        record.request_id = context["request_id"]
        record.user_id = context["user_id"]
        record.workspace_id = context["workspace_id"]
        return record

    logging.setLogRecordFactory(record_factory)
    _LOG_RECORD_FACTORY_INSTALLED = True


def add_context_task(background_tasks: Any, func: Callable[..., Any], *args: Any, **kwargs: Any) -> None:
    """Add a FastAPI BackgroundTasks item with the current log context copied."""
    context = get_log_context()

    async def runner() -> Any:
        tokens = set_log_context(**context)
        try:
            result = func(*args, **kwargs)
            if inspect.isawaitable(result):
                return await result
            return result
        finally:
            reset_log_context(tokens)

    background_tasks.add_task(runner)


def create_context_task(coro: Awaitable[Any]) -> asyncio.Task[Any]:
    """Create an asyncio task that inherits the current context explicitly."""
    return asyncio.create_task(coro, context=copy_context())
