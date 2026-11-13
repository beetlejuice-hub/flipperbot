"""Consoles, handhelds, PCs, laptops and PC parts, without AI: which exact thing a listing sells.

Electronics are priced by the exact model and variant, not by brand: a PS5 Digital and a PS5 Pro, an RTX
3060 12 GB and 8 GB, a Switch Lite and a Switch OLED are different prices. And a graphics card is an RTX
4070 whoever built the board (MSI, Asus, Gigabyte). So the model key is what the item IS:

    sony|ps5 pro          microsoft|xbox series s     nintendo|switch oled     valve|steam deck oled
    nvidia|rtx 4070 super amd|rx 7800 xt              amd|ryzen 7 7800x3d      intel|i5 13600k
    apple|macbook air m2  laptop|rtx 4060             pc|rtx 4070              ram|ddr5 32gb

Gaming laptops and PCs are priced by their graphics card (the part that sets the price); other laptops
by processor generation; MacBooks by line and chip. Segments (for repair costs and the AI's checks):
console, handheld, retro, gpu, cpu, laptop, mac, pc, ram.

Only the title says what's for sale: descriptions list games, other consoles, "works with PS5". For
laptops and PCs the description may add the graphics card or processor the title leaves out.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .watchdb import Brand

# Brands, for the relevance check outside the electronics categories (and Facebook). The model key's
# first part comes from the catalog below, not from these.
BRANDS: list[Brand] = [
    Brand("Sony", "console", ("playstation", "ps5", "ps4", "ps3", "ps vita", "psp", "ps2", "ps one", "psone")),
    Brand("Microsoft", "console", ("xbox",)),
    Brand("Nintendo", "console", ("switch", "gamecube", "game cube", "n64", "nintendo 64", "snes", "nes", "wii", "wii u",
                                  "game boy", "gameboy", "3ds", "2ds", "nintendo ds")),
    Brand("Valve", "handheld", ("steam deck", "steamdeck")),
    Brand("Sega", "retro", ("mega drive", "megadrive", "dreamcast", "saturn", "genesis")),
    Brand("Nvidia", "gpu", ("geforce", "rtx", "gtx")),
    Brand("AMD", "gpu", ("radeon", "ryzen")),
    Brand("Intel", "cpu", ("core i3", "core i5", "core i7", "core i9", "core ultra")),
    Brand("Apple", "mac", ("macbook", "macbook air", "macbook pro", "imac", "mac mini", "mac studio")),
    Brand("Asus", "laptop", ("rog", "rog ally", "tuf gaming", "zenbook", "vivobook")),
    Brand("Lenovo", "laptop", ("legion", "legion go", "thinkpad", "ideapad", "yoga")),
    Brand("Dell", "laptop", ("alienware", "xps", "latitude", "inspiron")),
    Brand("HP", "laptop", ("omen", "victus", "elitebook", "probook", "pavilion")),
    Brand("Acer", "laptop", ("nitro", "predator", "aspire", "swift")),
    Brand("MSI", "laptop", ("katana", "stealth", "raider")),
    Brand("Gigabyte", "laptop", ("aorus",)),
    Brand("Razer", "laptop", ("razer blade",)),
]

_BRAND_BY_NAME = {b.name.lower(): b for b in BRANDS}


def _w(pattern: str) -> re.Pattern[str]:
    return re.compile(rf"(?<![a-z0-9]){pattern}(?![a-z0-9])")


# --- consoles and handhelds: (pattern, brand, model, segment), first match wins: specific before general ---
CONSOLES: list[tuple[re.Pattern[str], str, str, str]] = [
    (_w(r"(?:ps ?5|playstation ?5)\s*pro"), "sony", "ps5 pro", "console"),
    (_w(r"(?:ps ?5|playstation ?5)(?:\s*slim)?\s*(?:digital|digitala|digitală|fara (?:unitate|disc)|without disc)"), "sony", "ps5 digital", "console"),
    (_w(r"(?:ps ?5|playstation ?5)"), "sony", "ps5", "console"),
    (_w(r"(?:ps ?vr ?2|playstation vr ?2)"), "sony", "ps vr2", "console"),
    (_w(r"(?:ps ?4|playstation ?4)\s*pro"), "sony", "ps4 pro", "console"),
    (_w(r"(?:ps ?4|playstation ?4)"), "sony", "ps4", "console"),
    (_w(r"(?:ps ?vita|playstation vita)"), "sony", "ps vita", "handheld"),
    (_w(r"(?:ps ?3|playstation ?3)"), "sony", "ps3", "retro"),
    (_w(r"(?:ps ?2|playstation ?2)"), "sony", "ps2", "retro"),
    (_w(r"(?:ps ?one|psone|ps ?1|playstation ?1)"), "sony", "ps1", "retro"),
    (_w(r"psp"), "sony", "psp", "retro"),
    (_w(r"(?:ps|playstation)\s*portal"), "sony", "ps portal", "handheld"),
    (_w(r"xbox\s*series\s*x"), "microsoft", "xbox series x", "console"),
    (_w(r"xbox\s*series\s*s"), "microsoft", "xbox series s", "console"),
    (_w(r"xbox\s*one\s*x"), "microsoft", "xbox one x", "console"),
    (_w(r"xbox\s*one(?:\s*s)?"), "microsoft", "xbox one", "console"),
    (_w(r"xbox\s*360"), "microsoft", "xbox 360", "retro"),
    (_w(r"(?:nintendo\s*)?(?:switch|swicht)\s*2(?!\s*(?:x\s|buc|manete|maneta|controller|controlere|controllere|jocuri|joy|joc))"),
     "nintendo", "switch 2", "console"),
    (_w(r"(?:nintendo\s*)?(?:switch|swicht)\s*oled"), "nintendo", "switch oled", "console"),
    (_w(r"(?:nintendo\s*)?(?:switch|swicht)\s*lite"), "nintendo", "switch lite", "handheld"),
    (_w(r"nintendo\s*(?:switch|swicht)|swi(?:tc|ct)h\s*nintendo"), "nintendo", "switch", "console"),
    (_w(r"(?:new\s*)?(?:nintendo\s*)?[23]ds(?:\s*xl)?"), "nintendo", "3ds", "handheld"),
    (_w(r"(?:nintendo\s*)?dsi?(?:\s*(?:xl|lite))?"), "nintendo", "ds", "retro"),
    (_w(r"(?:playstation|ps)\s*classic"), "sony", "ps classic", "retro"),
    (_w(r"anbernic\s*rg\s?[0-9a-z]+"), "anbernic", "rg handheld", "handheld"),
    (_w(r"miyoo\s*mini(?:\s*plus)?|miyoo"), "miyoo", "mini", "handheld"),
    (_w(r"retroid\s*pocket\s*\d?"), "retroid", "pocket", "handheld"),
    (_w(r"wii\s*u"), "nintendo", "wii u", "retro"),
    (_w(r"wii"), "nintendo", "wii", "retro"),
    (_w(r"game\s*cube|gamecube"), "nintendo", "gamecube", "retro"),
    (_w(r"n64|nintendo\s*64"), "nintendo", "n64", "retro"),
    (_w(r"snes|super\s*nintendo"), "nintendo", "snes", "retro"),
    (_w(r"game\s*boy\s*advance(?:\s*sp)?|gba(?:\s*sp)?"), "nintendo", "game boy advance", "retro"),
    (_w(r"game\s*boy(?:\s*color)?|gameboy(?:\s*color)?"), "nintendo", "game boy", "retro"),
    (_w(r"nes"), "nintendo", "nes", "retro"),
    (_w(r"steam\s*deck\s*oled|steamdeck\s*oled"), "valve", "steam deck oled", "handheld"),
    (_w(r"steam\s*deck|steamdeck"), "valve", "steam deck", "handheld"),
    (_w(r"rog\s*ally\s*x"), "asus", "rog ally x", "handheld"),
    (_w(r"rog\s*ally"), "asus", "rog ally", "handheld"),
    (_w(r"legion\s*go(?:\s*s)?"), "lenovo", "legion go", "handheld"),
    (_w(r"dreamcast"), "sega", "dreamcast", "retro"),
    (_w(r"mega\s*drive|megadrive|sega\s*genesis"), "sega", "mega drive", "retro"),
]

LAPTOP_WORDS = ("laptop", "notebook", "ultrabook", "macbook", "chromebook")
PC_WORDS = ("pc", "calculator", "sistem", "desktop", "unitate", "workstation", "computer", "gaming pc", "pc gaming",
            "mini pc", "imac", "mac mini", "mac studio", "tower", "optiplex", "elitedesk", "prodesk", "thinkcentre")
# Laptop lines named without the word "laptop" ("ASUS TUF Gaming F15 RTX 2050", "Lenovo Legion 7 16IRX9").
LAPTOP_RE = _w(r"(?:tuf(?: gaming)? [af]1[57]|legion (?:5|7|pro|slim)|loq|nitro (?:5|v|an\d*)|predator helios|omen (?:1[5-7]|transcend)|"
               r"victus|thinkpad|ideapad|zenbook|vivobook|xps 1[3-7]|latitude|elitebook|probook|inspiron|aspire|katana|"
               r"alienware [mx]\d*|rog zephyrus|rog flow|rog strix (?:g|scar)|matebook|galaxy book|surface laptop|yoga \d)")
GPU_WORDS = ("placa video", "placa grafica", "graphics card", "gpu", "videocard")
CPU_WORDS = ("procesor", "cpu", "processor")
RAM_WORDS = ("memorie ram", "memorii ram", "ram ddr", "kit ram", "memorie ddr", "ram")

NVIDIA = _w(r"(?:rtx|gtx)\s?(\d{3,4})\s?(ti\s?super|super|ti)?")
AMD_GPU = _w(r"(?:rx|radeon)\s?(\d{3,4})\s?(xtx|xt|gre)?")
VRAM = _w(r"(\d{1,2})\s?gb")
RYZEN = _w(r"ryzen\s?([3579])\s?(\d{4}x3d|\d{4}[a-z]{0,2})")
INTEL = _w(r"(?:core\s?)?i([3579])[\s-]?(\d{4,5})([a-z]{0,2}\d?)")
CORE_ULTRA = _w(r"(?:core\s?)?ultra\s?([579])\s?(\d{3}[a-z]{0,2})")
APPLE_M = _w(r"m([1-5])(?:\s?(pro|max|ultra))?")
DDR = _w(r"ddr([345])")
RAM_GB = _w(r"(?:(\d)\s?x\s?(\d{1,2})\s?gb|(\d{1,3})\s?gb)")

# Cards whose memory size changes the price a lot (3060 12 GB vs 8 GB, 4060 Ti 16 GB vs 8 GB).
VRAM_MATTERS = {"3060", "4060 ti", "3050", "6500 xt", "7600 xt"}


@dataclass
class TechMatch:
    brand: Brand
    model: str
    segment: str


def _brand(name: str, segment: str) -> Brand:
    b = _BRAND_BY_NAME.get(name)
    if b and b.segment == segment:
        return b
    return Brand(name.capitalize() if name not in ("amd", "hp", "msi") else name.upper(), segment)


def _pos(text: str, words: tuple[str, ...]) -> int | None:
    hits = [m.start() for w in words for m in [re.search(rf"(?<![a-z0-9]){re.escape(w)}(?![a-z0-9])", text)] if m]
    return min(hits) if hits else None


def _has(text: str, words: tuple[str, ...]) -> bool:
    return any(re.search(rf"(?<![a-z0-9]){re.escape(w)}(?![a-z0-9])", text) for w in words)


def gpu(text: str) -> tuple[str, str] | None:
    """('nvidia', 'rtx 4070 super') from 'MSI GeForce RTX 4070 SUPER 12GB'."""
    m = NVIDIA.search(text)
    if m:
        series = "rtx" if "rtx" in m.group(0) else "gtx"
        suffix = re.sub(r"ti\s?super", "ti super", m.group(2) or "")
        name = f"{series} {m.group(1)}" + (f" {suffix}" if suffix else "")
        short = name.split(" ", 1)[1]
        if short in VRAM_MATTERS:
            v = VRAM.search(text[m.end():m.end() + 40]) or VRAM.search(text)
            if v and 4 <= int(v.group(1)) <= 24:
                name += f" {v.group(1)}gb"
        return "nvidia", name
    m = AMD_GPU.search(text)
    if m and (int(m.group(1)) >= 400):
        name = f"rx {m.group(1)}" + (f" {m.group(2)}" if m.group(2) else "")
        return "amd", name
    return None


def cpu(text: str) -> tuple[str, str, str] | None:
    """('amd', 'ryzen 7 7800x3d', generation '7000') or ('intel', 'i5 13600k', '13')."""
    m = RYZEN.search(text)
    if m:
        return "amd", f"ryzen {m.group(1)} {m.group(2)}", m.group(2)[0] + "000"
    m = CORE_ULTRA.search(text)
    if m:
        return "intel", f"core ultra {m.group(1)} {m.group(2)}", "ultra"
    m = INTEL.search(text)
    if m:
        num = m.group(2)
        # 13600K / 10750H: 10th-14th gen; 1235U / 1135G7: 10th-13th on 4 digits; 8250U / 7700K: 2nd-9th
        gen = num[:2] if len(num) == 5 or (num[0] == "1" and num[1] in "0123") else num[0]
        return "intel", f"i{m.group(1)} {num}{m.group(3)}", gen
    return None


_SPELLING = [(re.compile(r"(?<![a-z])play\s*st[a-z]{2,6}n(?![a-z])"), "playstation"),  # play station, playstaition, playstion
             (re.compile(r"(?<![a-z])ps\s+(?=[1-5](?![0-9]))"), "ps")]  # "ps 4" -> "ps4"
# "mai bun ca PS5", "ca un PS5", "compatibil cu PS5", "pentru PS5": another device named for comparison or fit.
_COMPARED = re.compile(r"(?<![a-z])(?:mai (?:bun|buna|tare|rapid|rapida) (?:ca|decat)|ca (?:un|o|si)|similar[a]? cu|asemanator cu|"
                       r"alternativa (?:la|pentru)|compatibil[a]?(?: cu)?|pentru|for|tip) (?:consola )?\S+(?: (?:pro|slim|digital|oled|\d))?")


def _variant(rules: list[tuple[str, str]]):
    def pick(title: str) -> str | None:
        return next((model for pattern, model in rules if re.search(rf"(?<![a-z0-9]){pattern}(?![a-z0-9])", title)), None)
    return pick


# The variant can sit anywhere in the title, not right after the name: "Consola PlayStation 5 (PS5) Digital Edition".
VARIANT = {
    "ps5": _variant([("pro", "ps5 pro"), ("digital|digitala|fara unitate|fara disc|without disc", "ps5 digital")]),
    "ps4": _variant([("pro", "ps4 pro")]),
    "switch": _variant([("oled", "switch oled"), ("lite", "switch lite")]),
    "steam deck": _variant([("oled", "steam deck oled")]),
    "xbox one": _variant([("one x", "xbox one x")]),
}


def device_pos(title: str) -> int | None:
    """Where in the (clean) title the first console/handheld is named, if any."""
    plain = _COMPARED.sub(lambda m: " " * len(m.group(0)), title)
    hits = [m.start() for pattern, *_r in CONSOLES for m in [pattern.search(plain)] if m]
    return min(hits) if hits else None


GAMES = re.compile(r"(?<![a-z])(?:jocuri|joc|games|game|cd|cd-uri|dvd|caseta|casete|cartus|cartuse)(?![a-z])")


def clean(title: str) -> str:
    title = re.sub(r"[®™©]", " ", title)
    title = re.sub(r"(?<=rtx|gtx|ore|rce|eon|zen|tel)(?:tm|\(r\)|r)(?=\s)", "", title)  # "rtxtm 3060" (TM, R) after normalize
    title = re.sub(r"^(?:vand|vind)\s*(?:/|sau|si)\s*schimb\w*\s*", "", title)  # "vand/schimb RTX 3060": selling it
    for pattern, repl in _SPELLING:
        title = pattern.sub(repl, title)
    return title


def match(title: str, full: str) -> TechMatch | None:
    """What this listing sells. title and full are normalize()d. The device named FIRST in the title is the one
    for sale ("PS4 Slim + PS VR compatibil PS5" is a PS4); devices named only to compare or fit don't count."""
    title, full = clean(title), clean(full)
    plain = _COMPARED.sub(lambda m: " " * len(m.group(0)), title)
    hits = [(m.start(), i) for i, (pattern, *_r) in enumerate(CONSOLES) for m in [pattern.search(plain)] if m]
    if hits:
        _, i = min(hits)  # earliest in the title; at the same place, the more specific pattern (listed first)
        _p, brand, model, seg = CONSOLES[i]
        model = VARIANT.get(model, lambda t: model)(plain) or model  # "PlayStation 5 (PS5) Digital Edition"
        return TechMatch(_brand(brand, seg), model, seg)
    # Whichever comes first says what it is: "Placa video RTX 3060 pentru PC" is a card,
    # "PC gaming Ryzen 7 / placa video RTX 4070" is a PC.
    where = {k: _pos(title, words) for k, words in
             (("laptop", LAPTOP_WORDS), ("pc", PC_WORDS), ("part", GPU_WORDS + CPU_WORDS + RAM_WORDS))}
    first = min((k for k in where if where[k] is not None), key=lambda k: where[k], default=None)
    line = LAPTOP_RE.search(title)
    named_part = _has(title, GPU_WORDS + CPU_WORDS)  # "placa video", "procesor": a part, whatever else is listed
    laptop = first == "laptop" or "macbook" in title or bool(line and (where["part"] is None or line.start() < where["part"]))
    pc = (first == "pc" or (not named_part and bool(cpu(title)) and bool(gpu(title)))) and not laptop
    # ("Ryzen 9 5950X | RTX 4060 Ti 16GB | 64GB RAM": a processor and a card in one title is a whole PC)
    if "macbook" in title or (pc and _has(title, ("imac", "mac mini", "mac studio"))):
        line = next((x for x in ("macbook air", "macbook pro", "imac", "mac mini", "mac studio") if x in title), "macbook")
        chip = APPLE_M.search(title) or APPLE_M.search(full)
        if chip:
            return TechMatch(_brand("apple", "mac"), f"{line} m{chip.group(1)}" + (f" {chip.group(2)}" if chip.group(2) else ""), "mac")
        return TechMatch(_brand("apple", "mac"), f"{line} intel", "mac")
    if laptop or pc:
        what = "laptop" if laptop else "pc"
        g = gpu(title) or gpu(full)
        if g:
            return TechMatch(_brand(what, what), g[1], what)
        c = cpu(title) or cpu(full)
        if c:
            # "ryzen 5 gen 5000", "i7 gen 12", "core ultra 7 gen ultra": the tier and generation set the price
            words = c[1].split(" ")
            family = " ".join(words[:3]) if c[1].startswith("core ultra") else " ".join(words[:2]) if c[0] == "amd" else words[0]
            return TechMatch(_brand(what, what), f"{family} gen {c[2]}".replace(" gen ultra", ""), what)
        return TechMatch(_brand(what, what), "", what)  # brand-level only: too rough to price
    if _has(title, GPU_WORDS) or (gpu(title) and not cpu(title) and not DDR.search(title) and not _has(title, CPU_WORDS)):
        g = gpu(title)
        if g:
            return TechMatch(_brand(g[0], "gpu"), g[1], "gpu")
    if _has(title, CPU_WORDS):
        c = cpu(title)
        if c:
            return TechMatch(_brand(c[0], "cpu"), c[1], "cpu")
    if DDR.search(title) and (_has(title, RAM_WORDS + ("kit",)) or title.startswith("ddr")):
        m = RAM_GB.search(title)
        gb = None
        if m:
            gb = int(m.group(1)) * int(m.group(2)) if m.group(1) else int(m.group(3))
        laptop_ram = _has(title, ("so-dimm", "sodimm", "so dimm", "laptop"))
        if gb and gb in (8, 16, 24, 32, 48, 64, 96, 128):
            return TechMatch(_brand("ram", "ram"), f"ddr{DDR.search(title).group(1)} {gb}gb" + (" laptop" if laptop_ram else ""), "ram")
    return None


# --- flags particular to electronics ----------------------------------------------------------------

BROKEN = ["nu porneste", "nu mai porneste", "nu se aprinde", "nu afiseaza", "nu da imagine", "fara imagine", "ecran spart",
          "display spart", "afisaj spart", "placa de baza arsa", "placa arsa", "defect", "defecta", "defecte", "pentru piese",
          "nefunctional", "nefunctionala", "blue light of death", "ylod", "rrod", "artefacte", "artifacts",
          "se supraincalzeste", "se opreste singur", "se opreste singura", "nu citeste discuri"]
LOCKED = ["icloud", "activation lock", "blocat icloud", "blocat pe cont", "cont blocat", "mdm", "parola bios", "bios parolat",
          "bios blocat", "banned", "ban pe cont", "consola banata", "cont banat"]
MODDED = ["modat", "modata", "chipat", "chipata", "jailbreak", "jailbreakuit", "decodat", "decodata", "piratat", "piratata",
          "custom firmware", "cfw", "hackuit"]
# What's sold is an accessory or a game, not the device: the title starts with it, or says "for PS5".
PART_START = ["controller", "controler", "maneta", "manete", "joc", "jocuri", "panouri", "panou", "capac", "capace",
              "covers", "cover", "carcase", "geanta", "rucsac", "trackpad", "touchpad", "palmrest", "boxa", "difuzor", "abonament", "cont", "voucher", "pedale", "cockpit", "scaun", "husa", "huse", "cablu", "stand", "suport",
              "incarcator", "dock", "docking", "skin", "folie", "ventilator", "cooler", "carcasa", "pad", "joystick",
              "volan", "casti", "headset", "card", "figurina", "figurine", "telecomanda", "baterie", "display", "ecran",
              "tastatura", "topcase", "balamale", "placa de baza", "mufa", "sursa", "radiator", "pasta"]
ACCESSORY_ANYWHERE = ["pentru ps5", "pentru ps4", "pentru xbox", "pentru switch", "pentru steam deck", "compatibil ps5",
                      "compatibil cu ps5", "compatibila ps5", "for ps5", "for switch", "pentru nintendo"]
# Cheap clone consoles ("Consola Magica 10000 jocuri", game sticks): not the real thing.
CLONES = ["consola magica", "magica", "game stick", "gamestick", "retro game stick", "jocuri incluse", "10000 jocuri", "20000 jocuri",
          "mii de jocuri", "consola retro portabila", "m8 game", "x7 game", "r36s"]
LEADING = re.compile(r"^(?:vand|vind|vinde|vanzare|de vanzare|ofer|urgent|super pret|oferta|pachet|set|nou|noua)\b[\s:!,.-]*")
SERVICE = ["reparatii", "reparatie", "service", "repar", "inchiriez", "inchiriere", "decodare", "modare"]
WANTED = ["caut", "cumpar", "cumparam", "achizitionez", "achizitionam"]
