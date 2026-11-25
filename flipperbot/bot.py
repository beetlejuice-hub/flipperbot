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
    if n.key == "lots":
        from .lots import prefilter

        return prefilter(l.title, l.description, l.price_ron, len(l.photos))[0] > 0
    t = normalize(l.title)
    if any(re.search(rf"(?<![a-z]){re.escape(w)}(?![a-z])", t) for w in n.not_words):
        return False
    if l.source == "olx" and l.category_id in n.categories:
        return True
    if l.source != "olx" and any(re.search(rf"(?<![a-z]){re.escape(w)}(?![a-z])", t) for w in n.strong_words):
        return True  # no categories elsewhere: the word will do
    q = normalize(str(l.params.get("query") or "")) if isinstance(l.params, dict) else ""
    if l.source != "olx" and q and find_brands(l.title, n.key) and all(w in t for w in q.split() if len(w) > 2):
        return True  # found by a search for exactly this ("omega seamaster" -> "Omega Seamaster 300m")
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


# What new (sealed, with tags) adds over a used one, where there aren't enough new ones to compare with.
NEW_UPLIFT = {"electronics": 1.15, "phones": 1.15, "tools": 1.2, "sneakers": 1.3, "clothing": 1.35, "cameras": 1.15,
              "bikes": 1.2}


def evaluate(db: DB, l: Listing, s: Settings, ebay_cached_only: bool = False) -> Any:
    # OLX has its own "brand" field on watch listings; count it as part of the description.
    brand_field = l.params.get("brand") if isinstance(l.params.get("brand"), str) else ""
    ident = identify(l.title, f"{l.description} {brand_field}", l.niche)
    stored = db.get(l.key)
    if stored is not None and stored["model_fix"]:
        ident = apply_model_fix(ident, stored["model_fix"], l.niche)
    # Electronics: a sealed new console asks far more than a used one; compare used with used.
    # (LEGO prices sealed sets as their own model instead; the rest compare a used one with used private listings.)
    used_only = l.niche in ("electronics", "phones", "tools", "sneakers", "clothing", "bikes") and "new" not in ident.flags
    # Catalog categories: a broken one is compared with other broken ones of the model, not with working ones minus
    # a repair guess (a "pentru piese" iPhone isn't a working iPhone minus 400 lei).
    broken_comps = l.niche in ("electronics", "phones", "tools") and "broken" in ident.flags
    comps = db.comparable_prices(ident.model_key, exclude_key=l.key, used_only=used_only, broken=broken_comps) \
        if ident.model_key else []
    sold = db.sold(ident.model_key, used_only=used_only)
    new_note = None
    if "new" in ident.flags and l.niche in NEW_UPLIFT and ident.model_key and "broken" not in ident.flags:
        # New (sealed, with tags) is worth more than used: compared with other new ones, or with used ones plus
        # what new usually adds; the shop price caps it either way (with_retail).
        new_comps = db.comparable_prices(ident.model_key, exclude_key=l.key, new_only=True)
        if len(new_comps) >= s.min_comps:
            comps, sold, new_note = new_comps, [], "new: compared with other new ones"
        else:
            used = db.comparable_prices(ident.model_key, exclude_key=l.key, used_only=True)
            used_sold = db.sold(ident.model_key, used_only=True)
            if len(used) + len(used_sold) >= s.min_comps - 1:
                k = NEW_UPLIFT[l.niche]
                comps = [round(p * k) for p in used]
                sold = [(round(p * k), d) for p, d in used_sold]
                new_note = f"new: used ones +{round((k - 1) * 100)}%"
    broader = None
    if l.niche == "clothing" and ident.brand and len(comps) < s.min_comps and not sold:
        # Few of this line (a Stone Island Ghost jacket): compare with the brand's same kind of item, cautiously.
        from . import clothdb

        kind = clothdb.kind_of(ident.brand, clothdb.clean(normalize(l.title)))
        key = f"{ident.brand.name.lower()}|{kind}" if kind else None
        if key and key != ident.model_key:
            more = db.comparable_prices(key, exclude_key=l.key, used_only=used_only)
            if len(more) >= s.min_comps:
                comps, broader = more, f"{ident.brand.name} {kind}s in general"
    verdict = judge(l, ident, comps, s, db.model_price(ident.model_key), sold=[p for p, _ in sold])
    if broader and verdict.est_value_ron:
        verdict.reason += f" · few of this line for sale: compared with {broader}"
    if new_note and verdict.est_value_ron:
        verdict.reason += f" · {new_note}"
    from . import retail
    from .tiers import with_retail

    # what the model costs new in shops: the ceiling for any second-hand price
    verdict = with_retail(verdict, l.price_ron, retail.get(db, ident.model_key), ident.flags, s.good_profit_ron,
                          s.real_good_profit_ron)
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
    ebay_summary = with_ebay(db, l, ident, verdict, s, ebay_cached_only)
    liq = None
    if "|" in (ident.model_key or ""):  # only a precisely named model says anything about how it sells
        from .tiers import liquidity

        liq = liquidity(db.comparable_ages(ident.model_key, exclude_key=l.key), [d for _, d in sold])
    if liq and verdict.tier in ("good", "real_good") and liq["label"] in ("slow", "very slow"):
        # A cheap buy you can't sell isn't a deal: similar ones sit for months.
        verdict.tier = "mid" if liq["label"] == "very slow" or verdict.tier == "good" else "good"
        verdict.reason = (f"sells {liq['label']}: similar ones have been up ~{liq['median_days']} days, "
                          f"{liq['for_sale']} for sale · " + verdict.reason)
    origin = stored["orig_created_at"] if stored is not None and stored["orig_created_at"] else None
    # A delete-and-post-again keeps its real age: the first time this seller posted the item.
    age = listing_age_days(origin or l.created_at)
    if age is not None and age > s.max_listing_age_days and verdict.tier in ("good", "real_good") and not recent_price_cut(db, l):
        # Up for months and still "cheap"? A real deal would be gone: overpriced, fake, or bait.
        verdict.tier = "mid"
        how = "first posted" if origin else "listed"
        verdict.reason = f"{how} {age} days ago: a real deal wouldn't last that long · " + verdict.reason
    elif age is not None and age > s.max_listing_age_days and verdict.tier in ("good", "real_good"):
        verdict.reason = f"old listing ({age} days), but the price was just cut · " + verdict.reason
    if verdict.tier in ("good", "real_good") and not verdict.est_value_ron:
        # No price to compare with: nobody can call it a good deal yet. A "maybe" for the quick AI read
        # (which estimates a price) or for you, not a good one.
        verdict.tier = "mid"
        verdict.reason = "no price estimate yet · " + verdict.reason
    fixer = fixer_upper(db, l, ident, s)
    if fixer and fixer["odds"] == "low" and verdict.tier in ("good", "real_good"):
        # Cheap, but the fix is a gamble (a dead board, a locked or "for parts" smartwatch): a look, not a deal.
        from .repairs import line

        verdict.tier = "mid"
        verdict.reason = line(fixer) + " · " + verdict.reason
    elif fixer and fixer.get("worth_it") and verdict.tier in ("bad", "mid"):
        # Faulty, but fixed it sells like a working one: worth a look, with the sums.
        from .repairs import line

        verdict.tier = "mid"
        verdict.reason = line(fixer) + " · " + verdict.reason
    db.set_verdict(l.key, ident, verdict)
    from .scoring import rule_score

    rs, rwhy = rule_score(verdict.tier, ident.flags, verdict.reason, verdict.profit_ron, liq, age, s.good_profit_ron)
    if fixer and fixer.get("worth_it"):
        big = fixer["profit_if_fixed"] >= s.real_good_profit_ron
        rs, rwhy = max(rs, 6 if fixer["odds"] == "high" and big else 5 if fixer["odds"] == "high" else 4), \
            f"fixer-upper: ~{fixer['profit_if_fixed']} lei if fixed ({fixer['odds']} odds)"
    db.conn.execute("UPDATE listings SET fixer=? WHERE key=?", (json.dumps(fixer) if fixer else None, l.key))
    if l.niche == "lots" and verdict.tier != "bad":
        from .lots import prefilter

        rs, rwhy, _info = prefilter(l.title, l.description, l.price_ron, len(l.photos))  # the photo look decides more
    db.conn.execute("UPDATE listings SET ebay=?, liquidity=?, rule_score=?, rule_why=? WHERE key=?",
                    (json.dumps(ebay_summary) if ebay_summary else None, json.dumps(liq) if liq else None, rs, rwhy, l.key))
    db.conn.commit()
    db.update_score(l.key)
    return db.get(l.key)


def fixer_upper(db: DB, l: Listing, ident: Any, s: Settings) -> dict | None:
    """A faulty listing: what's probably wrong, the fix, and what it'd be worth fixed (working ones of the model)."""
    from . import repairs
    from .tiers import realistic_range

    if not ident.flags & {"broken", "battery", "worn_shutter"} or not l.price_ron:
        return None
    working = None
    if "|" in (ident.model_key or ""):
        comps = db.comparable_prices(ident.model_key, exclude_key=l.key, used_only=l.niche != "watches")
        comps += [p for p, _d in db.sold(ident.model_key, used_only=l.niche != "watches")] * 2
        if len(comps) >= s.min_comps:
            working = realistic_range(comps, bool(ident.refs))
    text = normalize(f"{l.title} . {l.description}")
    niche = "smartwatches" if l.niche in (None, "watches") and ident.segment in ("smart", "band") else (l.niche or "watches")
    return repairs.assess(niche, text, set(ident.flags), l.price_ron, working, s.good_profit_ron)


def apply_model_fix(ident: Any, model_text: str, niche: str | None) -> Any:
    """The listing's model as Claude named it (from the photos and the whole text), in place of the bot's guess
    from the title. Keeps what the title said about condition (broken, part, sealed...)."""
    fixed = identify(model_text, "", niche)
    if "|" not in (fixed.model_key or ""):
        return ident
    ident.brand, ident.family, ident.refs = fixed.brand, fixed.family, fixed.refs
    ident.focal, ident.lens = fixed.focal, fixed.lens
    if fixed.brand not in ident.brands:
        ident.brands = [fixed.brand, *ident.brands]
    return ident


def fix_model(db: DB, s: Settings, key: str, model_text: str) -> str | None:
    """Claude says the listing is a different model than the bot thought: re-key and re-price it.
    Returns the new model key, or None if the text doesn't name a model the bot knows."""
    row = db.get(key)
    if row is None or not model_text:
        return None
    new = apply_model_fix(identify(row["title"], row["description"] or "", row["niche"]), model_text, row["niche"]).model_key
    if "|" not in (new or "") or new == row["model_key"]:
        return None
    db.conn.execute("UPDATE listings SET model_fix=? WHERE key=?", (model_text[:120], key))
    db.conn.commit()
    evaluate(db, row_to_listing(db.get(key)), s, ebay_cached_only=True)
    return new


def with_ebay(db: DB, l: Listing, ident: Any, verdict: Any, s: Settings, cached_only: bool = False) -> dict | None:
    """When local listings can't price it, ask eBay (Germany, used) for this exact model. The range becomes
    the estimate; at most "good" from eBay alone (an international asking-price market): a Telegram alert
    still needs local data or Claude. Returns eBay's summary for the card, or None."""
    from . import pricecheck
    from .sources import ebay
    from .tiers import repair_cost

    if not ebay.enabled(s) or not ident.brand or ident.segment == "fashion" or not l.price_ron or l.price_ron > s.budget_ron:
        return None
    if ident.flags & {"lot", "wanted", "service", "replica", "part", "modded"} or verdict.tier == "suspect":
        return None
    if "|" not in (ident.model_key or "") and not ident.collectible:
        return None  # "omega" alone: eBay can't price that either
    summary = ebay.lookup(db, s, pricecheck.query_for(ident.model_key, l.title), cached_only=cached_only)
    if not summary or verdict.est_value_ron is not None:
        return summary  # local data already priced it: eBay is shown alongside
    repair = repair_cost(ident, s)
    profit = summary["low"] - l.price_ron - repair
    discount = 1 - l.price_ron / summary["median_ask"]
    verdict.est_value_ron, verdict.est_high_ron, verdict.profit_ron = summary["low"], summary["high"], profit
    note = (f"eBay: {summary['n']} similar listed, realistic ~{summary['low']}–{summary['high']} lei, "
            f"{round(discount * 100)}% under what they ask")
    if discount >= s.good_discount and profit >= s.good_profit_ron:
        verdict.tier = "good"
    elif verdict.tier == "bad" and discount >= s.mid_discount and profit > 0:
        verdict.tier = "mid"
    verdict.reason = note + " · " + verdict.reason
    return summary


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
    keys = list(s.niches)
    if s.niches_per_poll and len(keys) > s.niches_per_poll:
        # Watches and clothing (every_poll) every poll; the other categories take turns.
        always = [k for k in keys if k in s.every_poll]
        rest = [k for k in keys if k not in always]
        start = db.kv_get("niche_cursor", 0) % max(len(rest), 1)
        take = max(s.niches_per_poll - len(always), 1)
        picked = [rest[(start + i) % len(rest)] for i in range(min(take, len(rest)))]
        db.kv_set("niche_cursor", start + len(picked))
        keys = always + picked
    for key in keys:
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
        n_pages = max(pages, s.feed_pages) if cat and not query else pages
        got = list(olx.search(query, category_id=cat, pages=n_pages, eur_to_ron=s.eur_to_ron, pause=s.pause_between_requests_s))
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


MORE_SOURCES = ("publi24", "lajumate")


def poll_more(db: DB, s: Settings, log: Callable[[str], None] = print, sources: dict[str, Callable[..., Any]] | None = None) -> int:
    """Publi24 and Lajumate: a couple of searches per category on each, every `more_sources_every_min`,
    judged like OLX. Each site that fails is skipped this round; the rest go on."""
    if not s.more_sources or time.time() < db.kv_get("more_sources_next_at", 0):
        return 0
    db.kv_set("more_sources_next_at", time.time() + s.more_sources_every_min * 60)
    if sources is None:
        from .sources import lajumate, publi24

        sources = {"publi24": lambda q: publi24.search(q, eur_to_ron=s.eur_to_ron),
                   "lajumate": lambda q: lajumate.search(q, eur_to_ron=s.eur_to_ron)}
    seen = 0
    for key in s.niches:
        n = niches.get(key)
        pool = list(s.search_pool + s.focus_pool) if key == "watches" else list(n.search_pool + n.focus_pool)
        for term in random.sample(pool, min(s.more_sources_terms, len(pool))):
            for name in s.more_sources:
                fetch = sources.get(name)
                if not fetch:
                    continue
                try:
                    got = fetch(term)
                except Exception as e:  # a site down or refusing: skip it this round
                    log(f"  {name} {term!r}: {e!r}"[:160])
                    continue
                for l in got:
                    l.niche = key
                    l.params["query"] = term  # what was searched: lets "Omega Seamaster 300m" count as a watch
                process(db, got, s)
                seen += len(got)
                time.sleep(random.uniform(*s.pause_between_requests_s))
    log(f"  more sources: {seen} listings")
    return seen


def _fresh(db: DB) -> str:
    """Only listings found after the starter price book was loaded can alert or use Claude."""
    return db.kv_get("seeded_at") or "0"


def pending_alerts(db: DB, s: Settings) -> list[Any]:
    """What gets the full Claude check by itself: listings scored 8+ (the quick AI read put them there),
    or, with the quick step off, real good deals. Fresh, not yet checked or decided."""
    rank = "CASE {c} WHEN 'real_good' THEN 4 WHEN 'good' THEN 3 WHEN 'mid' THEN 2 WHEN 'suspect' THEN 1 WHEN 'bad' THEN 0 ELSE -1 END"
    # 8+ from the quick read with a good deal's profit, or a 7 with a real good deal's profit (the quick read is
    # text only and shy of 8s; the full check sees the photos and decides)
    which = ("COALESCE(json_extract(quick, '$.fake_risk'), '') != 'high' AND ("
             f"(json_extract(quick, '$.score') >= 8 AND COALESCE(json_extract(quick, '$.value_low'), 0) - price_ron >= {int(s.good_profit_ron)})"
             f" OR (json_extract(quick, '$.score') >= 7 AND COALESCE(json_extract(quick, '$.value_low'), 0) - price_ron >= {int(s.real_good_profit_ron)}))"
             if s.ai_quick else f"tier IN ({','.join(repr(t) for t in s.alert_tiers)})")
    q = f"""SELECT * FROM listings WHERE ({which}) AND ai IS NULL
            AND {rank.format(c='tier')} >= {rank.format(c='notified_tier')}
            AND notified_tier IS NULL
            AND first_seen >= ? AND last_seen >= datetime('now', '-1 day') AND hidden = 0
            ORDER BY COALESCE(score, 0) DESC, COALESCE(profit_ron, 0) DESC"""
    return db.conn.execute(q, [_fresh(db)]).fetchall()


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


def confirmed(result: dict[str, Any] | None, s: Settings, segment: str | None = None,
              price: int | None = None) -> tuple[bool, str]:
    """Is Claude sure enough about this deal, and does its own math leave a real profit, to message you?
    Luxury/Swiss needs more confidence."""
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
    from .scoring import claude_profit

    profit = claude_profit(result, price)
    if profit is not None and profit < s.good_profit_ron:
        return False, f"only ~{profit} lei profit by Claude's numbers (needs {s.good_profit_ron})"
    return True, ""


def deliver(db: DB, s: Settings, log: Callable[[str], None] = print, extra_ai: int = 1) -> None:
    """Real good deals: Claude reads the listing and photos (real or fake? worth it?). Only the
    ones it confirms (not fake, buy/negotiate, at least alert_min_confidence% sure) go to
    Telegram, as one message with Claude's notes. The rest stay on the dashboard with Claude's
    notes there. A deal Claude can't check yet (daily limit) waits for the next chance.
    Then, with budget left, Claude looks at a good one for the dashboard.

    By default (`ai_auto_real_good`) only real good deals are checked by themselves; with `ai_auto`
    the bot also sends lots, old watches and good deals to Claude."""
    from . import quick

    if s.ai_auto or s.ai_auto_real_good:
        quick.run(db, s, log)  # the cheap read first: it decides what's worth the full check
        from . import lots

        lots.look(db, s, log)  # the best new lots: a cheap look at their photos
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
        claude_value(db, r, result, s)
        row = db.get(r["key"])
        ok, why = confirmed(result, s, row["segment"], row["price_ron"])
        if ok and (row["score"] or 0) < 8:
            ok, why = False, f"Claude's score {row['score']}/10"
        if ok:
            notify.send(s, notify.deal_text(row, result), (json.loads(row["photos"] or "[]") or [None])[0])
            log(f"  sent to Telegram ({row['score']}/10, {confidence(result)}% sure): {row['title']}")
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
            ok, why = confirmed(result, s, row["segment"], row["price_ron"])
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


def reprice_model(db: DB, s: Settings, model_key: str | None, skip: str | None = None) -> int:
    """Judge this model's recent listings again, after Claude found what it really sells for."""
    if not model_key:
        return 0
    rows = db.conn.execute("SELECT * FROM listings WHERE model_key=? AND key IS NOT ? AND last_seen >= datetime('now', '-30 days')",
                           (model_key, skip)).fetchall()
    for r in rows:
        evaluate(db, row_to_listing(r), s, ebay_cached_only=True)
    return len(rows)


def check_sold(db: DB, s: Settings, seller_listings: Callable[..., Any] = olx.seller_listings,
               log: Callable[[str], None] = print) -> dict[str, int]:
    """Which listings are really gone, and why. For a few private sellers whose priced listings the searches
    haven't shown for a while, ask OLX for the seller's listings still up: one missing is gone, and
      expired   if it was up ~4 weeks since its last refresh (OLX ends ads after 30 days unless renewed),
      reposted  if the seller has a new listing of the same item,
      sold      otherwise.
    The sold ones are the price book's best prices: what similar ones really went for, and how fast."""
    # First the listings you'd look at (Interesting: 5+, not decided, not hidden) not confirmed up for 2 hours, so
    # a sold one leaves the list before you click it; then other 5+ ones every 6 hours (their prices stay current);
    # then the rest of the priced private listings once a day, to learn what sold.
    sellers = [r["seller_id"] for r in db.conn.execute(
        """SELECT seller_id FROM listings WHERE source='olx' AND COALESCE(seller_id, '') != '' AND gone_at IS NULL
           AND model_key LIKE '%|%' AND COALESCE(business, 0) = 0 AND last_seen >= datetime('now', '-30 days')
           AND ((COALESCE(score, 0) >= 5 AND hidden = 0 AND triage IS NULL AND last_seen < datetime('now', '-2 hours')
                 AND COALESCE(alive_checked_at, '') < datetime('now', '-2 hours'))
                OR (COALESCE(score, 0) >= 5 AND last_seen < datetime('now', '-6 hours')
                 AND COALESCE(alive_checked_at, '') < datetime('now', '-6 hours'))
                OR (last_seen < datetime('now', '-1 day') AND COALESCE(alive_checked_at, '') < datetime('now', '-1 day')))
           GROUP BY seller_id
           ORDER BY MAX(COALESCE(score, 0) >= 5 AND hidden = 0 AND triage IS NULL) DESC, MAX(COALESCE(score, 0) >= 5) DESC,
                    MAX(last_seen) DESC LIMIT ?""",
        (s.sold_checks_per_poll,))]
    counts = {"sold": 0, "expired": 0, "reposted": 0, "up": 0}
    for i, seller in enumerate(sellers):
        if i:
            time.sleep(random.uniform(*s.pause_between_requests_s))
        for k, n in check_seller(db, s, seller, seller_listings).items():
            counts[k] += n
    if sellers:
        log(f"  still up? {len(sellers)} sellers: {counts['sold']} sold, {counts['expired']} expired, "
            f"{counts['reposted']} reposted, {counts['up']} still up")
    return counts


def check_seller(db: DB, s: Settings, seller: str, seller_listings: Callable[..., Any] = olx.seller_listings,
                 pages: int = 2) -> dict[str, int]:
    """One seller's listings that we know: which are still up (and at what price), which are gone and why."""
    from .db import _days_between, _title_words, now as db_now

    counts = {"sold": 0, "expired": 0, "reposted": 0, "up": 0}
    up, complete = seller_listings(seller, pages=pages, eur_to_ron=s.eur_to_ron, pause=s.pause_between_requests_s)
    ids = {l.source_id for l in up}
    current = {l.source_id: l for l in up}
    t = db_now()
    for r in db.conn.execute("""SELECT * FROM listings WHERE source='olx' AND seller_id=? AND gone_at IS NULL
                                AND last_seen >= datetime('now', '-30 days')""", (seller,)).fetchall():
        if r["source_id"] in ids:
            # still up: store what it says NOW (a new price is re-judged), not just that it's there
            l = current[r["source_id"]]
            l.niche = r["niche"] or "watches"
            process(db, [l], s, alert=True)
            db.conn.execute("UPDATE listings SET last_seen=?, alive_checked_at=? WHERE key=?", (t, t, r["key"]))
            counts["up"] += 1
            continue
        if not complete:
            db.conn.execute("UPDATE listings SET alive_checked_at=? WHERE key=?", (t, r["key"]))
            continue  # a big seller: missing from the first pages proves nothing
        words = _title_words(r["title"])
        again = any(len(words & (w := _title_words(l.title))) / max(1, len(words | w)) >= 0.7 for l in up)
        if again:
            reason = "reposted"
        elif _days_between(r["refreshed_at"] or r["created_at"], t) >= 28:
            reason = "expired"
        else:
            reason = "sold"
        db.conn.execute("UPDATE listings SET gone_at=?, gone_reason=?, alive_checked_at=? WHERE key=?", (t, reason, t, r["key"]))
        counts[reason] += 1
    db.conn.commit()
    return counts


def check_alive(db: DB, s: Settings, key: str, seller_listings: Callable[..., Any] = olx.seller_listings,
                search: Callable[..., Any] = olx.search, fresh_min: int = 15) -> Any:
    """Is this one listing still up? Asked when you open it: its seller's listings (or, with no seller known, a search
    for its title). Not again within fresh_min minutes. Returns the row as it is now (gone_at set if it's gone)."""
    from .db import _days_between, now as db_now

    r = db.get(key)
    if r is None or r["source"] != "olx" or r["gone_at"]:
        return r
    if r["alive_checked_at"] and _days_between(r["alive_checked_at"], db_now()) * 1440 < fresh_min:
        return r
    try:
        if r["seller_id"]:
            check_seller(db, s, r["seller_id"], seller_listings, pages=3)
        else:
            refresh_listing(db, s, key, seller_listings=seller_listings, search=search)
            db.conn.execute("UPDATE listings SET alive_checked_at=? WHERE key=?", (db_now(), key))
            db.conn.commit()
    except Exception:  # OLX not answering: nothing learned
        return db.get(key)
    return db.get(key)


def refresh_listing(db: DB, s: Settings, key: str, seller_listings: Callable[..., Any] = olx.seller_listings,
                    search: Callable[..., Any] = olx.search) -> Any:
    """The listing as it is on OLX now (price, title, photos), from its seller's listings: before Claude judges it,
    so it never judges an old price. Unchanged if it can't be refreshed (not OLX, no seller, OLX not answering)."""
    r = db.get(key)
    if r is None or r["source"] != "olx":
        return r
    try:
        if r["seller_id"]:
            up, _complete = seller_listings(r["seller_id"], pages=1, eur_to_ron=s.eur_to_ron, pause=s.pause_between_requests_s)
        else:  # from the starter price book (no seller kept): find it by its title
            up = list(search(r["title"], pages=1, eur_to_ron=s.eur_to_ron, pause=s.pause_between_requests_s))
    except Exception:
        return r
    l = next((x for x in up if x.source_id == r["source_id"]), None)
    if l is not None:
        l.niche = r["niche"] or "watches"
        process(db, [l], s, alert=False)
    return db.get(key)


def rescore_all(db: DB, s: Settings, log: Callable[[str], None] = print) -> dict[str, int]:
    """Judge and score every stored listing again with today's rules. Returns how many per tier."""
    from .scoring import RULES_VERSION

    rows = db.all()
    for i, r in enumerate(rows, 1):
        l = row_to_listing(r)
        if is_relevant(l):
            evaluate(db, l, s, ebay_cached_only=True)
        else:
            why = f"not a {niches.get(l.niche).noun}"
            db.conn.execute("UPDATE listings SET tier='bad', reason=?, rule_score=0, rule_why=?, score=0, score_why=? WHERE key=?",
                            (why, why, why, l.key))
        if i % 1000 == 0:
            db.conn.commit()
            log(f"  re-judged {i}/{len(rows)}")
    db.conn.commit()
    db.kv_set("rules_version", RULES_VERSION)
    return {r["tier"]: r["n"] for r in db.conn.execute("SELECT tier, COUNT(*) n FROM listings GROUP BY tier")}


def rescore_if_rules_changed(db: DB, s: Settings, log: Callable[[str], None] = print) -> bool:
    """After an update (or on a fresh install) the stored scores may be missing or out of date: redo them once."""
    from .scoring import RULES_VERSION

    if not db.kv_get("publi24_prices_fixed"):
        # Publi24 prices were misread before (the old price after a cut; '2,999' as 999): drop those listings once,
        # the next polls read them again correctly.
        n = db.conn.execute("SELECT COUNT(*) FROM listings WHERE source='publi24'").fetchone()[0]
        db.conn.execute("DELETE FROM prices WHERE key LIKE 'publi24:%'")
        db.conn.execute("DELETE FROM listings WHERE source='publi24'")
        db.conn.commit()
        db.kv_set("publi24_prices_fixed", True)
        if n:
            log(f"Removed {n} Publi24 listings with misread prices; they're read again on the next polls.")
            db.kv_set("rules_version", 0)

    if db.kv_get("rules_version", 0) == RULES_VERSION:
        return False
    n = db.conn.execute("SELECT COUNT(*) FROM listings").fetchone()[0]
    log(f"The rules changed since last time: re-judging {n} stored listings (a minute or two)...")
    rescore_all(db, s, log)
    log("  done")
    return True


def run_forever(db: DB, s: Settings, digest_hour: int = 20) -> None:
    from . import web

    web.serve(s, background=True)
    print(f"flipperbot is running. Dashboard: {web.url(s)}")
    db.beat("starting: re-judging the stored listings with today's rules")
    try:
        rescore_if_rules_changed(db, s)
    except Exception as e:  # never let this stop the bot
        print(f"  re-judging failed: {e!r}")
    while True:
        stamp = datetime.now().strftime("%H:%M")
        started = time.time()
        try:
            print(f"[{stamp}] polling")
            db.beat("searching OLX")
            poll(db, s)
            if facebook_due(db, s):
                db.beat("searching Facebook Marketplace")
                poll_facebook(db, s)
            db.beat("checking the best finds with Claude")
            deliver(db, s)
            try:
                db.beat("searching Publi24 and Lajumate")
                poll_more(db, s)
            except Exception as e:  # never stops the main bot
                print(f"  more sources error: {e!r}")
            try:
                db.beat("checking which listings sold")
                check_sold(db, s)
            except olx.Blocked:
                raise
            except Exception as e:  # never stops the main bot
                print(f"  sold check error: {e!r}")
            try:
                from . import retail

                if retail.due(db, s):
                    db.beat("looking up new prices in shops")
                    retail.look_up(db, s)  # new prices in shops for the most-listed models, once a day
            except Exception as e:  # never stops the main bot
                print(f"  new-price look-up error: {e!r}")
            try:
                from . import radar

                db.beat("trend radar")
                radar.tick(db, s)
            except olx.Blocked:
                raise
            except Exception as e:  # the radar never stops the main bot
                print(f"  radar error: {e!r}")
            today = datetime.now().date().isoformat()
            if s.digest_telegram and datetime.now().hour >= digest_hour and db.kv_get("last_digest") != today:
                n = digest(db, s)
                db.kv_set("last_digest", today)
                print(f"  digest sent: {n}")
            # rounds start every 5-10 minutes from the START of the last one: a long round doesn't add a full wait
            wait = max(60.0, random.uniform(*s.poll_every_min) * 60 - (time.time() - started))
        except olx.Blocked as e:
            print(f"  {e}; waiting {s.blocked_backoff_min} min")
            wait = s.blocked_backoff_min * 60
        except Exception as e:  # network hiccups etc.: log and keep going
            print(f"  error: {e!r}")
            wait = 120
        db.beat("waiting for the next round", until=time.time() + wait)
        time.sleep(wait)
