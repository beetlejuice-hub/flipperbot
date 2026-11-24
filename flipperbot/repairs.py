"""Faulty items worth fixing: what's probably wrong, what the fix costs, and what it's worth once fixed.

People throw out a PS5 with a dead HDMI port, an iPhone with a cracked screen, a drill with worn brushes, a watch
that only needs a battery. Fixed, they sell like working ones. For a faulty listing the bot reads the fault from
the title and description, looks up the usual fix (cost in Romania, do it yourself or a repair shop, how often it
works), and prices it against WORKING ones of the same model: profit if fixed = what a working one sells for
(cautious end) - price - the fix's high cost. Claude's check then looks at the photos and gives its own view.

Costs are rough Romanian 2026 prices (parts plus a service where "service"); the price book is what really decides.
"""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class Fault:
    niches: tuple[str, ...]
    words: tuple[str, ...]  # normalize()d phrases in the title or description
    name: str
    fix: str
    cost: tuple[int, int]  # lei
    how: str  # "DIY" or "service"
    odds: str  # "high", "medium", "low": how often the fix works


ODDS_RANK = {"high": 0, "medium": 1, "low": 2}

# Specific faults first: when a listing names several, the riskiest and dearest one counts.
FAULTS: list[Fault] = [
    # --- consoles, PCs, laptops ---
    Fault(("electronics",), ("hdmi", "port hdmi", "mufa hdmi", "nu da imagine", "fara imagine", "no signal"),
          "no picture (HDMI port)", "replace the HDMI port", (150, 300), "service", "high"),
    Fault(("electronics",), ("se supraincalzeste", "supraincalzire", "se incinge", "ventilator", "zgomot", "face zgomot"),
          "overheating / loud fan", "clean it, new thermal paste", (50, 150), "DIY", "high"),
    Fault(("electronics",), ("nu citeste discuri", "nu citeste cd", "unitate optica", "nu baga discul", "nu scoate discul",
                             "disc drive"),
          "disc drive", "repair or replace the disc drive", (150, 350), "service", "medium"),
    Fault(("electronics",), ("drift", "joycon", "joy-con", "joy con"),
          "controller drift", "new stick modules", (30, 80), "DIY", "high"),
    Fault(("electronics",), ("nu incarca", "nu se incarca", "mufa incarcare", "port usb-c", "usb-c"),
          "won't charge (charging port/chip)", "charging port or charging chip", (120, 300), "service", "medium"),
    Fault(("electronics",), ("blue light of death", "bld", "ylod", "rrod", "red ring", "artefacte", "artifacts", "reball",
                             "placa de baza arsa", "placa arsa", "scurtcircuit"),
          "board/GPU fault", "board repair (reball, chip): often not worth it", (300, 800), "service", "low"),
    Fault(("electronics",), ("display spart", "ecran spart", "afisaj spart", "display crapat", "ecran crapat", "linii pe ecran",
                             "pixeli morti"),
          "cracked or dead screen", "new screen", (250, 700), "service", "high"),
    Fault(("electronics",), ("tastatura nu", "taste nu", "tastatura defecta", "lipsa taste"),
          "keyboard", "new keyboard", (100, 300), "service", "high"),
    Fault(("electronics",), ("baterie", "acumulator", "nu tine bateria", "tine putin"),
          "worn battery", "new battery", (120, 400), "DIY", "high"),
    Fault(("electronics",), ("parola bios", "bios", "parola", "blocat cu parola", "cont microsoft"),
          "password-locked", "BIOS/firmware reset by a repair shop", (100, 250), "service", "medium"),
    # --- phones ---
    Fault(("phones",), ("display spart", "ecran spart", "sticla sparta", "display crapat", "ecran crapat", "fisurat",
                        "crapat", "linii pe ecran", "pata pe ecran", "pixeli morti", "ecran ars", "burn in"),
          "cracked or damaged screen", "new screen (OEM or good aftermarket)", (250, 900), "service", "high"),
    Fault(("phones",), ("sticla spate", "spate spart", "capac spate"),
          "cracked back glass", "new back glass (laser)", (150, 400), "service", "high"),
    Fault(("phones",), ("baterie", "acumulator", "se descarca", "battery", "service baterie", "capacitate"),
          "worn battery", "new battery", (120, 300), "service", "high"),
    Fault(("phones",), ("nu incarca", "mufa", "port incarcare"),
          "won't charge (port)", "new charging port", (100, 250), "service", "high"),
    Fault(("phones",), ("camera nu functioneaza", "camera defecta", "camera spate nu", "camera fata nu"),
          "camera", "new camera module", (150, 500), "service", "medium"),
    Fault(("phones",), ("face id nu", "faceid nu", "face id nefunctional", "faceid nefunctional", "touch id nu"),
          "Face ID / Touch ID", "rarely fixable (paired to the board): value it without", (0, 400), "service", "low"),
    Fault(("phones",), ("probleme semnal", "probleme de semnal", "fara semnal", "nu are semnal", "nu prinde semnal",
                        "nu are retea", "no service", "baseband"),
          "no signal (baseband)", "board-level repair: often not worth it", (250, 600), "service", "low"),
    Fault(("phones",), ("buton on/off", "buton pornire", "butonul de pornire", "buton power", "buton volum", "butoane"),
          "stuck or dead button", "a new button flex", (80, 200), "service", "high"),
    Fault(("phones",), ("nu porneste", "nu se aprinde", "bootloop", "placa de baza", "a fost in apa", "a cazut in apa",
                        "udat", "oxidat"),
          "dead / water damage", "board repair: a gamble", (200, 700), "service", "low"),
    # --- watches ---
    Fault(("watches",), ("baterie", "nu are baterie", "necesita baterie", "schimbat bateria", "trebuie baterie"),
          "flat battery (quartz)", "a new battery", (30, 60), "DIY", "high"),
    Fault(("watches",), ("revizie", "necesita revizie", "de revizuit", "service", "o ia inainte", "ramane in urma",
                         "se opreste", "nu merge", "nu functioneaza", "stricat", "defect"),
          "needs a service (movement)", "a watchmaker's service", (300, 800), "service", "medium"),
    Fault(("watches",), ("geam zgariat", "sticla zgariata", "geam spart", "sticla sparta", "geam crapat"),
          "scratched or cracked crystal", "a new crystal", (80, 250), "service", "high"),
    Fault(("watches",), ("lipsa coroana", "fara coroana", "coroana rupta", "ax rupt"),
          "missing crown / broken stem", "a new crown and stem", (100, 300), "service", "medium"),
    # --- smartwatches (watches in the smart/band segment: their own faults, not a watchmaker's) ---
    Fault(("smartwatches",), ("display spart", "ecran spart", "sticla sparta", "geam spart", "ecran crapat", "fisurat"),
          "cracked screen", "a new screen", (300, 900), "service", "medium"),
    Fault(("smartwatches",), ("baterie", "se descarca", "nu tine bateria", "baterie umflata"),
          "worn battery", "a new battery", (150, 350), "service", "medium"),
    Fault(("smartwatches",), ("icloud", "blocat", "cont", "parola"),
          "account-locked", "not fixable: locked to the owner's account", (0, 0), "service", "low"),
    # --- cameras and lenses ---
    Fault(("cameras",), ("ciuperca", "ciuperci", "fungus", "ceata", "haze"),
          "fungus / haze in the lens", "a lens cleaning (fungus can etch glass)", (150, 400), "service", "medium"),
    Fault(("cameras",), ("nu declanseaza", "obturator", "shutter", "perdea"),
          "shutter", "shutter repair or replacement", (300, 900), "service", "medium"),
    Fault(("cameras",), ("eroare", "error", "err "),
          "error code", "depends on the code: aperture/flex cable is common", (150, 500), "service", "medium"),
    Fault(("cameras",), ("baterie", "acumulator", "fara incarcator"),
          "battery / charger missing", "a battery and charger", (60, 200), "DIY", "high"),
    # --- power tools ---
    Fault(("tools",), ("perii", "carbuni", "periile", "scantei", "scanteiaza"),
          "worn carbon brushes", "new carbon brushes", (30, 80), "DIY", "high"),
    Fault(("tools",), ("acumulator", "baterie", "fara acumulator", "acumulatorul nu", "nu tine"),
          "battery dead or missing", "a new battery (or sell as bare tool)", (150, 450), "DIY", "high"),
    Fault(("tools",), ("intrerupator", "buton", "trigger"),
          "trigger switch", "a new switch", (50, 150), "DIY", "high"),
    Fault(("tools",), ("mandrina", "percutie", "nu percuteaza", "nu bate"),
          "chuck / hammer mechanism", "chuck or mechanism repair", (100, 300), "service", "medium"),
    # --- clothing and sneakers ---
    Fault(("clothing",), ("fermoar stricat", "fermoar defect", "fermoarul nu", "fermoar rupt"),
          "broken zip", "a new zip at a tailor", (40, 120), "service", "high"),
    Fault(("clothing",), ("pata", "pete", "patat"),
          "stain", "a dry cleaner", (30, 80), "service", "medium"),
    Fault(("clothing",), ("gaura", "gauri", "rupt", "rupta", "ruptura", "descusut", "descusuta"),
          "hole or tear", "an invisible mend", (50, 150), "service", "medium"),
    Fault(("clothing",), ("lipsa nasture", "lipsa nasturi", "nasture lipsa"),
          "missing button", "a new button", (10, 40), "DIY", "high"),
    Fault(("sneakers",), ("dezlipit", "dezlipiti", "talpa dezlipita"),
          "sole coming off", "re-glue the sole at a cobbler", (40, 100), "service", "high"),
    Fault(("sneakers",), ("murdari", "murdar", "pateti", "pete"),
          "dirty / stained", "a deep clean", (30, 80), "DIY", "high"),
]

# Faulty, but nothing names what's wrong: an unknown fault, priced as a gamble.
UNKNOWN: dict[str, Fault] = {
    "electronics": Fault(("electronics",), (), "unknown fault (doesn't work)", "diagnose first: anything from a cable to the board",
                         (100, 600), "service", "low"),
    "phones": Fault(("phones",), (), "unknown fault", "diagnose first", (150, 600), "service", "low"),
    "watches": Fault(("watches",), (), "doesn't work", "a battery if quartz, a service if mechanical", (50, 600), "service", "medium"),
    "cameras": Fault(("cameras",), (), "unknown fault", "diagnose first", (150, 600), "service", "low"),
    "tools": Fault(("tools",), (), "unknown fault", "brushes or switch most often", (50, 250), "DIY", "medium"),
    "smartwatches": Fault(("smartwatches",), (), "dead, for parts or locked", "often account-locked or a dead board: a gamble",
                          (150, 600), "service", "low"),
}
FOR_PARTS = ("pentru piese", "for parts", "piese", "nefunctional", "nefunctionala")

# Never "fixable": a stolen or account-locked phone, a fake.
NOT_FIXABLE = {"locked", "replica", "part", "lot", "wanted", "service"}


def _hit(text: str, words: tuple[str, ...]) -> bool:
    return any(re.search(rf"(?<![a-z0-9]){re.escape(w.strip())}(?![a-z0-9])", text) for w in words)


def faults(niche: str, text: str) -> list[Fault]:
    """The known faults this (normalize()d) text names, for the category."""
    return [f for f in FAULTS if niche in f.niches and _hit(text, f.words)]


def diagnose(niche: str, text: str, flags: set[str]) -> Fault | None:
    """The fault for a faulty listing: everything it names, added up (the costs summed, the worst odds), or an unknown
    one. "niche" is "smartwatches" for smart watches and bands."""
    if flags & NOT_FIXABLE:
        return None
    found = faults(niche, text)
    faulty = flags & {"broken", "battery", "worn_shutter"}
    if not found and not faulty:
        return None
    if not found:
        if "battery" in flags and niche == "watches":
            return next(f for f in FAULTS if f.name == "flat battery (quartz)")
        if "worn_shutter" in flags:
            return Fault(("cameras",), (), "worn shutter (high click count)", "a new shutter, fitted", (700, 1100), "service",
                         "high")
        return UNKNOWN.get(niche)
    if not faulty:  # "battery 85%" in a working phone's ad isn't a fault: only count it if the listing is faulty
        return None
    if niche in ("phones", "smartwatches", "electronics") and _hit(text, FOR_PARTS) and len(found) == 1 \
            and found[0].odds != "low":
        found.append(UNKNOWN[niche])  # "for parts" with one named fault: there may be more wrong than it says
    if len(found) == 1:
        return found[0]
    found.sort(key=lambda f: (-ODDS_RANK[f.odds], -f.cost[1]))
    worst = found[0]
    return Fault(worst.niches, (), " + ".join(f.name for f in found), "; ".join(f.fix for f in found),
                 (sum(f.cost[0] for f in found), sum(f.cost[1] for f in found)),
                 "service" if any(f.how == "service" for f in found) else "DIY", worst.odds)


def assess(niche: str, text: str, flags: set[str], price: int, working: tuple[int, int] | None,
           good_profit: int) -> dict | None:
    """What fixing it would give: the fault, the fix, and profit if fixed against working ones of the model."""
    f = diagnose(niche, text, flags)
    if f is None:
        return None
    out = {"fault": f.name, "fix": f.fix, "cost": list(f.cost), "how": f.how, "odds": f.odds}
    if working:
        lo, hi = working
        out.update(working_low=lo, working_high=hi, profit_if_fixed=lo - price - f.cost[1],
                   worth_it=f.odds != "low" and lo - price - f.cost[1] >= good_profit)
    return out


def line(fx: dict) -> str:
    """One line for the reason: what's wrong, the fix, and what fixing it leaves."""
    s = f"🔧 {fx['fault']}: {fx['fix']} (~{fx['cost'][0]}–{fx['cost'][1]} lei, {fx['how']}, {fx['odds']} odds)"
    if "profit_if_fixed" in fx:
        s += f"; working ones sell ~{fx['working_low']}–{fx['working_high']}, ~{fx['profit_if_fixed']} lei if fixed"
    return s
