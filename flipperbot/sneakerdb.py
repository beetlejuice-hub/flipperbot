"""Sneakers without AI: brand + model line (nike|jordan 4, nike|dunk low, new balance|550, adidas|samba).
Size and colourway move the price too, but splitting by them leaves too few listings to compare; the AI check
looks at both. Replicas are everywhere: "calitate premium", "1:1", "UA", "cutie + eticheta" at a third of the price.
"""

from __future__ import annotations

import re

from .techdb import TechMatch, _brand, _w
from .watchdb import Brand

BRANDS: list[Brand] = [
    Brand("Nike", "hype", ("jordan", "air jordan")), Brand("Adidas", "hype", ("yeezy",)), Brand("New Balance", "hype", ("nb",)),
    Brand("Asics", "hype", ()), Brand("Salomon", "hype", ()), Brand("Onitsuka Tiger", "hype", ("onitsuka",)),
    Brand("Converse", "basic", ()), Brand("Vans", "basic", ()), Brand("Puma", "basic", ()), Brand("Reebok", "basic", ()),
    Brand("Hoka", "hype", ()), Brand("On", "hype", ("on running", "on cloud")),
]

# (pattern, brand, model, segment): specific first
MODELS: list[tuple[re.Pattern[str], str, str, str]] = [
    (_w(r"(?:air\s)?jordan\s?(?:air\s|retro\s)?(1)\s?(?:retro\s?)?(?:og\s?)?(high|mid|low)"), "nike", "jordan 1 {2}", "hype"),
    (_w(r"(?:air\s)?jordan\s?(?:air\s|retro\s)?(\d{1,2})(?:\s?retro)?"), "nike", "jordan {1}", "hype"),
    (_w(r"(?:nike\s)?(?:sb\s)?dunk\s?(?:sb\s)?(low|high)"), "nike", "dunk {1}", "hype"),
    (_w(r"(?:nike\s)?(?:sb\s)?dunk(?:\s?sb)?"), "nike", "dunk low", "hype"),  # a Dunk without low/high is nearly always a low
    (_w(r"air\s?force\s?1|af1"), "nike", "air force 1", "basic"),
    (_w(r"air\s?max\s?(1|90|95|97|plus|270|720|dn|scorpion|200)"), "nike", "air max {1}", "hype"),
    (_w(r"(?:nike\s)?(?:air\s?max\s)?tn|air\s?max\s?tn"), "nike", "air max plus", "hype"),  # TN = Air Max Plus
    (_w(r"(?:nike\s)?(?:vomero\s?5|p-?6000|cortez|blazer|v2k)"), "nike", "{0}", "basic"),
    (_w(r"yeezy\s?(?:boost\s?)?(350|380|500|700|qntm|slide|foam\s?runner|foam)"), "adidas", "yeezy {1}", "hype"),
    (_w(r"(samba|gazelle|spezial|campus\s?00s|campus|superstar|stan smith|forum|sl 72|handball spezial)"), "adidas", "{1}", "hype"),
    (_w(r"(?:new balance|nb)\s?(550|530|574|990\s?v\d|990|991|992|993|2002r|9060|1906r|1906|327|480|740)"), "new balance", "{1}", "hype"),
    (_w(r"(?:asics\s)?gel[\s-]?(kayano\s?14|1130|nyc|lyte\s?iii|lyte\s?3|nimbus\s?\d{1,2}|quantum\s?\d+)"), "asics", "gel {1}", "hype"),
    (_w(r"(?:salomon\s)?(xt-?6|xt-?4|acs pro|speedcross\s?\d?)"), "salomon", "{1}", "hype"),
    (_w(r"(?:onitsuka\s)?(?:tiger\s)?mexico\s?66"), "onitsuka tiger", "mexico 66", "hype"),
    (_w(r"(?:converse\s)?chuck\s?(?:taylor\s?)?(70|all star)"), "converse", "chuck {1}", "basic"),
    (_w(r"(?:vans\s)?(old skool|sk8-?hi|authentic|knu skool)"), "vans", "{1}", "basic"),
]
BRAND_RE = _w(r"(nike|jordan|adidas|yeezy|new balance|asics|salomon|onitsuka|converse|vans|puma|reebok|hoka|on running)")
SIZE = _w(r"(?:marime|marimea|masura|nr\.?|size|eu|m)\s?(3[5-9]|4[0-9])(?:[.,](5|33|66))?")


def match(title: str, full: str) -> TechMatch | None:
    hits = [(m.start(), i, m) for i, (p, *_r) in enumerate(MODELS) for m in [p.search(title)] if m]
    if hits:
        _, i, m = min(hits)
        _p, brand, model, seg = MODELS[i]
        name = model.format(*([m.group(0)] + [g or "" for g in m.groups()])).strip()
        name = re.sub(r"\s+", " ", name.replace("-", "")).replace("xt6", "xt 6").replace("xt4", "xt 4")
        return TechMatch(_brand(brand, seg), name, seg)
    b = BRAND_RE.search(title)
    if b:
        name = {"jordan": "nike", "yeezy": "adidas", "onitsuka": "onitsuka tiger", "on running": "on"}.get(b.group(1), b.group(1))
        return TechMatch(_brand(name, "basic"), "", "basic")
    return None


def size(text: str) -> str | None:
    m = SIZE.search(text)
    return f"{m.group(1)}{'.' + m.group(2) if m and m.group(2) else ''}" if m else None


BROKEN = ["rupt", "rupti", "rupte", "dezlipit", "dezlipiti", "talpa uzata", "foarte uzati", "uzati tare", "gauriti", "gaura"]
LOCKED: list[str] = []
PART_START = ["sireturi", "siret", "branturi", "brant", "cutie", "pungi", "spray", "crema", "solutie", "protectie", "tricou",
              "hanorac", "geaca", "pantaloni", "sosete", "sapca", "ghiozdan", "rucsac", "geanta", "jucarie", "breloc"]
ACCESSORY_ANYWHERE = ["doar cutie", "cutie goala", "cutie de", "sireturi pentru", "spray pentru"]
CLONES = ["replica", "copie", "calitate premium", "premium quality", "1:1", "1 la 1", "ua", "unauthorized", "mirror",
          "top quality", "high quality", "first copy", "aaa", "fake", "imitatie", "bootleg", "noi in cutie cu eticheta en gros"]
WANTED = ["caut", "cumpar", "cumparam", "achizitionez", "achizitionam"]
SERVICE = ["curatare", "curatat", "restaurare", "reconditionare", "custom"]
