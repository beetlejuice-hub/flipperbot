"""One poll: fetch the newest listings, store them, judge the new and the
re-priced ones, alert on the good ones, and let Claude look at one."""

from __future__ import annotations

import json
import random
import re
import time
from collections import Counter
from datetime import datetime
from typing import Any, Callable

from . import ai, niches, notify
from .config import Settings
from .db import DB, TIER_RANK
from .identify import find_brands, identify, normalize
from .models import Listing
from .sources import olx
from .tiers import judge

# Watches' OLX categories (kept here for older code and tests; niches.py has every niche's).
WATCH_CATEGORIES = list(niches.WATCHES.categories)


def watch_categories(db: DB) -> list[str]:
    return WATCH_CATEGORIES


def learn_categories(db: DB, listings: list[Listing]) -> None:
    """Counts which categories 'ceas' listings are filed under, for `flipperbot stats`."""
    counts = Counter(db.kv_get("olx_ceas_categories", {}))
    for l in listings:
        if l.category_id and "ceas" in normalize(l.title).split():
            counts[l.category_id] += 1
    db.kv_set("olx_ceas_categories", dict(counts))


def is_relevant(l: Listing, niche: str | None = None) -> bool:
    """Is this listing really one of the niche's things? Not a car-dashboard 'ceas', not a
    wall clock. In the niche's OLX categories everything counts; elsewhere the title needs a
    niche word (Facebook) or a brand plus a niche word."""
    n = niches.get(niche or l.niche)
    t = normalize(l.title)
    if any(re.search(rf"(?<![a-z]){re.escape(w)}(?![a-z])", t) for w in n.not_words):
        return False
    if l.source == "olx" and l.category_id in n.categories:
        return True
    if l.source != "olx" and any(re.search(rf"(?<![a-z]){re.escape(w)}(?![a-z])", t) for w in n.strong_words):
        return True  # no categories elsewhere: the word will do
    return bool(find_brands(l.title, n.key)) and any(w in t for w in n.words)


def is_watch(l: Listing, cats: list[str] | None = None) -> bool:
    return is_relevant(l, "watches")


def row_to_listing(r: Any) -> Listing:
    return Listing(
        source=r["source"], source_id=r["source_id"], url=r["url"], title=r["title"],
        description=r["description"] or "", price_ron=r["price_ron"], negotiable=bool(r["negotiable"]),
        params=json.loads(r["params"] or "{}"), seller_id=r["seller_id"] or "", niche=r["niche"] or "watches",
        created_at=r["created_at"] or "",
        city=r["city"] or "", photos=json.loads(r["photos"] or "[]"), category_id=r["category_id"] or "",
    )


def listing_age_days(created_at: str | None) -> int | None:
    """Days since the seller first posted it (OLX's created_time, which a paid refresh doesn't change)."""
    if not created_at:
        return None
    try:
        created = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
    except ValueError:
        return None
    now = datetime.now(created.tzinfo) if created.tzinfo else datetime.now()
    return max(0, (now - created).days)


def recent_price_cut(db: DB, l: Listing, days: int = 14) -> bool:
    """Did the seller lower the price lately? On an old listing that's a real signal."""
    rows = db.conn.execute(
        "SELECT price_ron, seen_at FROM prices WHERE key=? AND price_ron IS NOT NULL ORDER BY seen_at", (l.key,)
    ).fetchall()
    cutoff = (datetime.now() - __import__("datetime").timedelta(days=days)).isoformat()
    return any(b["price_ron"] < a["price_ron"] and b["seen_at"][:19] >= cutoff[:19] for a, b in zip(rows, rows[1:])) or bool(
        l.previous_price_ron and l.price_ron and l.price_ron < l.previous_price_ron)


def evaluate(db: DB, l: Listing, s: Settings) -> Any:
    # OLX has its own "brand" field on watch listings; count it as part of the description.
    brand_field = l.params.get("brand") if isinstance(l.params.get("brand"), str) else ""
    ident = identify(l.title, f"{l.description} {brand_field}", l.niche)
    comps = db.comparable_prices(ident.model_key, exclude_key=l.key) if ident.model_key else []
    verdict = judge(l, ident, comps, s)
    if verdict.tier in ("good", "real_good") and ident.segment in ("luxury", "swiss") and "vintage" not in ident.flags and l.seller_id:
        # One seller with a row of modern luxury/Swiss watches all far under market: a replica dealer.
        # (Not vintage: a vintage shop selling several old Swiss watches is normal.)
        n = db.conn.execute(
            """SELECT COUNT(*) FROM listings WHERE seller_id=? AND key!=? AND segment IN ('luxury','swiss')
               AND flags NOT LIKE '%"vintage"%'
               AND (tier IN ('good','real_good','suspect') OR reason LIKE '%likely fake%')""",
            (l.seller_id, l.key),
        ).fetchone()[0]
        if n >= 2:
            verdict.tier = "suspect"
            verdict.reason = f"seller has {n + 1} cheap luxury listings: likely replicas · " + verdict.reason
    age = listing_age_days(l.created_at)
    if age is not None and age > s.max_listing_age_days and verdict.tier in ("good", "real_good") and not recent_price_cut(db, l):
        # Up for months and still "cheap"? A real deal would be gone: overpriced, fake, or bait.
        verdict.tier = "mid"
        verdict.reason = f"listed {age} days ago: a real deal wouldn't last that long · " + verdict.reason
    elif age is not None and age > s.max_listing_age_days and verdict.tier in ("good", "real_good"):
        verdict.reason = f"old listing ({age} days), but the price was just cut · " + verdict.reason
    db.set_verdict(l.key, ident, verdict)
    return db.get(l.key)


def process(db: DB, listings: list[Listing], s: Settings, *, alert: bool = True) -> list[Any]:
    """Store, judge, alert. Returns rows that should get an AI look."""
    for_ai = []
    for l in listings:
        if not is_relevant(l):
            continue
        change, prev = db.upsert(l)
        if change == "seen" and prev is not None and prev["tier"]:
            continue
        row = evaluate(db, l, s)
        if not alert:  # backfill: price book only, never alert on these
            db.mark_notified(l.key, row["tier"])
        elif row["tier"] in s.ai_tiers and not row["ai"]:
            for_ai.append(row)
    return for_ai


Search = tuple  # (query or None, OLX category or None, niche)


def pick_searches(db: DB, s: Settings) -> list[Search]:
    """For each niche: its category feeds (newest listings), then a few random searches, most of
    them from its focus pool (lots, old, inherited)."""
    out: list[Search] = []
    for key in s.niches:
        n = niches.get(key)
        search_pool = s.search_pool if key == "watches" else list(n.search_pool)
        focus_pool = s.focus_pool if key == "watches" else list(n.focus_pool)
        out += [(None, c, key) for c in n.feeds]
        n_focus = round(s.searches_per_poll * s.focus_share)
        terms = random.sample(focus_pool, min(n_focus, len(focus_pool)))
        if key == "watches":
            n_modern = round(s.searches_per_poll * s.modern_share)
            terms += random.sample(s.modern_pool, min(n_modern, len(s.modern_pool)))
        rest = [t for t in search_pool if t not in terms]
        terms += random.sample(rest, min(s.searches_per_poll - len(terms), len(rest)))
        out += [(t, None, key) for t in terms]
    return out


def fetch_all(searches: list[Search], s: Settings, pages: int = 1, log: Callable[[str], None] = print) -> list[Listing]:
    out: list[Listing] = []
    for i, search in enumerate(searches):
        query, cat, key = (*search, "watches")[:3] if len(search) == 2 else search
        if i:
            time.sleep(random.uniform(*s.pause_between_requests_s))
        got = list(olx.search(query, category_id=cat, pages=pages, eur_to_ron=s.eur_to_ron, pause=s.pause_between_requests_s))
        for l in got:
            l.niche = key
        log(f"  olx {niches.get(key).icon} {'category ' + cat if cat else repr(query)}: {len(got)}")
        out.extend(got)
    return out


def poll(db: DB, s: Settings, log: Callable[[str], None] = print) -> list[Any]:
    listings = fetch_all(pick_searches(db, s), s, log=log)
    db.kv_set("last_poll", {"at": datetime.now().isoformat(timespec="seconds"), "listings": len(listings)})
    learn_categories(db, listings)
    return process(db, listings, s)


def facebook_due(db: DB, s: Settings) -> bool:
    from .sources import facebook

    state = db.kv_get("facebook", {})
    if not facebook.installed() or state.get("state") not in ("ok", "error"):
        return False  # not set up, or logged out: waits for `flipperbot facebook-login`
    return time.time() >= state.get("next_at", 0)


def poll_facebook(db: DB, s: Settings, log: Callable[[str], None] = print) -> int:
    """One Facebook run: a couple of searches, new watch-looking listings opened for details,
    then the same judging as OLX. Returns how many listings it saw."""
    from .sources import facebook

    state = db.kv_get("facebook", {})
    next_at = time.time() + random.uniform(*s.facebook_every_min) * 60
    try:
        pool = [(q, key) for key in s.niches for q in niches.get(key).facebook_queries]
        listings = list(facebook.search(
            random.sample(pool, min(s.facebook_searches_per_run, len(pool))),
            is_new=lambda key: db.get(key) is None,
            looks_like_watch=lambda l: is_relevant(l),
            max_details=s.facebook_max_details, eur_to_ron=s.eur_to_ron, log=log,
        ))
    except facebook.NotLoggedIn as e:
        db.kv_set("facebook", {**state, "state": "logged_out", "error": str(e)[:200], "at": datetime.now().isoformat(timespec="seconds")})
        log("  facebook: logged out. Run `flipperbot facebook-login` to log in again.")
        return 0
    except Exception as e:
        db.kv_set("facebook", {**state, "state": "error", "error": f"{type(e).__name__}: {e}"[:200], "next_at": next_at,
                               "at": datetime.now().isoformat(timespec="seconds")})
        log(f"  facebook error: {e!r}")
        return 0
    process(db, listings, s)
    db.kv_set("facebook", {"state": "ok", "next_at": next_at, "at": datetime.now().isoformat(timespec="seconds"), "listings": len(listings)})
    return len(listings)


def _fresh(db: DB) -> str:
    """Only listings found after the starter price book was loaded can alert or use Claude."""
    return db.kv_get("seeded_at") or "0"


def pending_alerts(db: DB, s: Settings) -> list[Any]:
    rank = "CASE {c} WHEN 'real_good' THEN 4 WHEN 'good' THEN 3 WHEN 'mid' THEN 2 WHEN 'suspect' THEN 1 WHEN 'bad' THEN 0 ELSE -1 END"
    q = f"""SELECT * FROM listings WHERE tier IN ({','.join('?' * len(s.alert_tiers))})
            AND {rank.format(c='tier')} > {rank.format(c='notified_tier')}
            AND first_seen >= ? AND last_seen >= datetime('now', '-1 day') AND hidden = 0
            ORDER BY COALESCE(profit_ron, 0) DESC"""
    return db.conn.execute(q, [*s.alert_tiers, _fresh(db)]).fetchall()


def pending_ai(db: DB, s: Settings) -> list[Any]:
    """What Claude looks at besides real good deals, lots first: every lot (unnamed old lots hide
    good watches), then good deals by profit. Results land on the dashboard; one that Claude values
    as a real good deal gets promoted and, if confirmed, sent."""
    tiers = [t for t in s.ai_tiers if t not in s.alert_tiers]
    q = f"""SELECT * FROM listings WHERE ai IS NULL AND hidden = 0
            AND (tier IN ({','.join('?' * len(tiers)) or "''"})
                 OR ((flags LIKE '%"lot"%' OR flags LIKE '%"naive"%' OR reason LIKE '%Claude will look%')
                     AND tier IN ('mid', 'good')))
            AND first_seen >= ? AND last_seen >= datetime('now', '-2 days')
            ORDER BY CASE WHEN flags LIKE '%"lot"%' THEN 3 WHEN flags LIKE '%"naive"%' THEN 2
                          WHEN flags LIKE '%"vintage"%' THEN 1 ELSE 0 END DESC, COALESCE(profit_ron, 0) DESC"""
    return db.conn.execute(q, [*tiers, _fresh(db)]).fetchall()


def claude_value(db: DB, row: Any, result: dict[str, Any], s: Settings) -> str | None:
    """Re-tier a listing from Claude's own valuation (how lots and unnamed watches get priced).
    Only ever upgrades. Returns the new tier if it changed."""
    if not result or "error" in result or not result.get("resale_ron_high"):
        return None
    low = result.get("resale_ron_low") or result["resale_ron_high"]
    worth = (low + result["resale_ron_high"]) / 2
    profit = round(low - row["price_ron"] - (result.get("repair_cost_ron") or 0))  # the cautious end
    discount = 1 - row["price_ron"] / worth if worth else 0
    tier = None
    if discount >= s.real_good_discount and profit >= s.real_good_profit_ron:
        tier = "real_good"
    elif discount >= s.good_discount and profit >= s.good_profit_ron:
        tier = "good"
    if not tier or TIER_RANK[tier] <= TIER_RANK.get(row["tier"], 0):
        return None
    notable = [w for w in (result.get("items") or result.get("watches")) or [] if w.get("notable")]
    what = f"{len(notable)} notable watches inside" if "lot" in (row["flags"] or "") and notable else "Claude's valuation"
    db.conn.execute(
        "UPDATE listings SET tier=?, est_value_ron=?, est_high_ron=?, profit_ron=?, reason=? WHERE key=?",
        (tier, round(low), result["resale_ron_high"], profit,
         f"Claude: sells for ~{round(low)}–{result['resale_ron_high']} lei ({what}) · was: {row['reason']}", row["key"]),
    )
    db.conn.commit()
    return tier


def ai_skip_reason(db: DB, s: Settings) -> str | None:
    if not s.ai_enabled:
        return "Claude checks are turned off"
    if not ai.available(s):
        return "Claude Code isn't installed on the Mac"
    if ai.used_today(db) >= s.ai_daily_limit:
        return f"today's {s.ai_daily_limit} Claude checks are used up"
    return None


def confidence(result: dict[str, Any]) -> int:
    c = result.get("confidence")
    if isinstance(c, (int, float)):
        return int(c)
    return {"likely_genuine": 60, "unsure": 40}.get(result.get("authenticity"), 0)  # older checks had no number


def confirmed(result: dict[str, Any] | None, s: Settings, segment: str | None = None) -> tuple[bool, str]:
    """Is Claude sure enough about this deal to message you? Luxury/Swiss needs more."""
    if not result:
        return False, "not checked by Claude"
    if "error" in result:
        return False, "Claude's check failed"
    if result.get("authenticity") == "likely_fake":
        return False, "Claude thinks it's fake"
    if (result.get("verdict") or "").lower() not in ("buy", "negotiate"):
        return False, f"Claude says {result.get('verdict') or 'skip'}"
    need = s.alert_min_confidence_luxury if segment in ("luxury", "swiss") else s.alert_min_confidence
    if confidence(result) < need:
        return False, f"Claude only {confidence(result)}% sure (needs {need})"
    return True, ""


def deliver(db: DB, s: Settings, log: Callable[[str], None] = print, extra_ai: int = 1) -> None:
    """Real good deals: Claude reads the listing and photos (real or fake? worth it?). Only the
    ones it confirms (not fake, buy/negotiate, at least alert_min_confidence% sure) go to
    Telegram, as one message with Claude's notes. The rest stay on the dashboard with Claude's
    notes there. A deal Claude can't check yet (daily limit) waits for the next chance.
    Then, with budget left, Claude looks at a good one for the dashboard.

    By default (`ai_auto_real_good`) only real good deals are checked by themselves; with `ai_auto`
    the bot also sends lots, old watches and good deals to Claude."""
    if not (s.ai_auto or s.ai_auto_real_good):
        return
    for r in pending_alerts(db, s):
        if r["ai"]:
            result = json.loads(r["ai"])
        else:
            why_not = ai_skip_reason(db, s)
            if why_not:
                log(f"  real good deal waiting for Claude ({why_not}): {r['title']}")
                continue
            log(f"  Claude checking a real good deal: {r['title']}")
            try:
                result = ai.check(db, r, s)
            except ai.UsageLimit:
                log("  Claude's usage limit reached: trying again next poll")
                return
            if result is None:
                continue
        row = db.get(r["key"])
        ok, why = confirmed(result, s, row["segment"])
        if ok:
            notify.send(s, notify.deal_text(row, result), (json.loads(row["photos"] or "[]") or [None])[0])
            log(f"  sent to Telegram ({confidence(result)}% sure): {row['title']}")
        else:
            log(f"  not sent ({why}): {row['title']}")
        db.mark_notified(row["key"], row["tier"])  # decided either way; it's on the dashboard
    if not s.ai_auto:
        return  # the rest waits for "Send to Claude"
    for r in pending_ai(db, s)[:extra_ai]:
        if ai_skip_reason(db, s):
            return
        log(f"  Claude checking {'a lot' if 'lot' in (r['flags'] or '') else 'for the dashboard'}: {r['title']}")
        try:
            result = ai.check(db, r, s)
        except ai.UsageLimit:
            return
        if result and claude_value(db, r, result, s) == "real_good":
            row = db.get(r["key"])
            ok, why = confirmed(result, s, row["segment"])
            if ok:
                notify.send(s, notify.deal_text(row, result), (json.loads(row["photos"] or "[]") or [None])[0])
                log(f"  Claude found a real good deal, sent ({confidence(result)}% sure): {row['title']}")
            else:
                log(f"  Claude values it as real good but didn't confirm ({why}): {row['title']}")
            db.mark_notified(row["key"], "real_good")


def digest(db: DB, s: Settings) -> int:
    rows = db.undigested(["real_good", "good", "mid", "suspect"])
    if rows:
        notify.send(s, notify.digest_text(rows))
        db.mark_digested([r["key"] for r in rows])
    return len(rows)


def run_forever(db: DB, s: Settings, digest_hour: int = 20) -> None:
    from . import web

    web.serve(s, background=True)
    print(f"flipperbot is running. Dashboard: {web.url(s)}")
    while True:
        stamp = datetime.now().strftime("%H:%M")
        try:
            print(f"[{stamp}] polling")
            poll(db, s)
            if facebook_due(db, s):
                poll_facebook(db, s)
            deliver(db, s)
            today = datetime.now().date().isoformat()
            if s.digest_telegram and datetime.now().hour >= digest_hour and db.kv_get("last_digest") != today:
                n = digest(db, s)
                db.kv_set("last_digest", today)
                print(f"  digest sent: {n}")
            wait = random.uniform(*s.poll_every_min) * 60
        except olx.Blocked as e:
            print(f"  {e}; waiting {s.blocked_backoff_min} min")
            wait = s.blocked_backoff_min * 60
        except Exception as e:  # network hiccups etc.: log and keep going
            print(f"  error: {e!r}")
            wait = 120
        time.sleep(wait)
