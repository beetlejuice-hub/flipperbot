"""A ready message to the seller for a good find: hello, is it available, the questions that matter for this
kind of item, and an offer. In Romanian, short and polite: you copy it into OLX's chat.

Claude's check, when it ran, supplies its own questions and offer; otherwise the questions come from the
category and the offer from the bot's estimate (your margin below the realistic sale price, never insulting).
"""

from __future__ import annotations

import json
import re
from typing import Any

QUESTIONS = {
    "watches": ["Funcționează și ține ora corect?", "Puteți trimite o poză cu capacul din spate (și cu mecanismul, dacă se poate)?"],
    "cameras": ["Ați testat declanșatorul la toate vitezele?",
                "Are ciuperci, ceață sau zgârieturi pe lentile? O poză prin obiectiv spre o lumină m-ar ajuta."],
    "electronics": ["Funcționează perfect și e resetată, fără cont pe ea?", "Aveți factura sau cutia? O poză cu ea pornită?"],
    "phones": ["Este decodat și scos din iCloud / contul Google?", "Ce procent are bateria? O poză cu Setări > Despre?"],
    "tools": ["Merge fără probleme? Un video scurt cu ea pornită?", "Câți acumulatori (ce Ah) și încărcător are?"],
    "lego": ["Este complet, cu minifigurinele, instrucțiunile și cutia?", "Sau e sigilat? O poză cu cutia din toate părțile?"],
    "sneakers": ["Ce mărime scrie pe eticheta din interior?", "Aveți cutia originală sau bonul? Poze cu talpa și eticheta?"],
    "lots": ["Se vinde tot lotul împreună?", "Puteți trimite poze mai de aproape cu obiectele din imagini?"],
}


def _round(x: float) -> int:
    step = 10 if x < 500 else 50 if x < 3000 else 100
    return int(x // step * step)


def offer(row: Any, ai: dict[str, Any] | None, good_profit: int = 150) -> int | None:
    """What to offer: Claude's offer if it gave one; else leave your margin under the low end of the realistic
    sale price; never under 60% of the asking price (an insulting offer ends the talk), never over it."""
    price = row["price_ron"]
    if not price:
        return None
    if ai and "error" not in ai and isinstance(ai.get("offer_ron"), (int, float)) and ai["offer_ron"] > 0:
        return min(price, int(ai["offer_ron"]))
    low = row["est_value_ron"]
    if not low:
        return _round(price * 0.85)
    target = low - good_profit
    return max(_round(price * 0.6), min(price, _round(target))) if target < price else _round(price * 0.9)


def message(row: Any, ai: dict[str, Any] | None = None, good_profit: int = 150) -> str:
    niche = (row["niche"] if "niche" in row.keys() else None) or "watches"
    title = re.sub(r"\s+", " ", row["title"] or "").strip()[:60]
    asks = []
    if ai and "error" not in ai:
        asks = [str(q).strip() for q in (ai.get("questions_for_seller") or []) if str(q).strip()][:2]
        if ai.get("ask_seller"):
            asks = [str(ai["ask_seller"]).strip()] + asks[:1]
    asks = asks or QUESTIONS.get(niche, QUESTIONS["watches"])
    o = offer(row, ai, good_profit)
    lines = [f"Bună ziua! Mai este disponibil anunțul „{title}”?", *asks]
    if o and row["price_ron"] and o < row["price_ron"]:
        lines.append(f"Dacă totul e în regulă, v-aș oferi {o} lei, cu ridicare personală sau plata la livrare.")
    lines.append("Mulțumesc!")
    return "\n".join(lines)


def for_row(row: Any, good_profit: int = 150) -> str | None:
    """The message for a listing worth writing to (score 5+), or None."""
    if (row["score"] or 0) < 5:
        return None
    try:
        ai = json.loads(row["ai"]) if row["ai"] else None
    except (TypeError, ValueError):
        ai = None
    return message(row, ai, good_profit)
