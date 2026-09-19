"""Administration des fils et de leurs membres.

    uv run python -m scripts.admin add-feed --name Yoann --chat @yoann_username --owner eva@example.com
    uv run python -m scripts.admin add-member --feed Yoann --email ami@example.com
    uv run python -m scripts.admin list

Un utilisateur est créé à l'avance par email ; sa première connexion Google le
rattache (par email) à son compte Firebase.
"""

from __future__ import annotations

import argparse

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.models import Feed, FeedMember, Link, Share, User


def ensure_user(session: Session, email: str) -> User:
    email = email.strip().lower()
    user = session.scalar(select(User).where(func.lower(User.email) == email))
    if user is None:
        user = User(email=email, name="", lang="en")
        session.add(user)
        session.flush()
    return user


def add_member(session: Session, feed: Feed, email: str, role: str = "member") -> None:
    user = ensure_user(session, email)
    if session.get(FeedMember, (feed.id, user.id)) is None:
        session.add(FeedMember(feed_id=feed.id, user_id=user.id, role=role))


def find_feed(session: Session, ref: str) -> Feed:
    feed = session.scalar(select(Feed).where((Feed.name == ref) | (Feed.telegram_chat == ref)))
    if feed is None:
        raise SystemExit(f"Fil introuvable : {ref}")
    return feed


def main() -> None:
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("add-feed")
    a.add_argument("--name", required=True)
    a.add_argument("--chat", required=True, help="@username, t.me/… ou id numérique")
    a.add_argument("--owner", required=True, help="email Google du propriétaire")
    m = sub.add_parser("add-member")
    m.add_argument("--feed", required=True)
    m.add_argument("--email", required=True)
    sub.add_parser("list")
    args = p.parse_args()

    with SessionLocal() as session:
        if args.cmd == "add-feed":
            feed = Feed(name=args.name, telegram_chat=args.chat.strip(), last_message_id=0)
            session.add(feed)
            session.flush()
            add_member(session, feed, args.owner, role="owner")
            session.commit()
            print(f"Fil « {feed.name} » créé (id {feed.id}).")
        elif args.cmd == "add-member":
            feed = find_feed(session, args.feed)
            add_member(session, feed, args.email)
            session.commit()
            print(f"{args.email} a accès au fil « {feed.name} ».")
        else:
            for feed in session.scalars(select(Feed)):
                n = session.scalar(
                    select(func.count(func.distinct(Share.link_id))).where(Share.feed_id == feed.id)
                )
                emails = session.scalars(
                    select(User.email).join(FeedMember).where(FeedMember.feed_id == feed.id)
                ).all()
                print(f"[{feed.id}] {feed.name} ({feed.telegram_chat}) — {n} liens — {', '.join(emails)}")
            by_status = session.execute(select(Link.status, func.count()).group_by(Link.status)).all()
            print("Liens :", dict(by_status))


if __name__ == "__main__":
    main()
