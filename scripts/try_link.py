"""Essai à blanc de l'enrichissement d'une URL (lecture + Codex), sans base de données.

    uv run python -m scripts.try_link https://x.com/karpathy/status/... ["message de Yoann"]

Pratique pour régler le prompt ou vérifier que codex est bien authentifié.
"""

from __future__ import annotations

import json
import sys
import time

from app.codex_cli import run_codex
from app.config import settings
from app.enrich import SCHEMA, build_prompt, normalize_themes
from app.fetch import fetch
from app.models import Link
from app.urls import parse_url


def main() -> None:
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    parsed = parse_url(sys.argv[1])
    if parsed is None:
        raise SystemExit("URL ignorée ou illisible.")
    print(f"canonique : {parsed.canonical} ({parsed.kind})")
    fetched = fetch(parsed)
    print(f"lecture   : {'ok' if fetched.ok else 'échec — ' + str(fetched.error)}")
    if fetched.text:
        print("extrait   :", fetched.text[:300].replace("\n", " "), "…")
    link = Link(url=parsed.url, kind=parsed.kind, domain=parsed.domain)
    prompt = build_prompt(link, fetched, sys.argv[2] if len(sys.argv) > 2 else "")
    t0 = time.monotonic()
    data, usage = run_codex(prompt, SCHEMA, settings.codex_web_search and not fetched.ok)
    data["themes"] = normalize_themes(data.get("themes"))
    print(f"\ncodex ({time.monotonic() - t0:.0f} s, {usage.input_tokens} in / "
          f"{usage.output_tokens} out) :")
    print(json.dumps(data, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
