import json

import pytest

from src.api import routes
from src.exceptions import BizException
from src.storage.database import Database


def _write_invites(path, invites):
    path.write_text(
        json.dumps({"version": 1, "invites": invites}, ensure_ascii=False),
        encoding="utf-8",
    )


def _payload(response):
    return response["data"]


async def test_claim_invite_returns_mapped_user_and_nickname(tmp_path, monkeypatch):
    invite_file = tmp_path / "invites.json"
    _write_invites(
        invite_file,
        [
            {
                "code": "RUMI-ALPHA-001",
                "user_id": "11111111-1111-4111-8111-111111111111",
                "nickname": "Alice",
                "enabled": True,
                "note": "internal note",
            }
        ],
    )
    registry = routes.InviteRegistry(str(invite_file))
    monkeypatch.setattr(routes, "invite_registry", registry)

    data = _payload(await routes.claim_invite(routes.ClaimInviteRequest(code="RUMI-ALPHA-001")))

    assert data == {
        "user_id": "11111111-1111-4111-8111-111111111111",
        "nickname": "Alice",
    }


async def test_invite_registry_reloads_when_file_changes(tmp_path, monkeypatch):
    invite_file = tmp_path / "invites.json"
    _write_invites(
        invite_file,
        [
            {
                "code": "OLD-CODE",
                "user_id": "11111111-1111-4111-8111-111111111111",
                "nickname": "Old",
                "enabled": True,
            }
        ],
    )
    registry = routes.InviteRegistry(str(invite_file))
    monkeypatch.setattr(routes, "invite_registry", registry)
    assert _payload(await routes.claim_invite(routes.ClaimInviteRequest(code="OLD-CODE")))["nickname"] == "Old"

    _write_invites(
        invite_file,
        [
            {
                "code": "NEW-CODE",
                "user_id": "22222222-2222-4222-8222-222222222222",
                "nickname": "New",
                "enabled": True,
            }
        ],
    )

    data = _payload(await routes.claim_invite(routes.ClaimInviteRequest(code="NEW-CODE")))

    assert data["user_id"] == "22222222-2222-4222-8222-222222222222"


async def test_workspace_apis_reject_user_id_not_backed_by_invite(tmp_path, monkeypatch):
    invite_file = tmp_path / "invites.json"
    valid_user_id = "11111111-1111-4111-8111-111111111111"
    _write_invites(
        invite_file,
        [
            {
                "code": "RUMI-ALPHA-001",
                "user_id": valid_user_id,
                "nickname": "Alice",
                "enabled": True,
            }
        ],
    )
    registry = routes.InviteRegistry(str(invite_file))
    db = Database(str(tmp_path / "rumi_ai.db"))
    await db.initialize()
    monkeypatch.setattr(routes, "invite_registry", registry)
    monkeypatch.setattr(routes, "db", db)

    await routes.create_workspace(routes.CreateWorkspaceRequest(user_id=valid_user_id, name="Valid"))

    with pytest.raises(BizException):
        await routes.create_workspace(
            routes.CreateWorkspaceRequest(user_id="old-localstorage-user", name="Invalid")
        )
    with pytest.raises(BizException):
        await routes.list_workspaces(user_id="old-localstorage-user")


async def test_workspace_id_access_rejects_workspace_owned_by_uninvited_user(tmp_path, monkeypatch):
    invite_file = tmp_path / "invites.json"
    _write_invites(
        invite_file,
        [
            {
                "code": "RUMI-ALPHA-001",
                "user_id": "11111111-1111-4111-8111-111111111111",
                "nickname": "Alice",
                "enabled": True,
            }
        ],
    )
    registry = routes.InviteRegistry(str(invite_file))
    db = Database(str(tmp_path / "rumi_ai.db"))
    await db.initialize()
    old_workspace = await db.create_workspace("old-localstorage-user", "Old")
    monkeypatch.setattr(routes, "invite_registry", registry)
    monkeypatch.setattr(routes, "db", db)

    with pytest.raises(BizException):
        await routes.get_workspace(old_workspace["id"])
