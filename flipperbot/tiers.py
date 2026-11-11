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
from .watchdb import VALUABLE_SEGMENTS


@dataclass
class Verdict:
    tier: str
    reason: str
    est_value_ron: int | None = None  # what it would sell for, working
    profit_ron: int | None = None
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


def repair_cost(ident: Identity, s: Settings) -> int:
    if "broken" in ident.flags:
        return s.repair_ron.get(ident.segment or "", 300)
    if "battery" in ident.flags:
        return s.battery_fix_ron
    return 0


def judge(l: Listing, ident: Identity, comps: list[int], s: Settings) -> Verdict:
    price = l.price_ron
    f = ident.flags
    seg = ident.segment

    # --- not for us ---------------------------------------------------------
    if not price or price < 10:
        return Verdict("bad", "no price")
    if "wanted" in f:
        return Verdict("bad", "someone buying, not selling")
    if "service" in f:
        return Verdict("bad", "repair shop ad")
    if "replica" in f:
        return Verdict("bad", "says replica/copy")
    if price > s.budget_ron:
        return Verdict("bad", f"over budget ({price} lei)")
    if seg == "fashion" and "lot" not in f and "solid_gold" not in f:
        return Verdict("bad", f"{ident.brand.name}: fashion brand, poor resale")
    if "part" in f and "lot" not in f:
        if seg == "luxury":
            return Verdict("mid", f"{ident.brand.name} part/accessory")
        return Verdict("bad", "part/accessory, not a watch")

    # --- too cheap to be real ---------------------------------------------------
    if ident.brand and ident.brand.fake_floor_ron and price < ident.brand.fake_floor_ron:
        why = {"broken", "lot", "vintage", "pocket"} & f
        if why and ident.brand_in_title:
            # A dead vintage Omega or a 1900s Omega pocket watch for 800 lei is plausible. Worth Claude's eyes.
            return Verdict("good", f"{ident.brand.name}, {'/'.join(sorted(why))}, very cheap: real or fake? check photos")
        return Verdict("suspect", f"{ident.brand.name} at {price} lei: likely fake")

    # --- lots ---------------------------------------------------------------------
    if "lot" in f:
        segs = {b.segment for b in ident.brands}
        names = ", ".join(b.name for b in ident.brands) or "no brands named"
        n = f"{ident.lot_count} watches" if ident.lot_count else "lot"
        if "solid_gold" in f or segs & {"luxury"}:
            return Verdict("good", f"{n} with {names}{', gold' if 'solid_gold' in f else ''}")
        if segs & (VALUABLE_SEGMENTS | {"soviet"}):
            return Verdict("mid", f"{n} with {names}")
        if ident.lot_count and price / ident.lot_count <= 30:
            return Verdict("mid", f"{n} at {round(price / ident.lot_count)} lei each ({names})")
        return Verdict("mid" if price <= 500 else "bad", f"{n}, {names}")

    # --- priced against the market -------------------------------------------------
    market = market_price(comps) if len(comps) >= s.min_comps else None
    if market:
        resale = round(market * s.resale_haircut)
        repair = repair_cost(ident, s)
        profit = resale - price - repair
        discount = 1 - price / market
        what = (ident.model_key or "?").replace("|", " ")
        detail = f"{what}: {price} lei vs market ~{market} ({len(comps)} listings), {round(discount * 100)}% under"
        if repair:
            detail += f", repair ~{repair}"
        v = Verdict("bad", detail, resale, profit, len(comps))
        if discount >= s.real_good_discount and profit >= s.real_good_profit_ron:
            v.tier = "real_good"
        elif discount >= s.good_discount and profit >= s.good_profit_ron:
            v.tier = "good"
        elif discount >= s.mid_discount and profit > 0:
            v.tier = "mid"
        if "|" not in (ident.model_key or ""):
            # Priced against every listing of the brand: a ladies' quartz Citizen vs all Citizens.
            # Too rough to alert on; a second look is enough.
            if v.tier in ("good", "real_good"):
                v.tier = "mid"
            v.reason += " (brand-level price only, model unknown)"
            v.est_value_ron = v.profit_ron = None  # too rough to show as a number
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
