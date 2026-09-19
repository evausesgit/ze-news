"""Identité de l'utilisateur connecté.

Même contrat que x-med : le proxy Next (web/proxy.ts) vérifie l'ID token
Firebase et transmet X-User-Uid / X-User-Email / X-User-Name, toujours écrasés
côté proxy. L'API n'est jamais exposée directement : en plus, si
INTERNAL_API_TOKEN est défini, le proxy doit présenter ce jeton.
"""

from __future__ import annotations

import hmac
from urllib.parse import unquote

from fastapi import Depends, Header, HTTPException
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_session
from app.models import User


def current_user(
    x_user_uid: str | None = Header(default=None),
    x_user_email: str | None = Header(default=None),
    x_user_name: str | None = Header(default=None),
    x_internal_token: str | None = Header(default=None),
    session: Session = Depends(get_session),
) -> User:
    if settings.internal_api_token and not hmac.compare_digest(
        x_internal_token or "", settings.internal_api_token
    ):
        raise HTTPException(401, "Appel direct refusé : passer par le proxy.")
    if not x_user_uid or not x_user_email:
        raise HTTPException(401, "Authentification requise.")
    email = x_user_email.strip().lower()
    name = unquote(x_user_name or "")

    user = session.scalar(select(User).where(User.firebase_uid == x_user_uid))
    if user is None:
        # Compte pré-créé par l'admin (scripts/admin.py) : rattachement par email.
        user = session.scalar(
            select(User).where(func.lower(User.email) == email, User.firebase_uid.is_(None))
        )
        if user is None:
            user = User(email=email, lang="en")
            session.add(user)
        user.firebase_uid = x_user_uid
        if name and not user.name:
            user.name = name
        try:
            session.commit()
        except IntegrityError:
            # Deux premières requêtes simultanées : l'autre a gagné, on relit.
            session.rollback()
            user = session.scalar(select(User).where(User.firebase_uid == x_user_uid))
            if user is None:
                raise HTTPException(409, "Email déjà rattaché à un autre compte.") from None
    return user
