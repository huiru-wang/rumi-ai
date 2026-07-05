import os


def is_debug_logging_enabled() -> bool:
    """Return whether content-heavy debug logs are allowed.

    Production logs should avoid prompts, document snippets, and other user
    content unless explicitly enabled for a troubleshooting session.
    """
    override = os.getenv("RUMI_DEBUG_LOGS", "").strip().lower()
    if override in {"1", "true", "yes", "on"}:
        return True
    if override in {"0", "false", "no", "off"}:
        return False

    app_env = os.getenv("APP_ENV", "dev").strip().lower()
    return app_env in {"dev", "local", "development", "test"}
