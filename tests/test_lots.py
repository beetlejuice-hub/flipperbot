import json
import subprocess

from flipperbot import bot, lots
from flipperbot.config import Settings
from flipperbot.db import DB
from flipperbot.sources import olx

from test_olx_and_bot import offer

S = Settings()


def lot(i, title, price, desc="", photos=6):
    o = offer(i, title, price)
    o["description"] = desc
    o["photos"] = [{"link": f"https://x/{i}-{n}.jpg;s={{width}}x{{height}}"} for n in range(photos)]
    l = olx.parse_offer(o)
    l.niche = "lots"
    return l


def test_free_lot_score():
    good, why, info = lots.prefilter("Lot obiecte vechi din pod", "De la bunicul: ceasuri vechi, aparat foto Zenit, monede, "
                                     "nu stiu ce valoare au. 40 buc", 300, 8)
    assert good >= 6 and "seller may not know" in why and {"watches", "cameras", "collect"} <= set(info["groups"])
    assert lots.prefilter("Lot haine copii 2-3 ani", "tricouri, pantaloni", 50, 3)[0] == 0  # a lot of junk
    assert lots.prefilter("Ceas Seiko 5", "functional", 300, 3)[0] == 0  # not a lot
    plain, _, _ = lots.prefilter("Lot diverse", "", 200, 2)
    assert 1 <= plain < 4  # a lot, but nothing says it's worth a look


def test_lots_are_kept_judged_and_wait_for_a_look():
    db = DB(":memory:")
    bot.process(db, [lot(1, "Lot obiecte vechi mostenire", 250, "ceasuri, argint, aparat foto, de la bunici"),
                     lot(2, "Lot haine dama", 40, "bluze, rochii")], S, alert=False)
    r = db.get("olx:1")
    assert r["niche"] == "lots" and r["tier"] == "mid" and r["rule_score"] >= 5
    assert r["score"] == 4 and "waiting for a look" in r["score_why"]  # no estimate yet: not a 5+
    assert db.get("olx:2") is None  # junk lots aren't kept


def test_the_photo_look_and_the_full_check_after_it(monkeypatch, tmp_path):
    monkeypatch.setattr(Settings, "photos_dir", property(lambda self: tmp_path))
    monkeypatch.setattr(lots.ai, "available", lambda s: True)
    monkeypatch.setattr(lots.ai, "log_call", lambda *a: None)
    monkeypatch.setattr(lots.ai, "download_photos", lambda urls, folder, max_photos=8: [folder / f"{i}.jpg" for i in range(1, 4)])
    db = DB(":memory:")
    bot.process(db, [lot(1, "Lot obiecte vechi din pod", 300, "ceasuri vechi, argint, de la bunicul, nu stiu ce valoare au")], S)
    answer = {"score": 9, "value_low": 1500, "value_high": 2200, "note": "an Omega and silver",
              "items": [{"what": "Omega Seamaster, gold-plated", "photo": "2.jpg", "value_ron": 1200}], "unclear": "the watch in 3.jpg"}
    seen = []

    def run(args, input, **kw):
        seen.append((args, input))
        return subprocess.CompletedProcess(args, 0, json.dumps({"result": json.dumps(answer)}), "")

    assert lots.look(db, S, log=lambda m: None, run=run) == 1
    args, prompt = seen[0]
    assert "--model" in args and args[args.index("--model") + 1] == S.quick_model
    assert "Read" in args and "WebSearch" in args[args.index("--disallowedTools"):]  # photos only, no web
    assert "Lot obiecte vechi din pod" in prompt and "1.jpg" in prompt
    r = db.get("olx:1")
    assert r["score"] == 7 and "waiting for Claude" in r["score_why"]  # the look alone never shows 8+
    assert [x["key"] for x in bot.pending_alerts(db, S)] == ["olx:1"]  # but it sends the lot to the full check
    assert lots.look(db, S, log=lambda m: None, run=run) == 0  # looked at once


def test_the_daily_cap(monkeypatch):
    monkeypatch.setattr(lots.ai, "available", lambda s: True)
    db = DB(":memory:")
    s = Settings()
    db.kv_set(f"lots_looked:{__import__('datetime').date.today().isoformat()}", s.lots_look_daily)
    assert lots.look(db, s, log=lambda m: None, run=lambda *a, **k: 1 / 0) == 0
