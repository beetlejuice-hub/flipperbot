"""eBay prices for a model, through eBay's official Browse API (free developer keys: `flipperbot ebay-setup`).

It returns what the model is listed for right now on eBay Germany (EUR, the closest big market to
Romania), used, buy-it-now. Those are asking prices: the free API has no sold prices (eBay keeps that
for approved partners), so the range is shaded down the same way as OLX asking prices. Sold prices
are one click away on every card ("eBay sold"), and Claude searches them when it checks a listing.

eBay's own web pages refuse plain requests (403), and the bot doesn't try to get around that.
Results are cached per model for 3 days; at most `ebay_daily_calls` searches a day.
"""

from __future__ import annotations

import base64
import json
import re
import statistics
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date
from typing import Any

from .. import net
from ..config import Settings
from ..db import DB

TOKEN_URL = "https://api.ebay.com/identity/v1/oauth2/token"
SEARCH_URL = "https://api.ebay.com/buy/browse/v1/item_summary/search"
MARKET = "EBAY_DE"
CACHE_DAYS = 3
# Not the watch itself: straps, boxes, parts (English and German titles).
NOT_A_WATCH = re.compile(
    r"(?<![a-z])(strap|band|armband|bracelet|uhrenarmband|box|case only|empty box|leerbox|parts|ersatzteil|teile|"
    r"dial only|zifferblatt|bezel|lunette|lünette|crown|krone|glass|glas|buckle|schließe|schliesse|clasp|link|"
    r"glied|movement only|werk|uhrwerk|manual|anleitung|poster|catalog|katalog)(?![a-z])",
    re.I,
)


def enabled(s: Settings) -> bool:
    return bool(s.ebay_client_id and s.ebay_client_secret)


def _token(db: DB, s: Settings) -> str:
    cached = db.kv_get("ebay_token") or {}
    if cached.get("token") and cached.get("expires", 0) > time.time() + 60:
        return cached["token"]
    basic = base64.b64encode(f"{s.ebay_client_id}:{s.ebay_client_secret}".encode()).decode()
    body = urllib.parse.urlencode({"grant_type": "client_credentials", "scope": "https://api.ebay.com/oauth/api_scope"}).encode()
    req = urllib.request.Request(TOKEN_URL, data=body, headers={
        "Authorization": f"Basic {basic}", "Content-Type": "application/x-www-form-urlencoded"})
    with net.urlopen(req, timeout=20) as r:
        data = json.loads(r.read())
    db.kv_set("ebay_token", {"token": data["access_token"], "expires": time.time() + int(data.get("expires_in", 7200))})
    return data["access_token"]


def _search_api(db: DB, s: Settings, query: str) -> list[dict[str, Any]]:
    params = {"q": query, "limit": "50", "filter": "buyingOptions:{FIXED_PRICE},conditions:{USED}"}
    req = urllib.request.Request(f"{SEARCH_URL}?{urllib.parse.urlencode(params)}", headers={
        "Authorization": f"Bearer {_token(db, s)}", "X-EBAY-C-MARKETPLACE-ID": MARKET, "Accept": "application/json"})
    with net.urlopen(req, timeout=20) as r:
        return json.loads(r.read()).get("itemSummaries") or []


def summarize(items: list[dict[str, Any]], eur_to_ron: float, sell_cost: float = 0.15) -> dict[str, Any] | None:
    """Realistic range in lei from eBay asking prices: lower quartile to median, minus ~15% (asking vs
    selling, fees, shipping to Romania). None with fewer than 4 usable listings."""
    prices = []
    for it in items:
        if NOT_A_WATCH.search(it.get("title") or ""):
            continue
        price = it.get("price") or {}
        try:
            value = float(price.get("value"))
        except (TypeError, ValueError):
            continue
        if price.get("currency") == "EUR" and value > 0:
            prices.append(value * eur_to_ron)
    if len(prices) < 4:
        return None
    prices.sort()
    q1 = statistics.quantiles(prices, n=4)[0]
    med = statistics.median(prices)
    return {"n": len(prices), "low": round(q1 * (1 - sell_cost)), "high": round(med * (1 - sell_cost)),
            "median_ask": round(med), "market": MARKET}


def lookup(db: DB, s: Settings, query: str, cached_only: bool = False) -> dict[str, Any] | None:
    """eBay's realistic range for a model query, cached for 3 days. None when not set up, out of the
    day's calls, nothing comparable, or eBay is unreachable (the bot carries on without it)."""
    if not enabled(s) or not query:
        return None
    key = f"ebay:{query.lower()}"
    cached = db.kv_get(key)
    if cached and cached.get("at", 0) > time.time() - CACHE_DAYS * 86400:
        return cached.get("summary")
    if cached_only:
        return None
    calls_key = f"ebay_calls:{date.today().isoformat()}"
    if db.kv_get(calls_key, 0) >= s.ebay_daily_calls:
        return None
    db.kv_set(calls_key, db.kv_get(calls_key, 0) + 1)
    try:
        summary = summarize(_search_api(db, s, query), s.eur_to_ron)
    except (urllib.error.URLError, OSError, ValueError, KeyError):
        return None
    db.kv_set(key, {"at": time.time(), "summary": summary})
    return summary
