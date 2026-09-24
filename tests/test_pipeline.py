from pathlib import Path

from sqlalchemy import func, select

from app import codex_cli
from app.codex_cli import CodexCliError, build_command, parse_usage
from app.enrich import (
    SCHEMA,
    enrich_link,
    enrich_pending,
    normalize_themes,
    pending_links,
    resummarize_link,
)
from app.fetch import Fetched
from app.models import Link, Share
from app.telegram_ingest import IncomingMessage, record_message
from tests.conftest import at


def _msg(i, text, day=10, urls=None):
    return IncomingMessage(id=i, date=at(day), sender="Yoann", text=text, entity_urls=urls or [])


def test_record_message_dedups_links_across_messages(session, feeds):
    feed = feeds["yoann"]
    assert record_message(session, feed, _msg(1, "https://twitter.com/a/status/9?s=20")) == 1
    assert record_message(session, feed, _msg(2, "encore https://x.com/a/status/9")) == 1
    # Même message relu : aucun doublon.
    assert record_message(session, feed, _msg(2, "encore https://x.com/a/status/9")) == 0
    session.commit()
    assert session.scalar(select(func.count(Link.id))) == 1
    assert session.scalar(select(func.count(Share.id))) == 2
    assert feed.last_message_id == 2


def test_same_tweet_twice_in_one_message(session, feeds):
    text = "https://twitter.com/a/status/9 et https://x.com/a/status/9?s=20"
    assert record_message(session, feeds["yoann"], _msg(1, text)) == 1
    session.commit()


def test_record_message_without_link_moves_cursor(session, feeds):
    feed = feeds["yoann"]
    assert record_message(session, feed, _msg(7, "salut, ça va ?")) == 0
    assert feed.last_message_id == 7


def _fake_runner(result):
    calls = []

    def run(prompt, schema, web_search):
        calls.append({"prompt": prompt, "schema": schema, "web_search": web_search})
        if isinstance(result, Exception):
            raise result
        return result, None

    run.calls = calls
    return run


def _ok_fetcher(parsed):
    return Fetched(ok=True, text="GPT-6 released with 10x context", author="@openai")


def _ko_fetcher(parsed):
    return Fetched(error="HTTP 403")


def test_enrich_link_success(session, feeds):
    record_message(session, feeds["yoann"], _msg(1, "wow https://x.com/openai/status/1"))
    session.commit()
    link = session.scalar(select(Link))
    runner = _fake_runner({
        "title": "GPT-6", "summary_en": "OpenAI ships GPT-6.", "summary_fr": "OpenAI sort GPT-6.",
        "interpretation_en": "A big step.", "interpretation_fr": " Un grand pas. ",
        "label": "AI", "themes": ["OpenAI", "#LLM", "openai"],
    })
    assert enrich_link(session, link, runner=runner, fetcher=_ok_fetcher)
    assert link.status == "done" and link.label == "AI"
    assert link.summary_en == "OpenAI ships GPT-6.\n\nA big step."
    assert link.summary_fr == "OpenAI sort GPT-6.\n\nUn grand pas."
    assert sorted(t.theme for t in link.themes) == ["llm", "openai"]
    assert link.author == "@openai"
    call = runner.calls[0]
    assert call["web_search"] is False  # contenu lu : pas besoin de recherche web
    assert "GPT-6 released" in call["prompt"] and "« wow" in call["prompt"]
    assert call["schema"] is SCHEMA


def test_enrich_uses_web_search_when_fetch_fails(session, feeds):
    record_message(session, feeds["yoann"], _msg(1, "https://example.com/paywall"))
    session.commit()
    link = session.scalar(select(Link))
    runner = _fake_runner({"title": "t", "summary_en": "e", "summary_fr": "f",
                           "label": "BOGUS", "themes": []})
    assert enrich_link(session, link, runner=runner, fetcher=_ko_fetcher)
    assert runner.calls[0]["web_search"] is True
    assert "HTTP 403" in runner.calls[0]["prompt"]
    assert link.label == "OTHER"  # label hors taxonomie → OTHER


def test_enrich_failure_retries_then_fails(session, feeds):
    record_message(session, feeds["yoann"], _msg(1, "https://example.com/x"))
    session.commit()
    link = session.scalar(select(Link))
    runner = _fake_runner(CodexCliError("boom"))
    for _ in range(3):
        assert not enrich_link(session, link, runner=runner, fetcher=_ok_fetcher)
    assert link.status == "failed" and link.attempts == 3 and "boom" in link.error
    assert pending_links(session, 10) == []


def test_resummarize_reuses_stored_content(session, feeds):
    record_message(session, feeds["yoann"], _msg(1, "https://x.com/openai/status/1"))
    session.commit()
    link = session.scalar(select(Link))
    first = _fake_runner({"title": "GPT-6", "summary_en": "old", "summary_fr": "ancien",
                          "label": "AI", "themes": ["openai", "llm"]})
    assert enrich_link(session, link, runner=first, fetcher=_ok_fetcher)
    runner = _fake_runner({"title": "x", "summary_en": "New.", "interpretation_en": "Why.",
                           "summary_fr": "Neuf.", "interpretation_fr": "Pourquoi.",
                           "label": "TECH", "themes": ["openai", "gpu"]})

    def no_fetch(*_a, **_k):
        raise AssertionError("le contenu stocké doit suffire")

    assert resummarize_link(session, link, runner=runner, fetcher=no_fetch)
    assert link.summary_fr == "Neuf.\n\nPourquoi." and link.label == "TECH"
    assert sorted(t.theme for t in link.themes) == ["gpu", "openai"]
    assert link.status == "done" and link.title == "GPT-6"
    assert "GPT-6 released" in runner.calls[0]["prompt"]


def test_resummarize_failure_keeps_old_summary(session, feeds):
    record_message(session, feeds["yoann"], _msg(1, "https://example.com/x"))
    session.commit()
    link = session.scalar(select(Link))
    ok = _fake_runner({"title": "t", "summary_en": "e", "summary_fr": "f",
                       "label": "NEWS", "themes": ["x"]})
    assert enrich_link(session, link, runner=ok, fetcher=_ok_fetcher)
    for _ in range(4):
        assert not resummarize_link(session, link, runner=_fake_runner(CodexCliError("boom")))
    assert link.status == "done" and link.summary_fr == "f" and link.attempts == 1
    assert [t.theme for t in link.themes] == ["x"]


def test_pending_links_newest_share_first(session, feeds):
    record_message(session, feeds["yoann"], _msg(1, "https://old.example.com/a", day=1))
    record_message(session, feeds["yoann"], _msg(2, "https://new.example.com/b", day=15))
    session.commit()
    domains = [link.domain for link in pending_links(session, 10)]
    assert domains == ["new.example.com", "old.example.com"]
    runner = _fake_runner({"title": "t", "summary_en": "e", "summary_fr": "f",
                           "label": "NEWS", "themes": ["x"]})
    assert enrich_pending(session, limit=1, runner=runner, fetcher=_ok_fetcher) == (1, 0)


def test_normalize_themes_caps_and_dedups():
    assert normalize_themes(["  A  b ", "a b", "#C", "d", "e", "f"]) == ["a b", "c", "d", "e"]


def test_codex_command_puts_search_before_exec(tmp_path: Path):
    cmd = build_command(tmp_path / "s.json", tmp_path / "o.json", web_search=True)
    assert cmd.index("--search") < cmd.index("exec")
    assert cmd[-1] == "-" and "--output-schema" in cmd and "read-only" in cmd
    assert "--search" not in build_command(tmp_path / "s", tmp_path / "o", web_search=False)


def test_parse_usage_reads_turn_completed():
    out = b'{"type":"x"}\nnot json\n{"type":"turn.completed","usage":{"input_tokens":5,"output_tokens":2}}\n'
    u = parse_usage(out)
    assert (u.input_tokens, u.output_tokens) == (5, 2)


def test_run_codex_missing_binary(monkeypatch):
    monkeypatch.setattr(codex_cli.settings, "codex_bin", "/nonexistent/codex")
    try:
        codex_cli.run_codex("hi", {"type": "object"})
    except CodexCliError as e:
        assert "introuvable" in str(e)
    else:
        raise AssertionError("CodexCliError attendue")


def test_sender_is_anonymised_to_initials(session, feeds):
    from app.telegram_ingest import initials

    assert initials("Yoann Dupont") == "YD"
    assert initials("jean-pierre martin") == "JPM"
    assert initials("Élodie") == "É"
    assert initials("moi") == "moi"
    assert initials("123456") == ""
    record_message(session, feeds["yoann"], IncomingMessage(
        id=1, date=at(3), sender="Yoann Dupont", text="https://a.example.com", entity_urls=[],
    ))
    session.flush()
    assert session.scalars(select(Share.sender_name)).all() == ["YD"]
