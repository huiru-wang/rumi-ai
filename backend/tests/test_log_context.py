import logging

from src.log_context import (
    add_context_task,
    configure_log_record_context,
    get_log_context,
    reset_log_context,
    set_log_context,
)


def test_log_record_context_injected(caplog):
    configure_log_record_context()
    tokens = set_log_context(
        trace_id="trc_test",
        request_id="req_test",
        user_id="user_test",
        workspace_id="ws_test",
    )
    try:
        logger = logging.getLogger("tests.log_context")
        with caplog.at_level(logging.INFO):
            logger.info("hello")
    finally:
        reset_log_context(tokens)

    record = caplog.records[-1]
    assert record.trace_id == "trc_test"
    assert record.request_id == "req_test"
    assert record.user_id == "user_test"
    assert record.workspace_id == "ws_test"


async def test_add_context_task_copies_current_context():
    class FakeBackgroundTasks:
        def __init__(self):
            self.tasks = []

        def add_task(self, func):
            self.tasks.append(func)

    seen = {}

    async def worker():
        seen.update(get_log_context())

    background_tasks = FakeBackgroundTasks()
    tokens = set_log_context(
        trace_id="trc_bg",
        request_id="req_bg",
        user_id="user_bg",
        workspace_id="ws_bg",
    )
    try:
        add_context_task(background_tasks, worker)
    finally:
        reset_log_context(tokens)

    await background_tasks.tasks[0]()

    assert seen == {
        "trace_id": "trc_bg",
        "request_id": "req_bg",
        "user_id": "user_bg",
        "workspace_id": "ws_bg",
    }
