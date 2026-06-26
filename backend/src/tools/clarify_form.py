import json

from langchain_core.tools import tool
from langgraph.types import interrupt
from pydantic import BaseModel, Field


class FormField(BaseModel):
    name: str = Field(description="字段名")
    label: str = Field(description="显示标签")
    type: str = Field(description="字段类型: select/multiselect")
    options: list[str] | None = Field(
        default=None, description="选项列表"
    )
    recommended: list[str] | None = Field(
        default=None, description="AI推荐的选项。前端会自动预选（select取第一个，multiselect全选）并显示推荐标记"
    )
    allow_custom: bool = Field(
        default=False, description="是否允许用户自定义输入（仅select有效）"
    )
    required: bool = Field(default=True)


class ClarifyFormInput(BaseModel):
    title: str = Field(description="表单标题")
    description: str = Field(description="向用户说明为什么需要这些信息")
    fields: list[FormField] = Field(description="表单字段列表")


@tool(args_schema=ClarifyFormInput)
def clarify_form(title: str, description: str, fields: list[dict], **kwargs) -> str:
    """向用户展示一个表单来收集信息。当需要用户澄清意图、选择选项或提供详细参数时使用此工具。
    表单会在前端渲染为交互式UI，用户填写后结果会返回给你。

    字段类型说明：
    - select：单选。可设置 recommended 预选推荐项，设置 allow_custom=true 允许用户自定义输入。
    - multiselect：多选。可设置 recommended 预选多个推荐项。

    recommended 字段：
    - AI 推荐的选项值列表。前端会自动将其作为默认选中项（select 取第一个，multiselect 全选），
      同时在 UI 上显示「推荐」标记。
    - 当用户已在消息中提供了部分信息时，将匹配到的值放入 recommended 以预填表单。
    - 即使无法推断用户意图，也应提供合理的推荐选项帮助用户快速决策。

    重要：
    - 如果返回值包含 cancelled=true，说明用户主动取消了表单，不希望继续当前任务。
      请尊重用户的意愿，礼貌地告知任务已取消，并等待用户的下一步指示。
    - 调用此工具时，请勿在同一条消息中附带说明文字。
      若需要向用户说明为何需要填写信息，请在调用此工具之前单独输出一条文字消息。
    """
    user_response = interrupt({
        "title": title,
        "description": description,
        "fields": fields,
    })

    # User cancelled the form
    if isinstance(user_response, dict) and user_response.get("__cancelled__"):
        return json.dumps({"cancelled": True, "message": "用户取消了表单，不希望继续此任务"}, ensure_ascii=False)

    return json.dumps(user_response, ensure_ascii=False)
