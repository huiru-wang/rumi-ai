import logging
from dataclasses import dataclass

from langchain.agents.middleware import AgentMiddleware, ModelResponse
from langchain_core.messages import AIMessage, ToolMessage
from langgraph.errors import GraphBubbleUp

logger = logging.getLogger(__name__)


# Error codes: Agent / LangGraph / Model (7xxxx)
ERR_AGENT_MODEL_AUTH = 70001
ERR_AGENT_MODEL_QUOTA = 70002
ERR_AGENT_MODEL_RATE_LIMIT = 70003
ERR_AGENT_MODEL_TIMEOUT = 70004
ERR_AGENT_MODEL_CONNECTION = 70005
ERR_AGENT_MODEL_BAD_REQUEST = 70006
ERR_AGENT_TOOL_FAILED = 70007
ERR_AGENT_INTERRUPT_FAILED = 70008
ERR_AGENT_RECURSION_LIMIT = 70009
ERR_AGENT_UNKNOWN = 79999


@dataclass(frozen=True)
class AgentError:
    code: int
    type: str
    message: str
    retryable: bool


def classify_agent_error(exc: BaseException) -> AgentError:
    """Map provider/runtime exceptions to stable user-facing Agent errors."""
    exc_name = type(exc).__name__
    status_code = getattr(exc, "status_code", None)
    text = f"{exc_name}: {exc}".lower()

    if status_code == 401 or "authentication" in text or "api key" in text:
        return AgentError(
            ERR_AGENT_MODEL_AUTH,
            "model_auth_error",
            "Rumi-AI服务认证异常，请联系管理员检查 API Key 配置后重试。",
            False,
        )

    if "quota" in text or "billing" in text or "insufficient" in text:
        return AgentError(
            ERR_AGENT_MODEL_QUOTA,
            "model_quota_error",
            "Rumi-AI服务异常，请稍后重试或联系管理员检查额度。",
            False,
        )

    if status_code == 429 or "rate limit" in text or "ratelimit" in text:
        return AgentError(
            ERR_AGENT_MODEL_RATE_LIMIT,
            "model_rate_limit_error",
            "Rumi-AI服务当前请求过于频繁，请稍后再试。",
            True,
        )

    if "timeout" in text or "timed out" in text:
        return AgentError(
            ERR_AGENT_MODEL_TIMEOUT,
            "model_timeout_error",
            "Rumi-AI服务响应超时，请稍后重试。",
            True,
        )

    if "connection" in text or "network" in text or "dns" in text or status_code in {502, 503, 504}:
        return AgentError(
            ERR_AGENT_MODEL_CONNECTION,
            "model_connection_error",
            "暂时无法连接Rumi-AI，请稍后重试。",
            True,
        )

    if status_code == 400 or "badrequest" in text or "context length" in text:
        return AgentError(
            ERR_AGENT_MODEL_BAD_REQUEST,
            "model_bad_request_error",
            "本次请求内容过长或格式不兼容，请缩短输入后重试。",
            False,
        )

    if "recursion" in text or "recursion_limit" in text:
        return AgentError(
            ERR_AGENT_RECURSION_LIMIT,
            "agent_recursion_limit",
            "任务步骤过多，已自动停止。你可以拆成更小的请求继续。",
            False,
        )

    return AgentError(
        ERR_AGENT_UNKNOWN,
        "agent_unknown_error",
        "Rumi-AI对话服务暂时不可用，请稍后再试。",
        True,
    )


def _error_metadata(error: AgentError) -> dict:
    return {
        "rumi_error": {
            "code": error.code,
            "type": error.type,
            "message": error.message,
            "retryable": error.retryable,
        }
    }


class AgentErrorMiddleware(AgentMiddleware):
    """Convert expected Agent runtime errors into stable, friendly messages."""

    async def awrap_model_call(self, request, handler):
        try:
            return await handler(request)
        except GraphBubbleUp:
            raise
        except Exception as exc:
            error = classify_agent_error(exc)
            logger.error(
                "[AgentErrorMiddleware] model_call_failed | workspace=%s | code=%s | type=%s",
                request.state.get("workspace_id", "default"),
                error.code,
                error.type,
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
        except Exception:
            tool_name = request.tool_call.get("name", "unknown")
            tool_call_id = request.tool_call.get("id", "")
            logger.error(
                "[AgentErrorMiddleware] tool_call_failed | tool=%s | tool_call_id=%s",
                tool_name,
                tool_call_id,
                exc_info=True,
            )
            error = AgentError(
                ERR_AGENT_TOOL_FAILED,
                "agent_tool_failed",
                "执行工具时出现问题，请稍后重试。",
                True,
            )
            return ToolMessage(
                content=error.message,
                tool_call_id=tool_call_id,
                name=tool_name,
                additional_kwargs=_error_metadata(error),
            )
