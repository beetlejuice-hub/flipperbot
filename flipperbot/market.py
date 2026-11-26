"""What sold, for how much, and how fast: the hard evidence, turned into advice.

Every listing the bot sees disappear as sold (bot.check_sold) leaves its last price, how long it was up, and its
price history (what the seller first asked). Per model that says:
- what it really sells for (the middle and the range of sold prices),
- how fast (days from posting to gone), and what the quick sales went for,
- how much sellers drop before it sells (first ask vs last price),
- whether prices are rising or falling (the last month vs the months before),
- so what to ask when you resell it, and how long to expect to wait.
For models with too few sales, the brand's sales in the category give at least the speed.
"""

from __future__ import annotations

import json
import statistics
from typing import Any

from .db import DB, _days_between, now

DAYS = 120
_BAD = {"broken", "lot", "replica", "part", "wanted", "service", "battery", "dealer", "not_mens", "fast_fashion"}


def _rows(db: DB, where: str, args: list[Any], used_only: bool) -> list[dict[str, Any]]:
    rows = db.conn.execute(
        f"""SELECT key, price_ron, gone_at, flags, COALESCE(orig_created_at, NULLIF(created_at, ''), first_seen) AS since,
                   (SELECT p.price_ron FROM prices p WHERE p.key = l.key ORDER BY p.seen_at LIMIT 1) AS first_price
            FROM listings l WHERE {where} AND gone_reason = 'sold' AND price_ron > 0
            AND gone_at >= datetime('now', '-{DAYS} days') {"AND COALESCE(business, 0) = 0" if used_only else ""}""",
        args).fetchall()
    out = []
    for r in rows:
        flags = set(json.loads(r["flags"] or "[]"))
        if flags & _BAD or (used_only and "new" in flags):
            continue
        out.append({"price": r["price_ron"], "days": max(0.0, _days_between(r["since"], r["gone_at"])),
                    "first": r["first_price"] or r["price_ron"], "gone_at": r["gone_at"]})
    return out


def _pct(p: list[float], q: float) -> float:
    p = sorted(p)
    return p[min(len(p) - 1, max(0, round(q * (len(p) - 1))))]


def summary(db: DB, model_key: str | None, used_only: bool = True, niche: str | None = None) -> dict[str, Any] | None:
    """The market for a model from its sales: None with no sales. With fewer than 3 of the model, the brand's sales in
    the category give the speed (brand_wide)."""
    if not model_key or "|" not in model_key:
        return None
    sales = _rows(db, "model_key = ?", [model_key], used_only)
    out: dict[str, Any] = {"model": model_key}
    if sales:
        prices = [s["price"] for s in sales]
        days = [s["days"] for s in sales]
        out.update(n=len(sales), median=round(statistics.median(prices)), low=round(_pct(prices, 0.25)),
                   high=round(_pct(prices, 0.75)), days=round(statistics.median(days)))
        quick = [s["price"] for s in sales if s["days"] <= 7]
        if len(quick) >= 2:
            out["quick_price"] = round(statistics.median(quick))  # what the ones that went within a week sold at
        cuts = [(s["first"] - s["price"]) / s["first"] for s in sales if s["first"] and s["first"] >= s["price"]]
        if len(cuts) >= 2:
            out["cut_pct"] = round(100 * statistics.median(cuts))  # how much sellers drop before it sells
        t = now()
        recent = [s["price"] for s in sales if _days_between(s["gone_at"], t) <= 30]
        older = [s["price"] for s in sales if _days_between(s["gone_at"], t) > 30]
        if len(recent) >= 2 and len(older) >= 2:
            out["trend_pct"] = round(100 * (statistics.median(recent) / statistics.median(older) - 1))
        if len(sales) >= 2:
            # Reselling: ask around the upper middle of what sold, expect about the median wait
            out["resell_ask"] = round(_pct(prices, 0.6) / (1 - (out.get("cut_pct", 5) / 100)) / 10) * 10
    if len(sales) < 3:
        brand = model_key.split("|")[0]
        where, args = "model_key LIKE ?", [f"{brand}|%"]
        if niche:
            where, args = where + " AND COALESCE(niche, 'watches') = ?", args + [niche]
        wide = _rows(db, where, args, used_only)
        if len(wide) >= 5:
            out.update(brand_days=round(statistics.median(s["days"] for s in wide)), brand_n=len(wide))
    if len(out) == 1:
        return None
    return out


def line(m: dict[str, Any] | None) -> str:
    """One sentence for a person (the card) or Claude (the prompt)."""
    if not m:
        return ""
    parts = []
    if m.get("n"):
        same = m["low"] == m["high"]
        parts.append(f"{m['n']} sold in the last {DAYS // 30} months at "
                     + (f"~{m['median']}" if same else f"{m['low']}-{m['high']} (middle {m['median']})")
                     + f" lei, usually within ~{m['days']} days")
        if m.get("quick_price"):
            parts.append(f"the ones gone within a week went at ~{m['quick_price']}")
        if m.get("cut_pct"):
            parts.append(f"sellers dropped ~{m['cut_pct']}% from their first price")
        if m.get("trend_pct") and abs(m["trend_pct"]) >= 5:
            parts.append(f"prices {'up' if m['trend_pct'] > 0 else 'down'} {abs(m['trend_pct'])}% this month")
    if m.get("brand_days") is not None:
        parts.append(f"this brand's similar items sell in ~{m['brand_days']} days ({m['brand_n']} sales)")
    return "; ".join(parts)


def hot(db: DB, niches: list[str] | None = None, limit: int = 25, days: int = 60) -> list[dict[str, Any]]:
    """What sells: the models that sold most lately, with how fast, for how much, and what's for sale now."""
    where = f"gone_reason = 'sold' AND gone_at >= datetime('now', '-{days} days') AND model_key LIKE '%|%'"
    args: list[Any] = []
    if niches:
        where += f" AND COALESCE(niche, 'watches') IN ({','.join('?' * len(niches))})"
        args += niches
    models = db.conn.execute(f"""SELECT model_key, MAX(niche) AS niche, COUNT(*) AS n FROM listings WHERE {where}
                                 GROUP BY model_key HAVING n >= 2 ORDER BY n DESC LIMIT ?""", [*args, limit * 2]).fetchall()
    out = []
    for r in models:
        used = r["niche"] in ("electronics", "phones", "tools", "sneakers", "clothing", "bikes")
        m = summary(db, r["model_key"], used_only=used, niche=r["niche"])
        if not m or not m.get("n"):
            continue
        # what's for sale now: working, whole ones (not the parts, broken ones and fakes listed under the model)
        up = [x["price_ron"] for x in db.conn.execute(
            """SELECT price_ron, flags FROM listings WHERE model_key = ? AND gone_at IS NULL AND price_ron > 0
               AND last_seen >= datetime('now', '-3 days') AND COALESCE(tier, '') != 'suspect'""", (r["model_key"],))
              if not set(json.loads(x["flags"] or "[]")) & _BAD]
        cheapest = min(up) if up else None
        m.update(niche=r["niche"], for_sale=len(up), cheapest=cheapest)
        if cheapest and m.get("median"):
            m["cheapest_vs_median_pct"] = round(100 * (cheapest / m["median"] - 1))
        out.append(m)
    # most sales first, then the fastest
    out.sort(key=lambda m: (-m["n"], m["days"]))
    return out[:limit]
