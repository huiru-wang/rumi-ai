import sys
import types

import httpx
import pytest

from src.admin_auth import AdminAuth
from src.storage.database import Database

fake_deps = types.ModuleType("src.api.deps")
fake_deps.db = None
fake_deps.doc_service = None
fake_deps.file_store = None
fake_deps.style_extract_manager = None
sys.modules["src.api.deps"] = fake_deps

from src.api import routes  # noqa: E402


@pytest.fixture
async def api_client(tmp_path, monkeypatch):
    database = Database(str(tmp_path / "api.db"))
    await database.initialize()
    monkeypatch.setattr(routes, "db", database)
    monkeypatch.setattr(
        routes,
        "admin_auth",
        AdminAuth("admin", "test-password", "test-session-secret"),
        raising=False,
    )
    transport = httpx.ASGITransport(app=routes.app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        yield client, database
    await database.close()


async def test_admin_dashboard_requires_login(api_client):
    client, _ = api_client

    response = await client.get("/api/admin/dashboard")

    assert response.status_code == 401


async def test_admin_can_login_and_read_dashboard(api_client):
    client, _ = api_client
    login = await client.post(
        "/api/admin/session",
        json={"username": "admin", "password": "test-password"},
    )

    assert login.status_code == 200
    token = login.json()["data"]["token"]
    response = await client.get(
        "/api/admin/dashboard?days=7",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    assert response.json()["data"]["kpis"]["total_users"] == 0
    assert "new_users" not in response.json()["data"]["kpis"]
    assert "funnel" not in response.json()["data"]
    assert "features" not in response.json()["data"]


async def test_admin_generated_invite_can_be_claimed_immediately(api_client):
    client, _ = api_client
    login = await client.post(
        "/api/admin/session",
        json={"username": "admin", "password": "test-password"},
    )
    token = login.json()["data"]["token"]
    created = await client.post(
        "/api/admin/invites",
        json={"nickname": "新用户", "expires_at": None},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert created.status_code == 200
    code = created.json()["data"]["code"]
    claimed = await client.post("/api/invites/claim", json={"code": code})

    assert claimed.status_code == 200
    assert claimed.json()["code"] == 0
    assert claimed.json()["data"]["nickname"] == "新用户"


async def test_admin_invite_rejects_invalid_expiration(api_client):
    client, _ = api_client
    login = await client.post(
        "/api/admin/session",
        json={"username": "admin", "password": "test-password"},
    )
    token = login.json()["data"]["token"]

    response = await client.post(
        "/api/admin/invites",
        json={"nickname": "新用户", "expires_at": "not-a-date"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 422
