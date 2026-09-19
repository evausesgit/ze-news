"""Ingestion Telegram : lit les nouveaux messages de chaque fil et enregistre les liens.

On se connecte en tant que COMPTE UTILISATEUR (Telethon + StringSession), pas
en bot : un bot ne peut pas lire une conversation privée entre deux personnes.
La session s'obtient une fois avec `python -m scripts.telegram_login`.

Le curseur `feeds.last_message_id` garantit qu'on ne relit jamais un message.
Au premier passage (curseur à 0) on remonte TOUT l'historique : l'enrichissement
traite ensuite les liens du plus récent au plus ancien, par lots.
"""

from __future__ import annotations

import asyncio
import datetime as dt
import logging
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import settings
from app.models import Feed, Link, Share
from app.urls import extract_urls, parse_url

log = logging.getLogger(__name__)


@dataclass
class IncomingMessage:
    id: int
    date: dt.datetime
    sender: str
    text: str
    entity_urls: list[str]


def get_or_create_link(session: Session, url: str) -> Link | None:
    parsed = parse_url(url)
    if parsed is None:
        return None
    link = session.scalar(select(Link).where(Link.canonical_url == parsed.canonical))
    if link is None:
        link = Link(
            canonical_url=parsed.canonical,
            url=parsed.url,
            kind=parsed.kind,
            domain=parsed.domain,
            status="pending",
            attempts=0,
        )
        session.add(link)
        session.flush()
    return link


def record_message(session: Session, feed: Feed, msg: IncomingMessage) -> int:
    """Enregistre les liens d'un message. Retourne le nombre de partages créés."""
    created = 0
    done: set[int] = set()
    for url in extract_urls(msg.text, msg.entity_urls):
        link = get_or_create_link(session, url)
        # twitter.com/… et x.com/… dans le même message = un seul lien.
        if link is None or link.id in done:
            continue
        done.add(link.id)
        exists = session.scalar(
            select(Share.id).where(
                Share.feed_id == feed.id,
                Share.telegram_message_id == msg.id,
                Share.link_id == link.id,
            )
        )
        if exists:
            continue
        session.add(
            Share(
                feed_id=feed.id,
                link_id=link.id,
                telegram_message_id=msg.id,
                sender_name=msg.sender[:200],
                message_text=msg.text or "",
                shared_at=msg.date,
            )
        )
        session.flush()  # visible des vérifications suivantes (autoflush désactivé)
        created += 1
    feed.last_message_id = max(feed.last_message_id or 0, msg.id)
    return created


# ------------------------------------------------------------------ Telethon


def _chat_ref(raw: str):
    raw = raw.strip()
    if raw.lstrip("-").isdigit():
        return int(raw)
    return raw


def _to_incoming(message, sender_name: str) -> IncomingMessage:
    from telethon.tl.types import MessageEntityTextUrl, MessageEntityUrl

    entity_urls: list[str] = []
    for ent, text in message.get_entities_text() or []:
        if isinstance(ent, MessageEntityTextUrl):
            entity_urls.append(ent.url)
        elif isinstance(ent, MessageEntityUrl):
            entity_urls.append(text)
    # Aperçu de lien (webpage) : parfois la seule trace d'une URL.
    webpage = getattr(getattr(message, "media", None), "webpage", None)
    if getattr(webpage, "url", None):
        entity_urls.append(webpage.url)
    return IncomingMessage(
        id=message.id,
        date=message.date,
        sender=sender_name,
        text=message.message or "",
        entity_urls=entity_urls,
    )


async def _ingest_async(session: Session) -> int:
    from telethon import TelegramClient
    from telethon.sessions import StringSession

    if not (settings.telegram_api_id and settings.telegram_api_hash and settings.telegram_session):
        raise RuntimeError(
            "Telegram non configuré : TELEGRAM_API_ID, TELEGRAM_API_HASH et "
            "TELEGRAM_SESSION sont requis (cf. scripts/telegram_login.py)."
        )
    client = TelegramClient(
        StringSession(settings.telegram_session),
        settings.telegram_api_id,
        settings.telegram_api_hash,
    )
    total = 0
    async with client:
        me = await client.get_me()
        for feed in session.scalars(select(Feed).order_by(Feed.id)):
            entity = await client.get_entity(_chat_ref(feed.telegram_chat))
            names: dict[int, str] = {}
            count = 0
            async for message in client.iter_messages(
                entity, min_id=feed.last_message_id or 0, reverse=True
            ):
                sid = message.sender_id or 0
                if sid not in names:
                    if sid == me.id:
                        names[sid] = "moi"
                    else:
                        sender = await message.get_sender()
                        names[sid] = (
                            " ".join(
                                x for x in (getattr(sender, "first_name", None),
                                            getattr(sender, "last_name", None)) if x
                            )
                            or getattr(sender, "title", None)
                            or getattr(sender, "username", None)
                            or str(sid)
                        )
                count += record_message(session, feed, _to_incoming(message, names[sid]))
                if message.id % 200 == 0:
                    session.commit()  # rattrapage long : on sauvegarde en route
            feed.last_polled_at = dt.datetime.now(dt.UTC)
            session.commit()
            log.info("fil %s : %d nouveau(x) partage(s)", feed.name, count)
            total += count
    return total


def ingest_all(session: Session) -> int:
    try:
        return asyncio.run(_ingest_async(session))
    except IntegrityError:
        session.rollback()
        raise
