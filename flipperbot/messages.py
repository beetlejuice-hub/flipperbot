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
    "clothing": ["Ce mărime scrie pe eticheta din interior? Îmi puteți trimite poze cu toate etichetele (gât, compoziție, codul)?",
                 "Are pete, găuri sau scame? De unde a fost cumpărată (bon, magazin)?"],
    "bikes": ["Ce mărime are cadrul și ce schimbătoare/frâne are? Când a avut ultima revizie?",
              "Aveți factura sau seria cadrului (e sub pedalier)? O poză cu ea m-ar ajuta."],
    "cool": ["Are ciobituri, fisuri sau alte defecte?",
             "Puteți trimite o poză și cu partea de jos sau din spate (marcaje, semnătură, eticheta)?"],
    "lots": ["Se vinde tot lotul împreună?", "Puteți trimite poze mai de aproape cu obiectele din imagini?"],
}


def _round(x: float) -> int:
    step = 10 if x < 500 else 50 if x < 3000 else 100
    return int(x // step * step)


def offer(row: Any, ai: dict[str, Any] | None, good_profit: int = 150, cut_pct: int | None = None) -> int | None:
    """What to offer: Claude's offer if it gave one; else leave your margin under the low end of the realistic
    sale price; never over the asking price, and never so low it ends the talk: under 60% of it, or, when the bot
    knows how much sellers of this model really drop before selling (cut_pct), much under that drop."""
    price = row["price_ron"]
    if not price:
        return None
    if ai and "error" not in ai and isinstance(ai.get("offer_ron"), (int, float)) and ai["offer_ron"] > 0:
        return min(price, int(ai["offer_ron"]))
    # sellers of this model drop ~cut_pct%: an offer at about twice that is a fair opening, not an insult
    floor = 1 - min(0.4, max(0.1, 2 * cut_pct / 100)) if cut_pct is not None else 0.6
    low = row["est_value_ron"]
    if not low:
        return _round(price * (0.85 if cut_pct is None else max(floor, 1 - (cut_pct + 5) / 100)))
    target = low - good_profit
    return max(_round(price * floor), min(price, _round(target))) if target < price else _round(price * 0.9)


def message(row: Any, ai: dict[str, Any] | None = None, good_profit: int = 150, cut_pct: int | None = None) -> str:
    niche = (row["niche"] if "niche" in row.keys() else None) or "watches"
    title = re.sub(r"\s+", " ", row["title"] or "").strip()[:60]
    asks = []
    if ai and "error" not in ai:
        asks = [str(q).strip() for q in (ai.get("questions_for_seller") or []) if str(q).strip()][:2]
        if ai.get("ask_seller"):
            asks = [str(ai["ask_seller"]).strip()] + asks[:1]
    faulty = "fixer" in row.keys() and bool(row["fixer"])
    if not asks and faulty:
        # faulty: what's wrong decides whether it's a 150-lei fix or a dead board
        asks = ["Ce anume nu funcționează exact și de când? Ce s-a întâmplat înainte (a căzut, s-a udat)?",
                "A fost deschis sau dus la reparat până acum?"]
    asks = asks or QUESTIONS.get(niche, QUESTIONS["watches"])
    o = offer(row, ai, good_profit, cut_pct)
    lines = [f"Bună ziua! Mai este disponibil anunțul „{title}”?", *asks]
    if o and row["price_ron"] and o < row["price_ron"]:
        lines.append(f"Dacă totul e în regulă, v-aș oferi {o} lei, cu ridicare personală sau plata la livrare.")
    lines.append("Mulțumesc!")
    return "\n".join(lines)


def for_row(row: Any, good_profit: int = 150, cut_pct: int | None = None) -> str | None:
    """The message for a listing worth writing to (score 5+), or None."""
    if (row["score"] or 0) < 5:
        return None
    try:
        ai = json.loads(row["ai"]) if row["ai"] else None
    except (TypeError, ValueError):
        ai = None
    return message(row, ai, good_profit, cut_pct)
