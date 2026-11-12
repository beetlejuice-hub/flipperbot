import json
import subprocess
import time
from datetime import datetime

import pytest

from flipperbot import ai, bot
from flipperbot.config import Settings
from flipperbot.db import DB
from flipperbot.sources import olx

from test_olx_and_bot import offer


def test_limit_reset_formats():
    now = datetime(2026, 11, 12, 13, 0).timestamp()
    assert ai.limit_reset("Claude AI usage limit reached|1731430800", now) == 1731430800
    at = datetime.fromtimestamp(ai.limit_reset("5-hour limit reached ∙ resets 3pm", now))
    assert (at.hour, at.minute) == (15, 1)
    at = datetime.fromtimestamp(ai.limit_reset("You've hit your limit · resets at 9:30", now))
    assert (at.day, at.hour, at.minute) == (13, 9, 31)  # 9:30 already passed today: tomorrow
    assert ai.limit_reset("Usage limit reached", now) == now + 3600
    assert ai.limit_reset('{"verdict": "buy"}', now) is None


def test_check_raises_and_saves_nothing_on_the_limit(tmp_path, monkeypatch):
    s = Settings()
    monkeypatch.setattr(Settings, "photos_dir", property(lambda self: tmp_path))
    db = DB(":memory:")
    bot.process(db, [olx.parse_offer(offer(1, "Ceas Seiko SKX007", 400))], s, alert=False)
    monkeypatch.setattr(ai, "available", lambda s: True)
    out = json.dumps({"type": "result", "is_error": True, "result": "Claude AI usage limit reached|1999999999"})
    monkeypatch.setattr(ai.subprocess, "run", lambda *a, **k: subprocess.CompletedProcess(a, 1, out, ""))
    with pytest.raises(ai.UsageLimit) as e:
        ai.check(db, db.get("olx:1"), s)
    assert e.value.until == 1999999999
    assert db.get("olx:1")["ai"] is None and ai.used_today(db) == 0  # not a check, not counted


def test_model_and_fewer_photos():
    args = ai.CLAUDE_ARGS("claude", "sonnet")
    assert args[args.index("--model") + 1] == "sonnet"
    assert Settings().ai_max_photos <= 5
    assert "at most 4 searches" in ai.PROMPT


def test_old_limit_errors_dont_count_as_checked():
    assert ai.is_limit_error({"error": "Claude AI usage limit reached|1731430800"})
    assert not ai.is_limit_error({"error": "timeout"})


def test_lean_call_and_fallback_for_older_claude(tmp_path, monkeypatch):
    s = Settings()
    monkeypatch.setattr(Settings, "photos_dir", property(lambda self: tmp_path))
    monkeypatch.setattr(ai, "log_call", lambda *a: None)
    db = DB(":memory:")
    bot.process(db, [olx.parse_offer(offer(1, "Ceas Seiko SKX007", 400))], s, alert=False)
    monkeypatch.setattr(ai, "available", lambda s: True)
    calls = []

    def run(args, **kw):
        calls.append(args)
        if "--tools" in args:
            return subprocess.CompletedProcess(args, 1, "", "error: unknown option '--tools'")
        return subprocess.CompletedProcess(args, 0, json.dumps({"result": '{"verdict": "skip", "watches": []}'}), "")

    monkeypatch.setattr(ai.subprocess, "run", run)
    assert ai.check(db, db.get("olx:1"), s)["verdict"] == "skip"
    assert "--tools" in calls[0] and "--system-prompt" in calls[0] and "--tools" not in calls[1]
    assert db.kv_get("claude_no_lean_flags") is True  # remembered: plain calls from now on
    lean = ai.CLAUDE_ARGS("claude", "sonnet")
    assert lean[lean.index("--tools") + 1] == "Read,WebSearch" and "Bash" in lean[lean.index("--disallowedTools") + 1:]
