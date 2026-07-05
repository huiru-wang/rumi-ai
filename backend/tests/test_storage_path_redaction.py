import json

from fastapi import HTTPException

from src.api import routes
from src.storage.database import Database
from src.storage.file_store import FileStore
from src.storage.providers import LocalProvider


class _AllowTestUserRegistry:
    def is_valid_user_id(self, user_id: str) -> bool:
        return user_id == "user-test"


async def _make_store(tmp_path, monkeypatch):
    db = Database(str(tmp_path / "rumi_ai.db"))
    await db.initialize()
    provider = LocalProvider(str(tmp_path / "files"))
    store = FileStore(str(tmp_path / "files"), provider=provider, db=db)
    workspace = await db.create_workspace("user-test", "Workspace")
    monkeypatch.setattr(routes, "invite_registry", _AllowTestUserRegistry())
    return db, store, workspace["id"]


def _payload(response):
    if isinstance(response, dict):
        return response["data"]
    return json.loads(response.body.decode("utf-8"))["data"]


def _assert_no_storage_paths(value):
    text = json.dumps(value, ensure_ascii=False)
    forbidden = [
        "storage_path",
        "file_path",
        "audio_path",
        "text_file_path",
        "preview_path",
        "preview_html_path",
        "pptx_storage_key",
        "resource_prefix",
        "/workspace/",
        "user/user-test/",
        "aliyuncs.com",
        "oss-",
    ]
    leaked = [token for token in forbidden if token in text]
    assert leaked == []


async def test_document_api_redacts_storage_path(tmp_path, monkeypatch):
    db, store, workspace_id = await _make_store(tmp_path, monkeypatch)
    monkeypatch.setattr(routes, "db", db)
    monkeypatch.setattr(routes, "file_store", store)

    await db.create_document(
        workspace_id=workspace_id,
        filename="source.pdf",
        file_type="pdf",
        storage_path=f"user/user-test/workspace/{workspace_id}/docs/source.pdf",
        content_hash="hash",
    )

    data = _payload(await routes.list_documents(workspace_id))

    assert data[0]["filename"] == "source.pdf"
    _assert_no_storage_paths(data)


async def test_task_api_redacts_result_data_storage_paths(tmp_path, monkeypatch):
    db, store, workspace_id = await _make_store(tmp_path, monkeypatch)
    monkeypatch.setattr(routes, "db", db)
    monkeypatch.setattr(routes, "file_store", store)

    ppt = await db.create_task(workspace_id, "ppt", "Demo PPT")
    await db.update_task(
        ppt["id"],
        status="completed",
        result_data=json.dumps(
            {
                "file_path": f"user/user-test/workspace/{workspace_id}/ppt/ppt-1/demo.html",
                "filename": "demo.html",
                "ppt_style": "sys-swiss-modern",
                "ppt_style_name": "瑞士现代",
            },
            ensure_ascii=False,
        ),
    )
    narration = await db.create_task(workspace_id, "narration", "Demo Narration", parent_task_id=ppt["id"])
    await db.update_task(
        narration["id"],
        status="completed",
        result_data=json.dumps(
            {
                "text_file_path": f"user/user-test/workspace/{workspace_id}/ppt/ppt-1/narration.md",
                "slides": [
                    {
                        "number": 1,
                        "title": "Intro",
                        "text": "Hello",
                        "audio_path": f"user/user-test/workspace/{workspace_id}/ppt/ppt-1/1.wav",
                    }
                ],
            }
        ),
    )

    data = _payload(await routes.list_tasks(workspace_id))

    assert data[0]["result_data"]["filename"] == "demo.html"
    assert data[0]["children"][0]["result_data"]["slides"][0]["has_audio"] is True
    _assert_no_storage_paths(data)


async def test_ppt_styles_api_redacts_preview_path(tmp_path, monkeypatch):
    db, store, _workspace_id = await _make_store(tmp_path, monkeypatch)
    monkeypatch.setattr(routes, "db", db)
    monkeypatch.setattr(routes, "file_store", store)

    await db.create_ppt_style(
        user_id="user-test",
        category="custom",
        name="Custom",
        name_en="custom",
        description="desc",
        preview_path="user/user-test/style/style-1/preview.html",
    )

    data = _payload(await routes.list_ppt_styles(user_id="user-test"))

    assert any(style["name"] == "Custom" for style in data)
    _assert_no_storage_paths(data)


async def test_task_preview_and_download_use_task_id_not_file_path(tmp_path, monkeypatch):
    db, store, workspace_id = await _make_store(tmp_path, monkeypatch)
    monkeypatch.setattr(routes, "db", db)
    monkeypatch.setattr(routes, "file_store", store)

    ppt = await db.create_task(workspace_id, "ppt", "Demo PPT")
    file_path = await store.save_ppt_file(workspace_id, ppt["id"], "demo.html", b"<html><body>Demo</body></html>")
    await db.update_task(
        ppt["id"],
        status="completed",
        result_data=json.dumps({"file_path": file_path, "filename": "demo.html"}),
    )

    preview = await routes.preview_task_file(ppt["id"])
    download = await routes.download_task_file(ppt["id"])

    assert preview.headers["Content-Disposition"] == "inline"
    assert "attachment" in download.headers["Content-Disposition"]
    assert b"Demo" in preview.body


async def test_old_path_based_file_routes_are_not_public(tmp_path, monkeypatch):
    db, store, workspace_id = await _make_store(tmp_path, monkeypatch)
    monkeypatch.setattr(routes, "db", db)
    monkeypatch.setattr(routes, "file_store", store)

    path = await store.save_ppt_file(workspace_id, "task-1", "demo.html", b"secret")

    for handler in (routes.download_file, routes.view_file):
        try:
            await handler(path)
        except HTTPException as exc:
            assert exc.status_code in {404, 410}
        else:
            raise AssertionError("path-based file route should not serve files")


async def test_document_asset_preview_uses_doc_id_not_public_path(tmp_path, monkeypatch):
    db, store, workspace_id = await _make_store(tmp_path, monkeypatch)
    monkeypatch.setattr(routes, "db", db)
    monkeypatch.setattr(routes, "file_store", store)

    source_path = await store.save_doc(workspace_id, "source.docx", b"source")
    doc = await db.create_document(
        workspace_id=workspace_id,
        filename="source.docx",
        file_type="docx",
        storage_path=source_path,
        content_hash="hash",
    )
    await store.save_doc(workspace_id, "source_assets/image_0001.png", b"image-bytes")

    response = await routes.preview_document_asset(doc["id"], "image_0001.png")

    assert response.headers["Content-Disposition"] == "inline"
    assert response.body == b"image-bytes"
