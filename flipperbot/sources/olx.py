"""OLX.ro through the JSON API its own web pages use (/api/v1/offers/).

Why not parse the HTML like the two OLX repos you linked? Both read the page
markup: kjanus03 by `data-cy="l-card"` and heading tags (it's built for
olx.pl), mirelconstantin by generated CSS class names like `css-qfzx1y` that
change whenever OLX rebuilds its site. The JSON API gives the same listings
with structured fields (exact price and currency, "price dropped from", the
full photo list, location, seller, OLX delivery) and no markup to break.

Run from home, slowly: OLX refuses requests from cloud servers (we got 403
from one), and a home connection polling every few minutes looks like what
it is, one person browsing.
"""

from __future__ import annotations

import html
import json
import re
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Iterator

from ..models import Listing

API = "https://www.olx.ro/api/v1/offers/"
PAGE_SIZE = 40  # OLX caps a page at 50
USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0 Safari/537.36"


class Blocked(RuntimeError):
    """OLX said no (403/429). Back off for a while instead of retrying."""


def _get(url: str, timeout: float = 25) -> dict[str, Any]:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/json",
            "Accept-Language": "ro-RO,ro;q=0.9,en;q=0.8",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        if e.code in (403, 429):
            raise Blocked(f"OLX answered {e.code} for {url}") from e
        raise


def search_url(
    query: str | None = None,
    *,
    category_id: str | None = None,
    offset: int = 0,
    limit: int = PAGE_SIZE,
    max_price: int | None = None,
    newest_first: bool = True,
) -> str:
    params: dict[str, Any] = {"offset": offset, "limit": limit}
    if query:
        params["query"] = query
    if category_id:
        params["category_id"] = category_id
    if newest_first:
        params["sort_by"] = "created_at:desc"
    if max_price:
        params["filter_float_price:to"] = max_price
    return API + "?" + urllib.parse.urlencode(params)


def search(
    query: str | None = None,
    *,
    category_id: str | None = None,
    pages: int = 1,
    max_price: int | None = None,
    eur_to_ron: float = 5.0,
    fetch=_get,
) -> Iterator[Listing]:
    """Newest listings for a search, page by page. `fetch` is swappable for tests."""
    for page in range(pages):
        data = fetch(search_url(query, category_id=category_id, offset=page * PAGE_SIZE, max_price=max_price))
        offers = data.get("data") or []
        for offer in offers:
            listing = parse_offer(offer, eur_to_ron=eur_to_ron)
            if listing:
                yield listing
        if len(offers) < PAGE_SIZE or not (data.get("links") or {}).get("next"):
            break


# --------------------------------------------------------------------------
# Parsing


_TAG = re.compile(r"<[^>]+>")


def _text(s: str | None) -> str:
    s = re.sub(r"<br\s*/?>", "\n", s or "", flags=re.I)
    return html.unescape(_TAG.sub(" ", s)).strip()


def _photo(p: dict[str, Any]) -> str | None:
    link = p.get("link")
    if not link:
        return None
    return link.replace("{width}", "1000").replace("{height}", "1000")


def _to_ron(value: Any, currency: str, eur_to_ron: float) -> int | None:
    try:
        v = float(value)
    except (TypeError, ValueError):
        return None
    if v <= 0:
        return None
    cur = (currency or "RON").upper()
    if cur in ("EUR", "€"):
        v *= eur_to_ron
    elif cur not in ("RON", "LEI"):
        return None
    return round(v)


def parse_offer(offer: dict[str, Any], *, eur_to_ron: float = 5.0) -> Listing | None:
    if offer.get("offer_type") not in (None, "offer"):
        return None  # "buy" ads: someone wanting to buy
    params = {p.get("key"): p for p in offer.get("params") or [] if isinstance(p, dict)}

    price = currency = None
    price_ron = prev_ron = None
    negotiable = False
    pv = (params.get("price") or {}).get("value") or {}
    if pv:
        price = pv.get("value")
        currency = pv.get("currency") or "RON"
        negotiable = bool(pv.get("negotiable"))
        price_ron = _to_ron(price, currency, eur_to_ron)
        prev_ron = _to_ron(pv.get("previous_value"), currency, eur_to_ron)

    state = ((params.get("state") or {}).get("value") or {}).get("key") or ""
    loc = offer.get("location") or {}
    user = offer.get("user") or {}
    delivery = ((offer.get("delivery") or {}).get("rock") or {}).get("active")

    return Listing(
        source="olx",
        source_id=str(offer.get("id")),
        url=offer.get("url") or "",
        title=(offer.get("title") or "").strip(),
        description=_text(offer.get("description")),
        price=price,
        currency=currency or "RON",
        price_ron=price_ron,
        negotiable=negotiable,
        previous_price_ron=prev_ron,
        city=((loc.get("city") or {}).get("name")) or "",
        region=((loc.get("region") or {}).get("name")) or "",
        photos=[u for u in (_photo(p) for p in offer.get("photos") or []) if u],
        created_at=offer.get("created_time") or "",
        refreshed_at=offer.get("last_refresh_time") or "",
        seller_id=str(user.get("id") or ""),
        seller_name=user.get("name") or "",
        business=bool(offer.get("business")),
        delivery=bool(delivery),
        condition=state,
        category_id=str((offer.get("category") or {}).get("id") or ""),
        params={
            k: (v.get("value") or {}).get("label") if isinstance(v.get("value"), dict) else v.get("value")
            for k, v in params.items()
            if k != "price"
        },
    )
