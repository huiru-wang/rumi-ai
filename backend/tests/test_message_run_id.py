from types import SimpleNamespace

import aiosqlite
from langchain_core.messages import AIMessage, ToolMessage

from src.agent.message_history import MessageHistoryCallback, MessageHistoryMiddleware
from src.storage.database import Database


async def test_message_run_id_is_persisted_and_returned(tmp_path):
    db = Database(str(tmp_path / "test.db"))

    await db.record_message(
        thread_id="thread-1",
        workspace_id="workspace-1",
        run_id="run-1",
        message_id="message-1",
        role="human",
        content="hello",
    )

    page = await db.list_thread_messages("thread-1")

    assert page["messages"][0]["run_id"] == "run-1"


async def test_message_run_id_is_not_overwritten_on_upsert(tmp_path):
    db = Database(str(tmp_path / "test.db"))

    await db.record_message(
        thread_id="thread-1",
        workspace_id="workspace-1",
        run_id="run-1",
        message_id="message-1",
        role="human",
        content="hello",
    )
    await db.record_message(
        thread_id="thread-1",
        workspace_id="workspace-1",
        run_id="run-2",
        message_id="message-1",
        role="human",
        content="hello again",
    )

    message = await db.get_message_by_id("message-1", "thread-1")

    assert message is not None
    assert message["run_id"] == "run-1"
    assert message["content"] == "hello again"


async def test_message_run_id_backfills_when_existing_message_has_no_run_id(tmp_path):
    db = Database(str(tmp_path / "test.db"))

    await db.record_message(
        thread_id="thread-1",
        workspace_id="workspace-1",
        run_id=None,
        message_id="message-1",
        role="human",
        content="hello",
    )
    await db.record_message(
        thread_id="thread-1",
        workspace_id="workspace-1",
        run_id="run-1",
        message_id="message-1",
        role="human",
        content="hello again",
    )

    message = await db.get_message_by_id("message-1", "thread-1")

    assert message is not None
    assert message["run_id"] == "run-1"
    assert message["content"] == "hello again"


async def test_message_run_id_migration_adds_column_before_indexes(tmp_path):
    db_path = tmp_path / "legacy.db"
    conn = await aiosqlite.connect(str(db_path))
    await conn.executescript(
        """
        CREATE TABLE message (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            thread_id TEXT NOT NULL,
            workspace_id TEXT,
            message_id TEXT NOT NULL,
            role TEXT NOT NULL,
            type TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            UNIQUE(thread_id, message_id, role)
        );
        """
    )
    await conn.commit()
    await conn.close()

    db = Database(str(db_path))
    await db.initialize()

    cursor = await db.connection.execute("PRAGMA table_info(message)")
    columns = {row["name"] for row in await cursor.fetchall()}
    cursor = await db.connection.execute(
        "SELECT name FROM sqlite_master WHERE type = 'index' AND name IN (?, ?)",
        ("idx_message_thread_run", "idx_message_run"),
    )
    indexes = {row["name"] for row in await cursor.fetchall()}

    assert "run_id" in columns
    assert indexes == {"idx_message_thread_run", "idx_message_run"}


async def test_message_history_middleware_records_runtime_run_id(tmp_path):
    db = Database(str(tmp_path / "test.db"))
    middleware = MessageHistoryMiddleware(MessageHistoryCallback(db))
    runtime = SimpleNamespace(
        execution_info=SimpleNamespace(thread_id="thread-1", run_id="run-1")
    )

    await middleware._record_state_messages(
        {"workspace_id": "workspace-1", "messages": [{"type": "human", "id": "message-1", "content": "hello"}]},
        runtime,
    )

    message = await db.get_message_by_id("message-1", "thread-1")

    assert message is not None
    assert message["run_id"] == "run-1"


async def test_message_history_middleware_allows_missing_runtime_run_id(tmp_path):
    db = Database(str(tmp_path / "test.db"))
    middleware = MessageHistoryMiddleware(MessageHistoryCallback(db))
    runtime = SimpleNamespace(
        execution_info=SimpleNamespace(thread_id="thread-1", run_id=None)
    )

    await middleware._record_state_messages(
        {"workspace_id": "workspace-1", "messages": [{"type": "human", "id": "message-1", "content": "hello"}]},
        runtime,
    )

    message = await db.get_message_by_id("message-1", "thread-1")

    assert message is not None
    assert message["run_id"] is None


async def test_message_history_middleware_records_after_model_ai_message(tmp_path):
    db = Database(str(tmp_path / "test.db"))
    middleware = MessageHistoryMiddleware(MessageHistoryCallback(db))
    runtime = SimpleNamespace(
        execution_info=SimpleNamespace(thread_id="thread-1", run_id="run-1")
    )

    await middleware.aafter_model(
        {
            "workspace_id": "workspace-1",
            "messages": [
                {"type": "human", "id": "human-1", "content": "hello"},
                AIMessage(id="ai-1", content="reply"),
            ],
        },
        runtime,
    )

    assert await db.get_message_by_id("human-1", "thread-1") is None
    message = await db.get_message_by_id("ai-1", "thread-1")

    assert message is not None
    assert message["run_id"] == "run-1"
    assert message["role"] == "ai"
    assert message["content"] == "reply"


async def test_message_history_middleware_records_tool_message_after_tool_call(tmp_path):
    db = Database(str(tmp_path / "test.db"))
    middleware = MessageHistoryMiddleware(MessageHistoryCallback(db))
    runtime = SimpleNamespace(
        execution_info=SimpleNamespace(thread_id="thread-1", run_id="run-1")
    )
    request = SimpleNamespace(
        state={"workspace_id": "workspace-1", "messages": []},
        runtime=runtime,
    )

    async def handler(_request):
        return ToolMessage(id="tool-1", content="tool result", tool_call_id="call-1")

    await middleware.awrap_tool_call(request, handler)

    message = await db.get_message_by_id("tool:call-1", "thread-1")

    assert message is not None
    assert message["run_id"] == "run-1"
    assert message["role"] == "tool"
    assert message["tool_call_id"] == "call-1"
    assert message["content"] == "tool result"


async def test_message_history_middleware_reconciles_tool_message_without_duplicate(tmp_path):
    db = Database(str(tmp_path / "test.db"))
    middleware = MessageHistoryMiddleware(MessageHistoryCallback(db))
    runtime = SimpleNamespace(
        execution_info=SimpleNamespace(thread_id="thread-1", run_id="run-1")
    )
    request = SimpleNamespace(
        state={"workspace_id": "workspace-1", "messages": []},
        runtime=runtime,
    )

    async def handler(_request):
        return ToolMessage(content="tool result", tool_call_id="call-1")

    result = await middleware.awrap_tool_call(request, handler)
    await middleware.aafter_agent(
        {
            "workspace_id": "workspace-1",
            "messages": [
                ToolMessage(
                    id="generated-tool-id",
                    content="tool result",
                    tool_call_id="call-1",
                )
            ],
        },
        runtime,
    )

    message = await db.get_message_by_id("tool:call-1", "thread-1")
    cursor = await db.connection.execute(
        "SELECT COUNT(*) AS count FROM message WHERE thread_id = ? AND tool_call_id = ?",
        ["thread-1", "call-1"],
    )
    count_row = await cursor.fetchone()

    assert isinstance(result, ToolMessage)
    assert message is not None
    assert message["message_id"] == "tool:call-1"
    assert message["tool_call_id"] == "call-1"
    assert count_row["count"] == 1


async def test_list_thread_history_runs_groups_messages_by_run_id(tmp_path):
    db = Database(str(tmp_path / "test.db"))

    await db.record_message(
        thread_id="thread-1",
        workspace_id="workspace-1",
        run_id="run-1",
        message_id="human-1",
        role="human",
        content="first",
    )
    await db.record_message(
        thread_id="thread-1",
        workspace_id="workspace-1",
        run_id="run-1",
        message_id="ai-1",
        role="ai",
        content="reply",
    )
    await db.record_message(
        thread_id="thread-1",
        workspace_id="workspace-1",
        run_id="run-2",
        message_id="human-2",
        role="human",
        content="second",
    )
    await db.record_message(
        thread_id="thread-1",
        workspace_id="workspace-1",
        run_id="run-2",
        message_id="tool-2",
        role="tool",
        content="large tool result",
        tool_call_id="call-2",
    )

    page = await db.list_thread_history_runs("thread-1", limit=10)

    assert page["next_cursor"] is None
    assert [run["run_id"] for run in page["runs"]] == ["run-1", "run-2"]
    assert [message["message_id"] for message in page["runs"][0]["messages"]] == ["human-1", "ai-1"]
    assert [message["message_id"] for message in page["runs"][1]["messages"]] == ["human-2", "tool-2"]
    assert page["runs"][1]["messages"][1]["content"] == ""


async def test_list_thread_history_runs_paginates_by_first_row_id(tmp_path):
    db = Database(str(tmp_path / "test.db"))

    for index in range(1, 4):
        await db.record_message(
            thread_id="thread-1",
            workspace_id="workspace-1",
            run_id=f"run-{index}",
            message_id=f"human-{index}",
            role="human",
            content=f"message {index}",
        )

    first_page = await db.list_thread_history_runs("thread-1", limit=2)
    second_page = await db.list_thread_history_runs(
        "thread-1",
        limit=2,
        before=first_page["next_cursor"],
    )

    assert [run["run_id"] for run in first_page["runs"]] == ["run-2", "run-3"]
    assert first_page["next_cursor"] == first_page["runs"][0]["first_row_id"]
    assert [run["run_id"] for run in second_page["runs"]] == ["run-1"]
    assert second_page["next_cursor"] is None


async def test_list_thread_history_runs_falls_back_to_human_turns_for_null_run_id(tmp_path):
    db = Database(str(tmp_path / "test.db"))

    await db.record_message(
        thread_id="thread-1",
        workspace_id="workspace-1",
        run_id=None,
        message_id="human-1",
        role="human",
        content="first",
    )
    await db.record_message(
        thread_id="thread-1",
        workspace_id="workspace-1",
        run_id=None,
        message_id="ai-1",
        role="ai",
        content="reply",
    )
    await db.record_message(
        thread_id="thread-1",
        workspace_id="workspace-1",
        run_id=None,
        message_id="human-2",
        role="human",
        content="second",
    )

    page = await db.list_thread_history_runs("thread-1", limit=10)

    assert [run["run_id"] for run in page["runs"]] == [None, None]
    assert [message["message_id"] for message in page["runs"][0]["messages"]] == ["human-1", "ai-1"]
    assert [message["message_id"] for message in page["runs"][1]["messages"]] == ["human-2"]
