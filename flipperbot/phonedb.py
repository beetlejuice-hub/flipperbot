"""Phones without AI: which exact phone a listing sells. Priced by model AND storage (an iPhone 13 Pro 128 GB
and 256 GB are different prices): apple|iphone 13 pro 256gb, samsung|galaxy s23 ultra 256gb, google|pixel 8 pro.
Only iPhones, Samsung Galaxy S/Z/A and Pixels are named exactly; other makers sell for little and fall to brand level.
"""

from __future__ import annotations

import re

from .techdb import TechMatch, _brand, _w
from .watchdb import Brand

BRANDS: list[Brand] = [
    Brand("Apple", "apple", ("iphone",)),
    Brand("Samsung", "samsung", ("galaxy",)),
    Brand("Google", "pixel", ("pixel",)),
    Brand("Xiaomi", "other", ("redmi", "poco")),
    Brand("OnePlus", "other", ()),
    Brand("Huawei", "other", ()),
    Brand("Motorola", "other", ()),
]

IPHONE = _w(r"(?:iphone|iphon|iohone|iphine|ipone|ifone)\s?(\d{1,2}|xs|xr|x|se|air)(?:\s?(pro\s?max|pro|plus|mini|max|e))?")
BARE_IPHONE = re.compile(r"^(1[1-8])\s?(pro\s?max|pro|plus|mini)\b")  # "18 pro max burgundy 256gb" in the phones category
GALAXY = _w(r"(?:samsung\s*)?(?:galaxy\s*)?(s\d{2}|a\d{2}|z\s?fold\s?\d|z\s?flip\s?\d|note\s?\d{1,2})(?:\s?(ultra|plus|\+|fe|edge))?")
PIXEL = _w(r"(?:google\s*)?pixel\s?(\d{1,2})(?:\s?(a|pro\s?xl|pro\s?fold|pro))?")
STORAGE = _w(r"(64|128|256|512|1\s?tb)\s?(?:gb|g)?")
OTHER = _w(r"(xiaomi|redmi|poco|oneplus|huawei|motorola|oppo|realme|honor|nokia|sony xperia)")


def _storage(title: str) -> str:
    m = STORAGE.search(title)
    if not m:
        return ""
    s = re.sub(r"\s", "", m.group(1))
    return " 1tb" if s == "1tb" else f" {s}gb"


def match(title: str, full: str) -> TechMatch | None:
    m = IPHONE.search(title) or BARE_IPHONE.search(title)
    if m:
        variant = re.sub(r"\s", " ", (m.group(2) or "")).replace("promax", "pro max")
        model = f"iphone {m.group(1)}" + (f" {variant}" if variant else "")  # "iphone air" too
        return TechMatch(_brand("apple", "apple"), model + _storage(title), "apple")
    m = GALAXY.search(title)
    if m and ("samsung" in title or "galaxy" in title):
        name = re.sub(r"\s", "", m.group(1))
        name = re.sub(r"z(fold|flip)(\d)", r"z \1 \2", name)
        variant = (m.group(2) or "").replace("+", "plus")
        model = f"galaxy {name}" + (f" {variant}" if variant else "")
        return TechMatch(_brand("samsung", "samsung"), model + _storage(title), "samsung")
    m = PIXEL.search(title)
    if m:
        variant = re.sub(r"\s", " ", m.group(2) or "")
        return TechMatch(_brand("google", "pixel"), f"pixel {m.group(1)}" + (f" {variant}" if variant else ""), "pixel")
    m = OTHER.search(title)
    if m:
        return TechMatch(_brand(m.group(1).split()[0], "other"), "", "other")
    return None


BROKEN = ["display spart", "ecran spart", "sticla sparta", "spart", "nu porneste", "nu se aprinde", "face id nu", "faceid nu",
          "bootloop", "placa de baza", "nu are semnal", "fara semnal", "defect", "defecta", "pentru piese", "nefunctional"]
# "neverlock(at)" means unlocked, so it's not here. Network-locked, iCloud/Google-locked, blacklisted: not resellable as is.
LOCKED = ["icloud", "blocat icloud", "cont icloud", "codat", "codat in retea", "blocat in retea", "blocat retea", "doar retea",
          "frp", "cont google", "blacklist", "raportat furat", "imei blocat", "blocat imei"]
PART_START = ["husa", "huse", "folie", "folii", "display", "ecran", "baterie", "acumulator", "carcasa", "rama", "incarcator",
              "cablu", "camera", "casti", "suport", "sticla", "capac", "mufa", "placa", "difuzor", "buton", "tastatura"]
ACCESSORY_ANYWHERE = ["pentru iphone", "pentru samsung", "compatibil iphone", "compatibil cu iphone", "for iphone", "pentru galaxy"]
CLONES = ["replica", "clona", "copie", "high copy", "1:1", "a+ quality", "aaa", "android in loc"]
WANTED = ["caut", "cumpar", "cumparam", "achizitionez", "achizitionam", "cumpar telefoane"]
SERVICE = ["reparatii", "reparatie", "service", "decodare", "decodez", "inlocuire display", "schimb display", "schimb baterie"]
