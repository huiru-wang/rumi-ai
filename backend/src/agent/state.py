from langchain.agents import AgentState


class MainAgentState(AgentState):
    """Extended agent state with workspace context."""
    workspace_id: str
    ppt_style: str  # 当前选中的PPT风格
    voice_id: str  # 当前选中的TTS声音
    current_ppt_task_id: str  # 当前正在处理的PPT任务ID
