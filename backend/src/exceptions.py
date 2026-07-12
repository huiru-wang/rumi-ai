"""Unified business errors and API response helpers."""

from enum import Enum
from typing import Any


class BusinessErrorCode(Enum):
    # Workspace / account: 1xxxx
    WORKSPACE_QUOTA = (10001, "工作区数量已达上限，请删除旧工作区后重试。", False)
    WORKSPACE_NAME_EXISTS = (10002, "工作区名称已存在。", False)
    WORKSPACE_NOT_FOUND = (10003, "工作区不存在。", False)
    INVITE_INVALID = (10004, "邀请码无效或已停用。", False)

    # Documents: 2xxxx
    DOCUMENT_QUOTA = (20001, "文档数量已达上限，请删除旧文档后重试。", False)
    DOCUMENT_DUPLICATE_NAME = (20002, "同名文档已存在，请勿重复上传。", False)
    DOCUMENT_DUPLICATE_HASH = (20003, "相同内容的文档已存在，请勿重复上传。", False)
    DOCUMENT_PARSE_FAILED = (20004, "文档解析失败，请检查文件后重试。", True)

    # Output tasks: 3xxxx
    PPT_TASK_QUOTA = (30001, "PPT 任务数量已达上限，请删除旧任务后重试。", False)
    NARRATION_QUOTA = (30002, "口播稿任务数量已达上限，请删除旧任务后重试。", False)
    TASK_NOT_FOUND = (30003, "任务不存在。", False)
    TASK_FILE_NOT_FOUND = (30004, "任务文件不存在。", False)
    TASK_NOT_COMPLETED = (30007, "任务尚未完成，无法执行该操作。", False)
    OUTPUT_SAVE_FAILED = (30010, "产出保存失败，请稍后重试。", True)
    NARRATION_GENERATION_FAILED = (30011, "口播稿生成失败，请稍后重试。", True)

    # PPT styles: 4xxxx
    STYLE_NOT_FOUND = (40001, "PPT 风格不存在。", False)
    SYSTEM_STYLE_DELETE = (40002, "系统风格不能删除。", False)
    STYLE_ALREADY_SAVED = (40003, "该风格已保存，请勿重复操作。", False)
    CUSTOM_STYLE_QUOTA = (40004, "自定义风格数量已达上限，请删除旧风格后重试。", False)

    # Files / storage: 5xxxx
    FILE_NOT_FOUND = (50001, "文件不存在。", False)
    TASK_NO_FILE = (50002, "任务没有可用文件。", False)
    STORAGE_FAILED = (50003, "文件存储失败，请稍后重试。", True)

    # Messages / shares: 6xxxx
    MESSAGE_NOT_FOUND = (60001, "消息不存在。", False)

    # Agent / model: 7xxxx
    AGENT_MODEL_AUTH = (70001, "Rumi-AI 服务认证异常，请联系管理员检查配置。", False)
    AGENT_MODEL_QUOTA = (70002, "Rumi-AI 服务额度不足，请恢复额度后重试。", True)
    AGENT_MODEL_RATE_LIMIT = (70003, "Rumi-AI 服务当前请求过于频繁，请稍后重试。", True)
    AGENT_MODEL_TIMEOUT = (70004, "Rumi-AI 服务响应超时，请稍后重试。", True)
    AGENT_MODEL_CONNECTION = (70005, "暂时无法连接 Rumi-AI，请稍后重试。", True)
    AGENT_MODEL_BAD_REQUEST = (70006, "本次请求内容过长或格式不兼容，请调整后重试。", False)
    AGENT_TOOL_FAILED = (70007, "执行工具时出现问题，请稍后重试。", True)
    AGENT_INTERRUPT_FAILED = (70008, "交互恢复失败，请重新提交。", True)
    AGENT_RECURSION_LIMIT = (70009, "任务步骤过多，已自动停止，请拆分请求后重试。", False)
    AGENT_UNKNOWN = (79999, "Rumi-AI 对话服务暂时不可用，请稍后重试。", True)

    # Style extraction: 8xxxx
    STYLE_EXTRACTION_QUOTA = (80001, "风格提取任务数量已达上限，请删除旧任务后重试。", False)
    STYLE_EXTRACTION_FORMAT = (80002, "仅支持有效的 PPTX 文件。", False)
    STYLE_EXTRACTION_MODEL_AUTH = (80003, "风格提取模型认证异常，请联系管理员检查配置。", False)
    STYLE_EXTRACTION_MODEL_QUOTA = (80004, "模型服务额度不足，请恢复额度后继续执行任务。", True)
    STYLE_EXTRACTION_MODEL_RATE_LIMIT = (80005, "模型服务请求过于频繁，请稍后继续执行任务。", True)
    STYLE_EXTRACTION_MODEL_TIMEOUT = (80006, "模型服务响应超时，请稍后继续执行任务。", True)
    STYLE_EXTRACTION_MODEL_CONNECTION = (80007, "暂时无法连接模型服务，请稍后继续执行任务。", True)
    STYLE_EXTRACTION_OUTPUT_INVALID = (80008, "模型返回格式异常，请重新执行任务。", True)
    STYLE_EXTRACTION_TEMPLATE_INVALID = (80009, "风格模板生成失败，请重新执行任务。", True)
    STYLE_EXTRACTION_PREVIEW_INVALID = (80010, "风格预览生成失败，请重新执行任务。", True)
    STYLE_EXTRACTION_UNKNOWN = (80999, "视觉风格提取失败，请稍后重试。", True)

    # TTS / vision: 9xxxx
    TTS_FAILED = (90001, "语音合成失败，请稍后重试。", True)
    VISION_FAILED = (90002, "图片理解失败，请稍后重试。", True)

    def __init__(self, code: int, message: str, retryable: bool):
        self.code = code
        self.message = message
        self.retryable = retryable


class BusinessError(Exception):
    """The only public business exception; it must be created from the enum."""

    def __init__(self, error: BusinessErrorCode, *, stage: str | None = None):
        if not isinstance(error, BusinessErrorCode):
            raise TypeError("BusinessError must be created from BusinessErrorCode")
        super().__init__(error.message)
        self.error = error
        self.code = error.code
        self.message = error.message
        self.retryable = error.retryable
        self.stage = stage

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "code": self.code,
            "message": self.message,
            "type": self.error.name.lower(),
            "retryable": self.retryable,
        }
        if self.stage:
            data["stage"] = self.stage
        return data


def success_response(data: Any = None) -> dict:
    return {"data": data, "code": 0, "message": ""}
