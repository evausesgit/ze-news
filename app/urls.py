"""Extraction des liens d'un message Telegram et normalisation.

La normalisation sert au dédoublonnage : Yoann peut partager le même tweet via
twitter.com, x.com, mobile.twitter.com, fxtwitter.com… avec ou sans `?s=20`.
Tous donnent la même `canonical_url` et donc le même `Link`.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

# Regex volontairement simple : Telegram fournit déjà les entités URL, la regex
# n'est qu'un filet de sécurité pour les messages sans entités.
_URL_RE = re.compile(r"https?://[^\s<>\"'«»]+", re.IGNORECASE)
_TRAILING = ".,;:!?)]}’”"

_TWEET_HOSTS = {
    "twitter.com", "x.com", "mobile.twitter.com", "mobile.x.com",
    "fxtwitter.com", "vxtwitter.com", "fixupx.com", "fixvx.com", "nitter.net",
}
_TWEET_PATH = re.compile(r"^/([A-Za-z0-9_]{1,30})/status(?:es)?/(\d+)")

_TRACKING_PARAMS = {
    "fbclid", "gclid", "igshid", "mc_cid", "mc_eid", "ref", "ref_src", "ref_url",
    "s", "t", "si", "feature", "cmpid", "smid", "src",
}

# Liens qu'on ne veut jamais transformer en carte (liens internes Telegram…).
_IGNORED_HOSTS = {"t.me", "telegram.me", "telegram.org"}


@dataclass(frozen=True)
class ParsedUrl:
    url: str  # telle que reçue
    canonical: str
    kind: str  # tweet | web
    domain: str
    tweet_id: str | None = None
    tweet_user: str | None = None


def _clean(raw: str) -> str:
    return raw.rstrip(_TRAILING)


def extract_urls(text: str, entity_urls: list[str] | None = None) -> list[str]:
    """URLs d'un message, dans l'ordre, sans doublons.

    `entity_urls` : URLs issues des entités Telegram (liens cachés derrière un
    texte cliquable inclus), prioritaires sur la regex.
    """
    seen: set[str] = set()
    out: list[str] = []
    for raw in [*(entity_urls or []), *_URL_RE.findall(text or "")]:
        url = _clean(raw.strip())
        if not url.lower().startswith(("http://", "https://")):
            url = "https://" + url
        if url not in seen:
            seen.add(url)
            out.append(url)
    return out


def parse_url(url: str) -> ParsedUrl | None:
    """Normalise une URL ; None si le lien est à ignorer."""
    try:
        parts = urlsplit(url.strip())
    except ValueError:
        return None
    host = (parts.hostname or "").lower()
    if not host or parts.scheme not in ("http", "https"):
        return None
    host = host.removeprefix("www.")
    if host in _IGNORED_HOSTS:
        return None

    if host in _TWEET_HOSTS:
        m = _TWEET_PATH.match(parts.path)
        if m:
            user, tweet_id = m.group(1), m.group(2)
            return ParsedUrl(
                url=url,
                canonical=f"https://x.com/{user}/status/{tweet_id}",
                kind="tweet",
                domain="x.com",
                tweet_id=tweet_id,
                tweet_user=user,
            )
        host = "x.com" if host != "nitter.net" else host

    query = [
        (k, v)
        for k, v in parse_qsl(parts.query, keep_blank_values=False)
        if not k.lower().startswith("utm_") and k.lower() not in _TRACKING_PARAMS
    ]
    query.sort()
    path = parts.path.rstrip("/") or ""
    canonical = urlunsplit(("https", host, path, urlencode(query), ""))
    return ParsedUrl(url=url, canonical=canonical, kind="web", domain=host)
