import json
import logging
import re
import time
from mimetypes import guess_type
from pathlib import Path, PurePosixPath
from urllib.parse import quote

from fastapi import BackgroundTasks, FastAPI, File, HTTPException, Query, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from src.api.deps import db, doc_service, file_store, skill_manager, style_extract_manager, vector_store
from src.exceptions import (
    BizException,
    success_response,
    ERR_WORKSPACE_QUOTA,
    ERR_WORKSPACE_NAME_EXISTS,
    ERR_WORKSPACE_NOT_FOUND,
    ERR_DOCUMENT_QUOTA,
    ERR_DOCUMENT_DUPLICATE_NAME,
    ERR_DOCUMENT_DUPLICATE_HASH,
    ERR_TASK_NOT_FOUND,
    ERR_TASK_FILE_NOT_FOUND,
    ERR_STYLE_EXTRACTION_QUOTA,
    ERR_STYLE_EXTRACTION_FORMAT,
    ERR_TASK_NOT_COMPLETED,
    ERR_STYLE_ALREADY_SAVED,
    ERR_CUSTOM_STYLE_QUOTA,
    ERR_STYLE_NOT_FOUND,
    ERR_SYSTEM_STYLE_DELETE,
    ERR_FILE_NOT_FOUND,
    ERR_TASK_NO_FILE,
    ERR_MESSAGE_NOT_FOUND,
    ERR_INVITE_INVALID,
)
from src.invite_registry import InviteRegistry
from src.limits import (
    MAX_WORKSPACES_PER_USER,
    MAX_DOCUMENTS_PER_WORKSPACE,
    MAX_STYLE_EXTRACTION_TASKS_PER_WORKSPACE,
    MAX_CUSTOM_STYLES_PER_USER,
)
from src.log_context import (
    add_context_task,
    configure_log_record_context,
    new_request_id,
    new_trace_id,
    reset_log_context,
    set_log_context,
)
from src.managers.doc_manager import DuplicateDocumentError
from src.storage.seeds import _BUILTIN_VOICES
from src.url_utils import (
    build_share_audio_url,
    build_share_ppt_url,
    build_style_extraction_resource_url,
    build_style_resource_url,
)

logger = logging.getLogger(__name__)
invite_registry = InviteRegistry.from_env()

# Configure root logger for development
configure_log_record_context()
logging.basicConfig(
    level=logging.INFO,
    format=(
        "%(asctime)s %(levelname)s "
        "trace_id=%(trace_id)s request_id=%(request_id)s "
        "user_id=%(user_id)s workspace_id=%(workspace_id)s "
        "module=%(name)s msg=%(message)s"
    ),
    datefmt="%H:%M:%S",
)

app = FastAPI(title="RumiAI API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Request-ID", "X-Trace-ID"],
)


_WORKSPACE_PATH_RE = re.compile(r"/api/workspaces/([^/?]+)")


def _extract_workspace_id_from_path(path: str) -> str:
    match = _WORKSPACE_PATH_RE.search(path)
    return match.group(1) if match else "-"


@app.middleware("http")
async def log_context_middleware(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID") or new_request_id()
    trace_id = request.headers.get("X-Trace-ID") or new_trace_id()
    workspace_id = _extract_workspace_id_from_path(request.url.path)
    user_id = request.query_params.get("user_id") or "-"
    tokens = set_log_context(
        trace_id=trace_id,
        request_id=request_id,
        user_id=user_id,
        workspace_id=workspace_id,
    )
    started = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        duration_ms = int((time.perf_counter() - started) * 1000)
        logger.exception("[API] request failed method=%s path=%s duration_ms=%d", request.method, request.url.path, duration_ms)
        raise
    finally:
        reset_log_context(tokens)

    response.headers["X-Request-ID"] = request_id
    response.headers["X-Trace-ID"] = trace_id
    return response


@app.exception_handler(BizException)
async def biz_exception_handler(request: Request, exc: BizException):
    return JSONResponse(
        status_code=200,
        content={"data": None, "code": exc.code, "message": exc.message},
    )


@app.on_event("startup")
async def startup():
    logger.info("[API] starting up, initializing database...")
    await db.initialize()
    logger.info("[API] database initialized")


# --- Workspace ---


class ClaimInviteRequest(BaseModel):
    code: str


@app.post("/api/invites/claim")
async def claim_invite(req: ClaimInviteRequest):
    record = invite_registry.claim(req.code)
    if not record:
        raise BizException(ERR_INVITE_INVALID, "邀请码无效或已停用")
    return success_response({"user_id": record.user_id, "nickname": record.nickname})


def _ensure_invited_user(user_id: str):
    if not invite_registry.is_valid_user_id(user_id):
        raise BizException(ERR_INVITE_INVALID, "邀请码无效或已停用")


async def _get_invited_workspace(workspace_id: str) -> dict:
    workspace = await db.get_workspace(workspace_id)
    if not workspace:
        raise BizException(ERR_WORKSPACE_NOT_FOUND, "工作区不存在")
    _ensure_invited_user(workspace["user_id"])
    set_log_context(user_id=workspace["user_id"], workspace_id=workspace_id)
    return workspace


class CreateWorkspaceRequest(BaseModel):
    user_id: str
    name: str


@app.post("/api/workspaces")
async def create_workspace(req: CreateWorkspaceRequest):
    logger.info("[API] POST /api/workspaces user_id=%s name=%s", req.user_id, req.name)
    _ensure_invited_user(req.user_id)
    count = await db.count_workspaces(req.user_id)
    if count >= MAX_WORKSPACES_PER_USER:
        raise BizException(ERR_WORKSPACE_QUOTA, f"每个用户最多创建 {MAX_WORKSPACES_PER_USER} 个工作区，当前已有 {count} 个。")
    try:
        result = await db.create_workspace(user_id=req.user_id, name=req.name)
    except ValueError as exc:
        raise BizException(ERR_WORKSPACE_NAME_EXISTS, "工作区名称已存在") from exc
    logger.info("[API] workspace created: id=%s", result["id"])
    return success_response(result)


@app.get("/api/workspaces")
async def list_workspaces(user_id: str):
    logger.info("[API] GET /api/workspaces user_id=%s", user_id)
    _ensure_invited_user(user_id)
    data = await db.list_workspaces(user_id=user_id)
    return success_response(data)


@app.get("/api/workspaces/{workspace_id}")
async def get_workspace(workspace_id: str):
    logger.info("[API] GET /api/workspaces/%s", workspace_id)
    workspace = await _get_invited_workspace(workspace_id)
    return success_response(workspace)


class UpdateThreadRequest(BaseModel):
    thread_id: str


class UpdateConfigRequest(BaseModel):
    key: str
    value: str | int | float | bool | dict | list | None


class SaveTaskFileRequest(BaseModel):
    content: str


def _parse_json_object(raw: str | dict | None) -> dict:
    if isinstance(raw, dict):
        return raw
    if not raw:
        return {}
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return {}
    return data if isinstance(data, dict) else {}


def _sanitize_document(doc: dict) -> dict:
    data = dict(doc)
    data.pop("storage_path", None)
    data.pop("content_hash", None)
    data["progress"] = _parse_json_object(data.pop("progress_data", None))
    return data


def _sanitize_result_data(task_type: str, raw: str | dict | None) -> dict:
    data = _parse_json_object(raw)
    if not data:
        return {}

    if task_type == "ppt":
        allowed = {
            "filename",
            "ppt_style",
            "ppt_style_name",
            "outline",
            "error",
        }
        return {key: data[key] for key in allowed if key in data}

    if task_type == "narration":
        safe_slides = []
        for slide in data.get("slides", []):
            if not isinstance(slide, dict):
                continue
            safe_slide = {
                key: slide[key]
                for key in ("number", "title", "text")
                if key in slide
            }
            safe_slide["has_audio"] = bool(slide.get("audio_path"))
            safe_slides.append(safe_slide)
        safe = {
            key: data[key]
            for key in ("language", "voice_id", "voice_name", "tts_progress", "tts_error")
            if key in data
        }
        safe["slides"] = safe_slides
        return safe

    if task_type == "ppt_style_extraction":
        allowed = {
            "description",
            "style_description",
            "style_name",
            "style_name_en",
            "pptx_filename",
            "progress_step",
            "saved_style_id",
            "error",
        }
        safe = {key: data[key] for key in allowed if key in data}
        if data.get("preview_html_path"):
            safe["has_preview"] = True
        return safe

    return {
        key: value
        for key, value in data.items()
        if key
        not in {
            "storage_path",
            "file_path",
            "audio_path",
            "text_file_path",
            "preview_path",
            "preview_html_path",
            "pptx_storage_key",
            "resource_prefix",
            "resource_manifest",
        }
    }


def _sanitize_task(task: dict) -> dict:
    data = dict(task)
    task_type = data.get("type", "")
    data["result_data"] = _sanitize_result_data(task_type, data.get("result_data"))
    if "children" in data:
        data["children"] = [_sanitize_task(child) for child in data.get("children") or []]
    return data


def _sanitize_ppt_style(style: dict) -> dict:
    data = dict(style)
    data.pop("preview_path", None)
    data.pop("resource_manifest", None)
    data.pop("style_description", None)
    return data


@app.patch("/api/workspaces/{workspace_id}/thread")
async def update_workspace_thread(workspace_id: str, req: UpdateThreadRequest):
    logger.info("[API] PATCH /api/workspaces/%s/thread thread_id=%s", workspace_id, req.thread_id)
    await _get_invited_workspace(workspace_id)
    await db.update_workspace_thread_id(workspace_id, req.thread_id)
    return success_response(None)


@app.patch("/api/workspaces/{workspace_id}/config")
async def update_workspace_config(workspace_id: str, req: UpdateConfigRequest):
    logger.info("[API] PATCH /api/workspaces/%s/config key=%s value=%s", workspace_id, req.key, req.value)
    await _get_invited_workspace(workspace_id)
    try:
        ext_data = await db.update_workspace_ext_data(workspace_id, req.key, req.value)
    except ValueError as exc:
        raise BizException(ERR_WORKSPACE_NOT_FOUND, "工作区不存在") from exc
    return success_response(ext_data)


@app.get("/api/threads/{thread_id}/messages")
async def list_thread_messages(
    thread_id: str,
    limit: int = Query(default=10, ge=1, le=100),
    before: int | None = Query(default=None, ge=1),
):
    logger.info(
        "[API] GET /api/threads/%s/messages limit=%s before=%s",
        thread_id,
        limit,
        before,
    )
    data = await db.list_thread_messages(thread_id, limit=limit, before=before)
    return success_response(data)


@app.get("/api/threads/{thread_id}/history-runs")
async def list_thread_history_runs(
    thread_id: str,
    limit: int = Query(default=10, ge=1, le=100),
    before: int | None = Query(default=None, ge=1),
):
    logger.info(
        "[API] GET /api/threads/%s/history-runs limit=%s before=%s",
        thread_id,
        limit,
        before,
    )
    data = await db.list_thread_history_runs(thread_id, limit=limit, before=before)
    return success_response(data)


@app.get("/api/threads/{thread_id}/messages/{message_id}")
async def get_message_detail(thread_id: str, message_id: str):
    logger.info(
        "[API] GET /api/threads/%s/messages/%s",
        thread_id,
        message_id,
    )
    msg = await db.get_message_by_id(message_id, thread_id)
    if not msg:
        raise BizException(ERR_MESSAGE_NOT_FOUND, "消息不存在")
    return success_response(msg)


@app.delete("/api/workspaces/{workspace_id}")
async def delete_workspace(workspace_id: str):
    logger.info("[API] DELETE /api/workspaces/%s", workspace_id)
    await _get_invited_workspace(workspace_id)
    await doc_service.delete_workspace(workspace_id)
    await db.delete_workspace(workspace_id)
    return success_response(None)


# --- Documents ---


@app.post("/api/workspaces/{workspace_id}/documents")
async def upload_document(
    workspace_id: str,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
):
    logger.info("[API] POST /api/workspaces/%s/documents filename=%s", workspace_id, file.filename)
    await _get_invited_workspace(workspace_id)
    doc_count = await db.count_documents(workspace_id)
    if doc_count >= MAX_DOCUMENTS_PER_WORKSPACE:
        raise BizException(ERR_DOCUMENT_QUOTA, f"每个工作区最多上传 {MAX_DOCUMENTS_PER_WORKSPACE} 个文档，当前已有 {doc_count} 个。")
    content = await file.read()
    logger.info("[API] file read: %d bytes", len(content))
    try:
        doc = await doc_service.create_document_upload(
            workspace_id=workspace_id,
            filename=file.filename,
            content=content,
        )
    except DuplicateDocumentError as exc:
        logger.info("[API] duplicate document rejected: %s", exc)
        if exc.existing_doc_id and "内容完全相同" in str(exc):
            raise BizException(ERR_DOCUMENT_DUPLICATE_HASH, str(exc)) from exc
        raise BizException(ERR_DOCUMENT_DUPLICATE_NAME, str(exc)) from exc
    add_context_task(background_tasks, doc_service.process_document, doc["id"])
    logger.info("[API] upload result: id=%s status=%s", doc["id"], doc["status"])
    return success_response(_sanitize_document(doc))


@app.get("/api/workspaces/{workspace_id}/documents")
async def list_documents(workspace_id: str):
    logger.info("[API] GET /api/workspaces/%s/documents", workspace_id)
    await _get_invited_workspace(workspace_id)
    data = await db.list_documents(workspace_id)
    return success_response([_sanitize_document(doc) for doc in data])


@app.delete("/api/workspaces/{workspace_id}/documents/{doc_id}")
async def delete_document(workspace_id: str, doc_id: str):
    logger.info("[API] DELETE /api/workspaces/%s/documents/%s", workspace_id, doc_id)
    await _get_invited_workspace(workspace_id)
    await doc_service.delete_document(workspace_id, doc_id)
    return success_response(None)


# --- Tasks ---


@app.get("/api/workspaces/{workspace_id}/tasks")
async def list_tasks(workspace_id: str):
    logger.info("[API] GET /api/workspaces/%s/tasks", workspace_id)
    await _get_invited_workspace(workspace_id)
    data = await db.list_tasks(workspace_id)
    return success_response([_sanitize_task(task) for task in data])


@app.delete("/api/workspaces/{workspace_id}/tasks/{task_id}")
async def delete_task(workspace_id: str, task_id: str):
    logger.info("[API] DELETE /api/workspaces/%s/tasks/%s", workspace_id, task_id)
    await _get_invited_workspace(workspace_id)

    task = await db.get_task(task_id)
    if not task:
        raise BizException(ERR_TASK_NOT_FOUND, "任务不存在")

    deleted_ids = await db.delete_task(task_id)
    revoked_count = await db.revoke_shares_for_tasks(deleted_ids, reason="task_deleted")

    # --- File cleanup (delegated to FileStore for local/OSS transparency) ---
    if task["type"] == "ppt":
        await file_store.delete_ppt_task_dir(workspace_id, task_id)
        logger.info("[API] removed PPT output directory for task: %s", task_id)
    elif task["type"] == "narration":
        result_data = {}
        if task.get("result_data"):
            try:
                result_data = json.loads(task["result_data"])
            except (json.JSONDecodeError, TypeError):
                pass
        for slide in result_data.get("slides", []):
            audio_path = slide.get("audio_path")
            if audio_path:
                await file_store.delete_async(audio_path)
        text_file_path = result_data.get("text_file_path")
        if text_file_path:
            await file_store.delete_async(text_file_path)
        logger.info("[API] cleaned narration files for task: %s", task_id)
    elif task["type"] == "ppt_style_extraction":
        await file_store.delete_style_task_dir(workspace_id, task_id)
        logger.info("[API] removed style extraction output directory for task: %s", task_id)

    return success_response({"deleted_ids": deleted_ids, "revoked_shares": revoked_count})


@app.put("/api/workspaces/{workspace_id}/tasks/{task_id}/file")
async def save_task_file(workspace_id: str, task_id: str, req: SaveTaskFileRequest):
    """Save updated HTML content back to a PPT task's file."""
    logger.info("[API] PUT /api/workspaces/%s/tasks/%s/file content_len=%d", workspace_id, task_id, len(req.content))
    await _get_invited_workspace(workspace_id)
    task = await db.get_task(task_id)
    if not task:
        raise BizException(ERR_TASK_NOT_FOUND, "任务不存在")
    result_data = {}
    if task.get("result_data"):
        try:
            result_data = json.loads(task["result_data"])
        except (json.JSONDecodeError, TypeError):
            pass
    file_path = result_data.get("file_path", "")
    if not file_path:
        raise BizException(ERR_TASK_FILE_NOT_FOUND, "任务文件不存在")
    if not await file_store.exists(file_path):
        raise BizException(ERR_TASK_FILE_NOT_FOUND, "任务文件不存在")
    await file_store.write_text(file_path, req.content)
    logger.info("[API] saved task file: %s (%d bytes)", file_path, len(req.content))
    return success_response(None)


def _share_payload(share: dict | None) -> dict:
    if not share:
        return {"enabled": False, "token": None, "type": None}
    token = share["token"]
    return {
        "enabled": True,
        "token": token,
        "type": share.get("type"),
    }


async def _validate_shareable_task(task_id: str) -> dict:
    task = await db.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    if task.get("type") not in {"ppt", "narration"}:
        raise HTTPException(status_code=400, detail="Task is not shareable")
    if task.get("status") != "completed":
        raise HTTPException(status_code=400, detail="Task is not completed")

    result_data = _parse_json_object(task.get("result_data"))
    if task["type"] == "ppt":
        if not result_data.get("file_path"):
            raise HTTPException(status_code=404, detail="PPT file not found")
    else:
        parent_task_id = task.get("parent_task_id")
        if not parent_task_id:
            raise HTTPException(status_code=404, detail="Parent PPT not found")
        parent_task = await db.get_task(parent_task_id)
        parent_result = _parse_json_object(parent_task.get("result_data") if parent_task else None)
        if not parent_task or parent_task.get("status") != "completed" or not parent_result.get("file_path"):
            raise HTTPException(status_code=404, detail="Parent PPT not found")
        has_audio = any(
            isinstance(slide, dict) and bool(slide.get("audio_path"))
            for slide in result_data.get("slides", [])
        )
        if not has_audio:
            raise HTTPException(status_code=404, detail="Narration audio not found")
    return task


@app.get("/api/tasks/{task_id}/share")
async def get_task_share(task_id: str):
    """Get current active share status for a task."""
    logger.info("[API] GET /api/tasks/%s/share", task_id)
    task = await db.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    share = await db.get_active_share_by_task(task_id)
    return success_response(_share_payload(share))


@app.post("/api/tasks/{task_id}/share")
async def create_task_share(task_id: str):
    """Create or reuse an active share link for a completed PPT/narration task."""
    logger.info("[API] POST /api/tasks/%s/share", task_id)
    task = await _validate_shareable_task(task_id)
    share = await db.create_or_get_active_share(task)
    return success_response(_share_payload(share))


@app.delete("/api/tasks/{task_id}/share")
async def delete_task_share(task_id: str):
    """Revoke the active share link for a task."""
    logger.info("[API] DELETE /api/tasks/%s/share", task_id)
    task = await db.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    revoked = await db.revoke_share_for_task(task_id, reason="user_revoked")
    return success_response({"ok": True, "revoked": revoked})


# --- Style Extraction ---


@app.post("/api/workspaces/{workspace_id}/style-extraction")
async def submit_style_extraction(
    workspace_id: str,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
):
    """Upload a PPTX file and start style extraction workflow."""
    logger.info("[API] POST /api/workspaces/%s/style-extraction filename=%s", workspace_id, file.filename)
    await _get_invited_workspace(workspace_id)
    if not file.filename or not file.filename.lower().endswith(".pptx"):
        raise BizException(ERR_STYLE_EXTRACTION_FORMAT, "仅支持 .pptx 文件")
    style_task_count = await db.count_tasks_by_type(workspace_id, "ppt_style_extraction")
    if style_task_count >= MAX_STYLE_EXTRACTION_TASKS_PER_WORKSPACE:
        raise BizException(ERR_STYLE_EXTRACTION_QUOTA, f"每个工作区最多创建 {MAX_STYLE_EXTRACTION_TASKS_PER_WORKSPACE} 个风格提取任务，当前已有 {style_task_count} 个。")

    content = await file.read()

    task = await db.create_task(
        workspace_id=workspace_id,
        type="ppt_style_extraction",
        title=f"风格提取: {file.filename}",
    )
    logger.info("[API] style extraction task created: id=%s", task["id"])

    add_context_task(
        background_tasks,
        style_extract_manager.run_extraction,
        task["id"], workspace_id, content, file.filename,
    )
    return success_response(task)


@app.get("/api/workspaces/{workspace_id}/tasks/{task_id}")
async def get_task(workspace_id: str, task_id: str):
    """Get a single task by ID."""
    logger.info("[API] GET /api/workspaces/%s/tasks/%s", workspace_id, task_id)
    await _get_invited_workspace(workspace_id)
    task = await db.get_task(task_id)
    if not task:
        raise BizException(ERR_TASK_NOT_FOUND, "任务不存在")
    return success_response(_sanitize_task(task))


@app.delete("/api/workspaces/{workspace_id}/style-extraction/{task_id}")
async def delete_style_extraction(workspace_id: str, task_id: str):
    """Cancel running extraction and delete the task."""
    logger.info("[API] DELETE /api/workspaces/%s/style-extraction/%s", workspace_id, task_id)
    await _get_invited_workspace(workspace_id)

    await style_extract_manager.cancel_extraction(task_id)

    task = await db.get_task(task_id)
    if not task:
        raise BizException(ERR_TASK_NOT_FOUND, "任务不存在")

    deleted_ids = await db.delete_task(task_id)

    await file_store.delete_style_task_dir(workspace_id, task_id)
    logger.info("[API] removed style extraction output directory for task: %s", task_id)

    return success_response({"deleted_ids": deleted_ids})


class SaveStyleRequest(BaseModel):
    user_id: str


@app.post("/api/style-extraction/{task_id}/save")
async def save_style_from_extraction(task_id: str, req: SaveStyleRequest):
    """Save completed extraction result as a custom PPT style."""
    logger.info("[API] POST /api/style-extraction/%s/save user_id=%s", task_id, req.user_id)
    style_count = await db.count_custom_styles(req.user_id)
    if style_count >= MAX_CUSTOM_STYLES_PER_USER:
        raise BizException(ERR_CUSTOM_STYLE_QUOTA, f"每个用户最多保存 {MAX_CUSTOM_STYLES_PER_USER} 个自定义风格，当前已有 {style_count} 个。")
    try:
        style = await style_extract_manager.save_as_custom_style(task_id, req.user_id)
    except ValueError as exc:
        msg = str(exc)
        if "未完成" in msg or "not completed" in msg.lower():
            raise BizException(ERR_TASK_NOT_COMPLETED, "任务未完成，无法保存") from exc
        if "已保存" in msg or "重复" in msg:
            raise BizException(ERR_STYLE_ALREADY_SAVED, "该风格已保存，请勿重复操作") from exc
        raise BizException(ERR_TASK_NOT_FOUND, msg) from exc
    return success_response(style)


# --- File download ---


@app.get("/api/ppt-styles")
async def list_ppt_styles(user_id: str = Query(default="")):
    """List PPT styles: system builtin + user custom (if user_id provided)."""
    logger.info("[API] GET /api/ppt-styles user_id=%s", user_id)
    user_ids = ["system"]
    if user_id:
        user_ids.append(user_id)
    data = await db.list_all_ppt_styles(user_ids)
    return success_response([_sanitize_ppt_style(style) for style in data])


@app.get("/api/voices")
async def list_voices():
    """List available TTS voices from builtin seed data."""
    logger.info("[API] GET /api/voices")
    return success_response(_BUILTIN_VOICES)


@app.delete("/api/ppt-styles/{style_id}")
async def delete_ppt_style(style_id: str):
    """Delete a custom PPT style and its preview file."""
    logger.info("[API] DELETE /api/ppt-styles/%s", style_id)
    style = await db.get_ppt_style(style_id)
    if not style:
        raise BizException(ERR_STYLE_NOT_FOUND, "风格不存在")
    if style["user_id"] == "system":
        raise BizException(ERR_SYSTEM_STYLE_DELETE, "不能删除系统风格")
    # Delete preview file and its directory if it exists
    preview_path = style.get("preview_path", "")
    if preview_path:
        if file_store.is_local_path(preview_path):
            style_dir = Path(preview_path).parent
            await file_store.delete_dir(str(style_dir))
            logger.info("[API] deleted style directory: %s", style_dir)
        else:
            await file_store.delete_user_style(style["user_id"], style_id)
            logger.info("[API] deleted style files for user=%s style=%s", style["user_id"], style_id)
    await db.delete_ppt_style(style_id)
    return success_response(None)


# Regex for stripping external font <link> tags (Google Fonts, loli, fontshare, gstatic)
_FONT_LINK_RE = re.compile(
    r'<link[^>]*href=["\'][^"\']*(?:fonts\.googleapis|fonts\.loli|fontshare|gstatic)[^"\']*["\'][^>]*/?>',
    re.IGNORECASE,
)

# Regex for stripping viewport-related @media blocks (max-width, max-height, etc.)
# These break thumbnail rendering because they trigger at the small iframe viewport.
_VIEWPORT_MEDIA_RE = re.compile(
    r'@media\s*\([^)]*(?:max-width|min-width|max-height|min-height)[^)]*\)\s*\{(?:[^{}]*|\{[^{}]*\})*\}',
    re.DOTALL | re.IGNORECASE,
)

# CSS + JS injected before </head> in thumbnail mode.
# Forces .slide to a fixed 1920x1080 reference size and scales via transform.
_THUMB_INJECT = """<style>
html,body{margin:0;padding:0;overflow:hidden;background:transparent}
.slide{width:1920px !important;height:1080px !important;transform-origin:0 0}
</style>
<script>
(function(){
  function fit(){
    var ss=document.querySelectorAll('.slide');
    var scale=Math.min(innerWidth/1920,innerHeight/1080);
    ss.forEach(function(s){s.style.transform='scale('+scale+')'});
  }
  addEventListener('load',fit);
  addEventListener('resize',fit);
})();
</script>"""


def _apply_thumb_transforms(html_text: str) -> str:
    """Apply all thumbnail optimizations for consistent scaled rendering.

    1. Strip external font links (avoid render blocking)
    2. Strip viewport @media blocks (prevent responsive breakpoints in small iframe)
    3. Replace vw/vh/dvh with fixed px (1920x1080 reference, so clamp() resolves correctly)
    4. Inject fixed-size CSS + transform scale JS
    """
    html_text = _FONT_LINK_RE.sub("", html_text)
    html_text = re.sub(r'<link[^>]*rel=["\']preconnect["\'][^>]*/?>', '', html_text, flags=re.IGNORECASE)
    html_text = _VIEWPORT_MEDIA_RE.sub("", html_text)
    html_text = re.sub(r'([\d.]+)dvh', lambda m: f'{float(m.group(1)) * 10.8:.1f}px', html_text)
    html_text = re.sub(r'([\d.]+)vw', lambda m: f'{float(m.group(1)) * 19.2:.1f}px', html_text)
    html_text = re.sub(r'([\d.]+)vh', lambda m: f'{float(m.group(1)) * 10.8:.1f}px', html_text)
    html_text = html_text.replace("</head>", _THUMB_INJECT + "\n</head>", 1)
    return html_text


def _resource_replacements_from_manifest(raw_manifest: str | list | None, url_builder) -> list[tuple[str, str]]:
    if isinstance(raw_manifest, str):
        try:
            manifest = json.loads(raw_manifest)
        except (json.JSONDecodeError, TypeError):
            manifest = []
    elif isinstance(raw_manifest, list):
        manifest = raw_manifest
    else:
        manifest = []

    replacements: list[tuple[str, str]] = []
    for item in manifest:
        if not isinstance(item, dict):
            continue
        old_url = item.get("url")
        filename = item.get("filename")
        if isinstance(old_url, str) and isinstance(filename, str) and old_url:
            replacements.append((old_url, url_builder(filename)))
    return replacements


def _resource_path(prefix: str, filename: str) -> str:
    relative = PurePosixPath(filename)
    if relative.is_absolute() or ".." in relative.parts:
        raise HTTPException(status_code=400, detail="Invalid resource path")
    return str(PurePosixPath(prefix.rstrip("/")) / "resource" / relative)


async def _serve_html_file(
    file_path: str,
    *,
    replacements: list[tuple[str, str]] | None = None,
    thumb: int = 0,
):
    if not await file_store.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")
    html_text = (await file_store.read(file_path)).decode("utf-8", errors="replace")
    for old, new in replacements or []:
        html_text = html_text.replace(old, new)
    if thumb:
        html_text = _apply_thumb_transforms(html_text)
    return Response(
        content=html_text,
        media_type="text/html; charset=utf-8",
        headers={
            "Content-Disposition": "inline",
            "Cache-Control": "no-store, no-cache, must-revalidate",
            "Pragma": "no-cache",
        },
    )


async def _serve_file(file_path: str, disposition: str, thumb: int = 0):
    """Unified file serving via FileStore (local / OSS transparent).

    Parameters
    ----------
    file_path:   relative key like ``user/{user_id}/workspace/...``
    disposition: ``"attachment"`` (download) or ``"inline"`` (preview)
    thumb:       when 1 and file is HTML, strip external font <link> tags
    """
    if not await file_store.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")

    content = await file_store.read(file_path)
    mime, _ = guess_type(file_path)
    filename = Path(file_path).name

    # HTML + thumb mode: apply full thumbnail transforms
    if thumb and (mime or "").startswith("text/html"):
        html_text = content.decode("utf-8", errors="replace")
        html_text = _apply_thumb_transforms(html_text)
        return Response(
            content=html_text,
            media_type="text/html; charset=utf-8",
            headers={
                "Content-Disposition": disposition,
                "Cache-Control": "no-store, no-cache, must-revalidate",
                "Pragma": "no-cache",
            },
        )

    # Build Content-Disposition header
    if disposition == "attachment":
        # filename= must be ASCII-safe (HTTP headers are latin-1);
        # filename*=UTF-8 carries the real name for modern browsers (RFC 5987).
        ascii_name = filename.encode("ascii", errors="replace").decode("ascii")
        disp = f"attachment; filename=\"{ascii_name}\"; filename*=UTF-8''{quote(filename, safe='')}"
    else:
        disp = "inline"

    return Response(
        content=content,
        media_type=mime or "application/octet-stream",
        headers={
            "Content-Disposition": disp,
            "Cache-Control": "no-store, no-cache, must-revalidate",
            "Pragma": "no-cache",
        },
    )


def _get_task_file_path(task: dict, key: str = "file_path") -> str:
    result_data = _parse_json_object(task.get("result_data"))
    value = result_data.get(key, "")
    return value if isinstance(value, str) else ""


async def _get_completed_task(task_id: str, expected_type: str | None = None) -> dict:
    task = await db.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    if expected_type and task.get("type") != expected_type:
        raise HTTPException(status_code=400, detail=f"Task is not {expected_type}")
    if task.get("status") != "completed":
        raise HTTPException(status_code=400, detail="Task is not completed")
    return task


async def _get_active_share_context(token: str) -> tuple[dict, dict, dict | None]:
    share = await db.get_active_share_by_token(token)
    if not share:
        raise HTTPException(status_code=404, detail="Share not found")
    task = await db.get_task(share["task_id"])
    if not task or task.get("status") != "completed":
        raise HTTPException(status_code=404, detail="Share not found")
    if task.get("type") == "narration":
        parent_task = await db.get_task(task.get("parent_task_id", ""))
        if not parent_task or parent_task.get("status") != "completed":
            raise HTTPException(status_code=404, detail="Share not found")
        return share, task, parent_task
    return share, task, None


def _share_detail_payload(token: str, task: dict, parent_task: dict | None = None) -> dict:
    if task.get("type") == "ppt":
        return {
            "type": "ppt",
            "title": task.get("title") or "PPT",
            "ppt": {
                "title": task.get("title") or "PPT",
                "html_url": build_share_ppt_url(token),
            },
        }

    result_data = _parse_json_object(task.get("result_data"))
    slides = []
    for slide in result_data.get("slides", []):
        if not isinstance(slide, dict):
            continue
        number = slide.get("number")
        has_audio = bool(slide.get("audio_path"))
        safe_slide = {
            key: slide[key]
            for key in ("number", "title", "text")
            if key in slide
        }
        safe_slide["has_audio"] = has_audio
        if has_audio and isinstance(number, int):
            safe_slide["audio_url"] = build_share_audio_url(token, number)
        slides.append(safe_slide)

    ppt_task = parent_task or {}
    return {
        "type": "narration",
        "title": task.get("title") or "口播稿",
        "ppt": {
            "title": ppt_task.get("title") or "PPT",
            "html_url": build_share_ppt_url(token),
        },
        "narration": {
            "title": task.get("title") or "口播稿",
            "voice_name": result_data.get("voice_name", ""),
            "slides": slides,
        },
    }


@app.get("/api/shares/{token}")
async def get_share_detail(token: str):
    """Public share metadata without exposing storage paths."""
    logger.info("[API] GET /api/shares/%s", token)
    _, task, parent_task = await _get_active_share_context(token)
    return success_response(_share_detail_payload(token, task, parent_task))


@app.get("/api/shares/{token}/ppt")
async def preview_share_ppt(token: str):
    """Public readonly PPT HTML for a share link."""
    logger.info("[API] GET /api/shares/%s/ppt", token)
    _, task, parent_task = await _get_active_share_context(token)
    ppt_task = parent_task if task.get("type") == "narration" else task
    file_path = _get_task_file_path(ppt_task)
    if not file_path:
        raise HTTPException(status_code=404, detail="PPT file not found")
    return await _serve_file(file_path, disposition="inline")


@app.get("/api/shares/{token}/audio/{slide_number}")
async def preview_share_audio(token: str, slide_number: int):
    """Public narration audio for a share link."""
    logger.info("[API] GET /api/shares/%s/audio/%s", token, slide_number)
    _, task, _ = await _get_active_share_context(token)
    if task.get("type") != "narration":
        raise HTTPException(status_code=404, detail="Audio not found")
    result_data = _parse_json_object(task.get("result_data"))
    for slide in result_data.get("slides", []):
        if isinstance(slide, dict) and slide.get("number") == slide_number:
            audio_path = slide.get("audio_path")
            if audio_path:
                return await _serve_file(audio_path, disposition="inline")
            break
    raise HTTPException(status_code=404, detail="Audio not found")


@app.get("/api/tasks/{task_id}/preview")
async def preview_task_file(task_id: str, thumb: int = Query(default=0)):
    """Preview a completed PPT task by task id without exposing storage paths."""
    logger.info("[API] GET /api/tasks/%s/preview thumb=%s", task_id, thumb)
    task = await _get_completed_task(task_id, expected_type="ppt")
    file_path = _get_task_file_path(task)
    if not file_path:
        raise HTTPException(status_code=404, detail="No previewable file for this task")
    return await _serve_file(file_path, disposition="inline", thumb=thumb)


@app.get("/api/tasks/{task_id}/download")
async def download_task_file(task_id: str):
    """Download the output file of a task (Content-Disposition: attachment).

    Frontend only needs the taskId — the backend resolves the file path
    from the task's result_data, keeping storage details encapsulated.
    """
    logger.info("[API] GET /api/tasks/%s/download", task_id)
    task = await _get_completed_task(task_id, expected_type="ppt")
    file_path = _get_task_file_path(task)
    if not file_path:
        raise HTTPException(status_code=404, detail="No downloadable file for this task")
    return await _serve_file(file_path, disposition="attachment")


@app.get("/api/tasks/{task_id}/audio/{slide_number}")
async def preview_task_audio(task_id: str, slide_number: int):
    """Preview/play a narration slide audio by task id and slide number."""
    logger.info("[API] GET /api/tasks/%s/audio/%s", task_id, slide_number)
    task = await _get_completed_task(task_id, expected_type="narration")
    result_data = _parse_json_object(task.get("result_data"))
    for slide in result_data.get("slides", []):
        if isinstance(slide, dict) and slide.get("number") == slide_number:
            audio_path = slide.get("audio_path")
            if audio_path:
                return await _serve_file(audio_path, disposition="inline")
            break
    raise HTTPException(status_code=404, detail="Audio not found")


@app.get("/api/tasks/{task_id}/audio/{slide_number}/download")
async def download_task_audio(task_id: str, slide_number: int):
    """Download a narration slide audio by task id and slide number."""
    logger.info("[API] GET /api/tasks/%s/audio/%s/download", task_id, slide_number)
    task = await _get_completed_task(task_id, expected_type="narration")
    result_data = _parse_json_object(task.get("result_data"))
    for slide in result_data.get("slides", []):
        if isinstance(slide, dict) and slide.get("number") == slide_number:
            audio_path = slide.get("audio_path")
            if audio_path:
                return await _serve_file(audio_path, disposition="attachment")
            break
    raise HTTPException(status_code=404, detail="Audio not found")


@app.get("/api/tasks/{task_id}/narration-text")
async def preview_narration_text(task_id: str):
    """Preview narration markdown text by narration task id."""
    logger.info("[API] GET /api/tasks/%s/narration-text", task_id)
    task = await _get_completed_task(task_id, expected_type="narration")
    text_path = _get_task_file_path(task, key="text_file_path")
    if not text_path:
        raise HTTPException(status_code=404, detail="Narration text not found")
    return await _serve_file(text_path, disposition="inline")


@app.get("/api/tasks/{task_id}/narration-text/download")
async def download_narration_text(task_id: str):
    """Download narration markdown text by narration task id."""
    logger.info("[API] GET /api/tasks/%s/narration-text/download", task_id)
    task = await _get_completed_task(task_id, expected_type="narration")
    text_path = _get_task_file_path(task, key="text_file_path")
    if not text_path:
        raise HTTPException(status_code=404, detail="Narration text not found")
    return await _serve_file(text_path, disposition="attachment")


@app.get("/api/tasks/{task_id}/style-preview")
async def preview_style_extraction_task(task_id: str, thumb: int = Query(default=0)):
    """Preview a completed style extraction task by task id."""
    logger.info("[API] GET /api/tasks/%s/style-preview thumb=%s", task_id, thumb)
    task = await _get_completed_task(task_id, expected_type="ppt_style_extraction")
    preview_path = _get_task_file_path(task, key="preview_html_path")
    if not preview_path:
        raise HTTPException(status_code=404, detail="Style preview not found")
    result_data = _parse_json_object(task.get("result_data"))
    replacements = _resource_replacements_from_manifest(
        result_data.get("resource_manifest"),
        lambda filename: build_style_extraction_resource_url(task_id, filename),
    )
    return await _serve_html_file(preview_path, replacements=replacements, thumb=thumb)


@app.get("/api/tasks/{task_id}/style-resource/{filename:path}")
async def preview_style_extraction_resource(task_id: str, filename: str):
    """Serve a style extraction resource by task id and resource filename."""
    logger.info("[API] GET /api/tasks/%s/style-resource/%s", task_id, filename)
    task = await _get_completed_task(task_id, expected_type="ppt_style_extraction")
    result_data = _parse_json_object(task.get("result_data"))
    resource_prefix = result_data.get("resource_prefix", "")
    if not isinstance(resource_prefix, str) or not resource_prefix:
        raise HTTPException(status_code=404, detail="Resource not found")
    resource_path = _resource_path(resource_prefix, filename)
    return await _serve_file(resource_path, disposition="inline")


@app.get("/api/files/{file_path:path}")
async def download_file(file_path: str):
    """Download a file by its storage path (Content-Disposition: attachment).

    For inline preview, use GET /api/file-view/{file_path} instead.
    """
    logger.info("[API] GET /api/files/%s", file_path)
    raise HTTPException(status_code=410, detail="Path-based file access is disabled")


@app.get("/api/file-view/{file_path:path}")
async def view_file(file_path: str, thumb: int = Query(default=0)):
    """Serve a file inline for browser preview (Content-Disposition: inline).

    When thumb=1 and file is HTML, external font <link> tags are stripped.
    """
    logger.info("[API] GET /api/file-view/%s thumb=%s", file_path, thumb)
    raise HTTPException(status_code=410, detail="Path-based file access is disabled")


@app.get("/api/documents/{doc_id}/asset/{filename:path}")
async def preview_document_asset(doc_id: str, filename: str):
    """Serve an extracted document asset without exposing storage paths."""
    logger.info("[API] GET /api/documents/%s/asset/%s", doc_id, filename)
    relative = PurePosixPath(filename)
    if relative.is_absolute() or ".." in relative.parts:
        raise HTTPException(status_code=400, detail="Invalid asset path")
    if db.connection is None:
        await db.initialize()
    cursor = await db.connection.execute(
        "SELECT * FROM document WHERE id = ?",
        (doc_id,),
    )
    row = await cursor.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Document not found")
    doc = dict(row)
    storage_path = str(doc.get("storage_path", ""))
    if not storage_path:
        raise HTTPException(status_code=404, detail="Document asset not found")
    asset_dir = f"{Path(doc.get('filename', '')).stem}_assets"
    if Path(storage_path).is_absolute():
        asset_path = str(Path(storage_path).parent / asset_dir / str(relative))
    else:
        asset_path = str(PurePosixPath(storage_path).parent / asset_dir / relative)
    return await _serve_file(asset_path, disposition="inline")


# --- Static assets for PPT skill ---

_static_dir = Path(__file__).resolve().parent.parent.parent / "static"
_static_mounts = {
    "/ppt-assets": _static_dir / "ppt-assets",
    "/ppt-templates": _static_dir / "ppt-templates",
}
for mount_path, directory in _static_mounts.items():
    if directory.exists():
        app.mount(mount_path, StaticFiles(directory=str(directory)), name=mount_path.strip("/"))
    else:
        logger.warning("[API] static directory missing, skip mount: %s", directory)


@app.get("/api/ppt-styles/{style_id}/preview")
async def preview_ppt_style_by_id(style_id: str, thumb: int = Query(default=0)):
    """Serve PPT style preview by style id without exposing preview_path."""
    logger.info("[API] GET /api/ppt-styles/%s/preview thumb=%s", style_id, thumb)
    style = await db.get_ppt_style(style_id)
    if not style:
        raise HTTPException(status_code=404, detail="Style not found")

    preview_path = style.get("preview_path", "")
    if not preview_path:
        raise HTTPException(status_code=404, detail="Preview file not found")

    builtin_dir = _static_dir / "ppt-styles"
    if style.get("user_id") == "system":
        resolved = builtin_dir / preview_path
        if not resolved.exists():
            raise HTTPException(status_code=404, detail="Preview file not found")
        html_text = resolved.read_text(encoding="utf-8")
    else:
        if not await file_store.exists(preview_path):
            raise HTTPException(status_code=404, detail="Preview file not found")
        html_text = (await file_store.read(preview_path)).decode("utf-8", errors="replace")
        replacements = _resource_replacements_from_manifest(
            style.get("resource_manifest"),
            lambda filename: build_style_resource_url(style_id, filename),
        )
        for old, new in replacements:
            html_text = html_text.replace(old, new)

    if thumb:
        html_text = _apply_thumb_transforms(html_text)
    return Response(
        content=html_text,
        media_type="text/html; charset=utf-8",
        headers={
            "Content-Disposition": "inline",
            "Cache-Control": "no-store, no-cache, must-revalidate",
            "Pragma": "no-cache",
        },
    )


@app.get("/api/ppt-styles/{style_id}/resource/{filename:path}")
async def preview_ppt_style_resource(style_id: str, filename: str):
    """Serve a custom style resource by style id and resource filename."""
    logger.info("[API] GET /api/ppt-styles/%s/resource/%s", style_id, filename)
    style = await db.get_ppt_style(style_id)
    if not style:
        raise HTTPException(status_code=404, detail="Style not found")
    if style.get("user_id") == "system":
        raise HTTPException(status_code=404, detail="Resource not found")
    preview_path = style.get("preview_path", "")
    if not preview_path:
        raise HTTPException(status_code=404, detail="Resource not found")
    resource_path = _resource_path(str(PurePosixPath(preview_path).parent), filename)
    return await _serve_file(resource_path, disposition="inline")


@app.get("/api/ppt-style-preview/{preview_path:path}")
async def preview_ppt_style(preview_path: str, thumb: int = Query(default=0)):
    """Serve PPT style preview HTML for both system and custom styles.

    - System styles: plain filename (e.g. "01-bold-signal.html") served from static/ppt-styles/
    - Custom styles: served inline via FileStore (local or OSS)
    """
    logger.info("[API] GET /api/ppt-style-preview/%s thumb=%s", preview_path, thumb)
    raise HTTPException(status_code=410, detail="Path-based style preview is disabled")
    builtin_dir = _static_dir / "ppt-styles"

    # System styles: plain filename (no path separator)
    if "/" not in preview_path and "\\" not in preview_path:
        resolved = builtin_dir / preview_path
        if not resolved.exists():
            raise HTTPException(status_code=404, detail=f"Preview file not found: {preview_path}")
        # For thumb mode, apply full thumbnail transforms
        if thumb:
            html_text = resolved.read_text(encoding="utf-8")
            html_text = _apply_thumb_transforms(html_text)
            return Response(
                content=html_text,
                media_type="text/html; charset=utf-8",
                headers={"Cache-Control": "no-store, no-cache, must-revalidate", "Pragma": "no-cache"},
            )
        response = FileResponse(path=str(resolved), media_type="text/html")
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        return response

    # Custom styles: serve inline via FileStore (local or OSS transparent)
    if not await file_store.exists(preview_path):
        raise HTTPException(status_code=404, detail=f"Preview file not found: {preview_path}")
    content = await file_store.read(preview_path)
    html_text = content.decode("utf-8", errors="replace")
    if thumb:
        html_text = _apply_thumb_transforms(html_text)
    return Response(
        content=html_text,
        media_type="text/html; charset=utf-8",
        headers={
            "Content-Disposition": "inline",
            "Cache-Control": "no-store, no-cache, must-revalidate",
            "Pragma": "no-cache",
        },
    )
