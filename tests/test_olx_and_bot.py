"""OLX parsing and one full poll, offline.

The offers below are hand-written in the shape of OLX's listing data
(the GraphQL gateway and /api/v1/offers/ return the same fields). Replace them with a real saved response (samples/olx-*.json) once
one has been captured from a home connection: see samples/README.md.
"""

import json
from pathlib import Path

from flipperbot import bot
from flipperbot.config import Settings
from flipperbot.db import DB
from flipperbot.sources import olx


def offer(id, title, price, currency="RON", desc="", cat=1677, prev=None):
    return {
        "id": id,
        "url": f"https://www.olx.ro/d/oferta/x-ID{id}.html",
        "title": title,
        "description": desc,
        "created_time": "2026-11-11T10:00:00+02:00",
        "last_refresh_time": "2026-11-11T10:00:00+02:00",
        "offer_type": "offer",
        "business": False,
        "category": {"id": cat, "type": "goods"},
        "params": [
            {"key": "price", "name": "Pret", "type": "price", "value": {
                "value": price, "currency": currency, "negotiable": True, "previous_value": prev, "label": f"{price} lei"}},
            {"key": "state", "name": "Stare", "type": "select", "value": {"key": "used", "label": "Utilizat"}},
        ],
        "location": {"city": {"name": "Cluj-Napoca"}, "region": {"name": "Cluj"}},
        "user": {"id": 42, "name": "Ion"},
        "photos": [{"link": "https://img.example/v1/files/abc/image;s={width}x{height}"}],
        "delivery": {"rock": {"active": True}},
    }


def page(*offers):
    return {"data": list(offers), "links": {}, "metadata": {"total_elements": len(offers)}}


def test_parse_offer():
    l = olx.parse_offer(offer(7, "Ceas Seiko 5", 300, desc="<p>Merge perfect<br/>cutie</p>"))
    assert l.key == "olx:7"
    assert l.price_ron == 300 and l.negotiable
    assert l.description == "Merge perfect\ncutie"
    assert l.photos == ["https://img.example/v1/files/abc/image;s=1000x1000"]
    assert l.city == "Cluj-Napoca" and l.delivery and l.condition == "used"


def test_eur_converted_and_buy_ads_dropped():
    assert olx.parse_offer(offer(1, "Ceas", 100, currency="EUR"), eur_to_ron=5.0).price_ron == 500
    o = offer(2, "Ceas", 100)
    o["offer_type"] = "buy"
    assert olx.parse_offer(o) is None


def test_search_params():
    p = {x["key"]: x["value"] for x in olx.search_params("lot ceasuri", max_price=5000)}
    assert p == {"offset": "0", "limit": "40", "query": "lot ceasuri", "sort_by": "created_at:desc", "filter_float_price:to": "5000"}


def test_poll_end_to_end(capsys):
    s = Settings()
    db = DB(":memory:")
    market = [offer(100 + i, "Ceas Seiko SKX007 automatic", p) for i, p in enumerate([1000, 1100, 950, 1050, 1000])]
    deal = offer(200, "Ceas Seiko SKX007 diver", 420)
    junk = offer(201, "Ceas Michael Kors dama", 150)
    car = offer(202, "Opel Omega 2.0 piese", 500, cat=999)
    listings = [olx.parse_offer(o) for o in [*market, deal, junk, car]]

    bot.learn_categories(db, listings)
    for_ai = bot.process(db, listings, s)

    assert db.get("olx:202") is None  # not a watch
    assert db.get("olx:201")["tier"] == "bad"
    # The deal came after the market listings in the same batch, so it is priced against them.
    row = db.get("olx:200")
    assert row["tier"] == "real_good", row["reason"]
    assert [r["key"] for r in for_ai] == ["olx:200"]
    assert "REAL GOOD" in capsys.readouterr().out  # no Telegram configured: alert printed

    # Seen again at the same price: nothing new. At a lower price: re-judged.
    assert bot.process(db, [olx.parse_offer(deal)], s) == []
    assert db.get("olx:200")["notified_tier"] == "real_good"


def test_mid_rejudged_on_price_drop():
    s = Settings()
    db = DB(":memory:")
    market = [olx.parse_offer(offer(100 + i, "Ceas Orient Bambino", p)) for i, p in enumerate([600, 650, 600, 620, 640])]
    bot.process(db, market, s)
    bot.process(db, [olx.parse_offer(offer(300, "Ceas Orient Bambino", 500))], s)
    assert db.get("olx:300")["tier"] == "mid"
    bot.process(db, [olx.parse_offer(offer(300, "Ceas Orient Bambino", 280))], s)
    assert db.get("olx:300")["tier"] == "good"  # 55% under, ~247 lei profit: under the 300 bar for real_good


def test_real_sample_if_present():
    """Parses every saved real OLX response in samples/, if any are there."""
    for path in sorted((Path(__file__).parent.parent / "samples").glob("olx-*.json")):
        data = json.loads(path.read_text())
        parsed = [olx.parse_offer(o) for o in data.get("data", [])]
        assert parsed and all(p is None or p.title for p in parsed), path


def test_dashboard_and_wall_clocks_are_not_watches():
    def L(title, cat):
        return olx.parse_offer(offer(1, title, 500, cat=cat))
    cats = bot.WATCH_CATEGORIES
    assert not bot.is_watch(L("Ceas bord Audi A6 C7 2016", 3561), cats)
    assert not bot.is_watch(L("Ceas vechi cu pendul de perete", 235), cats)
    assert not bot.is_watch(L("Apple watch SE 2", 1943), cats)
    assert bot.is_watch(L("Tissot T-Race Chronograph", 460), cats)
    assert not bot.is_watch(L("Set lampi numar LED Astra G, Omega A/B Vectra B", 999), cats)
    assert bot.is_watch(L("Ceas elegant Atlantic", 1677), cats)
