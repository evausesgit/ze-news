import stat

from scripts.telegram_login import upsert_env


def test_upsert_env_creates_file_with_600(tmp_path):
    env = tmp_path / ".env"
    upsert_env(env, {"TELEGRAM_SESSION": "abc"})
    assert env.read_text() == "TELEGRAM_SESSION=abc\n"
    assert stat.S_IMODE(env.stat().st_mode) == 0o600


def test_upsert_env_replaces_key_and_keeps_the_rest(tmp_path):
    env = tmp_path / ".env"
    env.write_text("# commentaire\nDATABASE_URL=postgres://x\nTELEGRAM_SESSION=vieille\nCODEX_BIN=codex\n")
    upsert_env(env, {"TELEGRAM_SESSION": "neuve", "TELEGRAM_API_ID": "42"})
    lines = env.read_text().splitlines()
    assert lines == [
        "# commentaire",
        "DATABASE_URL=postgres://x",
        "TELEGRAM_SESSION=neuve",
        "CODEX_BIN=codex",
        "TELEGRAM_API_ID=42",
    ]


def test_upsert_env_does_not_match_a_similar_key(tmp_path):
    env = tmp_path / ".env"
    env.write_text("MY_TELEGRAM_SESSION=autre\n")
    upsert_env(env, {"TELEGRAM_SESSION": "neuve"})
    assert env.read_text().splitlines() == ["MY_TELEGRAM_SESSION=autre", "TELEGRAM_SESSION=neuve"]
