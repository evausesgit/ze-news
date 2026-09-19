from app.fetch import parse_fxtwitter, parse_html
from app.urls import extract_urls, parse_url


def test_tweet_variants_share_one_canonical_url():
    variants = [
        "https://twitter.com/karpathy/status/123456?s=20",
        "https://x.com/karpathy/status/123456",
        "https://mobile.twitter.com/karpathy/status/123456/photo/1",
        "https://fxtwitter.com/karpathy/status/123456",
        "https://www.x.com/karpathy/statuses/123456",
    ]
    canon = {parse_url(v).canonical for v in variants}
    assert canon == {"https://x.com/karpathy/status/123456"}
    p = parse_url(variants[0])
    assert p.kind == "tweet" and p.tweet_id == "123456" and p.tweet_user == "karpathy"


def test_web_url_drops_tracking_and_www():
    p = parse_url("https://www.lemonde.fr/article/?utm_source=tw&id=3&fbclid=x#top")
    assert p.kind == "web"
    assert p.domain == "lemonde.fr"
    assert p.canonical == "https://lemonde.fr/article?id=3"


def test_telegram_links_are_ignored():
    assert parse_url("https://t.me/somechannel/12") is None
    assert parse_url("ftp://example.com/x") is None


def test_extract_urls_merges_entities_and_text_without_duplicates():
    text = "Regarde ça https://x.com/a/status/1, et ça (https://example.com/page)."
    urls = extract_urls(text, ["https://hidden.example.org/x", "https://x.com/a/status/1"])
    assert urls == [
        "https://hidden.example.org/x",
        "https://x.com/a/status/1",
        "https://example.com/page",
    ]


def test_extract_urls_adds_scheme_to_bare_entity():
    assert extract_urls("", ["example.com/x"]) == ["https://example.com/x"]


def test_parse_fxtwitter_with_quote():
    payload = {
        "tweet": {
            "url": "https://x.com/a/status/1",
            "text": "Big news",
            "author": {"screen_name": "a", "name": "Alice"},
            "created_timestamp": 1_700_000_000,
            "quote": {"text": "Original claim", "author": {"screen_name": "b", "name": "Bob"}},
        }
    }
    f = parse_fxtwitter(payload)
    assert f.ok and f.author == "@a"
    assert "Big news" in f.text and "Original claim" in f.text and "@b" in f.text
    assert f.published_at.year == 2023


def test_parse_fxtwitter_error():
    f = parse_fxtwitter({"code": 404, "message": "NOT_FOUND"})
    assert not f.ok and "NOT_FOUND" in f.error


def test_parse_html_extracts_meta_and_paragraphs():
    html = """<html><head><title>Fallback</title>
      <meta property="og:title" content="Le vrai titre">
      <meta name="description" content="Une description utile de la page.">
      <meta property="article:published_time" content="2026-09-01T08:00:00Z">
      <script>var x = "ne pas lire";</script></head>
      <body><nav>Menu Accueil Contact et autres liens de navigation inutiles</nav>
      <p>Premier paragraphe suffisamment long pour être gardé par le parseur.</p>
      <p>court</p></body></html>"""
    f = parse_html(html)
    assert f.ok
    assert f.title == "Le vrai titre"
    assert "Une description utile" in f.text
    assert "Premier paragraphe" in f.text
    assert "ne pas lire" not in f.text and "Menu Accueil" not in f.text
    assert f.published_at.day == 1
