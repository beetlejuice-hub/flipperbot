"""Lajumate.ro: a smaller Romanian classifieds site. Its search page answers plain requests and carries its
listings as page data (Next.js `__NEXT_DATA__`): id, title, description, price, date, city, seller.

Sellers' phone numbers are in that data too: the bot never stores them. Only listing facts are kept.
If Lajumate starts refusing plain requests, this source returns nothing: don't imitate a browser.
"""

from __future__ import annotations

import json
import re
import urllib.parse
import urllib.request
from typing import Any, Callable

from .. import net
from ..models import Listing

SEARCH = "https://lajumate.ro/cauta_{q}.html"
UA = "flipperbot/0.1 (personal price tracker)"


def _get(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with net.urlopen(req, timeout=25) as r:  # the search redirects to a results page
        return r.read().decode("utf-8", "replace")


def _ads(data: Any) -> list[dict[str, Any]]:
    """Every list of ads in the page data (the results, whatever the page calls them)."""
    found: list[dict[str, Any]] = []

    def walk(o: Any, depth: int = 0) -> None:
        if depth > 8:
            return
        if isinstance(o, dict):
            for v in o.values():
                walk(v, depth + 1)
        elif isinstance(o, list):
            if o and isinstance(o[0], dict) and {"id", "title", "slug", "price"} <= set(o[0]):
                found.extend(x for x in o if isinstance(x, dict))
            else:
                for v in o:
                    walk(v, depth + 1)

    walk(data)
    return found


def _price(ad: dict[str, Any], eur_to_ron: float) -> int | None:
    try:
        value = float(ad.get("price") or 0)
    except (TypeError, ValueError):
        return None
    if value <= 0:
        return None
    cur = str(ad.get("currency") or "lei").lower()
    return round(value * eur_to_ron) if cur in ("eur", "euro", "€") else round(value)


def _photo(ad: dict[str, Any]) -> list[str]:
    img = ad.get("mainImage")
    if isinstance(img, dict):
        img = img.get("url") or img.get("src") or img.get("path")
    return [img] if isinstance(img, str) and img.startswith("http") else []


def parse(page: str, eur_to_ron: float = 5.0) -> list[Listing]:
    m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', page, re.S)
    if not m:
        return []
    try:
        data = json.loads(m.group(1))
    except json.JSONDecodeError:
        return []
    out, seen = [], set()
    for ad in _ads(data):
        ad_id = str(ad.get("id") or "")
        if not ad_id or ad_id in seen or not ad.get("title"):
            continue
        seen.add(ad_id)
        user = ad.get("user") if isinstance(ad.get("user"), dict) else {}
        city = ad.get("city") if isinstance(ad.get("city"), dict) else {}
        listed = str(ad.get("listed_at") or ad.get("created_at") or "")
        out.append(Listing(
            source="lajumate", source_id=ad_id, url=f"https://lajumate.ro/ad/{ad.get('slug') or 'anunt'}-{ad_id}",
            title=str(ad["title"]), description=str(ad.get("description") or "")[:3000],
            price_ron=_price(ad, eur_to_ron), city=str(city.get("name") or ""), photos=_photo(ad),
            created_at=listed.replace(" ", "T") if listed else "",
            seller_id=str(user.get("id") or ""), seller_name=str(user.get("name") or ""),  # never the phone
        ))
    return out


def search(query: str, *, eur_to_ron: float = 5.0, get: Callable[[str], str] = _get) -> list[Listing]:
    slug = urllib.parse.quote_plus(query.strip().lower())
    return parse(get(SEARCH.format(q=slug)), eur_to_ron)
