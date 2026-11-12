from flipperbot import bot
from flipperbot.config import Settings
from flipperbot.db import DB
from flipperbot.sources import ebay, olx

from test_olx_and_bot import offer


def item(title, eur, cur="EUR"):
    return {"title": title, "price": {"value": str(eur), "currency": cur}}


ITEMS = [item("Seiko SKX007 automatic diver", p) for p in (150, 170, 180, 190, 200, 220, 250)] + [
    item("Seiko SKX007 strap original", 30), item("Seiko SKX007 box", 20), item("Seiko SKX007 USD", 300, "USD")]


def test_summarize_skips_parts_and_shades_asking_prices():
    sm = ebay.summarize(ITEMS, eur_to_ron=5.0)
    assert sm["n"] == 7  # straps, boxes and other currencies dropped
    assert sm["median_ask"] == 950 and sm["low"] < sm["high"] < sm["median_ask"]
    assert ebay.summarize(ITEMS[:3], 5.0) is None  # too few to say


def settings():
    s = Settings()
    s.ebay_client_id, s.ebay_client_secret, s.ebay_daily_calls = "id", "secret", 2
    return s


def test_lookup_caches_and_respects_the_daily_cap(monkeypatch):
    s, db, calls = settings(), DB(":memory:"), []
    monkeypatch.setattr(ebay, "_search_api", lambda db_, s_, q: calls.append(q) or ITEMS)
    assert ebay.lookup(db, s, "seiko SKX007")["n"] == 7
    assert ebay.lookup(db, s, "seiko SKX007")["n"] == 7 and calls == ["seiko SKX007"]  # cached
    ebay.lookup(db, s, "omega x")
    assert ebay.lookup(db, s, "tissot y") is None and len(calls) == 2  # cap of 2 a day
    assert ebay.lookup(db, Settings(), "seiko SKX007") is None  # not set up: nothing


def test_ebay_prices_a_model_local_listings_cant(monkeypatch):
    s, db = settings(), DB(":memory:")
    monkeypatch.setattr(ebay, "_search_api", lambda db_, s_, q: ITEMS)
    bot.process(db, [olx.parse_offer(offer(1, "Ceas Seiko SKX007 automatic", 300))], s, alert=False)
    row = db.get("olx:1")
    assert row["tier"] == "good" and row["reason"].startswith("eBay:")  # good at most: never real good from eBay alone
    assert row["est_value_ron"] < row["est_high_ron"] and row["profit_ron"] == row["est_value_ron"] - 300
    assert '"n": 7' in row["ebay"]


def test_ebay_not_used_for_brand_only_or_fashion(monkeypatch):
    s, db, calls = settings(), DB(":memory:"), []
    monkeypatch.setattr(ebay, "_search_api", lambda db_, s_, q: calls.append(q) or ITEMS)
    bot.process(db, [olx.parse_offer(offer(1, "Ceas Seiko barbatesc", 300)),
                     olx.parse_offer(offer(2, "Ceas Michael Kors MK5412", 300))], s, alert=False)
    assert calls == []
