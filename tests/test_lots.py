from flipperbot import ai, bot
from flipperbot.config import Settings
from flipperbot.db import DB
from flipperbot.identify import identify
from flipperbot.models import Listing
from flipperbot.sources import olx
from flipperbot.tiers import judge

from test_olx_and_bot import offer

LOT_RESULT = {
    "watches": [
        {"brand": "Omega", "model": "Seamaster", "reference": "2846", "photo": "3_q2.jpg", "value_ron": 2500, "notable": True},
        {"brand": "Poljot", "model": "", "photo": "1.jpg", "value_ron": 150, "notable": False},
        {"brand": "", "model": "", "photo": "2.jpg", "value_ron": 0, "notable": False},
    ],
    "authenticity": "likely_genuine", "verdict": "buy", "confidence": 65,
    "resale_ron_low": 2600, "resale_ron_high": 3200, "repair_cost_ron": 300, "summary": "The Omega makes it.",
}


def test_unnamed_expensive_lot_is_still_worth_a_look():
    l = Listing("olx", "1", "u", "Lot 30 ceasuri vechi", price_ron=1500)
    v = judge(l, identify(l.title), [], Settings())
    assert v.tier == "mid" and "Claude" in v.reason


def test_big_photos_for_lots():
    assert ai.big("https://cdn/v1/files/x/image;s=1000x1000") == "https://cdn/v1/files/x/image;s=2000x2000"
    assert ai.tiles.__doc__ and ai.LOT_BLOCK.count("value_ron") >= 1


def make_db(s):
    db = DB(":memory:")
    lot = olx.parse_offer(offer(500, "Lot ceasuri vechi diverse", 600))
    good_market = [olx.parse_offer(offer(100 + i, "Ceas Seiko SKX007", p)) for i, p in enumerate([1000, 1100, 950, 1050, 1000])]
    good = olx.parse_offer(offer(150, "Ceas Seiko SKX007", 650))
    bot.process(db, [*good_market, good, lot], s)
    return db


def test_lots_go_first_and_claude_values_them_into_a_sent_deal(monkeypatch):
    s = Settings()
    s.ai_auto = True  # these test the automatic mode
    db = make_db(s)
    assert db.get("olx:500")["tier"] == "mid"
    assert [r["key"] for r in bot.pending_ai(db, s)][:2] == ["olx:500", "olx:150"]  # the lot first

    sent = []

    def fake_check(db_, row, s_):
        result = LOT_RESULT if row["key"] == "olx:500" else {"error": "x"}
        db_.set_ai(row["key"], result)
        return result

    monkeypatch.setattr(bot.ai, "available", lambda s_: True)
    monkeypatch.setattr(bot.ai, "check", fake_check)
    monkeypatch.setattr(bot.notify, "send", lambda s_, text, photo=None: sent.append(text))
    bot.deliver(db, s, extra_ai=1, log=lambda m: None)

    row = db.get("olx:500")
    assert row["tier"] == "real_good"  # worth ~2900, 600 asked, profit 2600-600-300 = 1700
    assert row["profit_ron"] == 1700 and "1 notable watches inside" in row["reason"]
    assert len(sent) == 1
    assert "LOT" in sent[0] and "Omega Seamaster 2846 ~2500 lei ⭐" in sent[0] and "65% sure" in sent[0]


def test_claude_value_never_downgrades_or_sends_unconfirmed(monkeypatch):
    s = Settings()
    s.ai_auto = True  # these test the automatic mode
    db = make_db(s)
    sent = []
    result = {**LOT_RESULT, "confidence": 30}

    def fake_check(db_, row, s_):
        db_.set_ai(row["key"], result)
        return result

    monkeypatch.setattr(bot.ai, "available", lambda s_: True)
    monkeypatch.setattr(bot.ai, "check", fake_check)
    monkeypatch.setattr(bot.notify, "send", lambda s_, text, photo=None: sent.append(text))
    bot.deliver(db, s, extra_ai=1, log=lambda m: None)
    assert db.get("olx:500")["tier"] == "real_good"  # on the dashboard as real good...
    assert sent == []  # ...but Claude was only 30% sure: no message
    assert bot.claude_value(db, db.get("olx:500"), {**LOT_RESULT, "resale_ron_low": 100, "resale_ron_high": 200}, s) is None
