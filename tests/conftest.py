from __future__ import annotations

import datetime as dt
import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base, get_session
from app.main import app
from app.models import Feed, FeedMember, User


@pytest.fixture
def session():
    # TEST_DATABASE_URL=postgresql+psycopg://… pour rejouer la suite sur Postgres
    # (base jetable : elle est vidée à chaque test).
    url = os.environ.get("TEST_DATABASE_URL")
    if url:
        engine = create_engine(url)
        Base.metadata.drop_all(engine)
    else:
        engine = create_engine(
            "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
        )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    with Session() as s:
        yield s


@pytest.fixture
def feeds(session):
    """Deux fils : Eva voit « Yoann », Léa voit « Yoann » et « Autre »."""
    eva = User(email="eva@example.com", lang="en")
    lea = User(email="lea@example.com", lang="fr")
    yoann = Feed(name="Yoann", telegram_chat="@yoann", last_message_id=0)
    autre = Feed(name="Autre", telegram_chat="@autre", last_message_id=0)
    session.add_all([eva, lea, yoann, autre])
    session.flush()
    session.add_all([
        FeedMember(feed_id=yoann.id, user_id=eva.id, role="owner"),
        FeedMember(feed_id=yoann.id, user_id=lea.id),
        FeedMember(feed_id=autre.id, user_id=lea.id, role="owner"),
    ])
    session.commit()
    return {"eva": eva, "lea": lea, "yoann": yoann, "autre": autre}


@pytest.fixture
def client(session):
    app.dependency_overrides[get_session] = lambda: session
    yield TestClient(app)
    app.dependency_overrides.clear()


def headers(email: str, uid: str | None = None) -> dict:
    return {"x-user-email": email, "x-user-uid": uid or f"uid-{email}", "x-user-name": "Test"}


def at(day: int) -> dt.datetime:
    return dt.datetime(2026, 9, day, 12, 0, tzinfo=dt.UTC)
