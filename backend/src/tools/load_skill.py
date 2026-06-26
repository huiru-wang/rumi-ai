import json
import logging
from pathlib import Path
from typing import Annotated

from langchain_core.tools import tool

from src.managers.skill_manager import SkillManager

logger = logging.getLogger(__name__)


def create_load_skill_tool(skill_manager: SkillManager):
    """Create the load_skill tool with dynamic docstring listing available skills.

    Follows the LangChain Skills pattern: a single tool whose docstring
    contains all available skill names + descriptions. Agent sees the list
    via the tool schema and loads on-demand.
    """
    available = skill_manager.list_skills()
    skill_list = "\n".join(
        f"    - {s['name']}: {s['description']}" for s in available
    )

    dynamic_description = (
        "加载技能提示或技能内的文件。\n\n"
        "可用技能：\n"
        + (skill_list if skill_list else "    (no skills registered)")
        + "\n\n"
        "调用时不带 file_paths，返回技能主提示 + linked_files（仅包含技能目录中真实存在的 references/scripts/assets 等文件）。\n"
        "调用时带 file_paths（最多5 个），批量加载文件。\n\n"
        "file_paths 格式：['references/themes.md', 'scripts/save_and_output.py', 'assets/themes/tokyo-night.css']"
    )

    @tool(description=dynamic_description)
    def load_skill(
        skill_name: str,
        file_paths: Annotated[
            list[str],
            "要加载的文件路径列表，最多5 个，如 [\"references/docs.md\", \"scripts/save_and_output.py\", \"assets/theme.css\"]"
        ] = [],
        **kwargs,
    ) -> str:
        """加载技能提示或技能内的文件。

        Args:
            skill_name: 技能名称。
            file_paths: 要加载的技能引用、资源、脚本等文件路径列表，最多5个。必需给出技能的相对路径，如 "references/docs.md"，如果是在技能根目录，则为"docs.md"。
        """
        if len(file_paths) > 5:
            return json.dumps({
                "success": False,
                "error": "最多只能一次加载 5 个文件",
            })

        # Get linked_files for this skill
        linked_files = skill_manager.list_linked_files(skill_name)
        skill_dir = None
        skill_meta = skill_manager._skills.get(skill_name)
        if skill_meta:
            skill_dir = str(Path(skill_meta.file_path).parent)

        # If no file_paths, return skill content + linked_files
        if not file_paths:
            content = skill_manager.load_skill(skill_name)
            if content is None:
                available_names = [s["name"] for s in skill_manager.list_skills()]
                logger.warning(
                    "[Tool:load_skill] skill not found: %s, available=%s",
                    skill_name, available_names,
                )
                return json.dumps({
                    "success": False,
                    "error": f"Skill '{skill_name}' not found. Available: {', '.join(available_names)}",
                })

            # Substitute ${SKILL_DIR} with actual skill directory path
            if skill_dir and "${SKILL_DIR}" in content:
                content = content.replace("${SKILL_DIR}", skill_dir)

            logger.info(
                "[Tool:load_skill] skill loaded: %s, %d chars, skill_dir=%s",
                skill_name, len(content), skill_dir,
            )
            return json.dumps({
                "success": True,
                "name": skill_name,
                "content": content,
                "linked_files": linked_files,
            })

        # Batch load files
        logger.info(
            "[Tool:load_skill] batch loading: skill=%s, files=%s",
            skill_name, file_paths,
        )
        files_content = skill_manager.load_files(skill_name, file_paths)

        # Check for missing files
        missing = [p for p, c in files_content.items() if c is None]
        if missing:
            logger.warning(
                "[Tool:load_skill] some files not found: skill=%s, missing=%s",
                skill_name, missing,
            )

        result = {
            "success": True,
            "name": skill_name,
            "files": files_content,
            "missing_files": missing if missing else None,
            "linked_files": linked_files,
        }
        return json.dumps(result)

    return load_skill
