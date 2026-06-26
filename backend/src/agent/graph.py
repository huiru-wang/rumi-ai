import logging
import os

from langchain_openai import ChatOpenAI
from langchain.agents import create_agent

from src.agent.message_history import MessageHistoryCallback
from src.agent.state import MainAgentState
from src.app_context import AppContext
from src.middlewares import create_middlewares
from src.tools import create_tools

logger = logging.getLogger(__name__)


def create_graph(ctx: AppContext):
    # --- Model ---
    model = ChatOpenAI(
        model=os.getenv("MAIN_MODEL"),
        api_key=os.getenv("OPENAI_API_KEY"),
        base_url=os.getenv("OPENAI_API_BASE"),
        streaming=True,
        extra_body={"enable_thinking": True},
    )
    message_history_callback = MessageHistoryCallback(ctx.db)
    model.callbacks = [*(model.callbacks or []), message_history_callback]

    # --- Tools & Middlewares ---
    tools = create_tools(ctx)
    middlewares = create_middlewares(ctx, message_history_callback)

    return create_agent(
        model=model,
        tools=tools,
        state_schema=MainAgentState,
        middleware=middlewares,
    )


def _make_default_graph():
    """Create a default graph instance for langgraph serve."""
    from dotenv import load_dotenv

    load_dotenv()
    return create_graph(AppContext.from_env())


graph = _make_default_graph()
