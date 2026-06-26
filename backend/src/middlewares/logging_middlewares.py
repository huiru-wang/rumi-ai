import logging

from langchain.agents.middleware import AgentMiddleware
from langgraph.runtime import Runtime

logger = logging.getLogger(__name__)


class LoggingMiddleware(AgentMiddleware):
    """当前日志中间件没什么用"""

    def before_agent(self, state: dict, runtime: Runtime) -> None:
        pass

    def after_agent(self, state: dict, runtime: Runtime) -> None:
        pass

    async def awrap_model_call(self, request, handler):
        workspace_id = request.state.get("workspace_id", "default")
        ppt_style = request.state.get("ppt_style", "")
        voice_id = request.state.get("voice_id", "")
        current_ppt_task_id = request.state.get("current_ppt_task_id", "")
        logger.info(
            f"""
            [LoggingMiddleware] before_model | 
            workspaceId={workspace_id} | 
            ppt_style={ppt_style} | 
            voice_id={voice_id} | 
            current_ppt_task_id={current_ppt_task_id}
            """
        )
        return await handler(request)