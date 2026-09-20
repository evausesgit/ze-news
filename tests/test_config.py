from app.config import Settings


def test_empty_env_vars_fall_back_to_defaults(monkeypatch):
    # Coolify pose les variables pas encore remplies comme chaînes vides.
    for key in ("TELEGRAM_API_ID", "TELEGRAM_API_HASH", "POLL_INTERVAL_SECONDS",
                "ENRICH_BATCH_SIZE", "FETCH_TIMEOUT_SECONDS", "CODEX_WEB_SEARCH"):
        monkeypatch.setenv(key, "")
    s = Settings(_env_file=None)
    assert s.telegram_api_id == 0
    assert s.telegram_api_hash == ""
    assert s.poll_interval_seconds == 600
    assert s.enrich_batch_size == 20
    assert s.fetch_timeout_seconds == 15.0
    assert s.codex_web_search is True


def test_real_values_are_still_read(monkeypatch):
    monkeypatch.setenv("TELEGRAM_API_ID", "12345")
    monkeypatch.setenv("POLL_INTERVAL_SECONDS", "42")
    s = Settings(_env_file=None)
    assert s.telegram_api_id == 12345
    assert s.poll_interval_seconds == 42
