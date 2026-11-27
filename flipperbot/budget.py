"""How much of your Claude plan the bot may use by itself: Off, Economy (the default) or Normal.

The bot runs 24/7 and every automatic Claude call (quick reads, photo looks, full checks, the second fake check,
new-price look-ups, the trend radar) comes out of your subscription's usage. The mode is switched on the dashboard:
- off:     no automatic Claude calls at all; "Send to Claude" on a card still works,
- economy: about a third of Normal, the fake check on the small model, and nothing between midnight and 7:00
           (deals found at night wait for the morning),
- normal:  the limits in config.toml.
A mode only ever lowers your config's limits, never raises them. And today's usage is read from claude.log.
"""

from __future__ import annotations

import re
from dataclasses import replace
from datetime import date, datetime
from typing import Any

from .config import HOME, Settings
from .db import DB

MODES = ("off", "economy", "normal")
DEFAULT = "economy"
NIGHT = (0, 7)  # economy: no automatic Claude calls from midnight to 7:00
ECONOMY = {"ai_daily_limit": 10, "quick_daily_calls": 15, "lots_look_daily": 8, "cool_look_daily": 8, "retail_lookups": 8}


def mode(db: DB) -> str:
    m = db.kv_get("claude_mode", DEFAULT)
    return m if m in MODES else DEFAULT


def set_mode(db: DB, m: str) -> str:
    if m not in MODES:
        raise ValueError(m)
    db.kv_set("claude_mode", m)
    return m


def _off(s: Settings) -> Settings:
    return replace(s, ai_auto=False, ai_auto_real_good=False, ai_quick=False, lots_look=False, cool_look=False,
                   retail_lookups=0, radar_ai_refresh_days=0)


def night(now: datetime | None = None) -> bool:
    h = (now or datetime.now()).hour
    return NIGHT[0] <= h < NIGHT[1]


def effective(db: DB, s: Settings, now: datetime | None = None) -> Settings:
    """The settings the bot runs this round with: the mode's limits on top of yours (never above them)."""
    m = mode(db)
    if m == "off":
        return _off(s)
    if m == "economy":
        if night(now):
            return _off(s)
        caps = {k: min(getattr(s, k), v) for k, v in ECONOMY.items()}
        return replace(s, fake_hunt_model="haiku", radar_ai_refresh_days=max(s.radar_ai_refresh_days, 30), **caps)
    return s


KINDS = [("quick read", re.compile(r"^quick:")), ("fake check", re.compile(r":fake-hunt$")),
         ("cool-finds look", re.compile(r":cool-look$")), ("lots look", re.compile(r":lot-look$")),
         ("new prices", re.compile(r"^retail-lookup$")), ("trend radar", re.compile(r"^radar-refresh$"))]


def today(path: Any = None, day: date | None = None) -> dict[str, Any]:
    """Claude calls the bot made today, per kind, with what they'd cost at API prices (a guide to what uses the most:
    your plan counts usage its own way). From the end of claude.log."""
    path = path or HOME / "claude.log"
    stamp = (day or date.today()).isoformat()
    kinds: dict[str, dict[str, float]] = {}
    try:
        with open(path, "rb") as f:
            f.seek(0, 2)
            size = f.tell()
            f.seek(max(0, size - 2_000_000))  # today's lines are at the end
            text = f.read().decode("utf-8", "replace")
    except OSError:
        return {"calls": 0, "cost_usd": 0.0, "kinds": {}}
    for line in text.splitlines():
        if not line.startswith(stamp):
            continue
        parts = line.split()
        if len(parts) < 2:
            continue
        key = parts[1]
        kind = next((k for k, p in KINDS if p.search(key)), "full check")
        cost = next((float(x.split("=", 1)[1]) for x in parts if x.startswith("cost_usd=")
                     and re.fullmatch(r"cost_usd=[0-9.]+", x)), 0.0)
        k = kinds.setdefault(kind, {"calls": 0, "cost_usd": 0.0})
        k["calls"] += 1
        k["cost_usd"] = round(k["cost_usd"] + cost, 3)
    return {"calls": int(sum(k["calls"] for k in kinds.values())),
            "cost_usd": round(sum(k["cost_usd"] for k in kinds.values()), 2), "kinds": kinds}
