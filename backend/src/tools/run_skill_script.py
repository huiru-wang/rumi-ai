"""run_skill_script — 让 Agent 执行 Skill 目录下的脚本，无需感知绝对路径。

设计原则：
- Agent 只需提供 skill_name 和脚本文件名，SKILL_DIR 是工具的内在知识
- 只允许执行 skills/{skill_name}/scripts/ 目录下的脚本，防止越权
- 支持 .sh（bash）、.py（python）、.ts（npx tsx）、.js（node）
"""

import asyncio
import logging
from pathlib import Path
from typing import Annotated

from langchain_core.tools import tool

from src.managers.skill_manager import SkillManager

logger = logging.getLogger(__name__)

# 脚本类型 → 解释器命令（列表形式，支持带参数的解释器）
_INTERPRETER_MAP: dict[str, list[str]] = {
    ".sh": ["bash"],
    ".py": ["python"],
    ".js": ["node"],
    ".ts": ["npx", "tsx"],
}

_MAX_OUTPUT_CHARS = 8000


def create_run_skill_script_tool(skill_manager: SkillManager):
    available_skills = [s["name"] for s in skill_manager.list_skills()]
    skill_list = ", ".join(available_skills) if available_skills else "(无可用 Skill)"

    supported_types = ", ".join(_INTERPRETER_MAP.keys())

    @tool(description=(
        f"执行 Skill 目录下 scripts/ 中的脚本。\n"
        f"只能执行已注册 Skill 的 scripts/ 目录内的脚本，不能访问其他路径。\n"
        f"支持脚本类型：{supported_types}\n"
        f"可用 Skill：{skill_list}"
    ))
    async def run_skill_script(
        skill_name: str,
        script: Annotated[str, "脚本文件名，如 export-pdf.sh（只需文件名，无需路径）"],
        args: Annotated[list[str], "传给脚本的参数列表，如 [\"/data/outputs/deck.html\"]"] = [],
        timeout: Annotated[int, "超时时间（秒），默认 120"] = 120,
        **kwargs,
    ) -> str:
        """执行 Skill 目录下 scripts/ 中的脚本。

        脚本路径由工具内部解析，Agent 无需知道绝对路径。
        支持 .sh（bash）、.py（python）、.js（node）、.ts（npx tsx）。

        Args:
            skill_name: Skill 名称，如 "ppt"
            script: 脚本文件名，如 "export-pdf.sh" 或 "extract-pptx.py"
            args: 传给脚本的参数列表，如 ["/data/outputs/deck.html", "output.pdf"]
            timeout: 执行超时秒数，默认 120
        """
        # 1. 解析 skill 目录
        skill_meta = skill_manager._skills.get(skill_name)
        if not skill_meta:
            available = [s["name"] for s in skill_manager.list_skills()]
            return f"错误：Skill '{skill_name}' 不存在。可用 Skill：{', '.join(available)}"

        skill_dir = Path(skill_meta.file_path).parent
        scripts_dir = skill_dir / "scripts"

        if not scripts_dir.is_dir():
            return f"错误：Skill '{skill_name}' 没有 scripts/ 目录"

        # 2. 安全检查：脚本必须在 scripts/ 目录下，防止路径穿越
        script_path = (scripts_dir / script).resolve()
        if scripts_dir.resolve() not in script_path.parents:
            return "错误：脚本路径越界，只允许访问 scripts/ 目录内的脚本"

        if not script_path.exists() or not script_path.is_file():
            available_scripts = sorted(f.name for f in scripts_dir.iterdir() if f.is_file())
            return (
                f"错误：脚本 '{script}' 不存在于 Skill '{skill_name}' 的 scripts/ 目录。\n"
                f"可用脚本：{', '.join(available_scripts) or '（无）'}"
            )

        # 3. 根据扩展名选择解释器
        suffix = script_path.suffix.lower()
        interpreter = _INTERPRETER_MAP.get(suffix)
        if not interpreter:
            return (
                f"错误：不支持的脚本类型 '{suffix}'。"
                f"支持的类型：{', '.join(_INTERPRETER_MAP.keys())}"
            )

        # 4. 组装命令并执行
        cmd = interpreter + [str(script_path)] + [str(a) for a in args]

        logger.info(
            "[run_skill_script] executing: skill=%s script=%s args=%s timeout=%s",
            skill_name, script, args, timeout,
        )

        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(skill_dir),  # 工作目录为 skill 根目录，脚本内相对路径可正确解析
        )

        try:
            stdout, stderr = await asyncio.wait_for(
                process.communicate(), timeout=timeout
            )
        except asyncio.TimeoutError:
            process.kill()
            await process.wait()
            return f"错误：脚本执行超时（{timeout} 秒）\n命令：{' '.join(cmd)}"

        output = stdout.decode("utf-8", errors="replace").strip()
        errors = stderr.decode("utf-8", errors="replace").strip()

        # 5. 截断超长输出，防止撑满 context
        if len(output) > _MAX_OUTPUT_CHARS:
            output = output[:_MAX_OUTPUT_CHARS] + f"\n…（输出已截断，共 {len(output)} 字符）"

        if process.returncode != 0:
            logger.error(
                "[run_skill_script] failed: skill=%s script=%s exit=%s stderr=%s",
                skill_name, script, process.returncode, errors[:500],
            )
            parts = [f"脚本执行失败（exit code {process.returncode}）\n命令：{' '.join(cmd)}"]
            if output:
                parts.append(f"stdout:\n{output}")
            if errors:
                parts.append(f"stderr:\n{errors}")
            return "\n".join(parts)

        logger.info(
            "[run_skill_script] success: skill=%s script=%s output=%d chars",
            skill_name, script, len(output),
        )
        return output or errors or "(脚本执行成功，无输出)"

    return run_skill_script
