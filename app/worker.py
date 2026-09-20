"""Boucle du worker : ingestion Telegram puis enrichissement Codex, en continu.

    python -m app.worker          # boucle infinie (service `worker` du compose)
    python -m app.worker --once   # un seul cycle (debug, cron)

Les deux étapes sont indépendantes : si Telegram est en panne, on continue
d'enrichir les liens déjà en attente, et inversement.
"""

from __future__ import annotations

import argparse
import logging
import time

from app.config import settings
from app.db import SessionLocal
from app.enrich import enrich_pending
from app.telegram_ingest import ingest_all

log = logging.getLogger("zenews.worker")


def run_cycle() -> None:
    with SessionLocal() as session:
        try:
            n = ingest_all(session)
            log.info("ingestion : %d nouveau(x) partage(s)", n)
        except Exception:
            session.rollback()
            log.exception("ingestion Telegram en échec")
    with SessionLocal() as session:
        try:
            ok, ko = enrich_pending(session)
            log.info("enrichissement : %d réussi(s), %d échec(s)", ok, ko)
        except Exception:
            session.rollback()
            log.exception("enrichissement en échec")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    while True:
        started = time.monotonic()
        run_cycle()
        if args.once:
            return
        elapsed = time.monotonic() - started
        time.sleep(max(30, settings.poll_interval_seconds - elapsed))


if __name__ == "__main__":
    main()
