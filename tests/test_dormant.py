"""Mise en sommeil des liens anciens (rattrapage limité aux derniers mois)."""

import datetime as dt

from sqlalchemy import select

from app.enrich import archive_old_pending, pending_links, request_summary
from app.models import Link, Share
from app.telegram_ingest import IncomingMessage, record_message
from tests.conftest import headers

EVA = headers("eva@example.com")
NOW = dt.datetime.now(dt.UTC)
OLD = NOW - dt.timedelta(days=400)
RECENT = NOW - dt.timedelta(days=3)


def _msg(i, url, when):
    return IncomingMessage(id=i, date=when, sender="Yoann", text=url, entity_urls=[])


def _link(session, url_part):
    return session.scalar(select(Link).where(Link.canonical_url.contains(url_part)))


def test_old_share_creates_a_dormant_link(session, feeds):
    record_message(session, feeds["yoann"], _msg(1, "https://old.example.com/a", OLD))
    record_message(session, feeds["yoann"], _msg(2, "https://new.example.com/b", RECENT))
    session.commit()
    assert _link(session, "old.example.com").status == "dormant"
    assert _link(session, "new.example.com").status == "pending"


def test_a_recent_share_wakes_a_dormant_link(session, feeds):
    record_message(session, feeds["yoann"], _msg(1, "https://x.example.com/a", OLD))
    assert _link(session, "x.example.com").status == "dormant"
    record_message(session, feeds["yoann"], _msg(2, "https://x.example.com/a", RECENT))
    assert _link(session, "x.example.com").status == "pending"


def test_an_old_share_does_not_put_back_to_sleep_a_recent_link(session, feeds):
    # Deux fils : un partage récent dans l'un, un vieux partage arrivé ensuite.
    record_message(session, feeds["yoann"], _msg(1, "https://y.example.com/a", RECENT))
    record_message(session, feeds["autre"], _msg(1, "https://y.example.com/a", OLD))
    assert _link(session, "y.example.com").status == "pending"


def test_archive_old_pending_catches_up_history(session, feeds):
    # Lien ingéré avant l'existence de la mise en sommeil : pending mais vieux.
    record_message(session, feeds["yoann"], _msg(1, "https://z.example.com/a", RECENT))
    session.commit()
    link = _link(session, "z.example.com")
    share = session.scalar(select(Share).where(Share.link_id == link.id))
    share.shared_at = OLD
    session.commit()
    assert archive_old_pending(session) == 1
    session.refresh(link)
    assert link.status == "dormant"


def test_request_summary_jumps_the_queue_and_never_goes_back_to_sleep(session, feeds):
    record_message(session, feeds["yoann"], _msg(1, "https://ancien.example.com/a", OLD))
    record_message(session, feeds["yoann"], _msg(2, "https://recent.example.com/b", RECENT))
    session.commit()
    ancien = _link(session, "ancien.example.com")
    assert request_summary(session, ancien)
    assert ancien.status == "pending" and ancien.requested_at is not None
    # Demandé explicitement : passe AVANT le lien récent...
    assert pending_links(session, 10)[0].domain == "ancien.example.com"
    # ... et le rattrapage ne le rendort pas.
    assert archive_old_pending(session) == 0
    session.refresh(ancien)
    assert ancien.status == "pending"


def test_request_summary_is_a_no_op_on_done_links(session, feeds):
    record_message(session, feeds["yoann"], _msg(1, "https://fait.example.com/a", RECENT))
    session.commit()
    link = _link(session, "fait.example.com")
    link.status = "done"
    session.commit()
    assert not request_summary(session, link)
    assert link.status == "done"


def test_api_dormant_links_hidden_by_default_then_summarizable(client, session, feeds):
    record_message(session, feeds["yoann"], _msg(1, "https://dort.example.com/a", OLD))
    session.commit()
    link = _link(session, "dort.example.com")

    assert client.get("/links", headers=EVA).json()["total"] == 0
    page = client.get("/links", headers=EVA, params={"include_dormant": True}).json()
    assert [i["status"] for i in page["items"]] == ["dormant"]
    assert client.get("/facets", headers=EVA).json()["dormant"] == 1

    r = client.post(f"/links/{link.id}/summarize", headers=EVA)
    assert r.status_code == 200 and r.json()["status"] == "pending"
    facets = client.get("/facets", headers=EVA).json()
    assert (facets["dormant"], facets["pending"]) == (0, 1)


def test_api_summarize_respects_feed_visibility(client, session, feeds):
    record_message(session, feeds["autre"], _msg(1, "https://prive.example.com/a", OLD))
    session.commit()
    link = _link(session, "prive.example.com")
    # Eva n'est pas membre du fil « Autre ».
    assert client.post(f"/links/{link.id}/summarize", headers=EVA).status_code == 404
    session.refresh(link)
    assert link.status == "dormant"
