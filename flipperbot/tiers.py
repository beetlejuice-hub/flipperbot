"""Decide how good a listing is: bad, suspect, mid, good or real_good.

- bad:       skipped. Fashion brands, replicas, "cumpar" ads, too expensive, too close to market.
- suspect:   a luxury brand far too cheap: probably fake. Goes in the daily summary, flagged.
- mid:       maybe. Goes in the daily summary for a second look, and is re-checked if the price drops.
- good:      clearly under market. Telegram alert, and Claude takes a look.
- real_good: far under market with real profit. Telegram alert first, then Claude.

With enough listings of the same model in the database, "market" is their
median asking price. Until then the brand's segment and the listing's flags
(broken, lot, gold) decide, and the result is mostly mid: worth a look,
not worth an alert.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass

from .config import Settings
from .identify import Identity
from .models import Listing
from .niches import get as niche_of


@dataclass
class Verdict:
    tier: str
    reason: str
    est_value_ron: int | None = None  # realistic sale price, low end (what profit is counted from)
    profit_ron: int | None = None
    est_high_ron: int | None = None  # realistic sale price, high end
    comps: int = 0


def market_price(prices: list[int]) -> int | None:
    """Median after dropping outliers (the 1-leu placeholders and the 99999 dreamers)."""
    if not prices:
        return None
    p = sorted(prices)
    if len(p) >= 5:
        q1, _, q3 = statistics.quantiles(p, n=4)
        iqr = q3 - q1
        p = [x for x in p if q1 - 1.5 * iqr <= x <= q3 + 1.5 * iqr] or p
    return round(statistics.median(p))


def _clean(prices: list[int]) -> list[int]:
    p = sorted(prices)
    if len(p) >= 5:
        q1, _, q3 = statistics.quantiles(p, n=4)
        iqr = q3 - q1
        p = [x for x in p if q1 - 1.5 * iqr <= x <= q3 + 1.5 * iqr] or p
    return p


def percentile(sorted_prices: list[int], q: float) -> float:
    if len(sorted_prices) == 1:
        return sorted_prices[0]
    pos = q * (len(sorted_prices) - 1)
    lo = int(pos)
    hi = min(lo + 1, len(sorted_prices) - 1)
    return sorted_prices[lo] + (sorted_prices[hi] - sorted_prices[lo]) * (pos - lo)


def realistic_range(prices: list[int], exact: bool, sell_cost: float = 0.05) -> tuple[int, int]:
    """What it would realistically sell for, low to high. Listings are asking prices and the ones that
    sell are the cheaper ones, so: from the lower part of the asking prices (35th percentile; 20th when
    only the model family is known, since a family mixes cheap and dear variants) up to the median,
    minus selling costs (fees, shipping)."""
    p = _clean(prices)
    low = percentile(p, 0.35 if exact else 0.20)
    high = percentile(p, 0.50)
    return round(low * (1 - sell_cost)), round(high * (1 - sell_cost))


def repair_cost(ident: Identity, s: Settings) -> int:
    if "broken" in ident.flags:
        costs = s.repair_ron if ident.niche == "watches" else niche_of(ident.niche).repair_ron
        return costs.get(ident.segment or "", 300)
    if "battery" in ident.flags:
        return s.battery_fix_ron
    return 0


def judge(l: Listing, ident: Identity, comps: list[int], s: Settings) -> Verdict:
    price = l.price_ron
    f = ident.flags
    seg = ident.segment
    VALUABLE_SEGMENTS = niche_of(ident.niche).valuable_segments
    noun = niche_of(ident.niche).noun

    # --- not for us ---------------------------------------------------------
    if not price or price < 10:
        return Verdict("bad", "no price")
    if "wanted" in f:
        return Verdict("bad", "someone buying, not selling")
    if "service" in f:
        return Verdict("bad", "repair shop ad")
    if "locked" in f:
        return Verdict("bad", "locked to someone's account (iCloud/Google): stolen or unusable")
    if "replica" in f:
        return Verdict("bad", "says replica/copy")
    if price > s.budget_ron:
        return Verdict("bad", f"over budget ({price} lei)")
    if seg == "fashion" and "lot" not in f and "solid_gold" not in f:
        return Verdict("bad", f"{ident.brand.name}: fashion brand, poor resale")
    if "part" in f and "lot" not in f:
        if seg == "luxury":
            return Verdict("mid", f"{ident.brand.name} part/accessory")
        return Verdict("bad", f"part/accessory, not a {noun}")

    # --- replica seller talk on a luxury/Swiss brand ------------------------------
    if ident.brand_in_title and "naive" not in f and (
        ("fake_signs" in f and seg in ("luxury", "swiss")) or ("shop_talk" in f and seg == "luxury")
    ):
        why = "Japanese/Chinese movement or 'premium quality'" if "fake_signs" in f else "shop talk: many models, gift box"
        return Verdict("suspect", f"{ident.brand.name} sold the way replicas are ({why})")

    # --- too cheap to be real ---------------------------------------------------
    # A luxury name only in the description ("I also have a Rolex", "like an Omega"): no accusation, a look.
    if ident.brand and not ident.brand_in_title and ident.brand.fake_floor_ron and price < ident.brand.fake_floor_ron:
        return Verdict("mid", f"the description mentions {ident.brand.name}, the title doesn't; at {price} lei "
                              "probably a lookalike or another watch. Check the photos")
    if ident.brand and ident.brand_in_title and ident.brand.fake_floor_ron and price < ident.brand.fake_floor_ron:
        why = {"broken", "lot", "vintage", "pocket"} & f
        if why and ident.brand_in_title:
            # A dead vintage Omega or a 1900s Omega pocket watch for 800 lei is plausible. Worth Claude's eyes.
            return Verdict("good", f"{ident.brand.name}, {'/'.join(sorted(why))}, very cheap: real or fake? check photos")
        return Verdict("suspect", f"{ident.brand.name} at {price} lei: likely fake")

    # --- lots ---------------------------------------------------------------------
    if "lot" in f:
        segs = {b.segment for b in ident.brands}
        names = ", ".join(b.name for b in ident.brands) or "no brands named"
        n = f"{ident.lot_count} items" if ident.lot_count else "lot"
        if "solid_gold" in f or segs & {"luxury"}:
            return Verdict("good", f"{n} with {names}{', gold' if 'solid_gold' in f else ''}")
        if segs & (VALUABLE_SEGMENTS | {"soviet"}):
            return Verdict("mid", f"{n} with {names}")
        if ident.lot_count and price / ident.lot_count <= 30:
            return Verdict("mid", f"{n} at {round(price / ident.lot_count)} lei each ({names})")
        # Unnamed old lots are where good watches hide: always a look, and Claude goes through the photos.
        return Verdict("mid", f"{n}, {names}: Claude will go through the photos")

    # --- old, unclear watches: Claude, not the brand's average --------------------------
    # A 1940s Doxa or an inherited watch isn't priced by the average of all Doxas. If only the brand
    # (or nothing) is known and it's old, inherited, a pocket watch, or old and broken, Claude looks.
    model_known = "|" in (ident.model_key or "")
    # A collector reference ("6139", "Flightmaster", "Valjoux") with no price history yet: worth a look.
    if ident.collectible and not model_known and price <= 4000 and "quartz" not in f:
        return Verdict("good", f"{ident.collectible[0]}: collectors pay for these. Check prices / let Claude look")
    old_unclear = not model_known and "quartz" not in f and (
        "naive" in f or "pocket" in f or ("vintage" in f and ("broken" in f or seg in VALUABLE_SEGMENTS))
    )
    if old_unclear and (ident.brand is None or seg in VALUABLE_SEGMENTS | {"soviet", "japan"}) and price <= 2000:
        who = ident.brand.name if ident.brand else "unnamed"
        why = "seller doesn't seem to know what it is" if "naive" in f else f"old {noun}, model unclear"
        return Verdict("good" if seg in VALUABLE_SEGMENTS else "mid", f"{who}: {why}: Claude will look at the photos")

    # --- priced against the market -------------------------------------------------
    market = market_price(comps) if len(comps) >= s.min_comps else None
    if market:
        exact = bool(ident.refs)  # a reference number ("SKX007") vs only a family ("seamaster")
        low, high = realistic_range(comps, exact)
        repair = repair_cost(ident, s)
        profit = low - price - repair  # counted from the cautious end
        discount = 1 - price / market
        what = " ".join(dict.fromkeys((ident.model_key or "?").replace("|", " ").split()))  # "seiko seiko 5" -> "seiko 5"
        detail = (f"{what}: {price} lei, {round(discount * 100)}% under what similar ones ask (~{market}, "
                  f"{len(comps)} listings); realistic sale ~{low}–{high}")
        if repair:
            detail += f", repair ~{repair}"
        v = Verdict("bad", detail, est_value_ron=low, profit_ron=profit, est_high_ron=high, comps=len(comps))
        if discount >= s.real_good_discount and profit >= s.real_good_profit_ron:
            v.tier = "real_good"
        elif discount >= s.good_discount and profit >= s.good_profit_ron:
            v.tier = "good"
        elif discount >= s.mid_discount and profit > 0:
            v.tier = "mid"
        if v.tier in ("good", "real_good") and not ident.brand_in_title:
            v.tier = "mid"
            v.reason += " (brand only named in the description)"
        if v.tier in ("good", "real_good") and seg in ("luxury", "swiss") and discount >= 0.5:
            v.reason += " · this cheap for the brand: make sure it's real"
        if high > 2.5 * max(low, 1):
            # Similar listings range from cheap to dear ("Seamaster": a 90s quartz Polaris and a modern 300M):
            # no honest single price. No number, no alert: Claude or the price-check links say what it's worth.
            if v.tier in ("good", "real_good"):
                v.tier = "mid"
            v.reason = (f"{what}: {price} lei; similar listings range {low}–{high}: models vary too much to price. "
                        "Check prices / let Claude look")
            v.est_value_ron = v.profit_ron = v.est_high_ron = None
            return v
        if "|" not in (ident.model_key or ""):
            # Priced against every listing of the brand: a ladies' quartz Citizen vs all Citizens.
            # Too rough to alert on; a second look is enough.
            if v.tier in ("good", "real_good"):
                v.tier = "mid"
            v.reason += " (brand-level price only, model unknown)"
            v.est_value_ron = v.profit_ron = v.est_high_ron = None  # too rough to show as a number
        return v

    # --- no price history yet -------------------------------------------------------
    if "solid_gold" in f:
        return Verdict("good" if price <= 3000 else "mid", "solid gold case: worth at least the metal")
    if ident.brand is None:
        cheap_interesting = price <= 400 and ({"automatic", "broken"} & f or "vechi" in l.title.lower() or "vintage" in l.title.lower())
        return Verdict("mid" if cheap_interesting else "bad", "no brand named" + (", cheap old/automatic" if cheap_interesting else ""))
    name = ident.brand.name
    if seg == "luxury":
        return Verdict("good" if "broken" in f else "mid", f"{name} at {price} lei, no price history yet")
    if seg in ("swiss", "vintage"):
        cap = 1500 if seg == "swiss" else 800
        if price <= cap:
            return Verdict("mid", f"{name} at {price} lei, no price history yet")
        return Verdict("bad", f"{name} at {price} lei, no price history, not obviously cheap")
    if seg in ("japan", "soviet"):
        if price <= 300 and ({"automatic", "broken", "battery"} & f or ident.family or ident.refs):
            return Verdict("mid", f"{ident.model_key} at {price} lei, no price history yet")
        return Verdict("bad", f"{ident.model_key} at {price} lei, no price history yet")
    return Verdict("bad", f"{name}: nothing stands out")
