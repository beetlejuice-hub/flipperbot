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
    # designer sneakers: the most faked pairs there are
    Brand("Rick Owens", "luxury", ("drkshdw",)), Brand("Maison Margiela", "luxury", ("margiela", "mm6")),
    Brand("Balenciaga", "luxury", ()), Brand("Alexander McQueen", "luxury", ("mcqueen", "alexander mcqueen")),
    Brand("Golden Goose", "luxury", ("ggdb",)), Brand("Common Projects", "luxury", ()), Brand("Off-White", "luxury", ("off white",)),
    Brand("Amiri", "luxury", ()), Brand("Dior", "luxury", ()), Brand("Louis Vuitton", "luxury", ("lv",)),
    Brand("Prada", "luxury", ()), Brand("Gucci", "luxury", ()), Brand("Jil Sander", "luxury", ()), Brand("Lanvin", "luxury", ()),
    Brand("Valentino", "luxury", ()), Brand("Givenchy", "luxury", ()), Brand("Dsquared2", "luxury", ("dsquared",)),
    Brand("Bape", "hype", ("bapesta",)), Brand("Represent", "hype", ()), Brand("Axel Arigato", "basic", ()),
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
    # designer: (pattern, brand, model, segment)
    (_w(r"(?:rick owens\s?)?(geobasket|ramones?|dunks|jumbo laces?|bumper|vintage runner|mega bumper|turbowpn|abstract)"),
     "rick owens", "{1}", "luxury"),
    (_w(r"(?:maison\s)?margiela\s?(?:replica\s|gat\s)?(gat|replica|future|tabi|evolution|50-50)?"), "maison margiela",
     "{1}", "luxury"),
    (_w(r"(?:balenciaga\s)?(triple\s?s|track(?:\s?2)?|speed|runner|defender|3xl|10xl|cargo|x-?pander)"), "balenciaga", "{1}",
     "luxury"),
    (_w(r"(?:alexander\s)?mcqueen(?:\s?oversized)?"), "alexander mcqueen", "oversized", "luxury"),
    (_w(r"golden goose(?:\s?(superstar|super-?star|ball star|mid star|hi star|slide|purestar))?"), "golden goose", "{1}", "luxury"),
    (_w(r"common projects(?:\s?(achilles|bball|retro))?"), "common projects", "{1}", "luxury"),
    (_w(r"off[\s-]?white\s?(out of office|ooo|odsy|vulcanized|low vulc|be right back)"), "off-white", "{1}", "luxury"),
    (_w(r"(?:dior\s)?(b22|b23|b27|b30|b33|b57)"), "dior", "{1}", "luxury"),
    (_w(r"(?:amiri\s)?(skel(?:\s?top)?|ma-?1|bone runner|stadium)"), "amiri", "{1}", "luxury"),
    (_w(r"(?:prada\s)?(america'?s cup|cloudbust|downtown)"), "prada", "{1}", "luxury"),
    (_w(r"(?:gucci\s)?(ace|rhyton|screener|basket)(?=.*gucci)|gucci\s(ace|rhyton|screener|basket)"), "gucci", "{1}{2}", "luxury"),
    (_w(r"(?:louis vuitton|lv)\s?(trainer|skate|run away|archlight|frontrow)"), "louis vuitton", "{1}", "luxury"),
    (_w(r"bape\s?sta|bapesta"), "bape", "bapesta", "hype"),
    (_w(r"(?:vans\s)?(old skool|sk8-?hi|authentic|knu skool)"), "vans", "{1}", "basic"),
]
BRAND_RE = _w(r"(nike|jordan|adidas|yeezy|new balance|asics|salomon|onitsuka|converse|vans|puma|reebok|hoka|on running|"
              r"rick owens|margiela|balenciaga|mcqueen|golden goose|common projects|off[\s-]?white|amiri|dior|louis vuitton|"
              r"prada|gucci|jil sander|lanvin|valentino|givenchy|dsquared2?|bape)")
SIZE = _w(r"(?:marime|marimea|masura|nr\.?|size|eu|m)\s?(3[5-9]|4[0-9])(?:[.,](5|33|66))?")


_BY_LOWER = {b.name.lower(): b for b in BRANDS}


def _named(name: str, seg: str):
    b = _BY_LOWER.get(name)
    return b if b and b.segment == seg else _brand(name, seg) if name not in _BY_LOWER else Brand(_BY_LOWER[name].name, seg)


def clean(title: str) -> str:
    """Margiela's "Replica" is the name of a real line (the GAT trainer), not a confession."""
    from .techdb import clean as tech_clean

    t = tech_clean(title)
    t = re.sub(r"(?<![a-z])(margiela|mm6)(\s+\w+)?\s+(?:gat\s+)?replica(?:\s+gat)?(?![a-z])", r"\1\2 gat", t)
    return re.sub(r"(?<![a-z])replica\s+gat(?![a-z])", "gat", t)


def match(title: str, full: str) -> TechMatch | None:
    hits = [(m.start(), i, m) for i, (p, *_r) in enumerate(MODELS) for m in [p.search(title)] if m]
    if hits:
        _, i, m = min(hits)
        _p, brand, model, seg = MODELS[i]
        name = model.format(*([m.group(0)] + [g or "" for g in m.groups()])).strip()
        name = re.sub(r"\s+", " ", name.replace("-", "")).replace("xt6", "xt 6").replace("xt4", "xt 4")
        return TechMatch(_named(brand, seg), name, seg)
    b = BRAND_RE.search(title)
    if b:
        name = {"jordan": "nike", "yeezy": "adidas", "onitsuka": "onitsuka tiger", "on running": "on", "margiela": "maison margiela",
                "mcqueen": "alexander mcqueen", "off white": "off-white", "offwhite": "off-white", "dsquared": "dsquared2"}.get(
            b.group(1), b.group(1))
        seg = "luxury" if name in LUXURY else "basic"
        return TechMatch(_named(name, seg), "", seg)
    return None


LUXURY = {"rick owens", "maison margiela", "balenciaga", "alexander mcqueen", "golden goose", "common projects", "off-white",
          "amiri", "dior", "louis vuitton", "prada", "gucci", "jil sander", "lanvin", "valentino", "givenchy", "dsquared2"}
# "40 41 42 43 44", "39-45": every size of the pair in stock, a shop (of replicas, for hype and designer pairs)
MANY_SIZES = re.compile(r"(?<![0-9])(3[6-9]|4[0-7])(?:[.,]5)?(?:\s*[,/;\s-]\s*(3[6-9]|4[0-7])(?:[.,]5)?){2,}(?![0-9])"
                        r"|(?<![0-9])(3[6-9]|4[0-3])\s?-\s?(4[2-7])(?![0-9])")


def extra_flags(title: str, full: str) -> set[str]:
    """Replica talk in the description and shop-like listings, like clothes (clothdb), for pairs worth faking."""
    from . import clothdb

    flags: set[str] = set()
    m = match(title, full)
    if any(re.search(rf"(?<![a-z0-9]){re.escape(w)}(?![a-z0-9])", full) for w in clothdb.CLONES_IN_TEXT):
        flags.add("replica")
    if m and m.segment in ("hype", "luxury"):
        if clothdb.PREMIUM_WORD.search(title) or clothdb.split_brand(title):
            flags.add("replica")
        shop = sum(bool(re.search(rf"(?<![a-z0-9]){re.escape(w)}(?![a-z0-9])", full)) for w in clothdb.DEALER) >= 2
        if shop or MANY_SIZES.search(full) or any(
                re.search(rf"(?<![a-z0-9]){re.escape(w)}(?![a-z0-9])", full) for w in clothdb.SHOP_SIZES):
            flags.add("dealer")
    return flags


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


# Below these (lei), a pair of the model is almost never genuine: new ones are replicas, worn ones are suspect.
# Deliberately low, so honest worn pairs aren't caught; Claude's check judges the rest.
FLOORS = {"jordan 4": 350, "jordan 1 high": 300, "jordan 1 mid": 200, "jordan 1 low": 200, "jordan 3": 300, "jordan 11": 300,
          "dunk low": 200, "dunk high": 220, "yeezy 350": 250, "yeezy 700": 250, "yeezy slide": 120, "yeezy foam runner": 150,
          "air max 1": 150, "air max 90": 150, "air max 95": 200, "air max plus": 200, "samba": 150, "gazelle": 130,
          "spezial": 150, "550": 150, "9060": 250, "2002r": 200, "1906r": 200, "990 v6": 300, "gel kayano 14": 200,
          "gel 1130": 180, "xt 6": 300, "mexico 66": 150,
          # designer: worn genuine pairs rarely go under these; new ones far above
          "geobasket": 900, "ramones": 450, "ramone": 450, "dunks": 700, "jumbo laces": 600, "gat": 400, "replica": 400,
          "tabi": 700, "triple s": 900, "track": 700, "speed": 450, "runner": 700, "3xl": 700, "oversized": 400,
          "superstar": 450, "achilles": 500, "out of office": 450, "ooo": 450, "odsy": 500, "b22": 1000, "b23": 900,
          "b30": 700, "skel": 900, "skel top": 900, "ma1": 900, "america's cup": 700, "americas cup": 700, "ace": 500,
          "rhyton": 600, "trainer": 1200, "bapesta": 400}
