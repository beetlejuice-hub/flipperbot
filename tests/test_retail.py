import json
import subprocess

from flipperbot import bot, retail
from flipperbot.config import Settings
from flipperbot.db import DB
from flipperbot.identify import identify
from flipperbot.sources import olx

from test_olx_and_bot import offer

S = Settings()


def lst(i, title, price, cat=1943):
    l = olx.parse_offer({**offer(i, title, price), "category": {"id": cat}})
    l.niche = "watches"
    return l


def test_a_huawei_band_10_is_priced_as_a_band_10_and_against_its_new_price():
    db = DB(":memory:")
    # Huawei watches cost far more than the band: they must not set its price
    watches = [lst(100 + i, "Huawei Watch GT 5 Pro 46mm", p) for i, p in enumerate([900, 950, 1000, 980, 920])]
    bot.process(db, watches, S, alert=False)
    retail.store(db, "huawei|band 10", 150, 170, source="eMAG")
    bot.process(db, [lst(1, "Huawei Band 10 negru", 120)], S, alert=False)
    r = db.get("olx:1")
    assert r["model_key"] == "huawei|band 10"
    assert r["tier"] == "bad" and "almost the price of a new one" in r["reason"] and r["score"] == 0


def test_the_new_price_caps_estimates_and_gives_one_when_nothing_compares():
    db = DB(":memory:")
    retail.store(db, "apple|watch series 9", 1600, 1900, source="Altex")
    # five asking far above what a used one fetches (new is 1600): the estimate is held to ~85% of new
    asks = [lst(100 + i, "Apple Watch Series 9 45mm", p) for i, p in enumerate([2400, 2500, 2450, 2600, 2550])]
    bot.process(db, asks + [lst(1, "Apple Watch Series 9 45mm GPS", 700)], S, alert=False)
    r = db.get("olx:1")
    assert r["est_high_ron"] <= 1360 and r["est_value_ron"] <= 1200 and "capped by the new price" in r["reason"]
    # no similar listings at all: the new price alone gives a used estimate
    retail.store(db, "garmin|forerunner 265", 1800, 2000, source="eMAG")
    bot.process(db, [lst(2, "Garmin Forerunner 265", 900)], S, alert=False)
    g = db.get("olx:2")
    assert (g["est_value_ron"], g["est_high_ron"]) == (1350, 1530) and "new in shops" in g["reason"]


def test_discontinued_models_have_no_ceiling():
    db = DB(":memory:")
    retail.store(db, "garmin|fenix 6 pro", 0, discontinued=True, source="web search")
    assert retail.ceiling(retail.get(db, "garmin|fenix 6 pro")) is None


def test_daily_look_up_with_claude(monkeypatch):
    monkeypatch.setattr(retail.ai, "available", lambda s: True)
    monkeypatch.setattr(retail.ai, "log_call", lambda *a: None)
    db = DB(":memory:")
    bot.process(db, [lst(100 + i, "Huawei Band 10", 120 + i) for i in range(4)], S, alert=False)
    assert retail.candidates(db) == [("huawei|band 10", "watches")]
    seen = []

    def run(args, input, **kw):
        seen.append((args, input))
        answer = [{"id": 1, "new_low": 150, "new_high": 179, "not_sold_new": False, "source": "eMAG"}]
        return subprocess.CompletedProcess(args, 0, json.dumps({"result": json.dumps(answer)}), "")

    assert retail.look_up(db, S, run=run, log=lambda m: None) == 1
    args, prompt = seen[0]
    assert "WebSearch" in args and "Read" in args[args.index("--disallowedTools"):] and "huawei band 10" in prompt
    assert retail.get(db, "huawei|band 10")["low"] == 150
    assert not retail.due(db, S)  # once a day


def test_a_claude_check_stores_the_new_price():
    db = DB(":memory:")
    bot.process(db, [lst(1, "Huawei Watch Fit 3", 300)], S, alert=False)
    row = db.get("olx:1")
    assert retail.from_check(db, row, {"verdict": "buy", "new_price_ron": 499, "new_price_ron_high": 599})
    assert retail.get(db, "huawei|watch fit 3")["low"] == 499
    assert not retail.from_check(db, row, {"error": "x", "new_price_ron": 1})
