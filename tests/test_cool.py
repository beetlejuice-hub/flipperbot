import json
import subprocess

from flipperbot import bot, cool, web
from flipperbot.config import Settings
from flipperbot.db import DB
from flipperbot.models import Listing

S = Settings()


def listing(i, title, price, desc="", photos=3):
    l = Listing("olx", str(i), f"https://www.olx.ro/{i}", title, description=desc, price_ron=price,
                photos=[f"https://x/{i}/{n}.jpg" for n in range(photos)])
    l.niche = "cool"
    return l


def test_the_free_score():
    hi, why, _ = cool.prefilter("Lampa vintage anii 70 space age, crom", "", 80, 3)
    assert hi >= 5 and "cool find" in why
    assert cool.prefilter("Vaza Murano sommerso", "sticla murano, anii 60", 250, 3)[0] >= 4
    assert cool.prefilter("Dulap vechi din lemn masiv", "", 200, 3)[0] == 0  # furniture to haul, not a find
    assert cool.prefilter("Lampa vintage alama", "", 2500, 3)[0] == 0  # over the cool-finds limit
    assert cool.prefilter("Lampa noua de birou", "", 60, 3)[0] <= 1  # nothing unusual
    assert cool.prefilter("Pisoi de vanzare", "foarte jucaus, vintage", 50, 3)[0] == 0


def test_cool_finds_have_their_own_tab_and_stay_out_of_the_flips():
    db = DB(":memory:")
    bot.process(db, [listing(1, "Lampa vintage anii 70 space age, crom", 80), listing(2, "Lampa noua de birou", 60)], S)
    assert db.get("olx:2") is None  # not kept: nothing cool about it
    r = db.get("olx:1")
    assert r["niche"] == "cool" and r["score"] >= 4 and r["model_key"] is None
    assert [x["key"] for x in web.query(db, "cool")] == ["olx:1"]
    assert web.query(db, "interesting") == [] and web.query(db, "mid") == []
    assert bot.pending_alerts(db, S) == []  # never a Telegram deal alert


def test_the_photo_look_scores_it(monkeypatch, tmp_path):
    monkeypatch.setattr(Settings, "photos_dir", property(lambda self: tmp_path))
    monkeypatch.setattr(cool.ai, "available", lambda s: True)
    monkeypatch.setattr(cool.ai, "log_call", lambda *a: None)
    monkeypatch.setattr(cool.ai, "download_photos", lambda urls, folder, max_photos=8: [folder / "1.jpg", folder / "2.jpg"])
    db = DB(":memory:")
    bot.process(db, [listing(1, "Lampa vintage anii 70 space age, crom", 80)], S)
    answer = {"score": 9, "what": "1970s Italian mushroom lamp", "era_style": "space age, 1970s", "condition": "good",
              "usual_price_ron": 600, "note": "a classic shape, very cheap"}
    seen = []

    def run(args, input, **kw):
        seen.append((args, input))
        return subprocess.CompletedProcess(args, 0, json.dumps({"result": json.dumps(answer)}), "")

    assert cool.look(db, S, log=lambda m: None, run=run) == 1
    args, prompt = seen[0]
    assert args[args.index("--model") + 1] == S.quick_model and "Lampa vintage" in prompt
    assert "WebSearch" in args[args.index("--disallowedTools"):]  # photos only
    r = db.get("olx:1")
    assert r["score"] == 9 and r["score_why"].startswith("cool: 1970s Italian mushroom lamp")
    assert cool.look(db, S, log=lambda m: None, run=run) == 0  # looked at once
    card = web.listing_json(r, db)
    assert card["quick"]["usual_price_ron"] == 600


def test_searched_every_poll():
    assert "cool" in S.niches and "cool" in S.every_poll
    searches = bot.pick_searches(DB(":memory:"), S)
    assert sum(1 for q, c, n in searches if n == "cool" and q) == S.searches_per_poll
