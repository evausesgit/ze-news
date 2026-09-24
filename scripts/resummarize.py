"""Refait les résumés déjà produits avec le prompt actuel (phrase + interprétation).

    uv run python -m scripts.resummarize [--limit N] [--workers 3] [--dry-run]

Un lien est à refaire tant que son résumé n'a pas la structure en deux
paragraphes (pas de ligne vide) : le script est donc reprenable à volonté et
rattrape aussi les liens résumés entre-temps par un worker à l'ancien prompt.
Les plus récemment partagés passent en premier. Un échec laisse l'ancien
résumé en place.
"""

from __future__ import annotations

import argparse
import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from sqlalchemy import func, or_, select

from app.db import SessionLocal
from app.enrich import resummarize_link
from app.models import Link, Share

log = logging.getLogger("zenews.resummarize")


def links_to_redo(limit: int | None) -> list[int]:
    last_shared = (
        select(Share.link_id, func.max(Share.shared_at).label("last"))
        .group_by(Share.link_id)
        .subquery()
    )
    stmt = (
        select(Link.id)
        .join(last_shared, last_shared.c.link_id == Link.id, isouter=True)
        .where(
            Link.status == "done",
            or_(Link.summary_fr.is_(None), Link.summary_fr.not_like("%\n\n%")),
        )
        .order_by(last_shared.c.last.desc().nulls_last(), Link.id.desc())
        .limit(limit)
    )
    with SessionLocal() as session:
        return list(session.scalars(stmt))


def redo(link_id: int) -> bool:
    with SessionLocal() as session:
        link = session.get(Link, link_id)
        return link is not None and resummarize_link(session, link)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int)
    parser.add_argument("--workers", type=int, default=3)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")

    ids = links_to_redo(args.limit)
    log.info("%d lien(s) à re-résumer", len(ids))
    if args.dry_run or not ids:
        return
    ok = ko = 0
    t0 = time.monotonic()
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(redo, i): i for i in ids}
        for n, fut in enumerate(as_completed(futures), 1):
            try:
                success = fut.result()
            except Exception:
                log.exception("lien %s : erreur inattendue", futures[fut])
                success = False
            ok += success
            ko += not success
            if n % 10 == 0 or n == len(ids):
                log.info("%d/%d (%d ok, %d échec) — %.0f s", n, len(ids), ok, ko,
                         time.monotonic() - t0)
    log.info("terminé : %d ok, %d échec(s)", ok, ko)


if __name__ == "__main__":
    main()
