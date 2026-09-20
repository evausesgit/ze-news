"""Lecture du contenu d'un lien AVANT l'appel à Codex.

- Tweets : API publique fxtwitter (texte, auteur, date, tweet cité) — pas de clé,
  pas de navigateur headless. X ne sert plus de HTML lisible sans JavaScript.
- Pages web : GET httpx + extraction légère (titre, description, paragraphes).

Si la lecture échoue (paywall, anti-bot, timeout), on renvoie un `Fetched` vide
et Codex s'appuie sur sa recherche web. Le contenu lu est une DONNÉE non fiable :
le prompt Codex le présente comme tel.
"""

from __future__ import annotations

import datetime as dt
import logging
import re
from dataclasses import dataclass
from html.parser import HTMLParser

import httpx

from app.config import settings
from app.urls import ParsedUrl

log = logging.getLogger(__name__)

MAX_TEXT_CHARS = 6000
MAX_BYTES = 3_000_000
_UA = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/128.0 Safari/537.36 ZeNews/0.1"
)


@dataclass
class Fetched:
    ok: bool = False
    title: str | None = None
    author: str | None = None
    published_at: dt.datetime | None = None
    text: str = ""
    final_url: str | None = None
    error: str | None = None


def fetch(parsed: ParsedUrl, client: httpx.Client | None = None) -> Fetched:
    own = client is None
    client = client or httpx.Client(
        timeout=settings.fetch_timeout_seconds,
        follow_redirects=True,
        headers={"User-Agent": _UA, "Accept-Language": "en,fr;q=0.8"},
    )
    try:
        if parsed.kind == "tweet" and parsed.tweet_id:
            return fetch_tweet(client, parsed.tweet_id, parsed.tweet_user or "i")
        return fetch_web(client, parsed.url)
    except httpx.HTTPError as e:
        return Fetched(error=f"{type(e).__name__}: {e}"[:300])
    finally:
        if own:
            client.close()


# --------------------------------------------------------------------- tweets


def _tweet_block(tweet: dict) -> str:
    author = tweet.get("author") or {}
    lines = [f"@{author.get('screen_name', '?')} ({author.get('name', '')}) :"]
    lines.append(tweet.get("text") or "")
    article = tweet.get("article") or {}
    if article.get("title"):
        lines.append(f"[Article X] {article.get('title')} — {article.get('preview_text', '')}")
    for m in (tweet.get("media") or {}).get("all", []) or []:
        if m.get("altText"):
            lines.append(f"[image] {m['altText']}")
    return "\n".join(line for line in lines if line)


def parse_fxtwitter(payload: dict) -> Fetched:
    tweet = payload.get("tweet")
    if not isinstance(tweet, dict):
        return Fetched(error=f"fxtwitter: {payload.get('message', 'réponse vide')}")
    parts = [_tweet_block(tweet)]
    if isinstance(tweet.get("quote"), dict):
        parts.append("--- Tweet cité ---\n" + _tweet_block(tweet["quote"]))
    ts = tweet.get("created_timestamp")
    author = tweet.get("author") or {}
    return Fetched(
        ok=True,
        title=None,
        author=f"@{author['screen_name']}" if author.get("screen_name") else None,
        published_at=dt.datetime.fromtimestamp(ts, dt.UTC) if ts else None,
        text="\n\n".join(parts)[:MAX_TEXT_CHARS],
        final_url=tweet.get("url"),
    )


def fetch_tweet(client: httpx.Client, tweet_id: str, user: str) -> Fetched:
    r = client.get(f"https://api.fxtwitter.com/{user}/status/{tweet_id}")
    if r.status_code != 200:
        return Fetched(error=f"fxtwitter HTTP {r.status_code}")
    return parse_fxtwitter(r.json())


# ------------------------------------------------------------------ pages web

_SKIP_TAGS = {"script", "style", "noscript", "svg", "nav", "footer", "header", "aside", "form"}
_BLOCK_TAGS = {"p", "h1", "h2", "h3", "li", "blockquote", "pre", "td", "article"}


class _PageParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.title = ""
        self.meta: dict[str, str] = {}
        self.blocks: list[str] = []
        self._skip = 0
        self._in_title = False
        self._buf: list[str] = []

    def handle_starttag(self, tag, attrs):
        a = {k.lower(): (v or "") for k, v in attrs}
        if tag == "meta":
            key = (a.get("property") or a.get("name") or "").lower()
            if key and a.get("content") and key not in self.meta:
                self.meta[key] = a["content"].strip()
        elif tag == "title":
            self._in_title = True
        elif tag in _SKIP_TAGS:
            self._skip += 1
        elif tag in _BLOCK_TAGS:
            self._flush()

    def handle_endtag(self, tag):
        if tag == "title":
            self._in_title = False
        elif tag in _SKIP_TAGS and self._skip:
            self._skip -= 1
        elif tag in _BLOCK_TAGS:
            self._flush()

    def handle_data(self, data):
        if self._in_title:
            self.title += data
        elif not self._skip:
            self._buf.append(data)

    def _flush(self):
        text = re.sub(r"\s+", " ", "".join(self._buf)).strip()
        self._buf = []
        if len(text) >= 40:  # ignore menus, boutons, légendes
            self.blocks.append(text)

    def close(self):
        super().close()
        self._flush()


def parse_html(html: str) -> Fetched:
    p = _PageParser()
    p.feed(html)
    p.close()
    title = p.meta.get("og:title") or re.sub(r"\s+", " ", p.title).strip() or None
    desc = p.meta.get("og:description") or p.meta.get("description") or ""
    author = p.meta.get("author") or p.meta.get("article:author") or p.meta.get("og:site_name")
    published = None
    raw_date = p.meta.get("article:published_time") or p.meta.get("date")
    if raw_date:
        try:
            published = dt.datetime.fromisoformat(raw_date)
        except ValueError:
            published = None
    body = "\n".join(p.blocks)
    text = "\n\n".join(x for x in (desc, body) if x)[:MAX_TEXT_CHARS]
    return Fetched(
        ok=bool(title or len(text) > 80),
        title=title,
        author=author,
        published_at=published,
        text=text,
    )


def fetch_web(client: httpx.Client, url: str) -> Fetched:
    with client.stream("GET", url) as r:
        if r.status_code >= 400:
            return Fetched(error=f"HTTP {r.status_code}", final_url=str(r.url))
        ctype = r.headers.get("content-type", "")
        if "html" not in ctype and "text" not in ctype:
            return Fetched(error=f"contenu non textuel ({ctype or 'inconnu'})", final_url=str(r.url))
        chunks, size = [], 0
        for chunk in r.iter_bytes():
            chunks.append(chunk)
            size += len(chunk)
            if size > MAX_BYTES:
                break
        html = b"".join(chunks).decode(r.encoding or "utf-8", errors="replace")
        final_url = str(r.url)
    fetched = parse_html(html)
    fetched.final_url = final_url
    if not fetched.ok:
        fetched.error = "page sans contenu lisible (JavaScript, paywall ou anti-bot ?)"
    return fetched
