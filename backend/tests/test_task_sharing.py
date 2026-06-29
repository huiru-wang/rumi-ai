import json

from fastapi import HTTPException

from src.api import routes
from src.storage.database import Database
from src.storage.file_store import FileStore
from src.storage.providers import LocalProvider


async def _make_store(tmp_path, monkeypatch):
    db = Database(str(tmp_path / "rumi_ai.db"))
    await db.initialize()
    provider = LocalProvider(str(tmp_path / "files"))
    store = FileStore(str(tmp_path / "files"), provider=provider, db=db)
    workspace = await db.create_workspace("user-test", "Workspace")
    monkeypatch.setattr(routes, "db", db)
    monkeypatch.setattr(routes, "file_store", store)
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


async def _create_completed_ppt(db, store, workspace_id):
    task = await db.create_task(workspace_id, "ppt", "Share PPT")
    file_path = await store.save_ppt_file(
        workspace_id,
        task["id"],
        "share.html",
        b"<html><body><section class='slide'>Shared PPT</section></body></html>",
    )
    await db.update_task(
        task["id"],
        status="completed",
        result_data=json.dumps({"file_path": file_path, "filename": "share.html"}),
    )
    return task


async def _create_completed_narration(db, store, workspace_id, ppt_task):
    task = await db.create_task(
        workspace_id,
        "narration",
        "Share Narration",
        parent_task_id=ppt_task["id"],
    )
    audio_path = await store.save_ppt_file(
        workspace_id,
        ppt_task["id"],
        "slide-1.wav",
        b"audio-bytes",
    )
    await db.update_task(
        task["id"],
        status="completed",
        result_data=json.dumps(
            {
                "voice_name": "Cherry",
                "slides": [
                    {
                        "number": 1,
                        "title": "Intro",
                        "text": "Hello",
                        "audio_path": audio_path,
                    }
                ],
            },
            ensure_ascii=False,
        ),
    )
    return task


async def test_create_ppt_share_returns_token_without_public_url_or_paths(tmp_path, monkeypatch):
    db, store, workspace_id = await _make_store(tmp_path, monkeypatch)
    ppt = await _create_completed_ppt(db, store, workspace_id)

    data = _payload(await routes.create_task_share(ppt["id"]))

    assert data["enabled"] is True
    assert data["type"] == "ppt"
    assert data["token"]
    assert "url" not in data
    assert "path" not in data
    _assert_no_storage_paths(data)


async def test_public_ppt_share_detail_and_html_are_readonly_and_pathless(tmp_path, monkeypatch):
    db, store, workspace_id = await _make_store(tmp_path, monkeypatch)
    ppt = await _create_completed_ppt(db, store, workspace_id)
    share = _payload(await routes.create_task_share(ppt["id"]))

    detail = _payload(await routes.get_share_detail(share["token"]))
    html = await routes.preview_share_ppt(share["token"])

    assert detail["type"] == "ppt"
    assert detail["ppt"]["html_url"] == f"/api/shares/{share['token']}/ppt"
    assert b"Shared PPT" in html.body
    _assert_no_storage_paths(detail)


async def test_public_narration_share_detail_and_audio_are_pathless(tmp_path, monkeypatch):
    db, store, workspace_id = await _make_store(tmp_path, monkeypatch)
    ppt = await _create_completed_ppt(db, store, workspace_id)
    narration = await _create_completed_narration(db, store, workspace_id, ppt)
    share = _payload(await routes.create_task_share(narration["id"]))

    detail = _payload(await routes.get_share_detail(share["token"]))
    audio = await routes.preview_share_audio(share["token"], 1)

    assert detail["type"] == "narration"
    assert detail["ppt"]["html_url"] == f"/api/shares/{share['token']}/ppt"
    assert detail["narration"]["slides"][0]["audio_url"] == f"/api/shares/{share['token']}/audio/1"
    assert audio.body == b"audio-bytes"
    _assert_no_storage_paths(detail)


async def test_cancel_share_invalidates_public_link(tmp_path, monkeypatch):
    db, store, workspace_id = await _make_store(tmp_path, monkeypatch)
    ppt = await _create_completed_ppt(db, store, workspace_id)
    share = _payload(await routes.create_task_share(ppt["id"]))

    await routes.delete_task_share(ppt["id"])

    status = _payload(await routes.get_task_share(ppt["id"]))
    assert status["enabled"] is False
    try:
        await routes.get_share_detail(share["token"])
    except HTTPException as exc:
        assert exc.status_code == 404
    else:
        raise AssertionError("revoked share should be inaccessible")


async def test_delete_ppt_task_invalidates_parent_and_child_shares(tmp_path, monkeypatch):
    db, store, workspace_id = await _make_store(tmp_path, monkeypatch)
    ppt = await _create_completed_ppt(db, store, workspace_id)
    narration = await _create_completed_narration(db, store, workspace_id, ppt)
    ppt_share = _payload(await routes.create_task_share(ppt["id"]))
    narration_share = _payload(await routes.create_task_share(narration["id"]))

    await routes.delete_task(workspace_id, ppt["id"])

    for token in (ppt_share["token"], narration_share["token"]):
        try:
            await routes.get_share_detail(token)
        except HTTPException as exc:
            assert exc.status_code == 404
        else:
            raise AssertionError("shares for deleted tasks should be inaccessible")
