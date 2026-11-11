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


def setup_deal(s):
    db = DB(":memory:")
    market = [offer(100 + i, "Ceas Seiko SKX007 automatic", p) for i, p in enumerate([1000, 1100, 950, 1050, 1000])]
    good = offer(150, "Ceas Seiko SKX007 diver", 650)
    deal = offer(200, "Ceas Seiko SKX007 diver", 420)
    junk = offer(201, "Ceas Michael Kors dama", 150)
    car = offer(202, "Opel Omega 2.0 piese", 500, cat=999)
    listings = [olx.parse_offer(o) for o in [*market, good, deal, junk, car]]
    bot.learn_categories(db, listings)
    for_ai = bot.process(db, listings, s)
    return db, for_ai, deal


def test_without_claude_nothing_is_sent_and_the_deal_waits(capsys):
    s = Settings()
    s.claude_bin = "no-such-claude"
    db, for_ai, deal = setup_deal(s)

    assert db.get("olx:202") is None  # not a watch
    assert db.get("olx:201")["tier"] == "bad"
    # The deal came after the market listings in the same batch, so it is priced against them.
    assert db.get("olx:200")["tier"] == "real_good", db.get("olx:200")["reason"]
    assert db.get("olx:150")["tier"] == "good"
    assert {r["key"] for r in for_ai} == {"olx:150", "olx:200"}

    bot.deliver(db, s)
    out = capsys.readouterr().out
    assert "REAL GOOD" not in out  # no message without Claude's confirmation
    assert "waiting for Claude (Claude Code isn't installed" in out
    assert db.get("olx:200")["notified_tier"] is None  # still pending: checked when Claude can


def deliver_with(monkeypatch, verdict):
    s = Settings()
    db, _, _ = setup_deal(s)
    order = []

    def fake_check(db_, row, s_):
        order.append(("claude", row["key"]))
        result = {"watches": [{"brand": "Seiko", "model": "SKX007"}], "resale_ron_low": 800, "resale_ron_high": 1000,
                  "summary": "notes", **verdict}
        db_.set_ai(row["key"], result)
        return result

    monkeypatch.setattr(bot.ai, "available", lambda s_: True)
    monkeypatch.setattr(bot.ai, "check", fake_check)
    monkeypatch.setattr(bot.notify, "send", lambda s_, text, photo=None: order.append(("telegram", text)))
    bot.deliver(db, s, extra_ai=1, log=lambda m: None)
    return db, order


def test_confirmed_deal_is_sent_once_with_claudes_notes(monkeypatch):
    db, order = deliver_with(monkeypatch, {"verdict": "buy", "authenticity": "likely_genuine", "confidence": 70})
    assert order[0] == ("claude", "olx:200")  # Claude first
    kind, text = order[1]
    assert kind == "telegram" and "Claude: BUY" in text and "70% sure" in text and "looks genuine" in text
    assert order[2] == ("claude", "olx:150")  # then a good one, for the dashboard only
    assert len([o for o in order if o[0] == "telegram"]) == 1
    assert db.get("olx:200")["notified_tier"] == "real_good"


def test_unconfirmed_deals_stay_on_the_dashboard(monkeypatch):
    for verdict in (
        {"verdict": "buy", "authenticity": "likely_fake", "confidence": 90},  # fake
        {"verdict": "skip", "authenticity": "likely_genuine", "confidence": 80},  # not worth it
        {"verdict": "negotiate", "authenticity": "unsure", "confidence": 40},  # under half sure
        {"error": "timeout"},
    ):
        db, order = deliver_with(monkeypatch, verdict)
        assert not [o for o in order if o[0] == "telegram"], verdict
        assert db.get("olx:200")["notified_tier"] == "real_good"  # decided: not asked about again
        assert db.get("olx:200")["ai"]  # Claude's notes are on the dashboard


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


def test_replica_dealer_pattern():
    s = Settings()
    db = DB(":memory:")
    market = [olx.parse_offer(offer(100 + i, "TAG Heuer Carrera Calibre 5", p)) for i, p in enumerate([11000, 12000, 11500, 12500, 11800])]
    for l in market:
        l.seller_id = f"honest{l.source_id}"
    bot.process(db, market, s, alert=False)
    dealer = [olx.parse_offer(offer(300 + i, f"TAG Heuer Carrera Calibre 5 v{i}", 3050)) for i in range(3)]
    for l in dealer:
        l.seller_id = "dealer"
    bot.process(db, dealer, s, alert=False)
    assert db.get("olx:300")["tier"] == "real_good"  # one cheap one: could be a real deal
    assert db.get("olx:302")["tier"] == "suspect"  # the third from the same seller: a pattern
    assert "replicas" in db.get("olx:302")["reason"]
