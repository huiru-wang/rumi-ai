from src.app_context import AppContext
from src.managers.tts_manager import TTSManager
from src.tools.clarify_form import clarify_form
from src.tools.get_ppt_detail import create_get_ppt_detail_tool
from src.tools.get_style_template import create_get_style_template_tool
from src.tools.load_skill import create_load_skill_tool
from src.tools.rag_search import create_rag_search_tool
from src.tools.run_skill_script import create_run_skill_script_tool
from src.tools.save_narration import create_save_narration_tool
from src.tools.save_ppt import create_save_ppt_tool

__all__ = ["create_tools"]


def create_tools(ctx: AppContext) -> list:
    """Create all agent tools."""
    tts_service = TTSManager()
    return [
        clarify_form,
        create_rag_search_tool(ctx.vector_store),
        create_load_skill_tool(ctx.skill_manager),
        create_save_ppt_tool(ctx.db, ctx.file_store),
        create_run_skill_script_tool(ctx.skill_manager),
        create_get_ppt_detail_tool(ctx.db),
        create_get_style_template_tool(ctx.db),
        create_save_narration_tool(ctx.db, ctx.file_store, tts_service),
    ]
