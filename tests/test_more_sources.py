from datetime import date

from flipperbot import bot
from flipperbot.config import Settings
from flipperbot.db import DB
from flipperbot.sources import lajumate, publi24

PUBLI24 = """<html><div class="article-item " data-articleid="X">
<a href="https://www.publi24.ro/anunturi/moda-accesorii/accesorii/anunt/omega-seamaster-300m/abc123.html"><img src="https://s3.publi24.ro/a.webp" alt=""></a>
<h2 class="article-title"><a href="https://www.publi24.ro/anunturi/moda-accesorii/accesorii/anunt/omega-seamaster-300m/abc123.html">Omega Seamaster 300m</a></h2>
<p class="article-description">Ceas original, cutie si acte</p>
<p class="article-location"><span>Sector 4, Bucuresti</span></p><p class="article-date"><span>ieri 12:22</span></p>
<div class="article-info"><span class="article-price"><i class="svg-icon"><svg></svg></i>
<span class="new-price">2,999 RON</span> <span class="old-price">3,300 RON</span></span></div></div>
<div class="article-item " data-articleid="Y">
<h2 class="article-title"><a href="https://www.publi24.ro/anunturi/electronice/anunt/ps5-slim/def456.html">Vand PS5 Slim disc</a></h2>
<a href="https://www.publi24.ro/anunturi/electronice/anunt/ps5-slim/def456.html"></a>
<p class="article-location">Cluj-Napoca, Cluj</p><p class="article-date">12 Noiembrie</p><span class="article-price">500 EUR</span></div></html>"""

LAJUMATE = """<html><script id="__NEXT_DATA__" type="application/json">{"props": {"pageProps": {"adsServer": [
{"id": 17113837, "title": "Ceas Omega Speedmaster", "slug": "ceas-omega-speedmaster", "description": "functional",
 "price": "500.00", "currency": "lei", "listed_at": "2026-11-10 08:50:24", "mainImage": null,
 "user": {"id": 126071, "name": "Vlad", "phone": "0700000000"}, "city": {"name": "Satu Mare"}}]}}}</script></html>"""


def test_publi24_listings():
    ls = publi24.parse(PUBLI24, eur_to_ron=5.0, today=date(2026, 11, 13))
    assert [(l.source_id, l.price_ron, l.city, l.created_at[:10]) for l in ls] == [
        ("abc123", 2999, "Sector 4", "2026-11-12"), ("def456", 2500, "Cluj-Napoca", "2026-11-12")]
    assert ls[0].previous_price_ron == 3300  # the crossed-out price before the cut, not the current one
    assert ls[0].title == "Omega Seamaster 300m" and ls[0].photos and ls[0].key == "publi24:abc123"
    assert publi24.parse_date("13 Decembrie", today=date(2026, 1, 5)).startswith("2025-12-13")


def test_lajumate_listings_without_phone_numbers():
    (l,) = lajumate.parse(LAJUMATE)
    assert (l.key, l.price_ron, l.city, l.created_at) == ("lajumate:17113837", 500, "Satu Mare", "2026-11-10T08:50:24")
    assert l.url == "https://lajumate.ro/ad/ceas-omega-speedmaster-17113837"
    assert "0700000000" not in repr(l)  # the seller's phone is never kept


def test_more_sources_feed_the_same_pipeline(monkeypatch):
    monkeypatch.setattr(bot.time, "sleep", lambda x: None)
    s = Settings()
    s.niches = ["watches"]
    s.more_sources_terms = 1
    db = DB(":memory:")
    calls = []

    def fake(name):
        def run(q):
            calls.append((name, q))
            return publi24.parse(PUBLI24) if name == "publi24" else lajumate.parse(LAJUMATE)
        return run

    monkeypatch.setattr(bot.random, "sample", lambda pool, k: ["omega seamaster"][:k])
    n = bot.poll_more(db, s, log=lambda m: None, sources={"publi24": fake("publi24"), "lajumate": fake("lajumate")})
    assert n == 3 and {c[0] for c in calls} == {"publi24", "lajumate"}
    assert db.get("publi24:abc123")["model_key"] == "omega|seamaster"  # brand + searched words: a watch
    assert db.get("publi24:def456") is None  # a PS5 is not a watch
    assert db.get("lajumate:17113837")["niche"] == "watches"
    assert bot.poll_more(db, s, log=lambda m: None, sources={}) == 0  # not again for 15 minutes


def test_publi24_numbers():
    assert [publi24._number(x) for x in ("3 500", "2,999", "1.200", "15", "1 234,50", "12.5")] == [3500, 2999, 1200, 15, 1234, 12]
    assert publi24._amount("85 534 400 RON", 5.0) is None  # a building, not a flip
    assert publi24._amount("1.200 EUR", 5.0) == 6000


def test_misread_publi24_prices_are_dropped_once():
    from flipperbot.config import Settings
    s = Settings()
    db = DB(":memory:")
    def fresh():
        ls = publi24.parse(PUBLI24)
        for l in ls:
            l.params["query"] = "omega seamaster"
        return ls

    bot.process(db, fresh(), s, alert=False)
    db.conn.execute("INSERT INTO listings (key, source, title, price_ron) VALUES ('publi24:old', 'publi24', 'x', 300)")
    db.kv_set("rules_version", 0)
    bot.rescore_if_rules_changed(db, s, log=lambda m: None)
    assert db.conn.execute("SELECT COUNT(*) FROM listings WHERE source='publi24'").fetchone()[0] == 0
    bot.process(db, fresh(), s, alert=False)
    bot.rescore_if_rules_changed(db, s, log=lambda m: None)  # only once
    assert db.get("publi24:abc123") is not None
