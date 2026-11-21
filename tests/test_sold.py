from datetime import datetime, timedelta, timezone

from flipperbot import bot
from flipperbot.config import Settings
from flipperbot.db import DB
from flipperbot.sources import olx

from test_olx_and_bot import offer

S = Settings()


def iso(days_ago: float) -> str:
    return (datetime.now(timezone.utc) - timedelta(days=days_ago)).isoformat(timespec="seconds")


def listing(i, title, price, created, seller):
    o = offer(i, title, price)
    o.update(created_time=created, last_refresh_time=created, user={"id": seller, "name": "x"})
    return olx.parse_offer(o)


def stale(db, *keys):
    for k in keys:  # not shown by the searches for a few days
        db.conn.execute("UPDATE listings SET last_seen = datetime('now', '-3 days') WHERE key=?", (k,))


def test_gone_listings_are_sold_expired_or_reposted(monkeypatch):
    monkeypatch.setattr(bot.time, "sleep", lambda x: None)
    db = DB(":memory:")
    a = listing(1, "Ceas Seiko SKX007 diver", 800, iso(6), "s1")       # gone after 6 days: sold
    b = listing(2, "Ceas Seiko SKX009 pepsi", 900, iso(35), "s2")      # gone after 35 days: expired
    c = listing(3, "Ceas Seiko SKX013 mid size", 700, iso(10), "s3")   # gone, but posted again: reposted
    d = listing(4, "Ceas Seiko SKX007 jubilee", 850, iso(5), "s4")     # still up
    bot.process(db, [a, b, c, d], S, alert=False)
    stale(db, "olx:1", "olx:2", "olx:3", "olx:4")
    up = {"s1": [], "s2": [], "s3": [listing(30, "Vand Ceas Seiko SKX013 mid size", 650, iso(0), "s3")], "s4": [d]}
    counts = bot.check_sold(db, S, seller_listings=lambda sid, **kw: (up[sid], True), log=lambda m: None)
    assert counts == {"sold": 1, "expired": 1, "reposted": 1, "up": 1}
    assert [db.get(f"olx:{i}")["gone_reason"] for i in (1, 2, 3)] == ["sold", "expired", "reposted"]
    assert db.get("olx:4")["gone_at"] is None
    # checked: not asked again tomorrow-ish
    assert bot.check_sold(db, S, seller_listings=lambda sid, **kw: 1 / 0, log=lambda m: None)["up"] == 0


def test_a_big_sellers_missing_listing_proves_nothing(monkeypatch):
    db = DB(":memory:")
    bot.process(db, [listing(1, "Ceas Seiko SKX007", 800, iso(5), "shop")], S, alert=False)
    stale(db, "olx:1")
    bot.check_sold(db, S, seller_listings=lambda sid, **kw: ([], False), log=lambda m: None)
    assert db.get("olx:1")["gone_at"] is None


def test_sold_prices_beat_asking_prices():
    db = DB(":memory:")
    asks = [listing(100 + i, "Ceas Seiko SKX007 diver", p, iso(3), f"a{i}") for i, p in enumerate([1400, 1500, 1450, 1500, 1550])]
    sold = [listing(200 + i, "Ceas Seiko SKX007 diver", p, iso(12), f"b{i}") for i, p in enumerate([900, 950, 1000, 980])]
    bot.process(db, asks + sold, S, alert=False)
    db.conn.execute("UPDATE listings SET gone_at=?, gone_reason='sold' WHERE key LIKE 'olx:20%'", (iso(2),))
    bot.process(db, [listing(1, "Ceas Seiko SKX007 diver", 700, iso(0), "me")], S, alert=False)
    r = db.get("olx:1")
    assert "sold for" in r["reason"] and "4 sold lately" in r["reason"]
    assert r["est_value_ron"] < 1000  # from what sold (~950), not what's asked (~1500)
    import json
    liq = json.loads(r["liquidity"])
    assert liq["sold"] == 4 and liq["sold_days"] == 10 and liq["label"] == "normal"


def test_the_still_up_check_refreshes_prices(monkeypatch):
    monkeypatch.setattr(bot.time, "sleep", lambda x: None)
    db = DB(":memory:")
    market = [listing(100 + i, "Ceas Seiko SKX007 diver", p, iso(3), f"m{i}") for i, p in enumerate([1000, 1100, 950, 1050, 1000])]
    good = listing(1, "Ceas Seiko SKX007 diver", 600, iso(2), "s1")
    bot.process(db, [*market, good], S, alert=False)
    assert db.get("olx:1")["score"] >= 5
    # seen 8 hours ago: a 5+ listing is refreshed after 6 hours, not a day
    db.conn.execute("UPDATE listings SET last_seen = datetime('now', '-8 hours') WHERE key='olx:1'")
    now = listing(1, "Ceas Seiko SKX007 diver", 900, iso(2), "s1")  # the seller raised it
    asked = []
    bot.check_sold(db, S, seller_listings=lambda sid, **kw: (asked.append(sid) or [now], True), log=lambda m: None)
    assert asked == ["s1"]
    r = db.get("olx:1")
    assert r["price_ron"] == 900 and r["gone_at"] is None  # the card shows what OLX shows now


def test_claude_checks_the_price_it_has_now(monkeypatch):
    db = DB(":memory:")
    bot.process(db, [listing(1, "Ceas Seiko SKX007 diver", 600, iso(2), "s1")], S, alert=False)
    r = bot.refresh_listing(db, S, "olx:1", seller_listings=lambda sid, **kw: ([listing(1, "Ceas Seiko SKX007 diver", 550, iso(2), "s1")], True))
    assert r["price_ron"] == 550
    # OLX not answering: unchanged, no crash
    r = bot.refresh_listing(db, S, "olx:1", seller_listings=lambda sid, **kw: 1 / 0)
    assert r["price_ron"] == 550


def test_a_starter_price_book_listing_is_refreshed_by_its_title():
    db = DB(":memory:")
    bot.process(db, [listing(1, "Iphone 14 promax 128 gb", 1850, iso(4), "")], S, alert=False)
    r = bot.refresh_listing(db, S, "olx:1", seller_listings=lambda *a, **k: 1 / 0,
                            search=lambda q, **kw: [listing(1, "Iphone 14 promax 128 gb", 1670, iso(4), "s9")])
    assert r["price_ron"] == 1670 and r["seller_id"] == "s9"


def test_a_listing_you_open_is_checked_and_a_sold_one_leaves_interesting():
    from flipperbot import web
    from flipperbot.models import Listing

    s = Settings()
    db = DB(":memory:")
    l = Listing("olx", "1", "u", "Seiko SKX007 automatic", price_ron=400, seller_id="s1", created_at="2026-11-20T10:00:00+00:00")
    db.upsert(l)
    db.conn.execute("UPDATE listings SET score=7, last_seen=datetime('now', '-1 hour') WHERE key='olx:1'")
    db.conn.commit()
    assert [r["key"] for r in web.query(db, "interesting")] == ["olx:1"]
    calls = []

    def gone(seller, **kw):
        calls.append(seller)
        return [], True  # the seller has nothing up any more

    r = bot.check_alive(db, s, "olx:1", seller_listings=gone)
    assert calls == ["s1"] and r["gone_reason"] == "sold"
    assert web.query(db, "interesting") == []
    bot.check_alive(db, s, "olx:1", seller_listings=gone)
    assert calls == ["s1"]  # gone already: not asked again


def test_interesting_listings_are_checked_first():
    from flipperbot.models import Listing

    s = Settings()
    s.sold_checks_per_poll = 1
    db = DB(":memory:")
    for i, (seller, score) in enumerate([("old", 2), ("hot", 7)]):
        db.upsert(Listing("olx", str(i), "u", f"Seiko SKX007 v{i}", price_ron=400, seller_id=seller))
        db.conn.execute("UPDATE listings SET score=?, model_key='seiko|SKX007', last_seen=datetime('now', '-3 hours') "
                        "WHERE key=?", (score, f"olx:{i}"))
    db.conn.commit()
    asked = []
    bot.check_sold(db, s, seller_listings=lambda seller, **kw: (asked.append(seller), ([], False))[1], log=lambda m: None)
    assert asked == ["hot"]
