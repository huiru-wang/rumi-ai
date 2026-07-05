import json
import logging
from collections.abc import Awaitable, Callable

from langchain.agents.middleware import AgentMiddleware, ModelRequest, ModelResponse
from langchain_core.messages import SystemMessage
from langgraph.runtime import Runtime

from src.logging_utils import is_debug_logging_enabled
from src.managers.prompt_manager import PromptManager
from src.storage.database import Database

logger = logging.getLogger(__name__)


def _prompt_table_cell(value: object) -> str:
    text = "" if value is None else str(value)
    return text.replace("\n", " ").replace("|", "｜").strip()


class ContextInjectMiddleware(AgentMiddleware):
    """Inject dynamic document context and workspace task metadata into the system prompt."""

    def __init__(self, db: Database, prompt_manager: PromptManager | None = None) -> None:
        self.db = db
        self._prompt_manager = prompt_manager or PromptManager()

    async def awrap_model_call(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], Awaitable[ModelResponse]],
    ) -> ModelResponse:
        workspace_id = request.state.get("workspace_id", "default")
        ppt_style = request.state.get("ppt_style", "")
        voice_id = request.state.get("voice_id", "")
        current_ppt_task_id = request.state.get("current_ppt_task_id", "")
        docs_info = []
        tasks_info = []

        if self.db:
            if self.db.connection is None:
                await self.db.initialize()
            docs = await self.db.list_documents(workspace_id)
            docs_info = [
                {
                    "id": d.get("id", ""),
                    "filename": d.get("filename", ""),
                    "type": d.get("file_type", ""),
                    "status": d.get("status", ""),
                    "summary": d.get("summary", "") or "",
                    "error": d.get("error_message", "") or "",
                }
                for d in docs
            ]

            # Query current tasks and inject them as the latest workspace task facts.
            tasks = await self.db.list_tasks(workspace_id)
            for task in tasks:
                result_data = {}
                if task.get("result_data"):
                    try:
                        result_data = json.loads(task["result_data"])
                    except (json.JSONDecodeError, TypeError):
                        pass
                outline = result_data.get("outline", {})
                if not isinstance(outline, dict):
                    outline = {}
                topic = outline.get("topic", "")
                summary = outline.get("summary", "")

                # Summarize children (e.g. narration tasks)
                children = task.get("children", [])
                child_labels = []
                for child in children:
                    ctype = child.get("type", "")
                    cstatus = child.get("status", "")
                    status_map = {
                        "completed": "✅已完成",
                        "narrating": "⏳文本生成中",
                        "tts_generating": "🔊音频生成中",
                        "tts_failed": "⚠️音频失败",
                        "failed": "❌失败",
                    }
                    type_map = {"narration": "口播稿"}
                    label = type_map.get(ctype, ctype)
                    label += status_map.get(cstatus, cstatus)
                    child_labels.append(label)
                children_text = ", ".join(child_labels) if child_labels else "无"

                # Resolve style name for dedup naming
                ppt_style_name = result_data.get("ppt_style_name", "")
                if not ppt_style_name and result_data.get("ppt_style"):
                    # Fallback: look up style name from DB
                    try:
                        style_rec = await self.db.get_ppt_style(result_data["ppt_style"])
                        if not style_rec:
                            style_rec = await self.db.get_ppt_style_by_name_en(
                                result_data["ppt_style"]
                            )
                        if style_rec:
                            ppt_style_name = style_rec.get("name", "")
                    except Exception:
                        pass

                tasks_info.append(
                    {
                        "id": task["id"],
                        "type": task.get("type", ""),
                        "status": task.get("status", ""),
                        "title": task.get("title", "未命名"),
                        "topic": topic,
                        "summary": summary,
                        "style": ppt_style_name,
                        "parent": task.get("parent_task_id") or "无",
                        "children": children_text,
                    }
                )

        # Build dynamic system prompt
        prompt = self._prompt_manager.get_system_prompt()
        if docs_info:
            rows = []
            for d in docs_info:
                note = d["summary"] or d["error"] or ""
                rows.append(
                    "| "
                    + " | ".join(
                        [
                            _prompt_table_cell(d["id"]),
                            _prompt_table_cell(d["filename"]),
                            _prompt_table_cell(d["type"]),
                            _prompt_table_cell(d["status"]),
                            _prompt_table_cell(note),
                        ]
                    )
                    + " |"
                )
            table = (
                "| 文档ID | 文件名 | 类型 | 状态 | 摘要或说明 |\n"
                "|--------|--------|------|------|------------|\n"
            ) + "\n".join(rows)
            prompt += (
                f"\n\n## 当前知识库文档列表\n"
                f"以下列表是当前工作区的最新文档数据，也是判断知识库文档是否存在、是否可用于检索的唯一依据。\n"
                f"只有状态为 ready 的文档可用于 rag_search、知识问答、PPT 内容生成和引用标注。\n"
                f"状态为 uploaded、parsing、parsed、chunking、indexing、summarizing 的文档仍在处理中，不要声称已可检索；状态为 error 的文档不可用。\n"
                f"当用户问题涉及某篇文档时，优先使用该文档对应的 doc_id 调用 rag_search。\n\n"
                f"{table}"
            )
        else:
            prompt += (
                f"\n\n## 当前知识库文档列表\n"
                f"当前工作区没有任何文档。知识问答和 PPT 内容生成都没有可用知识库来源；不要根据对话历史假设文档仍然存在。"
            )

        # Fetch workspace once for both ppt_style and voice_info
        ws = None
        ext_data: dict = {}
        if self.db and self.db.connection:
            try:
                ws = await self.db.get_workspace(workspace_id)
                ext_data = (ws.get("ext_data") or {}) if ws else {}
            except Exception:
                logger.warning(
                    "[ContextInjectMiddleware] failed to fetch workspace=%s", workspace_id
                )

        # Build user preference section (ppt_style + voice)
        pref_lines: list[str] = []
        style_record = None

        if ppt_style:
            try:
                user_id = ws.get("user_id", "") if ws else ""
                # Primary: look up by id (new convention)
                style_record = await self.db.get_ppt_style(ppt_style)
                # Fallback: old data may store name_en instead of id
                if not style_record:
                    style_record = await self.db.get_ppt_style_by_name_en(
                        ppt_style, user_id=user_id
                    )
            except Exception:
                logger.warning(
                    "[ContextInjectMiddleware] failed to look up ppt_style=%s", ppt_style
                )

            if style_record:
                s_name = style_record.get("name", "")
                s_name_en = style_record.get("name_en", "")
                s_desc = style_record.get("description", "")
                s_id = style_record.get("id", ppt_style)
                pref_lines.append(
                    f"- PPT视觉风格：{s_name}，ID: {s_id}"
                    + (f"，{s_desc}" if s_desc else "")
                    + "（用户已预选，生成PPT时必须调用 get_style_template 工具获取完整风格规范）"
                )
            else:
                pref_lines.append(
                    f"- PPT视觉风格：{ppt_style}（用户已预选，生成PPT时直接使用该风格，跳过风格询问步骤）"
                )

        # Voice preference from ext_data.voice_info
        voice_info = ext_data.get("voice_info") if ext_data else None
        if voice_info and isinstance(voice_info, dict) and voice_info.get("name"):
            gender_map = {"female": "女性", "male": "男性"}
            gender_label = gender_map.get(voice_info.get("gender", ""), "")
            voice_line = f"- 语音音色：{voice_info['name']}"
            if gender_label:
                voice_line += f"（{gender_label}"
                if voice_info.get("trait"):
                    voice_line += f"，{voice_info['trait']}"
                voice_line += "）"
            elif voice_info.get("trait"):
                voice_line += f"（{voice_info['trait']}）"
            voice_line += "（生成口播稿时默认使用该音色）"
            pref_lines.append(voice_line)
        elif voice_id:
            # Fallback for old data without voice_info
            pref_lines.append(f"- 语音音色：{voice_id}（生成口播稿时默认使用该音色）")

        if pref_lines:
            prompt += f"\n\n## 用户配置偏好\n" + "\n".join(pref_lines)

        if tasks_info:
            rows = []
            for t in tasks_info:
                rows.append(
                    "| "
                    + " | ".join(
                        [
                            _prompt_table_cell(t["id"]),
                            _prompt_table_cell(t["type"]),
                            _prompt_table_cell(t["status"]),
                            _prompt_table_cell(t["title"]),
                            _prompt_table_cell(t["topic"]),
                            _prompt_table_cell(t["summary"]),
                            _prompt_table_cell(t.get("style", "")),
                            _prompt_table_cell(t["parent"]),
                            _prompt_table_cell(t["children"]),
                        ]
                    )
                    + " |"
                )
            table = (
                "| 任务ID | 类型 | 状态 | 标题 | 主题 | 摘要 | 风格 | 父任务 | 子任务 |\n"
                "|--------|------|------|------|------|------|------|--------|--------|\n"
            ) + "\n".join(rows)
            prompt += (
                f"\n\n## 当前任务列表\n"
                f"以下列表是当前工作区的最新任务数据，也是判断任务是否存在、类型、状态、父子关系的唯一依据。\n"
                f"必须严格以此列表为准；对话历史中的任务信息不得覆盖此列表。\n"
                f"当用户请求生成口播稿时，只能从当前任务列表中选择类型为 ppt 且状态为 completed 的任务。\n"
                f"如果列表中没有符合条件的 PPT，直接说明当前没有可用于生成口播稿的 PPT。\n"
                f"生成新 PPT 时，必须检查此列表避免标题重复——若主题相同，参考「风格」列在标题后追加括号区分。\n\n"
                f"{table}"
            )
        else:
            prompt += (
                f"\n\n## 当前任务列表\n"
                f"当前工作区没有任何可用任务。\n"
                f"对话历史中曾出现的任务、PPT、口播稿或任务 ID，均视为当前不存在或已删除。"
            )

        if is_debug_logging_enabled():
            logger.info(
                "[ContextInjectMiddleware] context_inject_debug | "
                "workspace_id=%s | ppt_style=%s | voice_id=%s | current_ppt_task_id=%s | "
                "docs=%d | tasks=%d | prompt_chars=%d | system_prompt=%s",
                workspace_id,
                ppt_style,
                voice_id,
                current_ppt_task_id,
                len(docs_info),
                len(tasks_info),
                len(prompt),
                prompt,
            )
        else:
            logger.info(
                "[ContextInjectMiddleware] context_inject | "
                "workspace_id=%s | ppt_style=%s | voice_id=%s | current_ppt_task_id=%s | "
                "docs=%d | tasks=%d | prompt_chars=%d",
                workspace_id,
                ppt_style,
                voice_id,
                current_ppt_task_id,
                len(docs_info),
                len(tasks_info),
                len(prompt),
            )

        request = request.override(system_message=SystemMessage(content=prompt))
        return await handler(request)
