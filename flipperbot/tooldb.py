"""Power tools without AI: brand + model code (makita|dhp485, dewalt|dcd796, milwaukee|m18 fpd2, hilti|te 30).
A bare tool ("doar corp", "fara acumulator", "solo") is priced apart from a kit with batteries and charger: the
batteries can be half the price. Batteries on their own are items too (makita|battery 5ah).

Chinese clones sold as "Makita 48V/88V/199V" (voltages the real brands don't make) are the classic fake here.
"""

from __future__ import annotations

import re

from .techdb import TechMatch, _brand, _w
from .watchdb import Brand

# segment: pro (resells well), diy (cheap, slow), garden (chainsaws, trimmers)
BRANDS: list[Brand] = [
    Brand("Makita", "pro", ()), Brand("DeWalt", "pro", ("de walt",)), Brand("Milwaukee", "pro", ()),
    Brand("Hilti", "pro", ()), Brand("Festool", "pro", ()), Brand("Metabo", "pro", ()), Brand("Hikoki", "pro", ("hitachi",)),
    Brand("Bosch", "pro", ("bosch professional",)), Brand("Fein", "pro", ()),  # not "Flex": in Romanian it means angle grinder
    Brand("Stihl", "garden", ()), Brand("Husqvarna", "garden", ()),
    Brand("Ryobi", "diy", ()), Brand("Einhell", "diy", ()), Brand("Parkside", "diy", ()), Brand("Black Decker", "diy", ("black+decker", "black & decker")),
    Brand("Worx", "diy", ()), Brand("Stanley", "diy", ()),
]
BRAND_RE = _w(r"(makita|dewalt|de walt|milwaukee|hilti|festool|metabo|hikoki|hitachi|bosch|fein|stihl|husqvarna|ryobi|"
              r"einhell|parkside|black\s?\+?\s?(?:&\s?)?decker|worx|stanley)")
# Model codes: Makita DHP485 / GA5040 / DTD153; DeWalt DCD796 / DCF887; Milwaukee M18 FPD2 / M12 FID; Hilti TE 30 / SF 6H-A22;
# Bosch GSR 18V-60 / GBH 2-26; Stihl MS 261 / FS 55; Husqvarna 435; Metabo SB 18 LTX.
CODE = re.compile(r"(?<![a-z0-9])(m1[28]\s?[a-z]{2,6}\d?|[a-z]{2,4}\s?\d{1,2}-\d{2,3}[a-z]?|\d{4}[a-z]{1,2}|[a-z]{1,4}\s?-?\d{2,4}[a-z0-9]{0,5}(?:\s?-\s?\d{1,3}v?)?(?:\s?-?a\d{2})?)(?![a-z0-9])")
NOT_CODE = re.compile(r"^(?:\d+\s?v|v\d+|\d+ah|ah\d*|\d+mm|mm\d+|\d+w|w\d+|nr\d*|lei\d*|ron\d*|\d+|x\d+|kg\d*|cm\d*|m\d|rpm\d*|"
                      r"lxt\d*|xr\d*|ip\d+|gen\d*|li-?ion\d*|set\d*|kit\d*|buc\d*)$")
MILWAUKEE = _w(r"m(1[28])\s?(?:fuel\s?)?(?!fuel)([a-z]{2,6}\d?(?:-\d{1,2})?)")
BARE = ["doar corp", "fara acumulator", "fara acumulatori", "fara baterie", "fara baterii", "body only", "solo", "corp masina",
        "fara incarcator si acumulator", "fara incarcator"]
BATTERY = _w(r"(?:acumulator|acumulatori|baterie|baterii|acumlatori)\s.*?(\d(?:[.,]\d)?)\s?ah")
# Voltages the real brands don't make for handheld tools: Chinese clones in Makita/DeWalt colours.
FAKE_VOLT = _w(r"(?:makita|dewalt|milwaukee|bosch)\D{0,20}(21|24|26|42|48|88|98|99|128|168|188|198|199|288|388)\s?v")


def match(title: str, full: str) -> TechMatch | None:
    b = BRAND_RE.search(title)
    if not b:
        return None
    name = re.sub(r"\s|\+|&", "", b.group(1)).replace("dewalt", "dewalt").replace("hitachi", "hikoki").replace("blackdecker", "black decker")
    brand = next((x for x in BRANDS if x.name.lower().replace(" ", "") == name.replace(" ", "")), None)
    seg = brand.segment if brand else "diy"
    key = brand.name.lower() if brand else name
    m = BATTERY.search(title)
    if m and title.split()[0] in ("acumulator", "acumulatori", "baterie", "baterii", "set", "2", "3", "acumlatori"):
        ah = m.group(1).replace(",", ".").rstrip("0").rstrip(".")
        return TechMatch(_brand(key, seg), f"battery {ah}ah", seg)
    after = title[b.end():]
    mw = MILWAUKEE.search(title)
    if key == "milwaukee" and mw:  # "M18 FUEL FPD2": the platform, the line, then the model
        bare = any(w in title for w in BARE) or any(w in full for w in BARE[:6])
        return TechMatch(_brand(key, seg), f"m{mw.group(1)} {mw.group(2)}" + (" solo" if bare else ""), seg)
    codes = [c.group(1) for c in CODE.finditer(after) if not NOT_CODE.match(re.sub(r"\s", "", c.group(1)))
             and not re.match(r"^m1[28](?:\s?fuel)?$", c.group(1))]
    if not codes:
        return TechMatch(_brand(key, seg), "", seg)  # brand only: too rough to price
    code = re.sub(r"\s+", " ", codes[0]).strip()
    if not code.startswith("m1"):
        code = re.sub(r"\s|-(?=\d)", "", code) if re.match(r"^[a-z]{1,4}\s?-?\d", code) and " v" not in code else code
    bare = any(w in title for w in BARE) or any(w in full for w in BARE[:6])
    return TechMatch(_brand(key, seg), code + (" solo" if bare else ""), seg)


BROKEN = ["nu porneste", "nu merge", "defect", "defecta", "pentru piese", "nefunctional", "nefunctionala", "carbuni uzati",
          "motor ars", "bobinaj ars", "rupt", "rupta", "sparta"]
LOCKED: list[str] = []
PART_START = ["cuie", "burghie", "burghiu", "biti", "bit", "disc", "discuri", "lama", "lame", "organizator", "suport",
              "adaptor", "perie", "perii", "carbuni", "cablu", "geanta", "cutie", "valiza", "accesorii", "set accesorii",
              "freza", "freze", "panza", "panze", "lant", "sarma", "furtun", "manere", "maner", "piese", "rotor", "stator",
              "intrerupator", "mandrina", "capac", "carcasa"]
ACCESSORY_ANYWHERE = ["compatibil makita", "compatibil dewalt", "compatibil milwaukee", "compatibil bosch", "tip makita",
                      "pentru makita", "pentru dewalt", "pentru milwaukee", "adaptor makita", "adaptor dewalt"]
CLONES = ["tip makita", "replica", "copie", "imitatie", "made in china makita"]
WANTED = ["caut", "cumpar", "cumparam", "achizitionez", "achizitionam"]
SERVICE = ["reparatii", "reparatie", "service", "inchiriez", "inchiriere", "bobinaj"]


def extra_flags(title: str, full: str) -> set[str]:
    return {"replica"} if FAKE_VOLT.search(title) else set()
