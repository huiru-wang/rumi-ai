from langchain_core.messages import AIMessage
from langgraph.errors import GraphInterrupt

from src.middlewares.agent_error_middleware import (
    ERR_AGENT_MODEL_AUTH,
    AgentErrorMiddleware,
    classify_agent_error,
)


class FakeAuthError(Exception):
    status_code = 401


class FakeRequest:
    state = {"workspace_id": "ws-test"}


async def test_classify_agent_error_maps_authentication_failure():
    error = classify_agent_error(FakeAuthError("invalid api key"))

    assert error.code == ERR_AGENT_MODEL_AUTH
    assert error.type == "model_auth_error"
    assert error.retryable is False
    assert "认证" in error.message


async def test_agent_error_middleware_returns_friendly_ai_message():
    async def failing_handler(_request):
        raise FakeAuthError("api key is invalid")

    response = await AgentErrorMiddleware().awrap_model_call(
        FakeRequest(),
        failing_handler,
    )

    assert len(response.result) == 1
    message = response.result[0]
    assert isinstance(message, AIMessage)
    assert "api key is invalid" not in message.content.lower()
    assert message.additional_kwargs["rumi_error"]["code"] == ERR_AGENT_MODEL_AUTH


async def test_agent_error_middleware_preserves_graph_interrupt():
    interrupt = GraphInterrupt()

    async def interrupting_handler(_request):
        raise interrupt

    try:
        await AgentErrorMiddleware().awrap_tool_call(
            FakeRequest(),
            interrupting_handler,
        )
    except GraphInterrupt as exc:
        assert exc is interrupt
    else:
        raise AssertionError("GraphInterrupt should bubble up")
