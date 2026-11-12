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

# Reasons a listing is not worth anyone's time, from the tier's own reason text.
_DEAD = ("someone buying", "repair shop", "replica", "over budget", "fashion brand", "part/accessory", "locked to",
         "not a watch", "not a camera", "no price", "a real deal wouldn't last")


def rule_score(tier: str | None, flags: list[str] | set[str], reason: str | None, profit: int | None,
               liquidity: dict | None, age_days: int | None, good_profit: int = 150) -> tuple[int, str]:
    reason = reason or ""
    f = set(flags or [])
    if tier == "suspect":
        return 0, "likely fake"
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
    return max(1, min(RULE_MAX, base)), ", ".join(why)


def claude_score(result: dict[str, Any] | None) -> tuple[int, str] | None:
    """The full check's verdict as a score. None if it didn't run or failed."""
    if not result or "error" in result:
        return None
    if result.get("authenticity") == "likely_fake":
        return 0, "Claude: likely fake"
    verdict = (result.get("verdict") or "").lower()
    conf = result.get("confidence") if isinstance(result.get("confidence"), (int, float)) else 50
    if verdict == "skip":
        return 2, "Claude: skip"
    if verdict == "buy":
        score = 10 if conf >= 75 else 9 if conf >= 50 else 7
    elif verdict == "negotiate":
        score = 9 if conf >= 75 else 8 if conf >= 50 else 6
    else:
        score = 5
    if result.get("authenticity") == "unsure":
        score = min(score, 7)
    return score, f"Claude: {verdict}, {int(conf)}% sure"


def quick_score(quick: dict[str, Any] | None) -> tuple[int, str] | None:
    if not quick or not isinstance(quick.get("score"), (int, float)):
        return None
    s = max(0, min(10, int(quick["score"])))
    if quick.get("fake_risk") == "high":
        s = min(s, 2)
    return s, "quick AI: " + str(quick.get("note") or "")[:80]


def final_score(row: Any) -> tuple[int, str]:
    """Full Claude check > quick AI read > free rules."""
    try:
        full = json.loads(row["ai"]) if row["ai"] else None
    except (TypeError, ValueError):
        full = None
    got = claude_score(full)
    if got:
        return got
    try:
        quick = json.loads(row["quick"]) if row["quick"] else None
    except (TypeError, ValueError, IndexError, KeyError):
        quick = None
    got = quick_score(quick)
    if got:
        return got
    return row["rule_score"] if row["rule_score"] is not None else 1, row["rule_why"] or ""
