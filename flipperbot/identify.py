"""Read a listing's title and description and work out what it is, without AI.

Romanian sellers write freely ("ceas omega automatic seamaster, merge perfect"),
so this is keyword and pattern matching on normalised text: lower case,
diacritics removed (ș -> s, ă -> a).
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field

from .watchdb import BRANDS, COLLECTIBLE, Brand

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

_PATTERNS: dict[str, list[tuple[re.Pattern[str], Brand, int]]] = {}


def _brand_patterns(niche: str) -> list[tuple[re.Pattern[str], Brand, int]]:
    if niche not in _PATTERNS:
        from .niches import get

        _PATTERNS[niche] = sorted(
            ((_phrase_re(normalize(p)), b, len(p)) for b in get(niche).brands for p in {b.name, *b.aliases}),
            key=lambda t: -t[2],  # longest first: "grand seiko" before "seiko", "tag heuer" before "heuer"
        )
    return _PATTERNS[niche]


def find_brands(text: str, niche: str = "watches") -> list[Brand]:
    """Brands mentioned in `text`, in order of first appearance, no duplicates."""
    t = normalize(text)
    taken: list[tuple[int, int]] = []
    hits: list[tuple[int, Brand]] = []
    for pattern, brand, _ in _brand_patterns(niche):
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


def _family_re(fam: str) -> re.Pattern[str]:
    """'jupiter 9' also matches 'jupiter-9' and 'jupiter9'; 'ae-1' matches 'ae 1'."""
    parts = [re.escape(p) for p in re.split(r"[\s-]+", normalize(fam)) if p]
    return re.compile(r"(?<![a-z0-9])" + r"[\s-]?".join(parts) + r"(?![a-z0-9])")



def _any(t: str, phrases: list[str]) -> bool:
    return any(_phrase_re(p).search(t) for p in phrases)


BROKEN = [
    "defect", "defecta", "defecte", "nu functioneaza", "nu merge", "nu mai merge", "nefunctional",
    "nefunctionala", "stricat", "stricata", "de reparat", "necesita reparatie", "necesita reparatii",
    "necesita revizie", "necesita service", "pentru piese", "pt piese", "pt. piese", "nu porneste",
    "se opreste", "sta pe loc", "geam spart", "sticla sparta", "fara coroana", "ax rupt",
    "for parts", "not working", "broken",
    "blocat",
]
BATTERY = [
    "fara baterie", "necesita baterie", "trebuie baterie", "baterie descarcata", "bateria descarcata",
    "trebuie schimbata bateria", "schimbat bateria", "bateria terminata", "baterie terminata",
    "nu are baterie", "bateria e moarta", "needs battery",
]
REPLICA = [
    "replica", "copie", "clona", "clone", "aaa", "aaa+", "imitatie", "nu este original", "nu e original",
    "inspired", "homage", "fake", "super clone", "superclone", "clone", "1:1", "mirror",
    # Apple Watch clones
    "hk9", "hk8", "hk9 pro", "dt8", "dt9", "dt no.1", "t800", "t900", "hello watch", "x8 ultra", "s8 ultra", "i8 ultra",
    "z59 ultra", "gs8 ultra", "ultra 9", "series 10 ultra", "replica apple",
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
# Locked to someone's account: stolen, or unusable for the next owner.
LOCKED = ["icloud blocat", "blocat icloud", "blocat in icloud", "blocat pe icloud", "cont icloud", "activation lock",
          "blocat in cont", "blocat cont", "cont google", "frp", "nu stiu parola", "nu am parola", "blocat de operator"]
WANTED = ["cumpar", "cumparam", "caut ceas", "caut ceasuri", "achizitionez", "achizitionam"]
SERVICE = ["reparatii ceasuri", "service ceasuri", "reparam ceasuri", "schimb baterii", "atelier"]
PART_START = [
    "curea", "bratara", "cutie", "geam", "coroana", "mecanism", "cadran", "baterie", "baterii",
    "suport", "husa", "folie", "incarcator", "cablu", "cabluri", "cutii", "zale", "catarama",
    "capac", "capace", "capacitori", "cadrane", "mecanisme", "coroane", "geamuri", "ace", "curele",
    "bratari", "accesorii", "accesoriu", "piese", "sticla",
    "parasolar", "filtru", "filtre", "adaptor", "inel", "inele", "geanta", "trepied", "blit", "acumulator",
    "acumulatori", "telecomanda", "grip", "capac", "teleconvertor", "monitor", "stabilizator", "gimbal", "sticle", "rotor", "ax", "arc", "set", "kit", "scule", "unelte",
]
BOX_PAPERS = ["full set", "fullset", "cutie si acte", "cutie si certificat", "cu acte", "certificat de garantie", "box and papers", "card garantie"]
GOLD = re.compile(r"(?<![a-z0-9])(aur|gold)(?![a-z0-9])[^.]{0,20}(14k|18k|14 k|18 k|585|750|masiv)|(14k|18k|585|750)[^.]{0,15}(aur|gold)")
PLATED = ["placat", "placata", "aurit", "aurita", "gold plated", "gold filled", "dublat", "laminat"]
VINTAGE = ["vintage", "vechi", "veche", "de colectie", "colectie", "antic", "antica", "retro", "sovietic", "rusesc", "urss", "cccp"]
VINTAGE_YEAR = re.compile(r"(?<![0-9])(?:an(?:ul|ii)?\s*)?(?:18[5-9]\d|19[0-8]\d|anii\s*[2-8]0)(?![0-9])")
POCKET = ["buzunar", "pocket watch", "ceas de buzunar"]
# Cameras and lenses: faults, lots, parts, film-era words.
CAMERA_BROKEN = ["ciuperca", "ciuperci", "fungus", "ceata", "lentila zgariata", "nu declanseaza", "obturator blocat",
                 "obturatorul nu", "nu armeaza", "diafragma blocata", "separare", "nu functioneaza blitul"]
CAMERA_LOT = ["lot aparate", "lot obiective", "aparate foto vechi", "obiective vechi", "colectie aparate"]
CAMERA_PART_START = ["parasolar", "filtru", "filtre", "adaptor", "inel", "inele", "geanta", "trepied", "blit", "acumulator",
                     "acumulatori", "telecomanda", "grip", "capac", "teleconvertor", "monitor", "stabilizator", "gimbal"]
CAMERA_PARTS = ["adaptor", "speed booster", "metabones", "viltrox", "inel adaptor", "adapter"]
CAMERA_VINTAGE = ["pe film", "analogic", "35mm film", "film 35mm", "burduf", "ddr", "gdr"]
FOCAL = re.compile(r"(?<![0-9.,])(\d{1,3}(?:\s?-\s?\d{2,3})?)\s?mm(?![a-z])")
APERTURE = re.compile(r"(?<![a-z0-9])(?:f|1:)\s?/?\s?(\d(?:[.,]\d{1,2})?)(?![0-9])")
# Camera bodies and compacts go by short model numbers: G10, S70, A75, D750, X-700...
CAM_REF = re.compile(r"(?<![a-z0-9])([a-z]{1,3}-?\d{1,4}[a-z]{0,3})(?![a-z0-9])")
# Not model numbers: apertures (f2, f1.8, f16, f22; but F65/F80/F100 are Nikon bodies), T-stops, units, mounts.
_NOT_CAM_REF = re.compile(r"^f\d$|^f[12]\d$|^t\d|^\d|^(?:mm|cm|mp|iso|usb|hd|fps|gb|mb|px|is|stm|usm|vr|ii|iii|mk)\d*$|^m42$|^m39$")
EOS = re.compile(r"(?<![a-z0-9])eos[\s-]?(\d{1,4}[a-z]{0,2}|ix[\s-]?\d{1,2}|[a-z]{1,2}\d{0,2})(?![a-z0-9])")
LENS_WORDS = ["obiectiv", "obiective", "lentila", "lens", "zoom", "prime"]
LOT = ["lot", "loturi", "colectie de ceasuri", "colectie ceasuri", "mai multe ceasuri", "set ceasuri", "set de ceasuri", "lot de ceasuri", "ceasuri vechi", "ceasuri de colectie"]
LOT_COUNT = re.compile(r"(?<![a-z0-9])(\d{1,3})\s*(?:buc|bucati|ceasuri|bc|aparate|obiective)(?![a-z])")


# Accessories wherever the word sits in the title ("Huse antisoc ... pentru Apple Watch").
ACCESSORY_ANYWHERE = ["pentru apple watch", "for apple watch", "huse", "husa pentru", "husa protectie", "statie incarcare",
                      "statie de incarcare", "cablu incarcare", "protectie ecran", "folie protectie", "curea pentru",
                      "curele pentru", "bratara pentru", "bratari pentru", "schimbare la carcasa"]
MECHANICAL = ["mecanic", "mecanica", "intoarcere manuala", "remontare manuala", "intoarcere", "manual wind",
              "rubine", "rubin", "jewels", "rubis", "hand wound", "handaufzug"]
QUARTZ = ["quartz", "cuart", "cuartz", "baterie", "battery"]
MODDED = ["modificat", "modificata", "mod", "seiko mod", "custom", "personalizat", "customizat", "franken"]
NEW_BOXED = ["sigilat", "nepurtat", "nou cu eticheta", "cu eticheta", "nou in cutie", "brand new", "new with tags"]


@dataclass
class Identity:
    brand: Brand | None
    brands: list[Brand]
    refs: list[str]
    family: str | None
    flags: set[str] = field(default_factory=set)
    lot_count: int | None = None
    brand_in_title: bool = False  # False: only the description names it, a weaker signal
    niche: str = "watches"
    collectible: list[str] = field(default_factory=list)  # which collector references matched
    focal: str | None = None  # lenses: "58 f2", "18-200 f3.5"
    lens: bool = False

    @property
    def model_key(self) -> str | None:
        """What we price by: 'seiko|SKX007', 'omega|seamaster', or just 'omega'."""
        if not self.brand:
            return None
        b = self.brand.name.lower()
        fam = self.family.replace("-", " ") if self.family else None
        if self.lens and fam:  # a lens name means little without its focal length
            if fam == "lens":  # no lens name: only the focal length says which lens
                return f"{b}|lens|{self.focal}" if self.focal else b
            return f"{b}|{fam}|{self.focal}" if self.focal else f"{b}|{fam}"
        if self.niche == "cameras" and fam:  # "ae 1 program" says more than the number "AE-1"
            return f"{b}|{fam}"
        if self.refs:
            return f"{b}|{self.refs[0]}"
        if fam:
            return f"{b}|{fam}"
        return b

    @property
    def segment(self) -> str | None:
        return self.brand.segment if self.brand else None


# "Ceas Mondaine automatic sch. Seiko citizen omega": brands after "sch"/"schimb" are what
# the seller would swap for, not what's for sale.
_SWAP = re.compile(r"(?<![a-z])(?:sch|schb|schimb|schimbat|schimbare|accept schimb|sau schimb)(?![a-z]).*$")


_TRADE = re.compile(r"(?<![a-z])(sch|schimb|schimburi|schimbat|accept variante|variante|trade|exchange|swap|"
                    r"tausch|la schimb|plus diferenta|cu diferenta)(?![a-z])")


def _without_trade_talk(description: str) -> str:
    """Drop sentences about swapping ("accept schimb cu Omega sau Rolex"): those brands are what the
    seller wants, not what's for sale."""
    parts = re.split(r"(?<=[.!?\n])|\s[-–]\s", description or "")
    return " ".join(p for p in parts if not _TRADE.search(normalize(p)))


def _smart_words(t: str) -> str:
    """Romanian smartwatch names: "seria 8"/"serie 8" -> "series 8", "apple watch 5" -> "apple watch series 5"."""
    t = re.sub(r"(?<![a-z])seri[ae](?= ?\d)", "series", t)
    return re.sub(r"(apple watch|iwatch) (\d{1,2})(?![0-9])", r"\1 series \2", t)


def identify(title: str, description: str = "", niche: str = "watches") -> Identity:
    title = _smart_words(_SWAP.sub("", normalize(title)).strip() or title)
    title_n = normalize(title)
    full_n = _smart_words(normalize(f"{title} . {description}"))

    # The title is what the seller is selling; the description often name-drops
    # other brands ("like Rolex"), so it only counts if the title has none.
    from .niches import get

    title_brands = find_brands(title, niche)
    brands = title_brands or find_brands(_without_trade_talk(description), niche)
    # "Audemars Piguet x Swatch Royal Pop", "Omega x Swatch MoonSwatch": it's a Swatch.
    if niche == "watches" and (any(b.name == "Swatch" for b in brands) or "moonswatch" in title_n):
        brands = [b for b in BRANDS if b.name == "Swatch"] + [b for b in brands if b.name != "Swatch"]
    brand = brands[0] if brands else None
    refs = find_refs(title, brand) or find_refs(description, brand)
    family = None
    if brand:
        # Title first: descriptions mention other models ("also have a Seamaster").
        # Smartwatch descriptions name other models ("like a Fenix 8", "fits Ultra"): title only.
        family_in_title = False
        for text in ((title_n,) if brand.segment == "smart" else (title_n, full_n)):
            family = next((fam for fam in brand.families if _family_re(fam).search(text)), None)
            if family:
                family_in_title = text is title_n
                break
        if niche == "cameras" and family in get(niche).lens_families and not family_in_title:
            family = None  # "Coolpix ... (also selling a Nikkor)": a lens named only in the description
    lens = bool(family and family in get(niche).lens_families)
    focal = None
    if niche == "cameras":
        m = FOCAL.search(title_n)
        if not m and _any(title_n, LENS_WORDS):  # "Obiectiv Sony 28-70": a zoom range without "mm"
            m = re.search(r"(?<![0-9.,])(\d{2,3}\s?-\s?\d{2,3})(?![0-9])", title_n)
        if m:
            focal = re.sub(r"\s", "", m.group(1))
            a = APERTURE.search(title_n)
            if a:
                focal += f" f{a.group(1).replace(',', '.')}"
        is_lens_listing = (bool(m) and (_any(title_n, LENS_WORDS) or lens or not family)) or (
            _any(title_n, LENS_WORDS) and not family)
        if is_lens_listing and not lens:
            family, lens = "lens", True  # "Obiectiv Sony 28-70 pentru A7": a lens, whatever body it mentions
        eos = EOS.search(title_n)
        if eos and not is_lens_listing:  # "Canon EOS 100 montura EF": the body, not the mount
            family, lens, refs = None, False, ["EOS " + re.sub(r"[\s-]", "", eos.group(1)).upper()]
        elif not lens and brand:
            cam_refs = [r.group(1) for r in CAM_REF.finditer(title_n) if not _NOT_CAM_REF.match(r.group(1))]
            refs = [r.upper() for r in cam_refs[:1]] or refs

    flags: set[str] = set()
    cam = niche == "cameras"
    if _any(full_n, BROKEN) or (cam and _any(full_n, CAMERA_BROKEN)):
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
    if _any(full_n, LOCKED):
        flags.add("locked")
    if _any(title_n, WANTED):
        flags.add("wanted")
    if _any(title_n, SERVICE):
        flags.add("service")
    first = re.split(r"[^a-z0-9]+", title_n)[0] if title_n else ""  # "husa/carcasa ..." -> "husa"
    if first in PART_START or _any(title_n, ACCESSORY_ANYWHERE) or (
            cam and (first in CAMERA_PART_START or _any(title_n, CAMERA_PARTS))):
        flags.add("part")
    if cam and brand and brand.name == "Leica" and re.search(r"(?<![a-z])(fed|zorki|zorkiy|kiev)(?![a-z])", title_n):
        flags.add("fake_signs")  # a Soviet FED/Zorki engraved "Leica": the classic fake
    if _any(full_n, BOX_PAPERS):
        flags.add("box_papers")
    if GOLD.search(full_n) and not _any(full_n, PLATED):
        flags.add("solid_gold")
    if _any(full_n, VINTAGE) or VINTAGE_YEAR.search(full_n) or (cam and _any(full_n, CAMERA_VINTAGE)):
        flags.add("vintage")
    if _any(full_n, POCKET):
        flags.add("pocket")
    if "automatic" in full_n or "automat" in full_n:
        flags.add("automatic")
    if cam:
        pass  # mechanical/quartz and the collector list are about watches
    elif flags & {"automatic"} or _any(full_n, MECHANICAL):
        flags.add("mechanical")
    elif _any(full_n, QUARTZ):
        flags.add("quartz")  # resale drops a lot for quartz, even good brands
    if _any(full_n, MODDED):
        flags.add("modded")  # "Seiko mod", "modificat": parts swapped on purpose, not a collector piece
    hits = []
    for pat, label in ([] if cam else COLLECTIBLE):
        r = _family_re(pat)
        makers = find_brands(label)
        if makers and brand and makers[0].name != brand.name:
            continue  # "Navigator" on a Marathon isn't a Tissot Navigator
        if r.search(title_n):
            hits.append(label)
        elif r.search(full_n):
            # In the description only: sellers paste famous names ("like a King Seiko"). Count it only if
            # it's this watch's own brand, or a movement/dial word on an unbranded or non-fashion watch.
            makers = find_brands(label)
            if makers:
                if brand and makers[0].name == brand.name:
                    hits.append(label)
            elif brand is None or brand.segment != "fashion":
                hits.append(label)
    if hits and "modded" not in flags:
        flags.add("collectible")
    else:
        hits = []
    if _any(full_n, NEW_BOXED):
        flags.add("new")

    lot_count = None
    m = LOT_COUNT.search(title_n)  # descriptions count other things ("2 buc curele")
    if m and re.search(r"limitat|editie|editia|serie|din \d", title_n):
        m = None  # "editie limitata 125 buc" is how many were made, not how many are for sale
    if m and int(m.group(1)) >= 2:
        lot_count = int(m.group(1))
    if _any(title_n, LOT) or (cam and _any(title_n, CAMERA_LOT)) or (lot_count and lot_count >= 2):
        flags.add("lot")

    return Identity(
        brand=brand, brands=brands, refs=refs, family=family, flags=flags, lot_count=lot_count,
        brand_in_title=bool(title_brands), niche=niche, collectible=hits, focal=focal, lens=lens,
    )
