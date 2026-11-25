"""Bicycles without AI: brand, line, kind of bike, and what sets its price (groupset, frame, wheels).

The flip: buy a decent used bike cheap (a sat-in-the-garage Trek, a Rockrider with a rusty chain), service it,
wash it, add a few accessories, sell it in spring. Priced by brand + line where the line is named
(trek|marlin 7, specialized|rockhopper, rockrider|st 540, cube|aim, canyon|grand canyon), else by brand + kind
(dhs|mtb 26, pegas|city). The groupset (Shimano Deore, SRAM NX...) and a carbon frame are read too: they move the price.

Segments: premium (Specialized, Trek, Canyon, Cannondale, Santa Cruz, Scott, Cube, Giant, Orbea, Bianchi...),
mid (Kellys, Author, CTM, Kross, Merida, Ghost, B'Twin/Rockrider/Triban from Decathlon...), basic (DHS, Velors,
Carpat, no-name), vintage (old steel road bikes: Peugeot, Raleigh, Favorit, old Pegas, Bianchi, Colnago).

Stolen bikes are a real risk: a premium bike far under market, with no invoice or serial, is a warning.
"""

from __future__ import annotations

import re

from .techdb import TechMatch, _w
from .techdb import clean as _tech_clean
from .watchdb import Brand

_B: list[tuple[str, str, tuple[str, ...]]] = [
    # premium
    ("Specialized", "premium", ()), ("Trek", "premium", ()), ("Canyon", "premium", ()), ("Cannondale", "premium", ()),
    ("Santa Cruz", "premium", ()), ("Scott", "premium", ()), ("Cube", "premium", ()), ("Giant", "premium", ()),
    ("Orbea", "premium", ()), ("Bianchi", "premium", ()), ("Pinarello", "premium", ()), ("Cervelo", "premium", ("cervélo",)),
    ("Colnago", "premium", ()), ("BMC", "premium", ()), ("Focus", "premium", ()), ("Lapierre", "premium", ()),
    ("Kona", "premium", ()), ("GT", "premium", ("gt bicycles",)), ("Marin", "premium", ()), ("Rose", "premium", ("rose bikes",)),
    ("YT", "premium", ("yt industries",)), ("Commencal", "premium", ()), ("Rocky Mountain", "premium", ()), ("Felt", "premium", ()),
    ("Ridley", "premium", ()), ("Haibike", "premium", ()), ("Mondraker", "premium", ()), ("Radon", "premium", ()),
    ("Nukeproof", "premium", ()), ("Brompton", "premium", ()), ("Look", "premium", ("look cycle",)), ("Wilier", "premium", ()),
    ("Factor", "premium", ()), ("Ghost", "mid", ()), ("Merida", "mid", ()), ("Fuji", "mid", ()), ("Bulls", "mid", ()),
    # mid: good value, sell steadily
    ("Kellys", "mid", ("kelly's",)), ("Author", "mid", ()), ("CTM", "mid", ()), ("Superior", "mid", ()), ("Kross", "mid", ()),
    ("Rockrider", "mid", ("rock rider", "btwin rockrider", "decathlon rockrider")), ("Triban", "mid", ("btwin triban",)),
    ("Riverside", "mid", ("btwin riverside",)), ("Van Rysel", "mid", ()), ("B'Twin", "mid", ("btwin", "b twin", "b'twin")),
    ("Elops", "mid", ()), ("Polygon", "mid", ()), ("Leader Fox", "mid", ("leaderfox",)), ("Head", "mid", ()), ("Dema", "mid", ()),
    ("Romet", "mid", ()), ("Dahon", "mid", ()), ("Tern", "mid", ()), ("Mongoose", "mid", ()), ("Wethepeople", "mid", ("wtp",)),
    ("Kink", "mid", ()), ("Sunday", "mid", ()), ("Woom", "mid", ()), ("Puky", "mid", ()), ("Early Rider", "mid", ()),
    ("Frog", "mid", ("frog bikes",)), ("Academy", "mid", ()),
    # basic: cheap brands, small margins
    ("DHS", "basic", ()), ("Velors", "basic", ()), ("Carpat", "basic", ()), ("Visitor", "basic", ()), ("Capriolo", "basic", ()),
    ("Kawasaki", "basic", ()), ("Devron", "basic", ()), ("Cross", "basic", ()), ("Sprint", "basic", ()), ("Kands", "basic", ()),
    # vintage: old steel road bikes and Romanian classics, a following of their own
    ("Pegas", "vintage", ("tohan",)), ("Peugeot", "vintage", ()), ("Raleigh", "vintage", ()), ("Motobecane", "vintage", ()),
    ("Gitane", "vintage", ()), ("Favorit", "vintage", ()), ("Diamant", "vintage", ()), ("Ukraina", "vintage", ()),
    ("Salut", "vintage", ()), ("Mercier", "vintage", ()), ("Gazelle", "vintage", ()), ("Batavus", "vintage", ()),
    ("Eddy Merckx", "vintage", ("merckx",)), ("Olmo", "vintage", ()), ("Legnano", "vintage", ()),
]
BRANDS: list[Brand] = []
for _n, _s, _a in _B:
    if not any(b.name == _n for b in BRANDS):
        BRANDS.append(Brand(_n, _s, _a))
_BY_NAME = {b.name: b for b in BRANDS}
_PATTERNS = sorted(((re.compile(r"(?<![a-z0-9])" + re.escape(a) + r"(?![a-z0-9])"), b) for b in BRANDS
                    for a in {b.name.lower(), *b.aliases}), key=lambda p: -len(p[0].pattern))
# Brand names that are ordinary Romanian or English words: only a brand next to a bike word ("bicicleta Cross")
_WORDY = {"Cross", "Look", "Focus", "Rose", "Head", "Academy", "Sprint", "Superior", "Author", "Frog", "Felt", "Factor",
          "Sunday", "Salut", "Scott", "Giant", "Ghost", "Kink", "Marin", "Fuji"}

# Named lines: (brand, pattern, line); the line, not only the brand, sets the price
LINES: list[tuple[str, re.Pattern[str], str]] = [
    ("Trek", _w(r"(marlin|x-?caliber|roscoe|fuel\s?-?e?x|top\s?fuel|remedy|slash|procaliber|supercaliber|domane|emonda|madone|"
                r"checkpoint|fx|dual sport|verve|powerfly|rail|precaliber|wahoo)\s?(\d{1,2}(?:\.\d)?|sl\s?\d|alr\s?\d)?"), "{1} {2}"),
    # old Treks by number: 820, 3700, 4900, 6000 (not a year, a price or a size)
    ("Trek", _w(r"(?!(?:19|20)\d\d(?![0-9]))([3-9]\d{2,3}|8[0-9]0)(?=\s|$)(?!\s?(?:lei|ron|eur|euro|km|kg|cm|w)\b)"), "{1}"),
    ("Specialized", _w(r"(rockhopper|chisel|epic|stumpjumper|enduro|fuse|status|allez|tarmac|roubaix|aethos|diverge|crux|"
                       r"sirrus|turbo\s?levo|turbo\s?vado|jett|riprock|hotrock|pitch)(?:\s?(comp|sport|expert|elite|pro|evo))?"),
     "{1} {2}"),
    ("Canyon", _w(r"(grand\s?canyon|neuron|spectral|strive|lux|exceed|stoic|torque|endurace|ultimate|aeroad|grizl|grail|"
                  r"roadlite|pathlite|commuter)(?:\s?(al|cf)?\s?(\d))?"), "{1} {2}{3}"),
    ("Cube", _w(r"(aim|attention|analog|acid|reaction|stereo|ams|nuroad|attain|agree|kathmandu|touring|nature|access|"
                r"ltd|elite|litening)(?:\s?(race|pro|sl|ex|slx|c:?62|tm|eaz|hybrid))?"), "{1} {2}"),
    ("Scott", _w(r"(aspect|scale|spark|genius|ransom|addict|speedster|contessa|sub cross|sub sport|roxter|voltage)\s?(\d{2,3})?"),
     "{1} {2}"),
    ("Giant", _w(r"(talon|fathom|trance|reign|stance|anthem|xtc|contend|defy|tcr|propel|revolt|escape|roam|toughroad|atx)"
                 r"\s?(\d|sl\s?\d|advanced)?"), "{1} {2}"),
    ("Cannondale", _w(r"(trail|scalpel|habit|jekyll|f-?si|caad\s?\d{1,2}|synapse|supersix|topstone|quick|treadwell)\s?(\d|sl|se)?"),
     "{1} {2}"),
    ("Rockrider", _w(r"(?:rockrider\s)?(st|xc|am|race|e-st|e-expl|expl|ebike)\s?-?(\d{2,3})s?"), "{1} {2}"),
    ("Rockrider", _w(r"rockrider\s?(\d{3})"), "{1}"),
    ("Triban", _w(r"(?:triban\s)?(rc|gravel|grvl)\s?(\d{3})"), "{1} {2}"),
    ("Triban", _w(r"triban\s?(\d{3})"), "{1}"),
    ("Van Rysel", _w(r"(?:van rysel\s)?(edr|ncr|rcr|gravel)\s?(cf|af)?\s?(\d{3})?"), "{1} {2} {3}"),
    ("Riverside", _w(r"(?:riverside\s)?(\d{3})"), "{1}"),
    ("Kellys", _w(r"(spider|tnt|thorx|gibon|hacker|madman|whip|swag|soot|phanatic|cristy|vanity|clea|kiru)\s?(\d{2,3})?"), "{1} {2}"),
    ("Author", _w(r"(solution|traction|outset|stratos|aura|impulse|instinct|ronin|smart)\s?(\d{2,3}|asl)?"), "{1} {2}"),
    ("Merida", _w(r"(big\.?\s?nine|big\.?\s?seven|one-?twenty|one-?forty|ninety-?six|scultura|reacto|silex|matts|crossway)"
                  r"\s?(\d{2,4})?"), "{1} {2}"),
    ("Ghost", _w(r"(kato|lanao|lector|nirvana|riot|asket|lawu|square)\s?(\d{1,2}\.\d|base|essential|advanced)?"), "{1} {2}"),
    ("Kross", _w(r"(level|hexagon|lea|esker|vento|trans|evado)\s?(\d\.\d|\d{1,2})?"), "{1} {2}"),
    ("Marin", _w(r"(bobcat trail|wildcat trail|nail trail|rift zone|san quentin|gestalt|nicasio|four corners|muirwoods|fairfax|"
                 r"larkspur)\s?(\d)?"), "{1} {2}"),
    ("Kona", _w(r"(lana'?i|mahuna|fire mountain|honzo|process|rove|sutra|dew)"), "{1}"),
    ("Orbea", _w(r"(alma|oiz|occam|rallon|laufey|mx\s?\d{2}|orca|avant|terra|vector|carpe)"), "{1}"),
    ("Pegas", _w(r"(practic|strada|popular|drumet|mini drumet|clasic|teren|suprem|hoinar|cursiera|cutezator|soim|ideal)"), "{1}"),
    ("Canyon", _w(r"(sender|torque|spectral|nerve|yellowstone)\s?(al|cf)?\s?(\d)?"), "{1} {2}{3}"),
    ("YT", _w(r"(izzo|jeffsy|capra|tues|decoy)"), "{1}"),
    ("Mondraker", _w(r"(super\s?foxy|foxy|raze|chaser|f-?podium|arid|dune|crafty|level)"), "{1}"),
    ("CTM", _w(r"(rambler|charisma|rein|swift|scroll|zephyr|terra|axon|metric|flynn|tranz|willie|berry|maxima)\s?(\d\.\d)?"), "{1} {2}"),
    ("Elops", _w(r"(?:elops\s)?(\d{3})"), "{1}"),
    ("Bianchi", _w(r"(sprint|oltre|infinito|via nirone|specialissima|aria|impulso|methanol|kuma|magma)"), "{1}"),
    ("Fuji", _w(r"(roubaix|sportif|jari|nevada|absolute|transonic|one\s?\.?\s?\d)"), "{1}"),
    ("Brompton", _w(r"(c\s?line|p\s?line|t\s?line|a\s?line|m\d[a-z]?|s\d[a-z]?|h\d[a-z]?)"), "{1}"),
]

KINDS: list[tuple[str, tuple[str, ...]]] = [
    ("e-bike", ("electrica", "electric", "e-bike", "ebike", "pedelec", "asistata", "cu motor")),
    ("kids", ("copii", "copil", "baieti", "fete", "junior", "kids", "balance", "fara pedale", "echilibru")),
    ("bmx", ("bmx",)),
    ("road", ("cursiera", "cursiere", "road", "sosea", "semicursiera")),
    ("gravel", ("gravel",)),
    ("full suspension", ("full suspension", "full-suspension", "full sus", "fully", "dubla suspensie", "suspensie dubla",
                         "enduro", "downhill", "dh ")),
    ("mtb", ("mtb", "mountain bike", "munte", "hardtail", "cross country", "xc")),
    ("folding", ("pliabila", "pliabil", "folding")),
    ("city", ("oras", "city", "trekking", "dama", "urban", "touring", "hibrid", "hybrid", "cos", "portbagaj")),
    ("fixie", ("fixie", "single speed", "singlespeed", "fixed gear")),
]
_KIND_RES = [(k, [_w(re.escape(w.strip())) for w in words]) for k, words in KINDS]

GROUPSETS = [  # (pattern, name, tier 1-5): what's on it moves the price as much as the brand
    (_w(r"(?:shimano\s)?(xtr|dura[\s-]?ace)"), "{1}", 5), (_w(r"(?:shimano\s)?(xt|ultegra|grx\s?8\d0)"), "{1}", 4),
    (_w(r"(?:shimano\s)?(slx|105|deore|grx)"), "{1}", 3), (_w(r"(?:shimano\s)?(alivio|tiagra|cues)"), "{1}", 2),
    (_w(r"(?:shimano\s)?(acera|altus|sora|claris|tourney)"), "{1}", 1),
    (_w(r"sram\s?(xx1|xx|x0|x01|red|force|axs)"), "sram {1}", 5), (_w(r"sram\s?(gx|rival)"), "sram {1}", 4),
    (_w(r"sram\s?(nx|apex|sx)"), "sram {1}", 2),
]
WHEEL = _w(r"(29|27[.,]5|26|28|24|20|16|14|12|700\s?c?)\s?(?:\"|''|”|inch|inchi|toli|er)?")
FRAME_SIZE = _w(r"(?:cadru|marime|marimea|size|frame)\s?:?\s?(xxs|xs|s|m|l|xl|xxl|\d{2}(?:[.,]5)?\s?(?:cm|\"|inch)?)")
CARBON = _w(r"carbon|carbonn?|full carbon|cadru carbon")


def find_brand(title: str) -> Brand | None:
    hits = []
    for p, b in _PATTERNS:
        for m in p.finditer(title):
            if b.name in _WORDY and not re.search(r"(bicicleta|bicicleta|bike|mtb|cursiera|cadru)", title):
                continue
            hits.append((m.start(), -len(m.group(0)), b.name))
            break
    return _BY_NAME[min(hits)[2]] if hits else None


def kind(title: str) -> str | None:
    hits = [(m.start(), -len(m.group(0)), k) for k, res in _KIND_RES for r in res for m in [r.search(title)] if m]
    # e-bike and kids first: they decide the price class whatever else the title says
    for k in ("e-bike", "kids"):
        if any(h[2] == k for h in hits):
            return k
    return min(hits)[2] if hits else None


def wheel(title: str) -> str | None:
    m = WHEEL.search(title)
    if not m:
        return None
    w = m.group(1).replace(",", ".").replace(" ", "")
    return {"700": "28", "700c": "28"}.get(w, w)


def groupset(text: str) -> tuple[str, int] | None:
    best = None
    for pattern, name, tier in GROUPSETS:
        m = pattern.search(text)
        if m and (best is None or tier > best[1]):
            best = (name.format(*([m.group(0)] + list(m.groups()))).replace("  ", " ").strip(), tier)
    return best


def _line(b: Brand, title: str) -> str:
    for brand, pattern, template in LINES:
        if brand != b.name:
            continue
        m = pattern.search(title)
        if m:
            line = template.format(*([m.group(0)] + [(g or "") for g in m.groups()]))
            return re.sub(r"\s+", " ", line.replace("-", "")).strip()
    return ""


def match(title: str, full: str) -> TechMatch | None:
    b = find_brand(title)
    if not b:
        return None
    line = _line(b, title)
    if line:
        return TechMatch(b, line, b.segment)
    k = kind(title)
    w = wheel(title)
    if k in ("kids", "bmx") or (k and b.segment in ("basic", "mid")):
        return TechMatch(b, f"{k} {w}" if w else k, b.segment)  # a DHS 26" MTB and a DHS 20" kids' bike aren't one price
    if not k and w and b.segment in ("basic", "mid"):
        return TechMatch(b, f"{w} inch", b.segment)  # "Bicicleta DHS 2625 26 inch": a cheap bike of that wheel size
    return TechMatch(b, k or "", b.segment)


def clean(title: str) -> str:
    t = _tech_clean(title)
    return re.sub(r"(?<![a-z])bicicl\w*", "bicicleta", t)


# --- the rest of the catalog interface ---------------------------------------------------------------------------
DAMAGE = ["cadru fisurat", "cadru crapat", "cadru indoit", "fisura cadru", "furca indoita", "janta stramba", "roata stramba",
          "roata acht", "acht", "lant ruginit", "ruginita", "ruginit", "rugina"]
BROKEN = DAMAGE + ["nu merge", "necesita reparatii", "necesita revizie", "necesita service", "de reparat", "pentru piese",
                   "defecta", "defect", "nu schimba", "nu schimba vitezele", "nu franeaza", "frane defecte", "frana defecta",
                   "are pana", "pana la roata", "roata dezumflata", "roti dezumflate", "camera sparta", "fara lant", "lipsa lant",
                   "a stat in curte", "a stat in garaj",
                   "a stat afara", "nefolosita de ani", "nefolosita de mult", "batuta", "baterie defecta", "nu tine bateria"]
LOCKED: list[str] = []
PART_START = ["stickere", "sticker", "abtibilduri", "dezmembrez", "dezmembrari", "cadre", "piese", "lot piese", "roata", "roti",
              "cadru", "furca", "ghidon", "sa", "sea", "scaun", "pedale", "pedala", "schimbator", "schimbatoare",
              "pinioane", "pinion", "caseta", "lant", "frana", "frane", "anvelope", "anvelopa", "cauciucuri", "cauciuc", "camera",
              "camere", "pompa", "lacat", "casca", "suport", "trainer", "role", "manete", "maneta", "jante", "janta", "butuc",
              "pedalier", "foaie", "foi", "amortizor", "suspensie", "portbagaj", "cos", "scaun copil", "remorca", "aparatori",
              "aparatoare", "far", "lumini", "stop", "sonerie", "bidon", "port bidon", "geanta", "manusi", "papuci", "pantofi",
              "echipament", "tricou", "pantaloni", "angrenaj", "grupset", "kit", "spite", "tija", "pipa", "ax", "rulmenti",
              "acumulator", "baterie", "incarcator", "motor", "display", "controller"]
ACCESSORY_ANYWHERE = ["dezmembrez", "piese mtb", "lot piese", "stickere bicicleta", "pentru bicicleta", "pt bicicleta", "pentru biciclete", "suport biciclete", "suport bicicleta",
                      "piese bicicleta", "piese biciclete", "accesorii bicicleta", "kit conversie", "kit electric",
                      "roti bicicleta", "cadru bicicleta"]
CLONES = ["replica", "copie", "clona", "fake", "imitatie"]
WANTED = ["caut", "cumpar", "cumparam", "achizitionez", "achizitionam"]
SERVICE = ["service biciclete", "reparatii biciclete", "reparatii", "reparatie", "inchiriez", "inchiriere", "revizie biciclete",
           "montaj", "transport biciclete"]
NO_PAPERS = ["fara acte", "fara factura", "nu am factura", "nu am acte", "fara documente", "nu are acte", "fara bon"]


def extra_flags(title: str, full: str) -> set[str]:
    flags: set[str] = set()
    if re.search(r"(?<![a-z])(fitness|spinning|eliptica|stationara|de camera|apartament)(?![a-z])", title):
        flags.add("part")  # an exercise bike isn't a bike
    if any(re.search(rf"(?<![a-z]){re.escape(w)}(?![a-z])", full) for w in NO_PAPERS):
        flags.add("no_papers")
    if CARBON.search(full):
        flags.add("carbon")
    named = {b.name for p, b in _PATTERNS if p.search(title)}
    if len(named) >= 3 or re.search(r"(?<![a-z])biciclete (?:gata|servisate|revizuite|de vanzare|import)", title):
        flags.add("lot")  # "Biciclete gata servisate, Bianchi, Pinarello, Canyon...": a shop's stock, not one bike
    return flags


# What a usable adult bike of the segment fetches at the least: under it, it's scrap, a kids' toy, or stolen.
FLOORS = {"premium": 600, "mid": 300, "vintage": 150}
