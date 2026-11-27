from datetime import date, datetime

from flipperbot import budget, web
from flipperbot.config import Settings
from flipperbot.db import DB

S = Settings()
DAY = datetime(2026, 11, 27, 14, 0)
NIGHT = datetime(2026, 11, 27, 3, 0)


def test_economy_is_the_default_and_lowers_the_limits():
    db = DB(":memory:")
    assert budget.mode(db) == "economy"
    e = budget.effective(db, S, now=DAY)
    assert e.ai_daily_limit == 10 and e.quick_daily_calls == 15 and e.lots_look_daily == 8 and e.cool_look_daily == 8
    assert e.fake_hunt_model == "haiku" and e.ai_auto_real_good  # still checks the real good deals, on less
    # never above your own config
    mine = Settings()
    mine.ai_daily_limit = 5
    assert budget.effective(db, mine, now=DAY).ai_daily_limit == 5


def test_economy_sleeps_at_night_and_off_is_off():
    db = DB(":memory:")
    n = budget.effective(db, S, now=NIGHT)
    assert not n.ai_auto_real_good and not n.ai_quick and not n.lots_look and not n.cool_look and n.retail_lookups == 0
    budget.set_mode(db, "off")
    o = budget.effective(db, S, now=DAY)
    assert not o.ai_auto_real_good and not o.ai_quick and o.radar_ai_refresh_days == 0
    budget.set_mode(db, "normal")
    assert budget.effective(db, S, now=NIGHT) == S


def test_todays_use_from_the_log(tmp_path):
    log = tmp_path / "claude.log"
    log.write_text(
        "2026-11-27T08:01:02 quick:20 exit=0 models=haiku cost_usd=0.012 error=False\n"
        "2026-11-27T08:05:02 olx:123 exit=0 models=haiku cost_usd=0.06 error=False\n"
        "2026-11-27T08:06:02 olx:123:fake-hunt exit=0 models=sonnet cost_usd=0.21 error=False\n"
        "    what Claude said when it failed\n"
        "2026-11-27T08:07:02 olx:9:cool-look exit=0 models=haiku cost_usd=0.008 error=False\n"
        "2026-11-26T23:59:02 olx:7:lot-look exit=0 models=haiku cost_usd=9 error=False\n")
    u = budget.today(log, day=date(2026, 11, 27))
    assert u["calls"] == 4 and u["cost_usd"] == 0.29
    assert u["kinds"]["fake check"]["calls"] == 1 and u["kinds"]["full check"]["cost_usd"] == 0.06
    assert budget.today(tmp_path / "missing.log")["calls"] == 0


def test_the_dashboard_shows_the_mode():
    db = DB(":memory:")
    budget.set_mode(db, "off")
    st = web.stats(db, S)
    assert st["claude_mode"] == "off" and "calls" in st["claude_today"]
