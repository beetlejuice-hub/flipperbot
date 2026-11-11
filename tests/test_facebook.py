"""Facebook needs a real logged-in account, so these cover everything around it,
with a stand-in for the browser part."""

import pytest

from flipperbot import bot
from flipperbot.config import Settings
from flipperbot.db import DB
from flipperbot.sources import facebook


@pytest.mark.parametrize("text, lei", [
    ("1.200 lei", 1200), ("RON1,200", 1200), ("1 200 lei", 1200), ("RON 12.500", 12500), ("RON1,200.00", 1200),
    ("€300", 1500), ("EUR 1.250,00", 6250), ("350", 350), ("450,50 lei", 450),
    ("Gratuit", None), ("$50", None), (None, None),
])
def test_parse_price(text, lei):
    assert facebook.parse_price(text, eur_to_ron=5.0) == lei


def item(i, title, price, **kw):
    return {"listing_id": str(i), "title": title, "price": price, "location": "Cluj-Napoca, Cluj",
            "url": f"https://www.facebook.com/marketplace/item/{i}/", "image_url": f"https://img/{i}.jpg", **kw}


def test_to_listing_uses_details_when_there():
    l = facebook.to_listing(item(5, "Ceas Seiko 5 automatic", "RON350", description="merge perfect",
                                 images=["https://img/a.jpg", "https://img/b.jpg"], seller_profile_url="https://fb/u/9"))
    assert (l.key, l.price_ron, l.city, l.region) == ("facebook:5", 350, "Cluj-Napoca", "Cluj")
    assert l.description == "merge perfect" and l.photos == ["https://img/a.jpg", "https://img/b.jpg"]
    assert l.seller_id == "https://fb/u/9"


def test_facebook_watch_titles():
    def L(title):
        return facebook.to_listing(item(1, title, "RON100"))
    assert bot.is_watch(L("Ceas barbatesc automatic vechi"), [])  # no brand, no category: "ceas" is enough here
    assert bot.is_watch(L("Seiko 5 automatic"), [])
    assert not bot.is_watch(L("Ceas de perete"), [])
    assert not bot.is_watch(L("Bicicleta"), [])


def run(monkeypatch, fake_search):
    s = Settings()
    db = DB(":memory:")
    db.kv_set("facebook", {"state": "ok", "next_at": 0})
    monkeypatch.setattr(facebook, "installed", lambda: True)
    monkeypatch.setattr(facebook, "search", fake_search)
    return s, db


def test_poll_facebook_judges_like_olx(monkeypatch):
    seen = []

    def fake_search(queries, *, is_new, looks_like_watch, **kw):
        assert len(queries) == 2
        listings = [facebook.to_listing(item(i, "Ceas Seiko SKX007", f"RON{p}")) for i, p in enumerate([1000, 1100, 950, 1050, 1000])]
        listings.append(facebook.to_listing(item(99, "Ceas Seiko SKX007 diver", "RON400")))
        seen.extend(l.key for l in listings if is_new(l.key) and looks_like_watch(l))
        yield from listings

    s, db = run(monkeypatch, fake_search)
    assert bot.facebook_due(db, s)
    assert bot.poll_facebook(db, s, log=lambda m: None) == 6
    assert len(seen) == 6
    assert db.get("facebook:99")["tier"] == "real_good"
    state = db.kv_get("facebook")
    assert state["state"] == "ok" and state["next_at"] > 0
    assert not bot.facebook_due(db, s)  # next run 30-60 minutes later


def test_logged_out_stops_facebook_until_login(monkeypatch):
    def fake_search(queries, **kw):
        raise facebook.NotLoggedIn("redirected to /login")
        yield  # pragma: no cover

    s, db = run(monkeypatch, fake_search)
    bot.poll_facebook(db, s, log=lambda m: None)
    assert db.kv_get("facebook")["state"] == "logged_out"
    assert not bot.facebook_due(db, s)


def test_not_set_up_means_no_facebook(monkeypatch):
    s = Settings()
    db = DB(":memory:")
    monkeypatch.setattr(facebook, "installed", lambda: True)
    assert not bot.facebook_due(db, s)
