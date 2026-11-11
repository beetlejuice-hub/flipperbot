"""One poll: fetch the newest listings, store them, judge the new and the
re-priced ones, alert on the good ones, and let Claude look at one."""

from __future__ import annotations

import json
import random
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

NOT_WATCHES = ["opel", "jante", "anvelope", "telefon", "apartament", "masina", "autoturism", "bicicleta", "parfum"]


def watch_categories(db: DB) -> list[str]:
    """OLX categories that hold watches, learned from what 'ceas' listings are filed under."""
    counts: dict[str, int] = db.kv_get("olx_watch_categories", {})
    total = sum(counts.values())
    if total < 40:
        return []
    return [c for c, n in counts.items() if n >= 20 and n / total >= 0.15]


def learn_categories(db: DB, listings: list[Listing]) -> None:
    counts = Counter(db.kv_get("olx_watch_categories", {}))
    for l in listings:
        if l.category_id and "ceas" in normalize(l.title).split():
            counts[l.category_id] += 1
    db.kv_set("olx_watch_categories", dict(counts))


def is_watch(l: Listing, cats: list[str]) -> bool:
    t = normalize(l.title)
    if any(w in t.split() for w in NOT_WATCHES):
        return False
    if "ceas" in t:
        return True
    if cats:
        return l.category_id in cats
    return bool(find_brands(l.title))


def row_to_listing(r: Any) -> Listing:
    return Listing(
        source=r["source"], source_id=r["source_id"], url=r["url"], title=r["title"],
        description=r["description"] or "", price_ron=r["price_ron"], negotiable=bool(r["negotiable"]),
        city=r["city"] or "", photos=json.loads(r["photos"] or "[]"), category_id=r["category_id"] or "",
    )


def evaluate(db: DB, l: Listing, s: Settings) -> Any:
    ident = identify(l.title, l.description)
    comps = db.comparable_prices(ident.model_key, exclude_key=l.key) if ident.model_key else []
    verdict = judge(l, ident, comps, s)
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
        tier = row["tier"]
        already = TIER_RANK.get(row["notified_tier"] or "", -1)
        if alert and tier in s.alert_tiers and TIER_RANK[tier] > already:
            notify.send(s, notify.listing_text(row, change), (json.loads(row["photos"] or "[]") or [None])[0])
            db.mark_notified(l.key, tier)
        if tier in s.ai_tiers and not row["ai"]:
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
        got = list(olx.search(query, category_id=cat, pages=pages, eur_to_ron=s.eur_to_ron))
        log(f"  olx {'category ' + cat if cat else repr(query)}: {len(got)}")
        out.extend(got)
    return out


def poll(db: DB, s: Settings, log: Callable[[str], None] = print) -> list[Any]:
    listings = fetch_all(pick_searches(db, s), s, log=log)
    learn_categories(db, listings)
    return process(db, listings, s)


def run_ai(db: DB, rows: list[Any], s: Settings, limit: int = 1, log: Callable[[str], None] = print) -> None:
    rows = sorted(rows, key=lambda r: (-TIER_RANK[r["tier"]], -(r["profit_ron"] or 0)))
    for r in rows[:limit]:
        if not ai.available(s):
            return
        if ai.used_today(db) >= s.ai_daily_limit:
            log("  AI: daily limit reached")
            return
        log(f"  AI checking: {r['title']}")
        result = ai.check(db, r, s)
        if result is not None:
            notify.send(s, notify.ai_text(db.get(r["key"]), result))


def pending_ai(db: DB, s: Settings) -> list[Any]:
    q = f"""SELECT * FROM listings WHERE ai IS NULL AND tier IN ({','.join('?' * len(s.ai_tiers))})
            AND last_seen >= datetime('now', '-2 days')"""
    return db.conn.execute(q, s.ai_tiers).fetchall()


def digest(db: DB, s: Settings) -> int:
    rows = db.undigested(["real_good", "good", "mid", "suspect"])
    if rows:
        notify.send(s, notify.digest_text(rows))
        db.mark_digested([r["key"] for r in rows])
    return len(rows)


def run_forever(db: DB, s: Settings, digest_hour: int = 20) -> None:
    while True:
        stamp = datetime.now().strftime("%H:%M")
        try:
            print(f"[{stamp}] polling")
            poll(db, s)
            run_ai(db, pending_ai(db, s), s)
            today = datetime.now().date().isoformat()
            if datetime.now().hour >= digest_hour and db.kv_get("last_digest") != today:
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
