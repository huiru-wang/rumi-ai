import logging

from langchain.agents.middleware import AgentMiddleware, ModelResponse
from langchain_core.messages import AIMessage, ToolMessage
from langgraph.errors import GraphBubbleUp

from src.exceptions import BusinessError, BusinessErrorCode

logger = logging.getLogger(__name__)


def classify_agent_error(exc: BaseException) -> BusinessError:
    """Map provider/runtime exceptions to the shared business error enum."""
    status_code = getattr(exc, "status_code", None)
    text = f"{type(exc).__name__}: {exc}".lower()

    if status_code == 401 or "authentication" in text or "api key" in text:
        code = BusinessErrorCode.AGENT_MODEL_AUTH
    elif "quota" in text or "billing" in text or "insufficient" in text or status_code == 402:
        code = BusinessErrorCode.AGENT_MODEL_QUOTA
    elif status_code == 429 or "rate limit" in text or "ratelimit" in text:
        code = BusinessErrorCode.AGENT_MODEL_RATE_LIMIT
    elif "timeout" in text or "timed out" in text:
        code = BusinessErrorCode.AGENT_MODEL_TIMEOUT
    elif "connection" in text or "network" in text or "dns" in text or status_code in {502, 503, 504}:
        code = BusinessErrorCode.AGENT_MODEL_CONNECTION
    elif status_code == 400 or "badrequest" in text or "context length" in text:
        code = BusinessErrorCode.AGENT_MODEL_BAD_REQUEST
    elif "recursion" in text or "recursion_limit" in text:
        code = BusinessErrorCode.AGENT_RECURSION_LIMIT
    else:
        code = BusinessErrorCode.AGENT_UNKNOWN
    return BusinessError(code)


def _error_metadata(error: BusinessError) -> dict:
    return {"rumi_error": error.to_dict()}


class AgentErrorMiddleware(AgentMiddleware):
    """Convert Agent runtime failures into shared business errors."""

    async def awrap_model_call(self, request, handler):
        try:
            return await handler(request)
        except GraphBubbleUp:
            raise
        except Exception as exc:
            error = exc if isinstance(exc, BusinessError) else classify_agent_error(exc)
            logger.error(
                "[AgentErrorMiddleware] model_call_failed | workspace=%s | code=%s | type=%s",
                request.state.get("workspace_id", "default"),
                error.code,
                error.error.name,
                exc_info=True,
            )
            return ModelResponse(
                result=[
                    AIMessage(
                        content=error.message,
                        additional_kwargs=_error_metadata(error),
                    )
                ]
            )

    async def awrap_tool_call(self, request, handler):
        try:
            return await handler(request)
        except GraphBubbleUp:
            raise
        except Exception as exc:
            tool_name = request.tool_call.get("name", "unknown")
            tool_call_id = request.tool_call.get("id", "")
            error = exc if isinstance(exc, BusinessError) else BusinessError(BusinessErrorCode.AGENT_TOOL_FAILED)
            logger.error(
                "[AgentErrorMiddleware] tool_call_failed | tool=%s | tool_call_id=%s | code=%s",
                tool_name,
                tool_call_id,
                error.code,
                exc_info=True,
            )
            return ToolMessage(
                content=error.message,
                tool_call_id=tool_call_id,
                name=tool_name,
                additional_kwargs=_error_metadata(error),
            )
