from src.logging_utils import is_debug_logging_enabled


def test_debug_logging_enabled_in_dev(monkeypatch):
    monkeypatch.setenv("APP_ENV", "dev")
    monkeypatch.delenv("RUMI_DEBUG_LOGS", raising=False)

    assert is_debug_logging_enabled() is True


def test_debug_logging_disabled_in_prod(monkeypatch):
    monkeypatch.setenv("APP_ENV", "prod")
    monkeypatch.delenv("RUMI_DEBUG_LOGS", raising=False)

    assert is_debug_logging_enabled() is False


def test_debug_logging_override(monkeypatch):
    monkeypatch.setenv("APP_ENV", "prod")
    monkeypatch.setenv("RUMI_DEBUG_LOGS", "1")

    assert is_debug_logging_enabled() is True

    monkeypatch.setenv("APP_ENV", "dev")
    monkeypatch.setenv("RUMI_DEBUG_LOGS", "0")

    assert is_debug_logging_enabled() is False
