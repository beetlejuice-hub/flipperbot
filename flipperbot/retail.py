"""What each model costs NEW in Romanian shops: the ceiling for any second-hand price.

A used Huawei Band 10 at 120 lei is no deal when a new one is 150 in shops. Shops refuse plain requests (eMAG,
Altex, Flanco, compari.ro...), so new prices come from Claude with web search:
- every full check also reports the new price (`new_price_ron`), stored for the model;
- once a day, one cheap call (Haiku + web search) looks up the most-listed models that have no recent new price.
Each is stored per model with when and where it was found; a model no longer sold new is noted as such.

The rules then use it: asking 80%+ of the new price (90% for sealed) isn't a deal, and a used estimate can't
go above ~85% of new.
"""

from __future__ import annotations

import json
import re
import subprocess
import tempfile
import time
from typing import Any, Callable

from . import ai
from .config import Settings
from .db import DB, now

SCHEMA = """CREATE TABLE IF NOT EXISTS retail (model_key TEXT PRIMARY KEY, low INTEGER, high INTEGER, discontinued INTEGER,
            source TEXT, at TEXT)"""

USED_LOW, USED_HIGH = 0.75, 0.85  # a used one realistically fetches up to this much of the new price
NOT_A_DEAL, NOT_A_DEAL_SEALED = 0.80, 0.90


def setup(db: DB) -> None:
    db.conn.execute(SCHEMA)


def get(db: DB, model_key: str | None, days: int = 45) -> dict[str, Any] | None:
    """The model's new price in shops, if known and recent: {low, high, discontinued, source, at}."""
    if not model_key or "|" not in model_key:
        return None
    setup(db)
    r = db.conn.execute("SELECT * FROM retail WHERE model_key=? AND at >= datetime('now', ?)", (model_key, f"-{days} days")).fetchone()
    return dict(r) if r else None


def store(db: DB, model_key: str, low: Any, high: Any = None, discontinued: bool = False, source: str = "") -> bool:
    try:
        lo = int(float(low)) if low else 0
        hi = int(float(high)) if high else lo
    except (TypeError, ValueError):
        return False
    if not model_key or "|" not in model_key or (lo <= 0 and not discontinued) or lo > 500_000:
        return False
    setup(db)
    db.conn.execute("INSERT OR REPLACE INTO retail VALUES (?, ?, ?, ?, ?, ?)",
                    (model_key, lo or None, max(hi, lo) or None, int(bool(discontinued)), str(source)[:120], now()))
    db.conn.commit()
    return True


def from_check(db: DB, row: Any, result: dict[str, Any]) -> bool:
    """A full Claude check's new price for the listing's model (only for a named model, not a lot or a fake)."""
    if "error" in result or result.get("authenticity") == "likely_fake" or "lot" in (row["flags"] or ""):
        return False
    return store(db, row["model_key"], result.get("new_price_ron"), result.get("new_price_ron_high"),
                 bool(result.get("not_sold_new")), "Claude's check")


def ceiling(r: dict[str, Any] | None, sealed: bool = False) -> tuple[int, int] | None:
    """The most a second-hand one of the model can realistically fetch (low, high), from its new price."""
    if not r or r.get("discontinued") or not r.get("low"):
        return None
    if sealed:
        return round(r["low"] * 0.85), round(r["low"] * 0.95)
    return round(r["low"] * USED_LOW), round(r["low"] * USED_HIGH)


# --- the daily look-up -------------------------------------------------------------------------------

PROMPT = """You look up what products cost NEW in Romania today, for a reseller who needs the ceiling for used prices.
Today is {today}. Use web search (at most 6 searches; shops like eMAG, Altex, Flanco, Cel, PC Garage, or compari.ro).

For each model below give the lowest and a typical new price in lei at Romanian shops now. If it isn't sold new
anymore (discontinued, only second-hand), say so and leave the prices 0. Never guess: if you can't find it, use 0.

Models:
{models}

Answer with ONLY a JSON array, one object per model, in the same order:
[{{"id": 1, "new_low": 0, "new_high": 0, "not_sold_new": false, "source": "shop name"}}]"""


def _name(model_key: str, niche: str | None) -> str:
    brand, _, model = model_key.partition("|")
    words = " ".join(dict.fromkeys(f"{brand} {model}".replace("|", " ").split()))
    return words + {"watches": "", "electronics": "", "phones": " (phone)", "tools": " (power tool)",
                    "lego": " (LEGO set)", "sneakers": " (sneakers)", "cameras": ""}.get(niche or "", "")


def candidates(db: DB, limit: int = 15) -> list[tuple[str, str]]:
    """The most-listed current models (last 2 weeks) with no new price from the last 30 days."""
    setup(db)
    return [(r["model_key"], r["niche"]) for r in db.conn.execute(
        """SELECT l.model_key, MAX(l.niche) AS niche, COUNT(*) AS n FROM listings l
           LEFT JOIN retail r ON r.model_key = l.model_key AND r.at >= datetime('now', '-30 days')
           WHERE l.model_key LIKE '%|%' AND l.last_seen >= datetime('now', '-14 days') AND r.model_key IS NULL
           AND COALESCE(l.niche, 'watches') != 'lots' AND l.flags NOT LIKE '%"vintage"%'
           GROUP BY l.model_key HAVING n >= 3 ORDER BY n DESC LIMIT ?""", (limit,))]


def due(db: DB, s: Settings) -> bool:
    return bool(s.retail_lookups) and time.time() - db.kv_get("retail_looked_at", 0) >= 86400


def look_up(db: DB, s: Settings, run: Callable[..., Any] | None = None, log: Callable[[str], None] = print) -> int:
    """One call: new prices for the most-listed models that have none. Returns how many were stored."""
    run = run or subprocess.run
    if not ai.available(s):
        return 0
    models = candidates(db, s.retail_lookups)
    db.kv_set("retail_looked_at", time.time())  # once a day, even if this one fails
    if not models:
        return 0
    from datetime import date

    prompt = PROMPT.format(today=date.today().isoformat(),
                           models="\n".join(f"{i}. {_name(k, n)}" for i, (k, n) in enumerate(models, 1)))
    args = [s.claude_bin, "-p", "--output-format", "json", "--model", s.quick_model, "--tools", "WebSearch",
            "--system-prompt", "You look up current new prices in Romanian shops. Answer only with the JSON asked for.",
            "--strict-mcp-config", "--disable-slash-commands", "--allowedTools", "WebSearch",
            "--disallowedTools", "Bash", "Edit", "Write", "Read", "NotebookEdit", "WebFetch", "Task"]
    with tempfile.TemporaryDirectory() as d:
        try:
            proc = run(args, input=prompt, cwd=d, capture_output=True, text=True, timeout=600)
        except subprocess.TimeoutExpired:
            return 0
    ai.log_call("retail-lookup", proc)
    try:
        wrapper = json.loads(proc.stdout)
        text = wrapper.get("result", "") if isinstance(wrapper, dict) else proc.stdout
    except json.JSONDecodeError:
        text = proc.stdout
    m = re.search(r"\[.*\]", text or "", re.S)
    try:
        got = json.loads(m.group(0)) if m else []
    except json.JSONDecodeError:
        got = []
    n = 0
    for g in got:
        if not isinstance(g, dict) or not isinstance(g.get("id"), int) or not 1 <= g["id"] <= len(models):
            continue
        key = models[g["id"] - 1][0]
        if store(db, key, g.get("new_low"), g.get("new_high"), bool(g.get("not_sold_new")), g.get("source") or "web search"):
            n += 1
    if n:
        log(f"  new prices in shops: found {n} of {len(models)} models")
    return n
