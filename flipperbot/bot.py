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

from . import ai, notify
from .config import Settings
from .db import DB, TIER_RANK
from .identify import find_brands, identify, normalize
from .models import Listing
from .sources import olx
from .tiers import judge

WATCH_WORDS = ["ceas", "watch", "chrono", "cronograf", "cronometru", "automatic", "mecanic", "quartz", "diver"]
NOT_WATCHES = ["opel", "jante", "anvelope", "telefon", "apartament", "masina", "autoturism", "bicicleta", "parfum"]


# OLX.ro categories: 1677 = men's watches, 1676 = women's watches (checked November 2026).
# Elsewhere "ceas" also means car dashboard clocks, wall clocks, smartwatches; those are skipped
# unless the title names a watch brand (a Tissot filed under the wrong category still counts).
WATCH_CATEGORIES = ["1677", "1676"]
WATCH_WORDS = ["ceas", "watch", "chrono", "cronograf", "cronometru", "automatic", "mecanic", "quartz", "diver"]
NOT_WATCHES = [
    "bord", "perete", "pendul", "cuc", "de masa", "masa", "semineu", "desteptator", "smart", "smartwatch", "apple watch", "galaxy watch",
    "opel", "jante", "anvelope", "telefon", "apartament", "masina", "autoturism", "bicicleta", "parfum",
]


def watch_categories(db: DB) -> list[str]:
    return WATCH_CATEGORIES


def learn_categories(db: DB, listings: list[Listing]) -> None:
    """Counts which categories 'ceas' listings are filed under, for `flipperbot stats`."""
    counts = Counter(db.kv_get("olx_ceas_categories", {}))
    for l in listings:
        if l.category_id and "ceas" in normalize(l.title).split():
            counts[l.category_id] += 1
    db.kv_set("olx_ceas_categories", dict(counts))


def is_watch(l: Listing, cats: list[str]) -> bool:
    t = normalize(l.title)
    if any(re.search(rf"(?<![a-z]){re.escape(w)}(?![a-z])", t) for w in NOT_WATCHES):
        return False
    if l.category_id in cats:
        return True
    # Outside the watch categories ("Opel Omega" parts, a Tissot filed under Jewellery):
    # it needs a watch brand and a watch word in the title.
    return bool(find_brands(l.title)) and any(w in t for w in WATCH_WORDS)


def row_to_listing(r: Any) -> Listing:
    return Listing(
        source=r["source"], source_id=r["source_id"], url=r["url"], title=r["title"],
        description=r["description"] or "", price_ron=r["price_ron"], negotiable=bool(r["negotiable"]),
        params=json.loads(r["params"] or "{}"), seller_id=r["seller_id"] or "",
        city=r["city"] or "", photos=json.loads(r["photos"] or "[]"), category_id=r["category_id"] or "",
    )


def evaluate(db: DB, l: Listing, s: Settings) -> Any:
    # OLX has its own "brand" field on watch listings; count it as part of the description.
    brand_field = l.params.get("brand") if isinstance(l.params.get("brand"), str) else ""
    ident = identify(l.title, f"{l.description} {brand_field}")
    comps = db.comparable_prices(ident.model_key, exclude_key=l.key) if ident.model_key else []
    verdict = judge(l, ident, comps, s)
    if verdict.tier in ("good", "real_good") and ident.segment in ("luxury", "swiss") and l.seller_id:
        # One seller with a row of luxury watches all far under market: a replica dealer.
        n = db.conn.execute(
            """SELECT COUNT(*) FROM listings WHERE seller_id=? AND key!=? AND segment IN ('luxury','swiss')
               AND (tier IN ('good','real_good','suspect') OR reason LIKE '%likely fake%')""",
            (l.seller_id, l.key),
        ).fetchone()[0]
        if n >= 2:
            verdict.tier = "suspect"
            verdict.reason = f"seller has {n + 1} cheap luxury listings: likely replicas · " + verdict.reason
    db.set_verdict(l.key, ident, verdict)
    return db.get(l.key)


def process(db: DB, listings: list[Listing], s: Settings, *, alert: bool = True) -> list[Any]:
    """Store, judge, alert. Returns rows that should get an AI look."""
    cats = watch_categories(db)
    for_ai = []
    for l in listings:
        if not is_watch(l, cats):
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


def pick_searches(db: DB, s: Settings) -> list[tuple[str | None, str | None]]:
    feeds: list[tuple[str | None, str | None]] = [(None, c) for c in watch_categories(db)]
    terms = random.sample(s.search_pool, min(s.searches_per_poll, len(s.search_pool)))
    return feeds + [(t, None) for t in terms]


def fetch_all(searches: list[tuple[str | None, str | None]], s: Settings, pages: int = 1, log: Callable[[str], None] = print) -> list[Listing]:
    out: list[Listing] = []
    for i, (query, cat) in enumerate(searches):
        if i:
            time.sleep(random.uniform(*s.pause_between_requests_s))
        got = list(olx.search(query, category_id=cat, pages=pages, eur_to_ron=s.eur_to_ron, pause=s.pause_between_requests_s))
        log(f"  olx {'category ' + cat if cat else repr(query)}: {len(got)}")
        out.extend(got)
    return out


def poll(db: DB, s: Settings, log: Callable[[str], None] = print) -> list[Any]:
    listings = fetch_all(pick_searches(db, s), s, log=log)
    db.kv_set("last_poll", {"at": datetime.now().isoformat(timespec="seconds"), "listings": len(listings)})
    learn_categories(db, listings)
    return process(db, listings, s)


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
    """Listings Claude should look at that won't go to Telegram (good ones): dashboard only."""
    tiers = [t for t in s.ai_tiers if t not in s.alert_tiers]
    if not tiers:
        return []
    q = f"""SELECT * FROM listings WHERE ai IS NULL AND tier IN ({','.join('?' * len(tiers))})
            AND first_seen >= ? AND last_seen >= datetime('now', '-2 days') AND hidden = 0
            ORDER BY COALESCE(profit_ron, 0) DESC"""
    return db.conn.execute(q, [*tiers, _fresh(db)]).fetchall()


def ai_skip_reason(db: DB, s: Settings) -> str | None:
    if not s.ai_enabled:
        return "Claude checks are turned off"
    if not ai.available(s):
        return "Claude Code isn't installed on the Mac"
    if ai.used_today(db) >= s.ai_daily_limit:
        return f"today's {s.ai_daily_limit} Claude checks are used up"
    return None


def deliver(db: DB, s: Settings, log: Callable[[str], None] = print, extra_ai: int = 1) -> None:
    """Real good deals: Claude reads the listing and photos first (real or fake? worth it?),
    then ONE Telegram message with the deal and Claude's notes. If Claude can't check it,
    the deal still goes out, saying why it wasn't checked. Then, with budget left, Claude
    looks at a good one for the dashboard."""
    for r in pending_alerts(db, s):
        result = None
        if r["tier"] in s.ai_tiers and not r["ai"]:
            why_not = ai_skip_reason(db, s)
            if why_not is None:
                log(f"  Claude checking before alert: {r['title']}")
                result = ai.check(db, r, s)
        row = db.get(r["key"])
        result = result or (json.loads(row["ai"]) if row["ai"] else None)
        note = None if result else (ai_skip_reason(db, s) or "Claude's check didn't finish")
        notify.send(s, notify.deal_text(row, result, note), (json.loads(row["photos"] or "[]") or [None])[0])
        db.mark_notified(row["key"], row["tier"])
    for r in pending_ai(db, s)[:extra_ai]:
        if ai_skip_reason(db, s):
            return
        log(f"  Claude checking for the dashboard: {r['title']}")
        ai.check(db, r, s)


def digest(db: DB, s: Settings) -> int:
    rows = db.undigested(["real_good", "good", "mid", "suspect"])
    if rows:
        notify.send(s, notify.digest_text(rows))
        db.mark_digested([r["key"] for r in rows])
    return len(rows)


def run_forever(db: DB, s: Settings, digest_hour: int = 20) -> None:
    from . import web

    web.serve(s, background=True)
    notify.send(s, f"🚀 flipperbot is running. Checking OLX every 5-10 minutes. Dashboard on your Mac: {web.url(s)}")
    while True:
        stamp = datetime.now().strftime("%H:%M")
        try:
            print(f"[{stamp}] polling")
            poll(db, s)
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
