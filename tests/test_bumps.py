from datetime import datetime, timedelta, timezone

from flipperbot import bot
from flipperbot.config import Settings
from flipperbot.db import DB
from flipperbot.sources import olx

from test_olx_and_bot import offer

S = Settings()


def iso(days_ago: float) -> str:
    return (datetime.now(timezone.utc) - timedelta(days=days_ago)).isoformat(timespec="seconds")


def listing(i, title, price, created, refreshed=None, seller="u1"):
    o = offer(i, title, price)
    o.update(created_time=created, last_refresh_time=refreshed or created, user={"id": seller, "name": "x"})
    return olx.parse_offer(o)


def test_a_bump_is_not_a_new_listing():
    db = DB(":memory:")
    l = listing(1, "Ceas Seiko SKX007", 900, iso(20), iso(20))
    assert db.upsert(l)[0] == "new" and db.get("olx:1")["bumps"] == 0
    bumped = listing(1, "Ceas Seiko SKX007", 900, iso(20), iso(0))
    assert db.upsert(bumped)[0] == "bumped" and db.get("olx:1")["bumps"] == 1
    assert db.conn.execute("SELECT COUNT(*) FROM listings").fetchone()[0] == 1  # no duplicate
    # first seen already bumped: refreshed long after it was posted
    db.upsert(listing(2, "Ceas Orient Bambino", 500, iso(60), iso(0)))
    assert db.get("olx:2")["bumps"] == 1


def test_a_repost_keeps_its_first_posting_date_and_the_old_listing_rule():
    db = DB(":memory:")
    market = [listing(100 + i, "Ceas Seiko SKX007 diver", p, iso(5), seller=f"m{i}") for i, p in enumerate([1000, 1100, 950, 1050, 1000])]
    old = listing(1, "Ceas Seiko SKX007 diver automatic", 450, iso(70), seller="s1")
    bot.process(db, [*market, old], S, alert=False)
    db.conn.execute("UPDATE listings SET last_seen = datetime('now', '-5 days') WHERE key='olx:1'")  # deleted on OLX
    again = listing(2, "Vand ceas Seiko SKX007 diver automatic", 430, iso(0), seller="s1")
    bot.process(db, [again], S, alert=False)
    r = db.get("olx:2")
    assert r["repost_of"] == "olx:1" and r["orig_created_at"][:10] == iso(70)[:10]
    assert "first posted 70 days ago" in r["reason"] and r["tier"] == "mid"


def test_a_shops_identical_listings_still_up_are_not_reposts():
    db = DB(":memory:")
    db.upsert(listing(1, "PS5 Slim disc 1TB nou sigilat", 2900, iso(10), seller="shop"))
    db.upsert(listing(2, "PS5 Slim disc 1TB nou sigilat", 2900, iso(0), seller="shop"))
    assert db.get("olx:2")["repost_of"] is None  # the first is still up: two units, not a repost
