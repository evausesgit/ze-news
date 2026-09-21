"""Endpoints des liens : fil, recherche, facettes, état lu / ouvert."""

from __future__ import annotations

import datetime as dt
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import Select, and_, exists, func, or_, select
from sqlalchemy.orm import Session

from app.api.identity import current_user
from app.db import get_session
from app.enrich import request_summary
from app.labels import LABEL_CODES, LABELS
from app.models import FeedMember, Link, LinkState, LinkTheme, Share, User

router = APIRouter()


class LinkOut(BaseModel):
    id: int
    url: str
    kind: str
    domain: str
    title: str | None
    author: str | None
    published_at: dt.datetime | None
    summary_en: str | None
    summary_fr: str | None
    label: str | None
    themes: list[str]
    status: str
    shared_at: dt.datetime
    shared_by: str
    message_text: str
    seen_at: dt.datetime | None
    opened_at: dt.datetime | None


class LinkPage(BaseModel):
    items: list[LinkOut]
    total: int
    offset: int
    limit: int


def _visible_shares(user: User):
    """Partages des fils dont l'utilisateur est membre, agrégés par lien."""
    my_feeds = select(FeedMember.feed_id).where(FeedMember.user_id == user.id)
    return (
        select(
            Share.link_id.label("link_id"),
            func.max(Share.shared_at).label("shared_at"),
        )
        .where(Share.feed_id.in_(my_feeds))
        .group_by(Share.link_id)
        .subquery()
    )


def _base_query(user: User) -> tuple[Select, object]:
    vis = _visible_shares(user)
    state = (
        select(LinkState)
        .where(LinkState.user_id == user.id)
        .subquery()
    )
    stmt = (
        select(Link, vis.c.shared_at, state.c.seen_at, state.c.opened_at)
        .join(vis, vis.c.link_id == Link.id)
        .join(state, state.c.link_id == Link.id, isouter=True)
    )
    return stmt, (vis, state)


def _latest_share(session: Session, user: User, link_id: int) -> Share | None:
    my_feeds = select(FeedMember.feed_id).where(FeedMember.user_id == user.id)
    return session.scalar(
        select(Share)
        .where(Share.link_id == link_id, Share.feed_id.in_(my_feeds))
        .order_by(Share.shared_at.desc())
        .limit(1)
    )


def _to_out(session: Session, user: User, row) -> LinkOut:
    link, shared_at, seen_at, opened_at = row
    share = _latest_share(session, user, link.id)
    return LinkOut(
        id=link.id,
        url=link.url,
        kind=link.kind,
        domain=link.domain,
        title=link.title,
        author=link.author,
        published_at=link.published_at,
        summary_en=link.summary_en,
        summary_fr=link.summary_fr,
        label=link.label,
        themes=[t.theme for t in link.themes],
        status=link.status,
        shared_at=shared_at,
        shared_by=share.sender_name if share else "",
        message_text=share.message_text if share else "",
        seen_at=seen_at,
        opened_at=opened_at,
    )


@router.get("/links", response_model=LinkPage)
def list_links(
    label: list[str] = Query(default=[]),
    theme: list[str] = Query(default=[]),
    q: str | None = None,
    date_from: dt.date | None = None,
    date_to: dt.date | None = None,
    read: Literal["all", "unread", "seen", "opened"] = "all",
    include_pending: bool = False,
    include_dormant: bool = False,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=30, ge=1, le=100),
    user: User = Depends(current_user),
    session: Session = Depends(get_session),
):
    stmt, (vis, state) = _base_query(user)
    conds = []
    statuses = ["done"]
    if include_pending:
        statuses += ["pending", "failed"]
    if include_dormant:  # liens anciens, pas encore résumés (résumables à la demande)
        statuses.append("dormant")
    conds.append(Link.status.in_(statuses))
    labels = [x.upper() for x in label if x]
    if labels:
        conds.append(Link.label.in_(labels))
    for t in theme:  # plusieurs thèmes = ET
        conds.append(
            exists().where(LinkTheme.link_id == Link.id, LinkTheme.theme == t.strip().lower())
        )
    if q and q.strip():
        for word in q.split():
            pat = f"%{word.strip()}%"
            conds.append(
                or_(
                    Link.title.ilike(pat),
                    Link.summary_en.ilike(pat),
                    Link.summary_fr.ilike(pat),
                    Link.author.ilike(pat),
                    Link.domain.ilike(pat),
                    Link.content_excerpt.ilike(pat),
                    exists().where(LinkTheme.link_id == Link.id, LinkTheme.theme.ilike(pat)),
                )
            )
    if date_from:
        conds.append(vis.c.shared_at >= dt.datetime.combine(date_from, dt.time.min, dt.UTC))
    if date_to:
        end = dt.datetime.combine(date_to + dt.timedelta(days=1), dt.time.min, dt.UTC)
        conds.append(vis.c.shared_at < end)
    if read == "unread":
        conds.append(state.c.seen_at.is_(None))
        conds.append(state.c.opened_at.is_(None))
    elif read == "seen":
        conds.append(or_(state.c.seen_at.is_not(None), state.c.opened_at.is_not(None)))
    elif read == "opened":
        conds.append(state.c.opened_at.is_not(None))
    if conds:
        stmt = stmt.where(and_(*conds))

    total = session.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = session.execute(
        stmt.order_by(vis.c.shared_at.desc(), Link.id.desc()).offset(offset).limit(limit)
    ).all()
    return LinkPage(
        items=[_to_out(session, user, r) for r in rows], total=total, offset=offset, limit=limit
    )


def _get_visible(session: Session, user: User, link_id: int):
    stmt, _ = _base_query(user)
    row = session.execute(stmt.where(Link.id == link_id)).first()
    if row is None:
        raise HTTPException(404, "Lien introuvable")
    return row


@router.get("/links/{link_id}", response_model=LinkOut)
def get_link(
    link_id: int, user: User = Depends(current_user), session: Session = Depends(get_session)
):
    return _to_out(session, user, _get_visible(session, user, link_id))


def _set_state(session: Session, user: User, link_id: int, **fields) -> LinkOut:
    _get_visible(session, user, link_id)
    st = session.get(LinkState, (user.id, link_id))
    if st is None:
        st = LinkState(user_id=user.id, link_id=link_id)
        session.add(st)
    for k, v in fields.items():
        setattr(st, k, v)
    session.commit()
    return _to_out(session, user, _get_visible(session, user, link_id))


@router.post("/links/{link_id}/seen", response_model=LinkOut)
def mark_seen(
    link_id: int, user: User = Depends(current_user), session: Session = Depends(get_session)
):
    st = session.get(LinkState, (user.id, link_id))
    if st is not None and st.seen_at is not None:
        return _to_out(session, user, _get_visible(session, user, link_id))
    return _set_state(session, user, link_id, seen_at=dt.datetime.now(dt.UTC))


@router.post("/links/{link_id}/opened", response_model=LinkOut)
def mark_opened(
    link_id: int, user: User = Depends(current_user), session: Session = Depends(get_session)
):
    now = dt.datetime.now(dt.UTC)
    st = session.get(LinkState, (user.id, link_id))
    fields = {"opened_at": now}
    if st is None or st.seen_at is None:
        fields["seen_at"] = now  # ouvrir implique avoir vu
    return _set_state(session, user, link_id, **fields)


@router.delete("/links/{link_id}/state", response_model=LinkOut)
def mark_unread(
    link_id: int, user: User = Depends(current_user), session: Session = Depends(get_session)
):
    return _set_state(session, user, link_id, seen_at=None, opened_at=None)


@router.post("/links/{link_id}/summarize", response_model=LinkOut)
def summarize(
    link_id: int, user: User = Depends(current_user), session: Session = Depends(get_session)
):
    """Demande le résumé d'un lien en sommeil (ou en échec).

    Le lien passe en tête de la file du worker : résumé au prochain passage.
    Sans effet sur un lien déjà résumé ou déjà en attente.
    """
    row = _get_visible(session, user, link_id)
    request_summary(session, row[0])
    return _to_out(session, user, _get_visible(session, user, link_id))


class LabelCount(BaseModel):
    code: str
    en: str
    fr: str
    count: int


class ThemeCount(BaseModel):
    theme: str
    count: int


class Facets(BaseModel):
    labels: list[LabelCount]
    themes: list[ThemeCount]
    total: int
    unread: int
    pending: int
    dormant: int


@router.get("/facets", response_model=Facets)
def facets(user: User = Depends(current_user), session: Session = Depends(get_session)):
    stmt, _ = _base_query(user)
    done = stmt.where(Link.status == "done").subquery()
    by_label = dict(
        session.execute(select(done.c.label, func.count()).group_by(done.c.label)).all()
    )
    themes = session.execute(
        select(LinkTheme.theme, func.count().label("n"))
        .join(done, done.c.id == LinkTheme.link_id)
        .group_by(LinkTheme.theme)
        .order_by(func.count().desc(), LinkTheme.theme)
        .limit(60)
    ).all()
    total = session.scalar(select(func.count()).select_from(done)) or 0
    unread = session.scalar(
        select(func.count()).select_from(done).where(
            done.c.seen_at.is_(None), done.c.opened_at.is_(None)
        )
    ) or 0
    def count_status(status: str) -> int:
        return session.scalar(
            select(func.count()).select_from(stmt.where(Link.status == status).subquery())
        ) or 0

    pending = count_status("pending")
    dormant = count_status("dormant")
    return Facets(
        labels=[
            LabelCount(code=c, en=LABELS[c]["en"], fr=LABELS[c]["fr"], count=by_label.get(c, 0))
            for c in LABEL_CODES
        ],
        themes=[ThemeCount(theme=t, count=n) for t, n in themes],
        total=total,
        unread=unread,
        pending=pending,
        dormant=dormant,
    )
