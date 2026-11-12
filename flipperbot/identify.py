"""Read a listing's title and description and work out what it is, without AI.

Romanian sellers write freely ("ceas omega automatic seamaster, merge perfect"),
so this is keyword and pattern matching on normalised text: lower case,
diacritics removed (ș -> s, ă -> a).
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field

from .watchdb import BRANDS, Brand

# --------------------------------------------------------------------------
# Text


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFKD", text or "")
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = text.lower().replace(" ", " ")
    return re.sub(r"\s+", " ", text).strip()


def _phrase_re(phrase: str) -> re.Pattern[str]:
    # Whole-word match; "&" and "-" inside the phrase are matched literally.
    return re.compile(r"(?<![a-z0-9])" + re.escape(phrase) + r"(?![a-z0-9])")


# --------------------------------------------------------------------------
# Brands

_BRAND_PATTERNS: list[tuple[re.Pattern[str], Brand, int]] = sorted(
    (
        (_phrase_re(normalize(p)), b, len(p))
        for b in BRANDS
        for p in {b.name, *b.aliases}
    ),
    key=lambda t: -t[2],  # longest first: "grand seiko" before "seiko", "tag heuer" before "heuer"
)


def find_brands(text: str) -> list[Brand]:
    """Brands mentioned in `text`, in order of first appearance, no duplicates."""
    t = normalize(text)
    taken: list[tuple[int, int]] = []
    hits: list[tuple[int, Brand]] = []
    for pattern, brand, _ in _BRAND_PATTERNS:
        for m in pattern.finditer(t):
            s, e = m.span()
            if any(s < te and e > ts for ts, te in taken):
                continue
            taken.append((s, e))
            hits.append((s, brand))
    seen: set[str] = set()
    out: list[Brand] = []
    for _, b in sorted(hits, key=lambda h: h[0]):
        if b.name not in seen:
            seen.add(b.name)
            out.append(b)
    return out


# --------------------------------------------------------------------------
# Reference numbers (SKX007, 6139-6002, 166.0202, GA-2100, 16610LN, 3133...)

_UNIT = r"(?:mm|m|cm|atm|bar|k|kt|ct|ml|g|gr|kg|lei|ron|eur|euro|buc|h|mah|j|jewels|rubine?|ani|an|zile|km|gb|w|v|x|ore)"
_ALNUM_REF = re.compile(r"(?<![a-z0-9])([a-z]{1,4}-?\d{2,6}(?:[.\-]\d{2,4})?[a-z0-9]{0,5}|\d{2,4}[a-z]{1,3}\d{1,4}[a-z0-9]{0,3})(?![a-z0-9])")
_SEP_REF = re.compile(r"(?<![a-z0-9.\-])(\d{3,4}[-.]\d{2,4}[a-z]{0,2})(?![a-z0-9])")
_DIGIT_REF = re.compile(r"(?<![a-z0-9.,\-])(\d{4,6}[a-z]{0,4})(?![a-z0-9.,])")
_NOT_REF = re.compile(rf"^\d+{_UNIT}$|^(?:19|20)\d\d$|^\d{{1,3}}(?:k|kt)\d*$")
# Brands whose references are plain digits (Rolex 16610, Poljot calibre 3133).
_DIGIT_REF_BRANDS = {"Rolex", "Tudor", "Patek Philippe", "Audemars Piguet", "Poljot", "Vostok", "Raketa", "Sturmanskie", "Slava"}


def find_refs(text: str, brand: Brand | None) -> list[str]:
    t = normalize(text)
    found: list[str] = []
    for m in _SEP_REF.finditer(t):
        found.append(m.group(1))
    for m in _ALNUM_REF.finditer(t):
        tok = m.group(1)
        if len(tok.replace("-", "")) >= 4 and not _NOT_REF.match(tok):
            found.append(tok)
    if brand and brand.name in _DIGIT_REF_BRANDS:
        for m in _DIGIT_REF.finditer(t):
            tok = m.group(1)
            if not _NOT_REF.match(tok):
                found.append(tok)
    out: list[str] = []
    for r in found:
        r = r.upper()
        if r not in out and not any(r in o for o in out):
            out.append(r)
    return out


# --------------------------------------------------------------------------
# What kind of listing is it


def _any(t: str, phrases: list[str]) -> bool:
    return any(_phrase_re(p).search(t) for p in phrases)


BROKEN = [
    "defect", "defecta", "defecte", "nu functioneaza", "nu merge", "nu mai merge", "nefunctional",
    "nefunctionala", "stricat", "stricata", "de reparat", "necesita reparatie", "necesita reparatii",
    "necesita revizie", "necesita service", "pentru piese", "pt piese", "pt. piese", "nu porneste",
    "se opreste", "sta pe loc", "geam spart", "sticla sparta", "fara coroana", "ax rupt",
    "for parts", "not working", "broken",
]
BATTERY = [
    "fara baterie", "necesita baterie", "trebuie baterie", "baterie descarcata", "bateria descarcata",
    "trebuie schimbata bateria", "schimbat bateria", "bateria terminata", "baterie terminata",
    "nu are baterie", "bateria e moarta", "needs battery",
]
REPLICA = [
    "replica", "copie", "clona", "clone", "aaa", "aaa+", "imitatie", "nu este original", "nu e original",
    "inspired", "homage", "fake", "super clone", "superclone", "clone", "1:1", "mirror",
    # replica factories and how replica sellers write
    "noob", "noob factory", "vsf", "vs factory", "clean factory", "zf factory", "apf factory", "ar factory",
    "bt factory", "gm factory", "3k factory", "eta clone", "swiss clone", "calitate 1:1", "high quality",
    "aaa quality", "mirror quality", "first copy", "master copy", "class a", "replica premium", "calitate replica",
]
# Weaker signs. A Japanese/Chinese movement in a luxury or Swiss watch is a fake ("fake_signs");
# shop talk ("many models", "gift box", "last pieces") is damning only on luxury brands ("shop_talk").
FAKE_SIGNS = ["mecanism japonez", "miyota", "seagull", "sea-gull", "mecanism chinezesc", "calitate premium"]
SHOP_TALK = [
    "cutie cadou", "stoc limitat", "ultimele bucati", "diverse modele", "mai multe modele", "toate modelele",
    "avem si alte modele", "alte modele disponibile",
]
# Sellers who don't know what they have: inherited, found, "no idea". Where underpriced old watches are.
# (Checked against real listings: "nu cunosc istoric service" and "cum se vede in poze" are everyday
# phrasing, not cluelessness, so they're not here.)
NAIVE = [
    "nu stiu nimic", "nu stiu multe", "nu stiu ce marca", "nu stiu marca", "nu stiu ce model", "nu stiu ce valoare",
    "nu stiu daca merge", "nu stiu daca functioneaza", "nu stiu daca e original", "nu ma pricep", "nu am idee",
    "habar n-am", "de la bunic", "bunicului", "bunicul", "bunica", "mostenire", "mostenit", "gasit in pod",
    "din pod", "de la tata", "de la parinti", "vechi de tot", "vechituri", "obiecte vechi", "golesc casa",
    "eliberez casa", "din casa batraneasca",
]
WANTED = ["cumpar", "cumparam", "caut ceas", "caut ceasuri", "achizitionez", "achizitionam"]
SERVICE = ["reparatii ceasuri", "service ceasuri", "reparam ceasuri", "schimb baterii", "atelier"]
PART_START = [
    "curea", "bratara", "cutie", "geam", "coroana", "mecanism", "cadran", "baterie", "baterii",
    "suport", "husa", "folie", "incarcator", "cablu", "cutii", "zale", "catarama",
    "capac", "capace", "capacitori", "cadrane", "mecanisme", "coroane", "geamuri", "ace", "curele",
    "bratari", "accesorii", "accesoriu", "piese", "sticla", "sticle", "rotor", "ax", "arc", "set", "kit", "scule", "unelte",
]
BOX_PAPERS = ["full set", "fullset", "cutie si acte", "cutie si certificat", "cu acte", "certificat de garantie", "box and papers", "card garantie"]
GOLD = re.compile(r"(?<![a-z0-9])(aur|gold)(?![a-z0-9])[^.]{0,20}(14k|18k|14 k|18 k|585|750|masiv)|(14k|18k|585|750)[^.]{0,15}(aur|gold)")
PLATED = ["placat", "placata", "aurit", "aurita", "gold plated", "gold filled", "dublat", "laminat"]
VINTAGE = ["vintage", "vechi", "veche", "de colectie", "colectie", "antic", "antica", "retro", "sovietic", "rusesc", "urss", "cccp"]
VINTAGE_YEAR = re.compile(r"(?<![0-9])(?:an(?:ul|ii)?\s*)?(?:18[5-9]\d|19[0-8]\d|anii\s*[2-8]0)(?![0-9])")
POCKET = ["buzunar", "pocket watch", "ceas de buzunar"]
LOT = ["lot", "loturi", "colectie de ceasuri", "colectie ceasuri", "mai multe ceasuri", "set ceasuri", "set de ceasuri", "lot de ceasuri", "ceasuri vechi", "ceasuri de colectie"]
LOT_COUNT = re.compile(r"(?<![a-z0-9])(\d{1,3})\s*(?:buc|bucati|ceasuri|bc)(?![a-z])")


@dataclass
class Identity:
    brand: Brand | None
    brands: list[Brand]
    refs: list[str]
    family: str | None
    flags: set[str] = field(default_factory=set)
    lot_count: int | None = None
    brand_in_title: bool = False  # False: only the description names it, a weaker signal

    @property
    def model_key(self) -> str | None:
        """What we price by: 'seiko|SKX007', 'omega|seamaster', or just 'omega'."""
        if not self.brand:
            return None
        b = self.brand.name.lower()
        if self.refs:
            return f"{b}|{self.refs[0]}"
        if self.family:
            return f"{b}|{self.family}"
        return b

    @property
    def segment(self) -> str | None:
        return self.brand.segment if self.brand else None


# "Ceas Mondaine automatic sch. Seiko citizen omega": brands after "sch"/"schimb" are what
# the seller would swap for, not what's for sale.
_SWAP = re.compile(r"(?<![a-z])(?:sch|schb|schimb|schimbat|schimbare|accept schimb|sau schimb)(?![a-z]).*$")


def identify(title: str, description: str = "") -> Identity:
    title = _SWAP.sub("", normalize(title)).strip() or title
    title_n = normalize(title)
    full_n = normalize(f"{title} . {description}")

    # The title is what the seller is selling; the description often name-drops
    # other brands ("like Rolex"), so it only counts if the title has none.
    title_brands = find_brands(title)
    brands = title_brands or find_brands(description)
    # "Audemars Piguet x Swatch Royal Pop", "Omega x Swatch MoonSwatch": it's a Swatch.
    if any(b.name == "Swatch" for b in brands) or "moonswatch" in title_n:
        brands = [b for b in BRANDS if b.name == "Swatch"] + [b for b in brands if b.name != "Swatch"]
    brand = brands[0] if brands else None
    refs = find_refs(title, brand) or find_refs(description, brand)
    family = None
    if brand:
        for fam in brand.families:
            if _phrase_re(normalize(fam)).search(full_n):
                family = fam
                break

    flags: set[str] = set()
    if _any(full_n, BROKEN):
        flags.add("broken")
    if _any(full_n, BATTERY):
        flags.add("battery")  # usually a 20-lei fix: the best kind of "broken"
    if _any(full_n, REPLICA):
        flags.add("replica")
    if _any(full_n, FAKE_SIGNS):
        flags.add("fake_signs")
    if _any(full_n, SHOP_TALK):
        flags.add("shop_talk")
    if _any(full_n, NAIVE):
        flags.add("naive")
    if _any(title_n, WANTED):
        flags.add("wanted")
    if _any(title_n, SERVICE):
        flags.add("service")
    first = title_n.split(" ", 1)[0] if title_n else ""
    if first in PART_START:
        flags.add("part")
    if _any(full_n, BOX_PAPERS):
        flags.add("box_papers")
    if GOLD.search(full_n) and not _any(full_n, PLATED):
        flags.add("solid_gold")
    if _any(full_n, VINTAGE) or VINTAGE_YEAR.search(full_n):
        flags.add("vintage")
    if _any(full_n, POCKET):
        flags.add("pocket")
    if "automatic" in full_n or "automat" in full_n:
        flags.add("automatic")

    lot_count = None
    m = LOT_COUNT.search(title_n)  # descriptions count other things ("2 buc curele")
    if m and re.search(r"limitat|editie|editia|serie|din \d", title_n):
        m = None  # "editie limitata 125 buc" is how many were made, not how many are for sale
    if m and int(m.group(1)) >= 2:
        lot_count = int(m.group(1))
    if _any(title_n, LOT) or (lot_count and lot_count >= 2):
        flags.add("lot")

    return Identity(
        brand=brand, brands=brands, refs=refs, family=family, flags=flags, lot_count=lot_count,
        brand_in_title=bool(title_brands),
    )
