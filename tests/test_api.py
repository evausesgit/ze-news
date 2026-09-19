from sqlalchemy import select

from app.config import settings
from app.models import Link, LinkTheme, User
from app.telegram_ingest import IncomingMessage, record_message
from tests.conftest import at, headers

EVA = headers("eva@example.com")
LEA = headers("lea@example.com")


def _add(session, feed, msg_id, url, label, themes, day, summary="s"):
    record_message(
        session, feed,
        IncomingMessage(id=msg_id, date=at(day), sender="Yoann", text=url, entity_urls=[]),
    )
    session.flush()
    link = session.scalars(select(Link).order_by(Link.id.desc())).first()
    link.status, link.label = "done", label
    link.summary_en, link.summary_fr = f"{summary} en", f"{summary} fr"
    link.themes = [LinkTheme(theme=t) for t in themes]
    session.commit()
    return link


def test_requires_identity(client):
    assert client.get("/links").status_code == 401


def test_internal_token_enforced(client, monkeypatch):
    monkeypatch.setattr(settings, "internal_api_token", "secret")
    assert client.get("/me", headers=EVA).status_code == 401
    assert client.get("/me", headers={**EVA, "x-internal-token": "secret"}).status_code == 200


def test_first_login_attaches_precreated_user(client, session, feeds):
    r = client.get("/me", headers=EVA)
    assert r.status_code == 200
    body = r.json()
    assert body["lang"] == "en" and [f["name"] for f in body["feeds"]] == ["Yoann"]
    eva = session.scalar(select(User).where(User.email == "eva@example.com"))
    assert eva.firebase_uid == "uid-eva@example.com"
    assert client.put("/me", headers=EVA, json={"lang": "fr"}).json()["lang"] == "fr"
    assert client.put("/me", headers=EVA, json={"lang": "de"}).status_code == 422


def test_unknown_user_sees_nothing(client, session, feeds):
    _add(session, feeds["yoann"], 1, "https://x.com/a/status/1", "AI", ["openai"], 10)
    r = client.get("/links", headers=headers("inconnu@example.com"))
    assert r.status_code == 200 and r.json()["total"] == 0


def test_users_only_see_their_feeds(client, session, feeds):
    _add(session, feeds["yoann"], 1, "https://x.com/a/status/1", "AI", ["openai"], 10)
    secret = _add(session, feeds["autre"], 1, "https://secret.example.com", "NEWS", [], 11)
    assert client.get("/links", headers=EVA).json()["total"] == 1
    assert client.get("/links", headers=LEA).json()["total"] == 2
    assert client.get(f"/links/{secret.id}", headers=EVA).status_code == 404
    assert client.post(f"/links/{secret.id}/seen", headers=EVA).status_code == 404


def test_filters_label_theme_date_query(client, session, feeds):
    y = feeds["yoann"]
    _add(session, y, 1, "https://x.com/a/status/1", "AI", ["openai", "gpt"], 5, "GPT launch")
    _add(session, y, 2, "https://x.com/b/status/2", "POLITICS", ["elections"], 10, "Vote")
    _add(session, y, 3, "https://x.com/c/status/3", "AI", ["gpu"], 15, "Nvidia chips")

    def ids(**params):
        items = client.get("/links", headers=EVA, params=params).json()["items"]
        return [i["summary_en"] for i in items]

    assert ids() == ["Nvidia chips en", "Vote en", "GPT launch en"]  # plus récent d'abord
    assert ids(label="ai") == ["Nvidia chips en", "GPT launch en"]
    assert ids(label=["AI", "POLITICS"], theme="elections") == ["Vote en"]
    assert ids(date_from="2026-09-06", date_to="2026-09-10") == ["Vote en"]
    assert ids(q="nvidia") == ["Nvidia chips en"]
    assert ids(q="gpt") == ["GPT launch en"]  # via thème et résumé
    assert ids(q="chips fr") == ["Nvidia chips en"]  # mots en ET


def test_pending_links_hidden_by_default(client, session, feeds):
    record_message(session, feeds["yoann"],
                   IncomingMessage(id=1, date=at(3), sender="Y", text="https://a.example.com",
                                   entity_urls=[]))
    session.commit()
    assert client.get("/links", headers=EVA).json()["total"] == 0
    r = client.get("/links", headers=EVA, params={"include_pending": True}).json()
    assert r["items"][0]["status"] == "pending"
    assert client.get("/facets", headers=EVA).json()["pending"] == 1


def test_read_state_is_per_user(client, session, feeds):
    link = _add(session, feeds["yoann"], 1, "https://x.com/a/status/1", "AI", [], 10)
    r = client.post(f"/links/{link.id}/seen", headers=EVA).json()
    assert r["seen_at"] and r["opened_at"] is None
    first_seen = r["seen_at"]
    # Revoir ne change pas la date de première lecture.
    assert client.post(f"/links/{link.id}/seen", headers=EVA).json()["seen_at"] == first_seen

    # Léa n'a rien lu.
    lea_item = client.get("/links", headers=LEA).json()["items"][0]
    assert lea_item["seen_at"] is None
    assert client.get("/links", headers=LEA, params={"read": "unread"}).json()["total"] == 1
    assert client.get("/links", headers=EVA, params={"read": "unread"}).json()["total"] == 0

    # Léa ouvre directement : ouvert implique vu.
    r = client.post(f"/links/{link.id}/opened", headers=LEA).json()
    assert r["opened_at"] and r["seen_at"]
    assert client.get("/links", headers=LEA, params={"read": "opened"}).json()["total"] == 1

    # Remettre en non lu.
    r = client.delete(f"/links/{link.id}/state", headers=EVA).json()
    assert r["seen_at"] is None
    assert client.get("/links", headers=EVA, params={"read": "unread"}).json()["total"] == 1


def test_facets(client, session, feeds):
    y = feeds["yoann"]
    link = _add(session, y, 1, "https://x.com/a/status/1", "AI", ["openai"], 5)
    _add(session, y, 2, "https://x.com/b/status/2", "AI", ["openai", "gpu"], 6)
    _add(session, y, 3, "https://x.com/c/status/3", "STATS", ["gpu"], 7)
    client.post(f"/links/{link.id}/seen", headers=EVA)
    f = client.get("/facets", headers=EVA).json()
    counts = {c["code"]: c["count"] for c in f["labels"]}
    assert counts["AI"] == 2 and counts["STATS"] == 1 and counts["POLITICS"] == 0
    assert {t["theme"]: t["count"] for t in f["themes"]} == {"openai": 2, "gpu": 2}
    assert (f["total"], f["unread"], f["pending"]) == (3, 2, 0)
    assert next(c for c in f["labels"] if c["code"] == "AI")["fr"] == "IA"
