from __future__ import annotations

import logging

from fastapi import FastAPI

from app.api import links, me

logging.basicConfig(level=logging.INFO)

# Le schéma est géré par Alembic (`alembic upgrade head` au démarrage du conteneur).
app = FastAPI(title="Le Fil")
app.include_router(me.router)
app.include_router(links.router)


@app.get("/health")
def health():
    return {"ok": True}
