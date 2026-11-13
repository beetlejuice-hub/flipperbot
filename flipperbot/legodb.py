"""LEGO without AI: by set number (lego|75192); sealed sets priced apart (lego|75192 sealed), since a sealed
retired set can be worth double a built one. "Tip LEGO", Lepin, Mould King and other compatible bricks are clones.
"""

from __future__ import annotations

import re

from .techdb import TechMatch, _brand, _w
from .watchdb import Brand

BRANDS: list[Brand] = [Brand("LEGO", "lego", ("lego",))]

# Set numbers: 4-6 digits (old 6080, modern 75192, 10307, 42143); not years, sizes or piece counts.
SET_NO = re.compile(r"(?<![0-9a-z.,])(\d{4,6})(?![0-9]|\s?(?:piese|pcs|buc|lei|ron|cm|mm|kg|ani|ron))")
SEALED = ["sigilat", "sigilata", "sigilate", "nedesfacut", "nedesfacuta", "new sealed", "sealed", "misb", "cutie sigilata"]
THEMES = ["star wars", "technic", "city", "creator", "ideas", "icons", "harry potter", "ninjago", "friends", "marvel",
          "super heroes", "architecture", "speed champions", "minecraft", "duplo", "castle", "pirates", "space"]


def match(title: str, full: str) -> TechMatch | None:
    if not re.search(r"(?<![a-z])lego(?![a-z])", title):
        return None
    for m in SET_NO.finditer(title):
        n = int(m.group(1))
        if 1950 <= n <= 2035 and len(m.group(1)) == 4:
            continue  # a year
        sealed = any(w in title for w in SEALED) or any(w in full for w in SEALED[:5])
        return TechMatch(_brand("lego", "lego"), m.group(1) + (" sealed" if sealed else ""), "lego")
    return TechMatch(_brand("lego", "lego"), "", "lego")  # no set number: too rough to price


BROKEN = ["incomplet", "incompleta", "lipsa piese", "lipsesc piese", "fara instructiuni si fara cutie", "piese lipsa"]
LOCKED: list[str] = []
PART_START = ["minifigurina", "minifigurine", "figurina", "figurine", "instructiuni", "cutie", "piese", "placa", "placi",
              "stand", "vitrina", "lumini", "led", "kit lumini", "set lumini"]
ACCESSORY_ANYWHERE = ["kit lumini", "set lumini", "lumini led pentru", "vitrina pentru", "stand pentru", "doar cutie",
                      "doar instructiuni", "cutie goala"]
CLONES = ["tip lego", "compatibil lego", "compatibil cu lego", "lego compatibil", "similar lego", "asemanator lego",
          "nu este lego", "nu e lego", "lepin", "mould king", "mouldking", "cada", "sembo", "bela", "replica",
          "neoriginal", "neoriginale", "non lego", "gen lego", "stil lego"]
WANTED = ["caut", "cumpar", "cumparam", "achizitionez", "achizitionam"]
SERVICE: list[str] = []
LOT = ["lot lego", "kg lego", "kilograme", "vrac", "piese lego amestecate", "mix lego", "colectie lego"]


def extra_flags(title: str, full: str) -> set[str]:
    return {"lot"} if any(w in title for w in LOT) else set()
