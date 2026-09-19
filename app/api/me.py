from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.identity import current_user
from app.db import get_session
from app.models import Feed, FeedMember, User

router = APIRouter()


class FeedOut(BaseModel):
    id: int
    name: str
    role: str


class MeOut(BaseModel):
    email: str
    name: str
    lang: str
    feeds: list[FeedOut]


class MeIn(BaseModel):
    lang: Literal["en", "fr"]


def _me(session: Session, user: User) -> MeOut:
    rows = session.execute(
        select(Feed.id, Feed.name, FeedMember.role)
        .join(FeedMember, FeedMember.feed_id == Feed.id)
        .where(FeedMember.user_id == user.id)
        .order_by(Feed.name)
    ).all()
    return MeOut(
        email=user.email,
        name=user.name,
        lang=user.lang,
        feeds=[FeedOut(id=i, name=n, role=r) for i, n, r in rows],
    )


@router.get("/me", response_model=MeOut)
def get_me(user: User = Depends(current_user), session: Session = Depends(get_session)):
    return _me(session, user)


@router.put("/me", response_model=MeOut)
def put_me(
    body: MeIn, user: User = Depends(current_user), session: Session = Depends(get_session)
):
    user.lang = body.lang
    session.commit()
    return _me(session, user)
