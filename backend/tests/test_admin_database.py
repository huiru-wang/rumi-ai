from datetime import datetime, timedelta, timezone

import pytest

from src.storage.database import Database


@pytest.fixture
async def database(tmp_path):
    db = Database(str(tmp_path / "rumi.db"))
    await db.initialize()
    try:
        yield db
    finally:
        await db.close()


async def test_import_and_claim_invite_tracks_first_and_latest_claim(database):
    await database.import_invites(
        [
            {
                "code": "RUMI-LEGACY",
                "user_id": "11111111-1111-4111-8111-111111111111",
                "nickname": "老用户",
                "enabled": True,
                "expires_at": None,
            }
        ]
    )

    first = await database.claim_invite(" RUMI-LEGACY ")
    second = await database.claim_invite("RUMI-LEGACY")

    assert first["user_id"] == "11111111-1111-4111-8111-111111111111"
    assert first["nickname"] == "老用户"
    assert first["claim_count"] == 1
    assert first["claimed_at"]
    assert second["claim_count"] == 2
    assert second["claimed_at"] == first["claimed_at"]
    assert second["last_claimed_at"] >= first["last_claimed_at"]


async def test_generated_invite_is_immediately_claimable_and_can_be_disabled(database):
    invite = await database.create_invite("测试用户")

    assert invite["code"].startswith("RUMI-")
    assert await database.claim_invite(invite["code"])

    await database.set_invite_enabled(invite["id"], False)

    assert await database.claim_invite(invite["code"]) is None


async def test_legacy_import_does_not_override_admin_status(database):
    record = {
        "code": "RUMI-IMPORTED",
        "user_id": "22222222-2222-4222-8222-222222222222",
        "nickname": "导入用户",
        "enabled": True,
        "expires_at": None,
    }
    await database.import_invites([record])
    page = await database.list_invites()
    await database.set_invite_enabled(page["items"][0]["id"], False)

    await database.import_invites([record])

    assert await database.claim_invite(record["code"]) is None


async def test_legacy_import_ignores_duplicate_user_mapping(database):
    user_id = "33333333-3333-4333-8333-333333333333"

    await database.import_invites(
        [
            {"code": "RUMI-FIRST", "user_id": user_id, "nickname": "用户", "enabled": True},
            {"code": "RUMI-SECOND", "user_id": user_id, "nickname": "用户", "enabled": True},
        ]
    )

    page = await database.list_invites()
    assert page["total"] == 1


async def test_expired_invite_cannot_be_claimed(database):
    expired = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()
    invite = await database.create_invite("过期用户", expires_at=expired)

    assert await database.claim_invite(invite["code"]) is None


async def test_invite_list_masks_existing_codes(database):
    await database.create_invite("测试用户", code="RUMI-ABCD-EFGH")

    page = await database.list_invites(page=1, page_size=20)

    assert page["total"] == 1
    assert page["items"][0]["code_masked"] == "RUMI-****-EFGH"
    assert "code" not in page["items"][0]


async def test_admin_dashboard_reports_usage_conversion_and_trends(database):
    first = await database.create_invite("活跃用户", code="RUMI-ACTIVE")
    second = await database.create_invite("普通用户", code="RUMI-SECOND")
    await database.claim_invite(first["code"])
    await database.claim_invite(second["code"])
    first_workspace = await database.create_workspace(first["user_id"], "活跃空间")
    second_workspace = await database.create_workspace(second["user_id"], "普通空间")
    orphan_workspace = await database.create_workspace("orphan-user", "孤立空间")
    orphan_ppt = await database.create_task(orphan_workspace["id"], "ppt", "孤立任务")
    await database.update_task(orphan_ppt["id"], status="completed")
    old = (datetime.now() - timedelta(days=10)).isoformat()
    await database.connection.execute(
        "UPDATE workspace SET created_at = ? WHERE id = ?",
        (old, second_workspace["id"]),
    )
    await database.create_document(
        first_workspace["id"], "report.pdf", "pdf", "safe/path/report.pdf"
    )
    await database.connection.execute(
        "UPDATE document SET status = 'ready' WHERE workspace_id = ?",
        (first_workspace["id"],),
    )
    await database.record_message(
        thread_id="thread-active",
        workspace_id=first_workspace["id"],
        message_id="human-1",
        role="human",
        content="生成一个 PPT",
    )
    ppt = await database.create_task(first_workspace["id"], "ppt", "汇报")
    await database.update_task(ppt["id"], status="completed")
    narration = await database.create_task(
        first_workspace["id"], "narration", "口播稿", parent_task_id=ppt["id"]
    )
    await database.update_task(narration["id"], status="completed")
    await database.create_or_get_active_share(await database.get_task(ppt["id"]))
    await database.connection.commit()

    dashboard = await database.get_admin_dashboard(days=7)

    assert dashboard["range_days"] == 7
    assert dashboard["kpis"] == {
        "total_users": 2,
        "active_today": 1,
        "active_7d": 1,
        "core_conversion_rate": 50.0,
        "completed_ppts": 1,
        "completed_narrations": 1,
    }
    assert "new_users" not in dashboard["kpis"]
    assert len(dashboard["trends"]) == 7
    assert dashboard["trends"][-1]["active_users"] == 1
    assert dashboard["trends"][-1]["human_messages"] == 1
    assert "funnel" not in dashboard
    assert "features" not in dashboard


async def test_admin_user_list_contains_usage_summary(database):
    invite = await database.create_invite("张三", code="RUMI-ZHANGSAN")
    await database.claim_invite(invite["code"])
    workspace = await database.create_workspace(invite["user_id"], "项目空间")
    await database.create_document(
        workspace["id"], "notes.md", "markdown", "safe/path/notes.md"
    )
    await database.record_message(
        thread_id="thread-user",
        workspace_id=workspace["id"],
        message_id="human-user",
        role="human",
        content="总结文档",
    )
    ppt = await database.create_task(workspace["id"], "ppt", "总结")
    await database.update_task(ppt["id"], status="completed")

    page = await database.list_admin_users(page=1, page_size=20, keyword="张三")

    assert page["total"] == 1
    user = page["items"][0]
    assert user["nickname"] == "张三"
    assert user["workspace_count"] == 1
    assert user["document_count"] == 1
    assert user["message_count"] == 1
    assert user["ppt_count"] == 1
    assert user["last_active_at"]
