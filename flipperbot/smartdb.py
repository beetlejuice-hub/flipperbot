"""Smartwatches and fitness bands without AI: the exact model, so each is priced against the same model only.

A Huawei Band 10 (a 150-lei tracker) and a Huawei Watch GT 5 Pro (a 1,500-lei watch) share a brand and nothing
else: lumping them priced the band against the watches and called it a steal. Here every listing gets its line
and generation: huawei|band 10, huawei|watch fit 3, huawei|watch gt 5 pro, xiaomi|smart band 9, samsung|galaxy
watch 6 classic, samsung|galaxy fit 3, apple|watch series 9, apple|watch ultra 2, garmin|fenix 7x, amazfit|bip 5...
Segment "band" (cheap trackers) or "smart" (watches).
"""

from __future__ import annotations

import re

from .techdb import TechMatch, _brand, _w

# (pattern, brand, model template, segment); first match wins, so the more specific lines come first.
# {1}, {2}... are the pattern's groups.
MODELS: list[tuple[re.Pattern[str], str, str, str]] = [
    # Huawei
    (_w(r"huawei\s*(?:smart\s*)?band\s*(\d{1,2})(?:\s*(pro|nfc))?"), "huawei", "band {1} {2}", "band"),
    (_w(r"huawei\s*watch\s*fit\s*(\d)?(?:\s*(pro|special edition|se|new))?"), "huawei", "watch fit {1} {2}", "smart"),
    (_w(r"huawei\s*(?:watch\s*)?gt\s*(\d)?(?:\s*(pro|runner|se|cyber))?"), "huawei", "watch gt {1} {2}", "smart"),
    (_w(r"huawei\s*watch\s*(ultimate|d2|d|kids)"), "huawei", "watch {1}", "smart"),
    (_w(r"huawei\s*watch\s*(\d)(?:\s*(pro))?"), "huawei", "watch {1} {2}", "smart"),
    (_w(r"(?:honor\s*)?(?:magic\s*)?band\s*(\d)"), "honor", "band {1}", "band"),
    # Xiaomi
    (_w(r"(?:xiaomi\s*)?(?:smart|mi)\s*band\s*(\d{1,2})(?:\s*(pro|active|nfc))?"), "xiaomi", "smart band {1} {2}", "band"),
    (_w(r"(?:xiaomi\s*)?redmi\s*(?:smart\s*)?band\s*(\d)?(?:\s*(pro))?"), "xiaomi", "redmi band {1} {2}", "band"),
    (_w(r"xiaomi\s*(?:mi\s*)?watch\s*(s\d|\d)?(?:\s*(active|pro|lite))?"), "xiaomi", "watch {1} {2}", "smart"),
    (_w(r"redmi\s*watch\s*(\d)?(?:\s*(active|lite))?"), "xiaomi", "redmi watch {1} {2}", "smart"),
    # Samsung
    (_w(r"galaxy\s*fit\s*(\d)?(?:\s*(e|pro))?"), "samsung", "galaxy fit {1} {2}", "band"),
    (_w(r"galaxy\s*watch\s*(ultra|fe)"), "samsung", "galaxy watch {1}", "smart"),
    (_w(r"samsung\s*(?:galaxy\s*)?watch\s*(\d)(?:\s*(classic|pro|active))?"), "samsung", "galaxy watch {1} {2}", "smart"),
    (_w(r"galaxy\s*watch\s*(\d)(?:\s*(classic|pro|active))?"), "samsung", "galaxy watch {1} {2}", "smart"),
    (_w(r"galaxy\s*watch\s*active\s*(\d)?"), "samsung", "galaxy watch active {1}", "smart"),
    # Apple
    (_w(r"apple\s*watch\s*ultra\s*(\d)?|(?:^|\s)watch\s*ultra\s*(\d)?(?=.*apple)"), "apple", "watch ultra {1}", "smart"),
    (_w(r"apple\s*watch\s*se\s*(\d)?"), "apple", "watch se {1}", "smart"),
    (_w(r"(?:apple\s*w\w{2,4}ch|iwatch)\s*(?:series\s*|s)?(\d{1,2})"), "apple", "watch series {1}", "smart"),
    # Garmin
    # fenix 7, 7s, 7x, 7 pro, 7x pro, 8, e; Solar/Sapphire left out (they'd split the comparison too thin)
    (_w(r"(?:garmin\s*)?fenix\s*(\d|e)(x|s)?(?:\s*(?:x|s)(?= ))?(?:\s*(pro))?"), "garmin", "fenix {1}{2} {3}", "smart"),
    (_w(r"(?:garmin\s*)?epix\s*(?:gen\s*)?(\d)?(?:\s*(pro))?"), "garmin", "epix {1} {2}", "smart"),
    (_w(r"(?:garmin\s*)?forerunner\s*(\d{2,3})"), "garmin", "forerunner {1}", "smart"),
    (_w(r"(?:garmin\s*)?venu\s*(\d|sq\s*\d?|x1)?(?:\s*(s|plus))?"), "garmin", "venu {1} {2}", "smart"),
    (_w(r"(?:garmin\s*)?vivoactive\s*(\d)"), "garmin", "vivoactive {1}", "smart"),
    (_w(r"(?:garmin\s*)?vivosmart\s*(\d)"), "garmin", "vivosmart {1}", "band"),
    (_w(r"(?:garmin\s*)?instinct\s*(\d|e|crossover)?(?:\s*(x|s|solar|pro))?"), "garmin", "instinct {1} {2}", "smart"),
    (_w(r"(?:garmin\s*)?(?:tactix|marq|enduro|quatix|descent)\s*(\w+)?"), "garmin", "{0}", "smart"),
    # Amazfit, Fitbit, others
    (_w(r"amazfit\s*(bip|gtr|gts|balance|active|cheetah|t-rex|trex|band|helio|falcon)\s*(\d|mini|pro|edge|ultra)?(?:\s*(pro|mini|ultra))?"),
     "amazfit", "{1} {2} {3}", "smart"),
    (_w(r"fitbit\s*(charge|inspire|luxe|versa|sense|ace)\s*(\d)?"), "fitbit", "{1} {2}", "band"),
    (_w(r"(?:google\s*)?pixel\s*watch\s*(\d)?"), "google", "pixel watch {1}", "smart"),
    (_w(r"(?:oneplus|one plus)\s*watch\s*(\d)?"), "oneplus", "watch {1}", "smart"),
    (_w(r"suunto\s*(race|vertical|9|7|5|run|ocean)\s*(peak|s|pro)?"), "suunto", "{1} {2}", "smart"),
    (_w(r"polar\s*(vantage|grit|pacer|ignite|unite)\s*(\w+)?"), "polar", "{1} {2}", "smart"),
    (_w(r"(?:whoop|oura)\s*(\w+)?"), "whoop", "{0}", "band"),
]
# A title that names a fitness tracker: the price class of a band, whatever the brand.
BAND_WORDS = ("bratara fitness", "bratara inteligenta", "smart band", "smartband", "fitness tracker", "fit tracker")


def match(title: str) -> TechMatch | None:
    """The exact smartwatch or band model in a (normalize()d) title, or None."""
    hits = [(m.start(), i, m) for i, (p, *_r) in enumerate(MODELS) for m in [p.search(title)] if m]
    if not hits:
        return None
    _, i, m = min(hits, key=lambda h: (h[0], h[1]))
    _p, brand, template, seg = MODELS[i]
    groups = [m.group(0)] + [g or "" for g in m.groups()]
    model = re.sub(r"\s+", " ", template.format(*groups)).strip()
    if template == "{0}":
        model = re.sub(r"^(garmin|whoop|oura)\s*", "", model)
        brand = "oura" if "oura" in m.group(0) else brand
    return TechMatch(_brand(brand, seg), model, seg)
