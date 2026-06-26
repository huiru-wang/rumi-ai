"""
Terminal tool — lets the agent execute shell commands.
暂时不使用，如果后续需要使用，完整构建Sandbox沙箱模块后再启用
"""

import asyncio
import logging
import os
import re
import shlex
from typing import Annotated, Optional

from langchain_core.tools import tool

logger = logging.getLogger(__name__)

# Shell metacharacters that are dangerous in path contexts
_WORKDIR_META_CHARS = re.compile(r"[;&|`$(){}[\]!?*<>~\"\\]")
# Exit codes that are NOT errors (semantic success)
_SEMANTIC_SUCCESS_CODES = {0, 1}  # grep returns 1 when no match, find returns 1 when not found


def _validate_workdir(workdir: Optional[str]) -> Optional[str]:
    """Validate workdir is safe. Returns validated path or None."""
    if not workdir:
        return None
    # Must be absolute path
    if not os.path.isabs(workdir):
        raise ValueError(f"workdir must be an absolute path, got: {workdir}")
    # Check for shell metacharacters
    if _WORKDIR_META_CHARS.search(workdir):
        raise ValueError(f"workdir contains unsafe characters: {workdir}")
    # Must exist and be a directory
    if not os.path.isdir(workdir):
        raise ValueError(f"workdir does not exist or is not a directory: {workdir}")
    return workdir


def _interpret_exit_code(returncode: int, command: str) -> str:
    """Interpret exit code semantically.

    Returns a human-readable interpretation of the exit code.
    """
    if returncode == 0:
        return "success"

    # Semantic success codes (command succeeded in its intent, even if exit code != 0)
    # grep returns 1 when no matches found — not an error
    if returncode == 1 and ("grep" in command or "rg" in command or "find" in command.split()[0]):
        return "no matches found (semantic success)"

    # find returns 1 when no files found — not an error
    if returncode == 1 and command.strip().startswith("find"):
        return "no matches found (semantic success)"

    return f"exit code {returncode}"


@tool
async def terminal(
    command: str,
    *,
    workdir: Annotated[Optional[str], "工作目录（必须是绝对路径）"] = None,
    timeout: Annotated[Optional[int], "超时时间（秒），默认 60 秒"] = 60,
    background: Annotated[bool, "是否在后台执行"] = False,
    **kwargs,
) -> str:
    """执行 shell 命令并返回输出。用于运行技能脚本、检查文件等。

    Args:
        command: 要执行的 shell 命令（必需）
        workdir: 工作目录，必须是绝对路径，默认为 None（继承父进程 cwd）
        timeout: 超时时间（秒），默认 60 秒，None 表示无超时
        background: 是否在后台执行，默认 False
    """
    # Validate workdir
    validated_workdir = _validate_workdir(workdir)

    logger.info(
        "[Tool:terminal] executing: %s (workdir=%s, timeout=%s, background=%s)",
        command,
        validated_workdir,
        timeout,
        background,
    )

    # Build shell command with cd to workdir if specified
    if validated_workdir:
        # Use shlex.quote to safely embed the path
        safe_workdir = shlex.quote(validated_workdir)
        shell_command = f"cd {safe_workdir} && {command}"
    else:
        shell_command = command

    if background:
        # Background execution: spawn process and return immediately
        process = await asyncio.create_subprocess_shell(
            shell_command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        logger.info("[Tool:terminal] background started with PID %s", process.pid)
        return f"后台进程已启动 (PID: {process.pid})\n命令: {command}"

    # Foreground execution with timeout
    process = await asyncio.create_subprocess_shell(
        shell_command,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    try:
        if timeout:
            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=timeout,
            )
        else:
            stdout, stderr = await process.communicate()
    except asyncio.TimeoutError:
        logger.warning("[Tool:terminal] command timed out after %s seconds", timeout)
        process.kill()
        await process.wait()
        return f"错误: 命令执行超时（{timeout}秒）\n命令: {command}"

    output = stdout.decode("utf-8", errors="replace").strip()
    errors = stderr.decode("utf-8", errors="replace").strip()

    # Build unified output format
    result: dict = {
        "stdout": output,
        "stderr": errors,
        "exit_code": process.returncode,
    }

    if process.returncode != 0:
        interpretation = _interpret_exit_code(process.returncode, command)
        logger.error(
            "[Tool:terminal] failed (%s): %s",
            interpretation,
            errors or "(no stderr)",
        )
        result["error"] = interpretation
        # Format failure output as string for backward compatibility
        combined = f"Exit code: {process.returncode}"
        if interpretation:
            combined += f" ({interpretation})"
        combined += "\n"
        if output:
            combined += f"stdout:\n{output}\n"
        if errors:
            combined += f"stderr:\n{errors}"
        return combined

    logger.info(
        "[Tool:terminal] success (output=%d chars, stderr=%d chars)",
        len(output),
        len(errors),
    )
    # Success: combine stdout + stderr for backward compatibility
    result_text = output
    if errors:
        result_text += f"\n{errors}"
    return result_text or "(no output)"