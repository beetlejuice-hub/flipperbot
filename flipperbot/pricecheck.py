"""How to look an item's price up: the search words for it and one-click price-check links."""

from __future__ import annotations

import re
from typing import Any

_FILLER = {"ceas", "ceasuri", "barbatesc", "barbati", "dama", "de", "mana", "vand", "vând", "vînd", "original", "nou",
           "stare", "foarte", "buna", "impecabil", "impecabila", "superb", "rar", "pentru", "si", "cu", "la", "in", "-", "–"}


def price_query(r: Any) -> str:
    """What to search to price this watch: the model the bot identified, else the title's key words."""
    return query_for(r["model_key"], r["title"])


def query_for(model_key: str | None, title: str | None) -> str:
    mk = model_key or ""
    if "|" in mk:
        return " ".join(dict.fromkeys(mk.replace("|", " ").split()))
    words = [w for w in re.split(r"[\s,/!.()]+", (title or "").lower()) if w and w not in _FILLER]
    return " ".join(words[:6])


def price_links(r: Any) -> list[list[str]]:
    """Free one-click price checks, no Claude: eBay sold listings (real sale prices), Chrono24 asking
    prices, OLX and Okazii in Romania."""
    from urllib.parse import quote_plus

    q = price_query(r)
    if not q:
        return []
    niche = (r["niche"] if "niche" in r.keys() else None) or "watches"
    # The specialist shop for each kind: Chrono24 for watches, Kamerastore for cameras, eMAG (new price) for electronics.
    shop = {
        "watches": ["Chrono24", f"https://www.chrono24.com/search/index.htm?query={quote_plus(q)}"],
        "cameras": ["Kamerastore", f"https://kamerastore.com/search?q={quote_plus(q)}"],
        "electronics": ["eMAG new", f"https://www.emag.ro/search/{quote_plus(q)}"],
        "phones": ["eMAG new", f"https://www.emag.ro/search/{quote_plus(q)}"],
        "tools": ["eMAG new", f"https://www.emag.ro/search/{quote_plus(q)}"],
        "lego": ["BrickLink", f"https://www.bricklink.com/v2/search.page?q={quote_plus(q.replace('lego ', '').replace(' sealed', ''))}"],
        "sneakers": ["StockX", f"https://stockx.com/search?s={quote_plus(q)}"],
    }.get(niche)
    return [
        ["eBay sold", f"https://www.ebay.com/sch/i.html?_nkw={quote_plus(q)}&LH_Sold=1&LH_Complete=1"],
        *([shop] if shop else []),
        ["OLX", f"https://www.olx.ro/oferte/q-{quote_plus(q.replace(' ', '-'))}/"],
        ["Okazii", f"https://www.google.com/search?q={quote_plus('site:okazii.ro ' + q)}"],
    ]


