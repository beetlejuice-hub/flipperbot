"""Men's clothing without AI: which brand, which kind of item (and the model line where it sets the price), and
whether it reads like a replica.

Priced by brand + item: stone island|jacket, moncler|puffer, arcteryx|beta lt, carhartt|detroit jacket,
the north face|nuptse 1996, ralph lauren|polo bear sweater... A size is noted but doesn't split the comparison.

Segments:
- grail:      archive and designer labels whose old pieces keep or gain value (Rick Owens, Margiela, Raf Simons,
              Chrome Hearts, Kapital, Visvim, CDG, Yohji, Undercover, Number (N)ine, Helmut Lang...)
- luxury:     luxury houses and luxury outerwear (Moncler, Canada Goose, Prada, Gucci, Balenciaga, Loro Piana...),
              the most faked clothes there are
- premium:    the reseller's bread and butter (Stone Island, C.P. Company, Arc'teryx, Barbour, Patagonia, The North
              Face, Carhartt WIP, Stussy, Supreme, Our Legacy, Acne Studios, Aime Leon Dore, Fear of God...)
- basic:      sells, but for little (Ralph Lauren, Lacoste, Tommy Hilfiger, Levi's, Nike, Adidas, Hugo Boss...)
- fast:       fast fashion: no resale value (Zara, H&M, Pull&Bear, Shein...)

Replicas are everywhere in Romanian men's clothing: "premium", "super calitate", "calitate 1:1", "colectie noua"
next to a luxury name, the brand split to dodge OLX's filter ("mo n cler", "b@lenciaga"), every size in stock.
"""

from __future__ import annotations

import re

from .techdb import TechMatch, _w
from .techdb import clean as _tech_clean
from .watchdb import Brand

# (display name, segment, aliases): the aliases are normalize()d spellings sellers use
_B: list[tuple[str, str, tuple[str, ...]]] = [
    # grail / archive
    ("Rick Owens", "grail", ("rick owens", "drkshdw", "rick owens drkshdw")),
    ("Maison Margiela", "grail", ("margiela", "mm6", "maison martin margiela")),
    ("Raf Simons", "grail", ()), ("Helmut Lang", "grail", ()), ("Undercover", "grail", ("undercover jun takahashi",)),
    ("Number (N)ine", "grail", ("number nine", "number (n)ine", "number n ine")), ("Chrome Hearts", "grail", ()),
    ("Comme des Garcons", "grail", ("cdg", "comme des garcons", "comme des garcons play", "cdg play")),
    ("Yohji Yamamoto", "grail", ("yohji", "y's")), ("Issey Miyake", "grail", ("homme plisse", "pleats please")),
    ("Kapital", "grail", ()), ("Visvim", "grail", ()), ("Jean Paul Gaultier", "grail", ("jpg", "gaultier")),
    ("Vivienne Westwood", "grail", ()), ("Carol Christian Poell", "grail", ("ccp",)), ("Boris Bidjan Saberi", "grail", ("bbs",)),
    ("Jil Sander", "grail", ()), ("Dries Van Noten", "grail", ()), ("Ann Demeulemeester", "grail", ()),
    ("Junya Watanabe", "grail", ()), ("Sacai", "grail", ()), ("Enfants Riches Deprimes", "grail", ("erd",)),
    # luxury
    ("Moncler", "luxury", ()), ("Canada Goose", "luxury", ()), ("Prada", "luxury", ()), ("Gucci", "luxury", ()),
    ("Balenciaga", "luxury", ()), ("Louis Vuitton", "luxury", ("lv",)), ("Dior", "luxury", ("dior homme", "christian dior")),
    ("Saint Laurent", "luxury", ("ysl", "yves saint laurent")), ("Givenchy", "luxury", ()), ("Burberry", "luxury", ()),
    ("Loro Piana", "luxury", ()), ("Brunello Cucinelli", "luxury", ()), ("Bottega Veneta", "luxury", ()),
    ("Versace", "luxury", ()), ("Fendi", "luxury", ()), ("Valentino", "luxury", ()), ("Celine", "luxury", ()),
    ("Off-White", "luxury", ("off white", "offwhite")), ("Amiri", "luxury", ()), ("Palm Angels", "luxury", ()),
    ("Dsquared2", "luxury", ("dsquared", "d squared")), ("Parajumpers", "luxury", ()), ("Mackage", "luxury", ()),
    ("Moose Knuckles", "luxury", ()), ("Herno", "luxury", ()), ("Belstaff", "luxury", ()),
    ("Arc'teryx Veilance", "luxury", ("veilance",)), ("Thom Browne", "luxury", ()), ("Lanvin", "luxury", ()),
    # premium
    ("Stone Island", "premium", ("stone island shadow project",)), ("C.P. Company", "premium", ("cp company", "c.p. company",
                                                                                                 "c p company", "c.p company")),
    ("Massimo Osti", "premium", ("osti",)), ("Arc'teryx", "premium", ("arcteryx", "arc teryx", "arc'teryx", "arc’teryx")),
    ("The North Face", "premium", ("north face", "tnf", "the north face")), ("Patagonia", "premium", ()),
    ("Barbour", "premium", ()), ("Carhartt", "premium", ("carhartt wip", "carhart", "carharrt")),
    ("Stussy", "premium", ()), ("Supreme", "premium", ()), ("Palace", "premium", ("palace skateboards",)),
    ("Bape", "premium", ("a bathing ape", "bathing ape")), ("Corteiz", "premium", ("crtz",)), ("Trapstar", "premium", ()),
    ("Represent", "premium", ("represent clo",)), ("Fear of God", "premium", ("fear of god essentials", "fog essentials")),
    ("Aime Leon Dore", "premium", ("ald", "aime leon dore")), ("Kith", "premium", ()), ("Our Legacy", "premium", ()),
    ("Acne Studios", "premium", ("acne",)), ("AMI Paris", "premium", ("ami de coeur", "ami paris")),
    ("Maison Kitsune", "premium", ()), ("A.P.C.", "premium", ("apc", "a.p.c")), ("Needles", "premium", ()),
    ("Engineered Garments", "premium", ()), ("Nanamica", "premium", ()), ("And Wander", "premium", ()),
    ("Snow Peak", "premium", ()), ("Neighborhood", "premium", ()), ("Wtaps", "premium", ()), ("Human Made", "premium", ()),
    ("Gallery Dept", "premium", ("gallery dept.", "gallery department")), ("Sp5der", "premium", ("spider worldwide",)),
    ("Hellstar", "premium", ()), ("Denim Tears", "premium", ()), ("Broken Planet", "premium", ()),
    ("Cav Empt", "premium", ("c.e", "cavempt")), ("Y-3", "premium", ("y3",)), ("Salomon", "premium", ()),
    ("Napapijri", "basic", ()), ("Woolrich", "premium", ()), ("Fjallraven", "basic", ("fjall raven",)),
    ("Haglofs", "basic", ()), ("Norrona", "premium", ()), ("Mammut", "basic", ()), ("Montbell", "premium", ("mont-bell",)),
    ("Peak Performance", "basic", ()), ("Ralph Lauren RRL", "premium", ("rrl", "double rl")), ("Dime", "premium", ()),
    ("Polar Skate", "premium", ("polar skate co",)), ("Diesel", "basic", ()), ("Moschino", "basic", ()),
    ("Kenzo", "basic", ()), ("Moncler Grenoble", "luxury", ()), ("Nike ACG", "premium", ("acg",)),
    ("Schott", "premium", ("schott nyc",)), ("Alpha Industries", "basic", ()), ("Dr. Martens", "basic", ("dr martens",)),
    # basic: sells, for little
    ("Ralph Lauren", "basic", ("polo ralph lauren", "ralph lauren", "polo rl", "polo by ralph lauren", "polo sport")),
    ("Lacoste", "basic", ()), ("Tommy Hilfiger", "basic", ("tommy", "hilfiger", "tommy jeans")),
    ("Levi's", "basic", ("levis", "levi's", "levi’s", "levi strauss")), ("Nike", "basic", ()), ("Adidas", "basic", ()),
    ("Hugo Boss", "basic", ("boss", "hugo")), ("Fred Perry", "basic", ()), ("Gant", "basic", ()), ("Columbia", "basic", ()),
    ("Calvin Klein", "basic", ("ck",)), ("Armani", "basic", ("emporio armani", "armani exchange", "ea7", "giorgio armani")),
    ("Guess", "basic", ()), ("G-Star", "basic", ("g-star raw", "g star")), ("Dickies", "basic", ()), ("Champion", "basic", ()),
    ("Colmar", "basic", ()), ("Timberland", "basic", ()), ("Karl Lagerfeld", "basic", ("karl",)), ("Puma", "basic", ()),
    ("New Balance", "basic", ()), ("Under Armour", "basic", ()), ("Wrangler", "basic", ()), ("Lee", "basic", ()),
    ("Paul & Shark", "basic", ("paul shark", "paul and shark")), ("Napapijri", "basic", ()),
    # fast fashion: no resale value
    ("Zara", "fast", ()), ("H&M", "fast", ("h&m", "h & m", "hm")), ("Pull&Bear", "fast", ("pull&bear", "pull and bear", "pull & bear")),
    ("Bershka", "fast", ()), ("Reserved", "fast", ()), ("LC Waikiki", "fast", ("lcw", "lc waikiki")), ("Shein", "fast", ()),
    ("Primark", "fast", ()), ("Jack & Jones", "fast", ("jack&jones", "jack and jones", "jack & jones")), ("C&A", "fast", ("c&a",)),
    ("Sinsay", "fast", ()), ("Cropp", "fast", ()), ("House", "fast", ()), ("New Yorker", "fast", ()), ("Decathlon", "fast", ()),
    ("Kiabi", "fast", ()), ("Pepco", "fast", ()), ("Terranova", "fast", ()), ("Defacto", "fast", ()), ("Mango", "fast", ()),
    ("Springfield", "fast", ()), ("Celio", "fast", ()), ("Only & Sons", "fast", ("only&sons",)), ("Uniqlo", "basic", ()),
    ("Massimo Dutti", "basic", ()),
]
BRANDS: list[Brand] = []
_seen: set[str] = set()
for _name, _seg, _al in _B:
    if _name not in _seen:
        _seen.add(_name)
        _forms = {_name.lower(), *_al}
        _joined = {f.replace(" ", "") for f in _forms if " " in f and len(f.replace(" ", "")) >= 6}  # "stoneisland"
        BRANDS.append(Brand(_name, _seg, tuple(dict.fromkeys([*_al, *sorted(_joined)]))))
_BY_NAME = {b.name: b for b in BRANDS}

# --- the kind of item: the earliest one named in the title wins ("geaca de blugi" is a jacket) ----------------------
TYPES: list[tuple[str, tuple[str, ...]]] = [
    ("puffer", ("geaca de puf", "geaca puf", "geaca puffer", "puffer", "doudoune", "geaca cu puf", "down jacket", "nuptse")),
    ("vest", ("vesta", "veste", "vest", "gilet", "bodywarmer")),
    ("coat", ("palton", "paltoane", "trenci", "trench", "parka", "parca", "haina lunga", "geaca lunga", "overcoat")),
    ("tracksuit", ("trening", "treninguri", "tracksuit", "compleu", "costum sport", "set trening")),
    ("hoodie", ("hanorac", "hanorace", "hoodie", "hoody", "hooded")),
    ("fleece", ("polar", "fleece", "sherpa")),
    ("overshirt", ("overshirt", "camasa jacheta", "shacket")),
    ("jacket", ("geaca", "geci", "jacheta", "jachete", "jacket", "windbreaker", "bomber", "hardshell", "softshell",
                "shell", "anorak", "blouson", "geaca piele", "biker")),
    ("sweater", ("pulover", "pulovere", "sweater", "cardigan", "helanca", "jerseu", "knit", "tricotaj")),
    ("sweatshirt", ("bluza", "bluze", "sweatshirt", "crewneck", "crew neck", "quarter zip", "1/4 zip", "half zip")),
    ("polo", ("tricou polo", "polo shirt", "polo pique")),
    ("shirt", ("camasa", "camasi", "shirt")),
    ("tee", ("tricou", "tricouri", "t-shirt", "t shirt", "tshirt", "tee", "maieu", "longsleeve", "long sleeve")),
    ("jeans", ("blugi", "jeans", "denim", "jeansi")),
    ("shorts", ("pantaloni scurti", "shorts", "short", "bermude", "bermuda", "sort", "sorti")),
    ("pants", ("pantaloni", "pants", "trousers", "cargo", "chino", "chinos", "joggers", "jogger")),
    ("cap", ("sapca", "sepci", "cap", "caciula", "beanie", "fes", "bucket hat", "palarie")),
    ("bag", ("geanta", "genti", "rucsac", "borseta", "bag", "backpack", "side bag", "shoulder bag", "portofel", "wallet")),
    ("jewelry", ("inel", "lant", "lantisor", "bratara", "pandantiv", "cercei", "ring", "necklace", "bracelet")),
    ("belt", ("curea", "belt")),
    ("scarf", ("fular", "esarfa", "scarf")),
    ("boots", ("ghete", "bocanci", "cizme", "boots")),
]
_TYPE_RES = [(t, [_w(re.escape(w)) for w in words]) for t, words in TYPES]
OUTERWEAR = {"puffer", "coat", "jacket", "vest", "fleece", "overshirt"}

# --- model lines where the line, not just the kind of item, sets the price ------------------------------------------
# (brand, pattern, line); first match wins, so the specific ones first
LINES: list[tuple[str, re.Pattern[str], str]] = [
    ("Arc'teryx", _w(r"(alpha|beta|gamma|zeta|theta)\s?(sv|ar|lt|sl|mx|fl)"), "{1} {2}"),
    ("Arc'teryx", _w(r"(atom|cerium|proton|squamish|solano|rush|sabre|macai|thorium|kyanite|delta|covert|nuclei)\s?(lt|sv|ar|hoody|hoodie|jacket|vest)?"), "{1}"),
    ("Arc'teryx", _w(r"(beta|alpha|gamma|zeta)(?:\s?jacket)?"), "{1}"),
    ("The North Face", _w(r"(?:1996\s?)?(?:retro\s?)?nuptse(?:\s?(700|1996|vest))?"), "nuptse {1}"),
    ("The North Face", _w(r"(himalayan|denali|mountain light|mountain jacket|mcmurdo|summit series|steep tech|baltoro)"), "{1}"),
    ("Moncler", _w(r"(maya|montclar|montgenevre|karakorum|maures|acorus|tib|cardere|ecrins|grenoble|genius|bormes|vezere)"), "{1}"),
    ("Canada Goose", _w(r"(expedition|chilliwack|wyndham|langford|macmillan|carson|crofton|hybridge|freestyle|lodge|"
                        r"chateau|citadel|emory|approach|garson|selkirk|constable)"), "{1}"),
    ("Patagonia", _w(r"(retro[\s-]?x|snap[\s-]?t|nano[\s-]?puff|down sweater|torrentshell|synchilla|better sweater|"
                     r"r1|r2|baggies|isthmus|das parka|micro puff)"), "{1}"),
    ("Barbour", _w(r"(bedale|beaufort|international|ashby|border|transport|spey|liddesdale|duke|northumbria)"), "{1}"),
    ("Carhartt", _w(r"(detroit|og active|active jacket|michigan|chore|double knee|single knee|santa fe|nimbus|"
                    r"chase|og santa fe|j97|j130)"), "{1}"),
    ("Stone Island", _w(r"(shadow project|ghost piece|ghost|marina|ice jacket|membrana|crinkle reps|nylon metal|"
                        r"soft shell-r|soft shell)"), "{1}"),
    ("C.P. Company", _w(r"(goggle|mille miglia|explorer|metropolis|lens)"), "{1}"),
    ("Supreme", _w(r"(box logo|bogo)"), "box logo"),
    ("Ralph Lauren", _w(r"(polo bear|bear sweater|ursulet)"), "polo bear"),
    ("Levi's", _w(r"(501|505|517|550|560|511|512|514|levi's vintage clothing|lvc|big e|type (?:i|ii|iii) trucker|trucker)"), "{1}"),
    ("Nike", _w(r"(tech fleece|tech)"), "tech fleece"),
    ("Chrome Hearts", _w(r"(cross|dagger|horseshoe|matty boy|cemetery)"), "{1}"),
    ("Rick Owens", _w(r"(geobasket|ramones|dunks|creatch|bauhaus|cargobelas|tecuatl|drkshdw)"), "{1}"),
]
_LINE_FIX = {"retro x": "retro-x", "retrox": "retro-x", "snap t": "snap-t", "snapt": "snap-t", "nano puff": "nano puff",
             "nanopuff": "nano puff", "bogo": "box logo", "lvc": "levi's vintage clothing", "tech": "tech fleece"}

SIZE = re.compile(r"(?:(?<![a-z0-9'’])(?:marimea?|masura|size|mar\.?)\s?:?\s?(xxs|xs|s|m|l|xl|xxl|xxxl|2xl|3xl|4[4-9]|5[0-8])"
                  r"|(?<![a-z0-9'’])(xxs|xs|xl|xxl|xxxl|2xl|3xl)|(?<=[\s(,/-])(s|m|l)(?=\s*(?:$|[),/]|\s-)))(?![a-z0-9])")


def _type(title: str) -> tuple[str, int] | None:
    hits = [(m.start(), -len(m.group(0)), t) for t, res in _TYPE_RES for r in res for m in [r.search(title)] if m]
    if not hits:
        return None
    pos, _, t = min(hits)
    return t, pos


def item_type(title: str) -> str | None:
    t = _type(title)
    return t[0] if t else None


_PATTERNS = sorted(((re.compile(r"(?<![a-z0-9])" + re.escape(a) + r"(?![a-z0-9])"), b) for b in BRANDS
                    for a in {b.name.lower(), *b.aliases}), key=lambda p: -len(p[0].pattern))


def find_brand(title: str) -> Brand | None:
    """The brand named first in the title ("polo ralph lauren", "stone island")."""
    hits = [(m.start(), -len(m.group(0)), b.name) for p, b in _PATTERNS for m in [p.search(title)] if m]
    if not hits:
        return None
    return _BY_NAME[min(hits)[2]]


# Lines that name the item by themselves (a Maya is a puffer, an Alpha SV a shell jacket, a 501 jeans)
LINE_KIND = {"Moncler": "puffer", "Canada Goose": "puffer", "Arc'teryx": "jacket", "The North Face": "puffer",
             "Barbour": "jacket", "Levi's": "jeans", "Patagonia": "fleece"}
NO_SUFFIX = set(LINE_KIND) | {"Supreme", "Chrome Hearts", "Ralph Lauren", "Rick Owens"}


def _line(b: Brand, title: str) -> str:
    for brand, pattern, template in LINES:
        if brand != b.name and not (brand == "Arc'teryx" and b.name == "Arc'teryx Veilance"):
            continue
        m = pattern.search(title)
        if m:
            line = template.format(*([m.group(0)] + [g or "" for g in m.groups()])).strip()
            return re.sub(r"\s+", " ", _LINE_FIX.get(line, line))
    return ""


def kind_of(b: Brand, title: str) -> str | None:
    """The kind of item, with a named line's own kind where the title's word misleads ("Geaca Moncler Maya": a puffer)."""
    kind = item_type(title)
    line = _line(b, title)
    if line and b.name in LINE_KIND and kind in (None, "jacket", "coat"):
        if b.name == "The North Face" and not line.startswith("nuptse"):
            return kind or "jacket"
        if b.name == "Patagonia" and line in ("torrentshell", "das parka", "isthmus"):
            return "jacket"
        if b.name == "Patagonia" and line in ("nano puff", "down sweater", "micro puff"):
            return "puffer"
        return LINE_KIND[b.name] if kind is None or b.name not in ("Levi's",) else kind
    return kind


def match(title: str, full: str) -> TechMatch | None:
    b = find_brand(title)
    if not b:
        split = split_brand(title)  # "mo n cler": still a Moncler (a fake one), so it's judged as one
        b = _BY_NAME[split] if split else None
    if not b:
        return None
    kind = kind_of(b, title)
    line = _line(b, title)
    if line and (b.name in NO_SUFFIX or not kind or kind in line):
        model = line
        if b.name == "Supreme" and kind:
            model = f"box logo {kind}"
    elif line:
        model = f"{line} {kind}"  # "detroit jacket", "shadow project pants", "goggle hoodie"
    else:
        model = kind or ""
    return TechMatch(b, model, b.segment)


_NEGATED = re.compile(r"(?<![a-z])(?:fara|nu are|nu prezinta|nici o|nicio|niciun|zero|lipsa)\s+(?:nici\s+o\s+|nicio\s+|niciun\s+)?"
                      r"(?:(?:pete|pata|gauri|gaura|defecte|defect|urme de uzura|uzura|scame|rupturi|decolorari|"
                      r"probleme|imperfectiuni)(?:\s*(?:,|si|sau|ori)\s*)?)+")


def clean(title: str) -> str:
    """Like the electronics one, and "fara pete, fara gauri, fara defecte" (no stains, no holes) said away first."""
    return _NEGATED.sub(" ", _tech_clean(title))


def size(text: str) -> str | None:
    m = SIZE.search(text)
    return next(g for g in m.groups() if g).upper() if m else None


# --- fakes ---------------------------------------------------------------------------------------------------------
# In the title (or the description, for the strongest): how replica sellers write. Romanian replica slang first.
CLONES = ["replica", "replici", "copie", "calitate premium", "premium quality", "super calitate", "calitate superioara",
          "calitate top", "top calitate", "calitate 1:1", "1:1", "1 la 1", "aaa", "a+++", "first copy", "high copy",
          "mirror", "mirror quality", "top quality", "high quality", "calitate turceasca", "import turcia",
          "fake", "imitatie", "inspired", "inspirat", "model inspirat", "tip "]
CLONES_IN_TEXT = ["replica", "calitate premium", "super calitate", "calitate 1:1", "1:1", "first copy", "high copy",
                  "mirror quality", "calitate turceasca", "import turcia", "nu este original", "nu e original",
                  "nu sunt originale", "nu este originala", "nu e originala", "calitatea a", "inspired by"]
# A shop selling every size of a "luxury" piece, new, is selling replicas.
DEALER = ["toate marimile", "marimi disponibile", "disponibil pe toate marimile", "pe stoc", "stoc limitat",
          "ultimele stocuri", "en gros", "engros", "angro", "colectie noua", "colectia noua", "promo", "reducere",
          "livrare gratuita", "livrare in 24", "transport gratuit", "transport inclus", "plata la livrare", "ramburs",
          "comanda", "comenzi", "orice marime", "toate culorile", "mai multe culori", "set de 3", "pachet 3"]
PREMIUM_WORD = re.compile(r"(?<![a-z])(premium|calitate|lux)(?![a-z])")
WANTED = ["caut", "cumpar", "cumparam", "achizitionez", "achizitionam"]
SERVICE = ["croitorie", "retus", "spalatorie", "curatatorie", "inchiriez", "inchiriere"]
LOCKED: list[str] = []
BROKEN = ["rupt", "rupta", "rupte", "ruptura", "gaura", "gauri", "gaurit", "patat", "pata", "pete", "decolorat",
          "decolorata", "scamosat", "scamosata", "uzat", "uzata", "uzura", "fermoar stricat", "fermoar defect",
          "lipsa nasture", "lipsa nasturi", "descusut", "descusuta", "arsura", "ars de tigara", "pentru reparat"]
# Sold on its own: a badge, a tag, a patch (often to make fakes) is not the garment.
PART_START = ["badge", "patch", "eticheta", "etichete", "emblema", "nasturi", "nasture", "fermoar", "umeras", "umerase",
              "punga", "pungi", "cutie", "sacosa"]
ACCESSORY_ANYWHERE = ["doar badge", "doar eticheta", "badge stone island", "patch stone island", "badge original",
                      "pentru geaca", "set badge"]
NOT_MENS = ["dama", "femei", "femeie", "fete", "fata", "copii", "copil", "baieti", "baietel", "fetita", "rochie", "rochii",
            "fusta", "fuste", "colanti", "sutien", "body bebe", "bebe", "gravide", "women", "womens", "woman", "girls", "kids"]


_SUB = {"a": "a@4", "o": "o0", "i": "i1!", "s": "s$5", "e": "e3"}
_SEP = r"[\s.@*_\-+|/]{0,2}"


def _loose(name: str) -> re.Pattern[str]:
    letters = re.sub(r"[^a-z]", "", name)
    return re.compile(r"(?<![a-z])" + _SEP.join(f"[{re.escape(_SUB.get(c, c))}]" for c in letters) + r"(?![a-z])")


_LOOSE = [(b, _loose(b.name.lower()), {f for s in {b.name.lower(), *b.aliases} for f in (re.sub(r"\s+", " ", s), s.replace(" ", ""))})
          for b in BRANDS if b.segment in ("luxury", "grail", "premium") and len(re.sub(r"[^a-z]", "", b.name.lower())) >= 5]


def split_brand(title: str) -> str | None:
    """A brand name broken up or disguised to slip past OLX's filters ("mo n cler", "b@lenciaga", "s t o n e island",
    "g.u.c.c.i"): the seller knows it's a copy. Returns the brand, or None."""
    for b, loose, spellings in _LOOSE:
        for m in loose.finditer(title):
            seen = re.sub(r"\s+", " ", m.group(0).strip())
            if seen not in spellings:
                return b.name
    return None


def extra_flags(title: str, full: str) -> set[str]:
    flags: set[str] = set()
    m = find_brand(title)
    seg = m.segment if m else None
    if any(re.search(rf"(?<![a-z0-9]){re.escape(w)}(?![a-z0-9])", full) for w in CLONES_IN_TEXT):
        flags.add("replica")
    if split_brand(title):
        flags.add("replica")
    if seg in ("luxury", "grail", "premium") and PREMIUM_WORD.search(title):
        flags.add("replica")  # "Hanorac Balenciaga premium", "Tricou Moncler calitate": the seller's own word for a copy
    if seg in ("luxury", "grail", "premium") and sum(
            bool(re.search(rf"(?<![a-z0-9]){re.escape(w)}(?![a-z0-9])", full)) for w in DEALER) >= 2:
        flags.add("dealer")  # a shop: every size, delivery, cash on delivery
    if any(re.search(rf"(?<![a-z]){re.escape(w)}(?![a-z])", title) for w in NOT_MENS):
        flags.add("not_mens")
    if seg == "fast":
        flags.add("fast_fashion")
    return flags


# --- the lowest believable price (lei) for a genuine one, used: under it, it's nearly always a replica ------------
# Deliberately low, so an honest worn piece or a naive seller isn't caught; Claude's check judges the rest.
_FLOOR_BY_SEG = {"luxury": {"puffer": 700, "coat": 700, "jacket": 450, "vest": 450, "hoodie": 250, "sweatshirt": 200,
                            "sweater": 250, "tee": 120, "polo": 150, "shirt": 150, "jeans": 200, "pants": 200,
                            "tracksuit": 300, "bag": 400, "belt": 200, "cap": 120, "jewelry": 300},
                 "grail": {"jacket": 400, "coat": 400, "hoodie": 200, "tee": 100, "jeans": 200, "pants": 200,
                           "jewelry": 300, "boots": 400}}
FLOORS: dict[tuple[str, str], int] = {
    ("Moncler", "puffer"): 900, ("Moncler", "vest"): 600, ("Canada Goose", "puffer"): 1100, ("Canada Goose", "coat"): 1100,
    ("Canada Goose", "vest"): 600, ("Stone Island", "jacket"): 300, ("Stone Island", "puffer"): 400,
    ("Stone Island", "coat"): 400, ("Stone Island", "overshirt"): 300, ("Stone Island", "hoodie"): 150,
    ("Stone Island", "sweatshirt"): 150, ("Stone Island", "sweater"): 150, ("Stone Island", "pants"): 120,
    ("Stone Island", "tracksuit"): 250, ("Stone Island", "tee"): 70, ("Stone Island", "vest"): 250,
    ("C.P. Company", "jacket"): 300, ("C.P. Company", "hoodie"): 150, ("C.P. Company", "sweatshirt"): 120,
    ("Arc'teryx", "jacket"): 300, ("Arc'teryx", "puffer"): 250, ("Arc'teryx", "beta lt"): 600, ("Arc'teryx", "beta ar"): 700,
    ("Arc'teryx", "alpha sv"): 900, ("Arc'teryx", "atom"): 250, ("Arc'teryx", "alpha"): 600, ("Arc'teryx", "beta"): 450,
    ("The North Face", "nuptse"): 250, ("Moncler", "jacket"): 500, ("Moncler", "hoodie"): 250, ("Moncler", "tee"): 120,
    ("The North Face", "nuptse 1996"): 250, ("The North Face", "puffer"): 200, ("Supreme", "box logo hoodie"): 500,
    ("Supreme", "box logo tee"): 150, ("Chrome Hearts", "tee"): 250, ("Chrome Hearts", "hoodie"): 600,
    ("Chrome Hearts", "jewelry"): 400, ("Gallery Dept", "tee"): 150, ("Gallery Dept", "pants"): 300,
    ("Sp5der", "hoodie"): 200, ("Hellstar", "tee"): 120, ("Corteiz", "tracksuit"): 200, ("Trapstar", "puffer"): 250,
    ("Trapstar", "tracksuit"): 150, ("Fear of God", "hoodie"): 120, ("Barbour", "jacket"): 250,
    ("Patagonia", "retro-x"): 250, ("Ralph Lauren", "polo bear"): 200, ("Nike", "tech fleece"): 120,
}


# The brands replica sellers copy most: a cheap one gets the careful photo check and the second, skeptical check.
OFTEN_FAKED = {"Stone Island", "C.P. Company", "Moncler", "Canada Goose", "Arc'teryx", "The North Face", "Supreme",
               "Chrome Hearts", "Off-White", "Balenciaga", "Gucci", "Louis Vuitton", "Dior", "Burberry", "Prada", "Amiri",
               "Palm Angels", "Dsquared2", "Corteiz", "Trapstar", "Fear of God", "Gallery Dept", "Sp5der", "Hellstar",
               "Ralph Lauren", "Lacoste", "Parajumpers", "Hugo Boss", "Bape", "Represent", "Givenchy", "Versace",
               "Saint Laurent", "Rick Owens", "Maison Margiela", "Loro Piana", "Denim Tears", "Broken Planet"}


def floor(brand: str, segment: str, model: str, kind: str | None = None) -> int | None:
    """The lowest price a genuine one plausibly asks, for this brand and line or kind of item."""
    kind = kind or (model.split()[-1] if model else "")
    for key in (model, " ".join(model.split()[:2]), model.split()[0] if model else "", kind):
        if key and (brand, key) in FLOORS:
            return FLOORS[(brand, key)]
    return _FLOOR_BY_SEG.get(segment, {}).get(kind)
