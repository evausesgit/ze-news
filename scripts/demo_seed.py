"""Remplit une base de DÉMO avec quelques vrais liens, résumés par le vrai Codex.

    DATABASE_URL=... uv run python -m scripts.demo_seed eva@example.com

Simule des messages Telegram (pas de connexion Telegram) : utile pour voir le
dashboard avant d'avoir configuré la session Telegram. À ne pas lancer en prod.
"""

from __future__ import annotations

import datetime as dt
import sys

from sqlalchemy import select

from app.db import SessionLocal
from app.enrich import enrich_pending
from app.models import Feed
from app.telegram_ingest import IncomingMessage, record_message
from scripts.admin import add_member

DEMO = [
    ("https://twitter.com/elonmusk/status/1585341984679469056?s=20", "le jour où…"),
    ("https://en.wikipedia.org/wiki/Telegram_(software)", "super historique"),
    ("https://www.reuters.com/technology/", ""),
    ("https://x.com/karpathy/status/1886192184808149383", "à lire absolument"),
    ("https://ourworldindata.org/co2-emissions", "les chiffres"),
    ("https://www.lemonde.fr/politique/", ""),
]


def main() -> None:
    email = sys.argv[1] if len(sys.argv) > 1 else "eva@example.com"
    with SessionLocal() as session:
        feed = session.scalar(select(Feed).where(Feed.telegram_chat == "demo"))
        if feed is None:
            feed = Feed(name="Yoann (démo)", telegram_chat="demo", last_message_id=0)
            session.add(feed)
            session.flush()
        add_member(session, feed, email, role="owner")
        now = dt.datetime.now(dt.UTC)
        for i, (url, text) in enumerate(DEMO, start=1):
            record_message(
                session, feed,
                IncomingMessage(
                    id=i, date=now - dt.timedelta(days=len(DEMO) - i, hours=i),
                    sender="Yoann", text=f"{text} {url}".strip(), entity_urls=[],
                ),
            )
        session.commit()
        ok, ko = enrich_pending(session, limit=len(DEMO))
        print(f"démo : {ok} lien(s) résumé(s), {ko} échec(s)")


if __name__ == "__main__":
    main()
