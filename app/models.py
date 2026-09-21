"""Schéma de données — multi-utilisateur dès la v1.

Idée structurante : un **lien** est une connaissance partagée (résumé, label et
thèmes calculés UNE fois par Codex), tandis que ce qui est propre à chacun vit
dans des tables à part :

- `feeds`        : une conversation Telegram surveillée (ex. « Yoann ») ;
- `feed_members` : qui voit quel fil (un utilisateur ne voit que les liens des
                   fils dont il est membre) ;
- `shares`       : chaque apparition d'un lien dans un fil (message, expéditeur,
                   date) — un même lien partagé deux fois = 1 link, 2 shares ;
- `link_states`  : l'état de lecture PAR utilisateur (vu = swipé, ouvert =
                   double-clic).
"""

from __future__ import annotations

import datetime as dt

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


def _now() -> dt.datetime:
    return dt.datetime.now(dt.UTC)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    firebase_uid: Mapped[str | None] = mapped_column(String(128), unique=True)
    email: Mapped[str] = mapped_column(String(320), unique=True)
    name: Mapped[str] = mapped_column(String(200), default="")
    # Langue par défaut des cartes (« en » ou « fr ») ; chaque carte peut basculer.
    lang: Mapped[str] = mapped_column(String(2), default="en")
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), default=_now, server_default=func.now()
    )


class Feed(Base):
    __tablename__ = "feeds"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    # @username, lien t.me ou identifiant numérique de la conversation Telegram.
    telegram_chat: Mapped[str] = mapped_column(String(200), unique=True)
    # Curseur d'ingestion : dernier message Telegram déjà lu.
    last_message_id: Mapped[int] = mapped_column(BigInteger, default=0)
    last_polled_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), default=_now, server_default=func.now()
    )


class FeedMember(Base):
    __tablename__ = "feed_members"

    feed_id: Mapped[int] = mapped_column(ForeignKey("feeds.id", ondelete="CASCADE"), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    role: Mapped[str] = mapped_column(String(20), default="member")  # owner | member


class Link(Base):
    __tablename__ = "links"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # URL normalisée (x.com/<user>/status/<id>, sans utm_*) : clé de dédoublonnage.
    canonical_url: Mapped[str] = mapped_column(String(2048), unique=True)
    url: Mapped[str] = mapped_column(String(2048))  # telle que reçue la 1re fois
    kind: Mapped[str] = mapped_column(String(20))  # tweet | web
    domain: Mapped[str] = mapped_column(String(255), default="")

    title: Mapped[str | None] = mapped_column(Text)
    author: Mapped[str | None] = mapped_column(String(300))
    published_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    # Texte lu par le fetcher (tronqué), conservé pour la recherche et le debug.
    content_excerpt: Mapped[str | None] = mapped_column(Text)

    summary_en: Mapped[str | None] = mapped_column(Text)
    summary_fr: Mapped[str | None] = mapped_column(Text)
    label: Mapped[str | None] = mapped_column(String(20), index=True)

    # pending → done | failed ; dormant = trop ancien pour être résumé d'office.
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    # Résumé demandé explicitement pour un lien en sommeil : passe en tête de file.
    requested_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str | None] = mapped_column(Text)
    enriched_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), default=_now, server_default=func.now()
    )

    themes: Mapped[list[LinkTheme]] = relationship(
        cascade="all, delete-orphan", order_by="LinkTheme.theme", lazy="selectin"
    )


class LinkTheme(Base):
    __tablename__ = "link_themes"

    link_id: Mapped[int] = mapped_column(ForeignKey("links.id", ondelete="CASCADE"), primary_key=True)
    # Thème libre en minuscules (« nvidia », « élection présidentielle »…).
    theme: Mapped[str] = mapped_column(String(80), primary_key=True)

    __table_args__ = (Index("ix_link_themes_theme", "theme"),)


class Share(Base):
    __tablename__ = "shares"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    feed_id: Mapped[int] = mapped_column(ForeignKey("feeds.id", ondelete="CASCADE"))
    link_id: Mapped[int] = mapped_column(ForeignKey("links.id", ondelete="CASCADE"))
    telegram_message_id: Mapped[int] = mapped_column(BigInteger)
    sender_name: Mapped[str] = mapped_column(String(200), default="")
    message_text: Mapped[str] = mapped_column(Text, default="")
    shared_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), index=True)

    __table_args__ = (
        UniqueConstraint("feed_id", "telegram_message_id", "link_id", name="uq_share_message_link"),
        Index("ix_shares_feed_link", "feed_id", "link_id"),
    )


class LinkState(Base):
    __tablename__ = "link_states"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    link_id: Mapped[int] = mapped_column(ForeignKey("links.id", ondelete="CASCADE"), primary_key=True)
    # Vu = la carte a été swipée (résumé lu). Ouvert = double-clic vers la source.
    seen_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    opened_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
