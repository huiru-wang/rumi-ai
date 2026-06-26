"""Unified business exception and response helpers for RumiAI API.

All JSON business endpoints return HTTP 200 with structured body:
    {"data": ..., "code": 0, "message": ""}

Business errors are raised as BizException and caught by the global handler.
"""

from typing import Any


# ---------------------------------------------------------------------------
# Exception
# ---------------------------------------------------------------------------


class BizException(Exception):
    """Business-level exception that carries a structured error code and message."""

    def __init__(self, code: int, message: str = ""):
        super().__init__(message)
        self.code = code
        self.message = message


# ---------------------------------------------------------------------------
# Response helper
# ---------------------------------------------------------------------------


def success_response(data: Any = None) -> dict:
    """Wrap data in the unified success envelope."""
    return {"data": data, "code": 0, "message": ""}


# ---------------------------------------------------------------------------
# Error codes — Workspace (1xxxx)
# ---------------------------------------------------------------------------

ERR_WORKSPACE_QUOTA = 10001        # 每个用户最多创建 5 个工作区
ERR_WORKSPACE_NAME_EXISTS = 10002  # 工作区名称已存在
ERR_WORKSPACE_NOT_FOUND = 10003    # 工作区不存在

# ---------------------------------------------------------------------------
# Error codes — Knowledge / Documents (2xxxx)
# ---------------------------------------------------------------------------

ERR_DOCUMENT_QUOTA = 20001         # 每个工作区最多上传 5 个文档
ERR_DOCUMENT_DUPLICATE_NAME = 20002  # 文档已存在，请勿重复上传
ERR_DOCUMENT_DUPLICATE_HASH = 20003  # 与已有文档内容完全相同

# ---------------------------------------------------------------------------
# Error codes — Output / Tasks (3xxxx)
# ---------------------------------------------------------------------------

ERR_PPT_TASK_QUOTA = 30001         # 每个工作区最多生成 10 个 PPT 任务
ERR_NARRATION_QUOTA = 30002        # 每个 PPT 最多生成 5 个口播稿
ERR_TASK_NOT_FOUND = 30003         # 任务不存在
ERR_TASK_FILE_NOT_FOUND = 30004    # 任务文件不存在
ERR_STYLE_EXTRACTION_QUOTA = 30005  # 每个工作区最多创建 10 个风格提取任务
ERR_STYLE_EXTRACTION_FORMAT = 30006  # 仅支持 .pptx 文件
ERR_TASK_NOT_COMPLETED = 30007     # 任务未完成，无法保存
ERR_STYLE_ALREADY_SAVED = 30008    # 该风格已保存，请勿重复操作
ERR_CUSTOM_STYLE_QUOTA = 30009     # 每个用户最多保存 5 个自定义风格

# ---------------------------------------------------------------------------
# Error codes — Config (4xxxx)
# ---------------------------------------------------------------------------

ERR_STYLE_NOT_FOUND = 40001        # 风格不存在
ERR_SYSTEM_STYLE_DELETE = 40002    # 不能删除系统风格

# ---------------------------------------------------------------------------
# Error codes — File (5xxxx)
# ---------------------------------------------------------------------------

ERR_FILE_NOT_FOUND = 50001         # 文件不存在
ERR_TASK_NO_FILE = 50002           # 任务无可下载文件

# ---------------------------------------------------------------------------
# Error codes — Message (6xxxx)
# ---------------------------------------------------------------------------

ERR_MESSAGE_NOT_FOUND = 60001      # 消息不存在
