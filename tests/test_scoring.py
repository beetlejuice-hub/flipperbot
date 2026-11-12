import json
import subprocess

import pytest

from flipperbot import bot, quick
from flipperbot.config import Settings
from flipperbot.db import DB
from flipperbot.scoring import claude_score, rule_score
from flipperbot.sources import olx

from test_olx_and_bot import offer


def test_rule_scores():
    assert rule_score("suspect", [], "likely fake", None, None, 5)[0] == 0
    assert rule_score("bad", ["replica"], "says replica", None, None, 5)[0] == 0
    assert rule_score("mid", [], "listed 400 days ago: a real deal wouldn't last that long", None, None, 400)[0] == 0
    assert rule_score("bad", [], "seiko 5: 900 lei, -20% under what similar ones ask", None, None, 3)[0] == 0  # overpriced
    assert rule_score("bad", [], "no brand named", None, None, 3)[0] == 1
    assert rule_score("mid", ["lot"], "lot", None, None, 10)[0] == 4
    assert rule_score("real_good", [], "x", 900, {"label": "fast"}, 1)[0] == 7  # capped: 8+ needs an AI
    assert rule_score("good", [], "x", 200, {"label": "very slow"}, 20)[0] == 4
    # "no price" means the listing has no price; "no price history yet" is a different, often interesting, thing
    assert rule_score("bad", [], "no price", None, None, 3)[0] == 0
    assert rule_score("mid", [], "zodiac sea wolf at 400 lei, no price history yet", None, None, 3)[0] >= 3
    assert rule_score("bad", [], "seiko|7s26 at 900 lei, no price history yet", None, None, 3)[0] == 1


def test_old_listings_without_a_score_get_one_when_the_bot_starts():
    from flipperbot import web
    from flipperbot.scoring import RULES_VERSION

    s = Settings()
    db = setup(s)
    db.conn.execute("UPDATE listings SET score=NULL, rule_score=NULL, score_why=NULL")  # a database from before the score
    db.kv_set("rules_version", 0)
    assert "removed" not in web.stats(db, s)["bands"]  # no score yet is not "removed"
    assert bot.rescore_if_rules_changed(db, s, log=lambda m: None)
    assert db.conn.execute("SELECT COUNT(*) FROM listings WHERE score IS NULL").fetchone()[0] == 0
    assert db.get("olx:200")["score"] == 7
    assert db.kv_get("rules_version") == RULES_VERSION
    assert not bot.rescore_if_rules_changed(db, s, log=lambda m: None)  # only once per rules change


def test_claude_scores():
    assert claude_score({"authenticity": "likely_fake", "verdict": "buy", "confidence": 90}) == (0, "Claude: likely fake")
    assert claude_score({"verdict": "buy", "confidence": 80, "authenticity": "likely_genuine"})[0] == 10
    assert claude_score({"verdict": "negotiate", "confidence": 60})[0] == 8
    assert claude_score({"verdict": "buy", "confidence": 90, "authenticity": "unsure"})[0] == 7
    assert claude_score({"verdict": "skip"})[0] == 2
    assert claude_score({"error": "x"}) is None


def setup(s):
    db = DB(":memory:")
    market = [olx.parse_offer(offer(100 + i, "Ceas Seiko SKX007", p)) for i, p in enumerate([1000, 1100, 950, 1050, 1000])]
    bot.process(db, [*market, olx.parse_offer(offer(150, "Ceas Seiko SKX007", 650)),
                     olx.parse_offer(offer(200, "Ceas Seiko SKX007 diver", 420))], s)
    return db


@pytest.mark.real_quick
def test_quick_batch_scores_and_8_plus_gets_the_full_check(monkeypatch):
    s = Settings()
    db = setup(s)
    assert db.get("olx:200")["score"] == 7 and db.get("olx:150")["score"] >= 4
    cands = quick.candidates(db, s)
    assert {r["key"] for r in cands} == {"olx:150", "olx:200"}
    ids = {r["key"]: i + 1 for i, r in enumerate(cands)}
    answer = [{"id": ids["olx:200"], "score": 9, "value_low": 900, "value_high": 1000, "fake_risk": "low", "note": "cheap SKX"},
              {"id": ids["olx:150"], "score": 4, "value_low": 700, "value_high": 800, "fake_risk": "low", "note": "ok"}]
    seen = []

    def fake_run(args, **kw):
        seen.append(args)
        return subprocess.CompletedProcess(args, 0, json.dumps({"result": json.dumps(answer)}), "")

    monkeypatch.setattr(quick.subprocess, "run", fake_run)
    monkeypatch.setattr(quick.ai, "available", lambda s_: True)
    monkeypatch.setattr(quick.ai, "log_call", lambda *a: None)
    full, sent = [], []

    def fake_check(db_, row, s_):
        full.append(row["key"])
        r = {"verdict": "buy", "authenticity": "likely_genuine", "confidence": 80, "resale_ron_low": 850, "resale_ron_high": 1000}
        db_.set_ai(row["key"], r)
        return r

    monkeypatch.setattr(bot.ai, "available", lambda s_: True)
    monkeypatch.setattr(bot.ai, "check", fake_check)
    monkeypatch.setattr(bot.notify, "send", lambda s_, text, photo=None: sent.append(text))
    bot.deliver(db, s, log=lambda m: None)
    args = seen[0]
    assert args[args.index("--model") + 1] == "haiku" and args[args.index("--tools") + 1] == ""  # cheap, no tools
    assert db.get("olx:150")["score"] == 4 and "quick AI" in db.get("olx:150")["score_why"]
    assert full == ["olx:200"]  # only the 9 got the expensive check
    assert db.get("olx:200")["score"] == 10 and len(sent) == 1 and "10/10" in sent[0]
    assert quick.used_today(db) == 1


@pytest.mark.real_quick
def test_quick_step_respects_its_daily_cap(monkeypatch):
    s = Settings()
    s.quick_daily_calls = 0
    db = setup(s)
    monkeypatch.setattr(quick.ai, "available", lambda s_: True)
    monkeypatch.setattr(quick.subprocess, "run", lambda *a, **k: pytest.fail("called Claude past the cap"))
    assert quick.run(db, s, log=lambda m: None) == 0
