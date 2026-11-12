"""The 0-10 score: one number for how much a listing deserves your attention.

    0      gone from view: likely fake, replica, locked, overpriced, old, parts, wanted ads...
    1-7    the free rules: tier, profit, how fast it sells, how fresh, how interesting
    4-7 -> a cheap AI read (Haiku, text only, 20 listings a call) can move it anywhere 0-10
    8-10   the full Claude check (photos, fakes, sold prices) sets the final score

Each step only sees what the step before let through, so most listings never cost any AI.
"""

from __future__ import annotations

import json
from typing import Any

RULE_MAX = 7  # free rules alone never go above 7: an 8+ needs an AI to agree

# Bump when the rules that judge or score a listing change: the bot then re-judges every stored listing
# once at start, so an update never leaves old listings with stale or missing scores.
RULES_VERSION = 6

# Reasons a listing is not worth anyone's time, from the tier's own reason text.
_DEAD = ("someone buying", "repair shop", "replica", "over budget", "fashion brand", "part/accessory", "locked to",
         "not a watch", "not a camera", "a real deal wouldn't last")


def rule_score(tier: str | None, flags: list[str] | set[str], reason: str | None, profit: int | None,
               liquidity: dict | None, age_days: int | None, good_profit: int = 150) -> tuple[int, str]:
    reason = reason or ""
    f = set(flags or [])
    if tier == "suspect":
        return 0, "likely fake"
    if reason == "no price":  # exact: "... no price history yet" is a different, often interesting, thing
        return 0, "not worth it: no price"
    if f & {"replica", "locked", "wanted", "service"} or any(d in reason for d in _DEAD):
        return 0, "not worth it: " + next((d for d in _DEAD if d in reason), "replica/locked/wanted")
    if tier == "bad":
        # Priced and not under market = overpriced; nothing known = barely a look.
        if any(x in reason for x in ("under what similar ones ask", "under what they ask", "vs market", "realistic sale")):
            return 0, "overpriced: not under what similar ones sell for"
        return 1, "nothing stands out"
    base = {"mid": 3, "good": 6, "real_good": 7}.get(tier or "", 1)
    why = [f"{tier}"]
    if profit and profit >= 4 * good_profit:
        base += 1
        why.append(f"profit ~{profit}")
    if liquidity:
        delta = {"fast": 1, "normal": 0, "slow": -1, "very slow": -2}.get(liquidity.get("label"), 0)
        if delta:
            base += delta
            why.append(f"sells {liquidity['label']}")
    if age_days is not None and age_days <= 2:
        base += 1
        why.append("just posted")
    if tier == "mid" and f & {"lot", "collectible", "naive"}:
        base += 1
        why.append("lot/collector/seller doesn't know")
    if profit is None:
        # No price estimate: it can be worth a look, never a top score. The quick AI read (4+) estimates one.
        base = min(base, 4)
        why.append("no price estimate yet")
    return max(1, min(RULE_MAX, base)), ", ".join(why)


def claude_profit(result: dict[str, Any] | None, price: int | None) -> int | None:
    """What Claude's own numbers leave you: the low end of its resale range, minus price and repair."""
    if not result or "error" in result or not result.get("resale_ron_low") or price is None:
        return None
    try:
        return int(result["resale_ron_low"]) - int(price) - int(result.get("repair_cost_ron") or 0)
    except (TypeError, ValueError):
        return None


def claude_score(result: dict[str, Any] | None, price: int | None = None, good_profit: int = 150) -> tuple[int, str] | None:
    """The full check's verdict as a score, held down by Claude's own math: a "buy" that loses money
    or leaves less than a good deal's profit is not an 8+. None if it didn't run or failed."""
    if not result or "error" in result:
        return None
    if result.get("authenticity") == "likely_fake":
        return 0, "Claude: likely fake"
    verdict = (result.get("verdict") or "").lower()
    conf = result.get("confidence") if isinstance(result.get("confidence"), (int, float)) else 50
    if verdict == "skip":
        return 2, "Claude: skip"
    # Half sure isn't sure: 8+ needs Claude at least 60% sure (or a confident "buy").
    if verdict == "buy":
        score = 10 if conf >= 75 else 9 if conf >= 60 else 7 if conf >= 50 else 6
    elif verdict == "negotiate":
        score = 9 if conf >= 75 else 8 if conf >= 60 else 6
    else:
        score = 5
    why = f"Claude: {verdict}, {int(conf)}% sure"
    if result.get("authenticity") == "unsure":
        score = min(score, 7)
    fh = result.get("fake_hunt") or {}
    if fh.get("verdict") == "fake":
        return 0, "Claude's second check: fake"
    low = result.get("resale_ron_low")
    if price and isinstance(low, (int, float)) and price < 0.35 * low and not result.get("verified"):
        # Under a third of what it sells for: replicas are, real ones almost never. No 8+ without the fake check.
        score, why = min(score, 7), f"{why}, but too cheap to trust without the second (fake) check"
    profit = claude_profit(result, price)
    if not result.get("resale_ron_low") and not result.get("resale_ron_high"):
        score, why = min(score, 6), f"{why}, but no price estimate"
    elif profit is not None and profit <= 0:
        score, why = min(score, 2), f"{why}, but its own numbers lose money ({profit} lei)"
    elif profit is not None and profit < good_profit:
        score, why = min(score, 6), f"{why}, but only ~{profit} lei profit"
    return score, why


QUICK_MAX = 7  # the quick read can send a listing to the full check, but only the full check gives an 8+


def quick_score(quick: dict[str, Any] | None, price: int | None = None, good_profit: int = 150) -> tuple[int, str] | None:
    """The quick read's score, held down by its own price estimate like the full check's."""
    if not quick or not isinstance(quick.get("score"), (int, float)):
        return None
    s = max(0, min(10, int(quick["score"])))
    note = str(quick.get("note") or "")[:80]
    if quick.get("fake_risk") == "high":
        s = min(s, 2)
    low = quick.get("value_low") if isinstance(quick.get("value_low"), (int, float)) else None
    if not low:
        return min(s, 4), "quick AI (no price estimate): " + note
    if price is not None and low - price <= 0:
        return min(s, 2), f"quick AI: sells for ~{int(low)}, not under {price}: " + note
    if price is not None and low - price < good_profit:
        return min(s, 5), f"quick AI: only ~{int(low - price)} lei profit: " + note
    if s > QUICK_MAX:
        return QUICK_MAX, f"quick AI says {s}/10, waiting for Claude's full check: {note}"
    return s, "quick AI: " + note


def final_score(row: Any, good_profit: int = 150) -> tuple[int, str]:
    """Full Claude check > quick AI read > free rules."""
    try:
        full = json.loads(row["ai"]) if row["ai"] else None
    except (TypeError, ValueError):
        full = None
    got = claude_score(full, row["price_ron"], good_profit)
    if got:
        return got
    try:
        quick = json.loads(row["quick"]) if row["quick"] else None
    except (TypeError, ValueError, IndexError, KeyError):
        quick = None
    got = quick_score(quick, row["price_ron"], good_profit)
    if got:
        return got
    return row["rule_score"] if row["rule_score"] is not None else 1, row["rule_why"] or ""
