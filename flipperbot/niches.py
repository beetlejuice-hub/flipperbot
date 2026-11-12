"""The kinds of things flipperbot hunts. Everything that differs between watches and cameras
lives here: brands, OLX categories, searches, what makes a listing relevant, repair costs,
and what Claude is told to look for. The rest of the bot (tiers, lots, Claude, dashboard,
Telegram, Facebook) is shared.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from . import camdb, watchdb
from .watchdb import Brand


@dataclass(frozen=True)
class Niche:
    key: str
    label: str
    icon: str
    noun: str  # "watch", "camera or lens"
    brands: list[Brand]
    valuable_segments: frozenset[str]
    categories: tuple[str, ...]  # OLX categories where everything counts
    feeds: tuple[str, ...]  # OLX categories whose newest listings are read every poll
    words: tuple[str, ...]  # outside those categories, the title needs one of these (and a brand)
    not_words: tuple[str, ...]
    search_pool: tuple[str, ...]
    focus_pool: tuple[str, ...]  # lots, old, inherited: where sellers don't know what they have
    facebook_queries: tuple[str, ...]
    strong_words: tuple[str, ...] = ()  # where there are no categories (Facebook), the title needs one
    repair_ron: dict[str, int] = field(default_factory=dict)
    lens_families: frozenset[str] = frozenset()
    claude_checks: str = ""  # niche-specific: authenticity, condition, where prices are
    claude_old: str = ""


WATCHES = Niche(
    key="watches", label="Watches", icon="⌚", noun="watch",
    brands=watchdb.BRANDS,
    valuable_segments=frozenset(watchdb.VALUABLE_SEGMENTS),
    categories=("1677", "1676"),  # men's, women's watches
    feeds=("1677", "1676"),
    words=("ceas", "watch", "chrono", "cronograf", "cronometru", "automatic", "mecanic", "quartz", "diver"),
    not_words=("bord", "perete", "pendul", "cuc", "desteptator", "smart", "smartwatch", "apple watch", "galaxy watch",
               "de masa", "masa", "semineu", "opel", "jante", "anvelope", "telefon", "apartament", "masina",
               "autoturism", "bicicleta", "parfum"),
    search_pool=(),  # from Settings.search_pool (config.SEARCH_POOL), so it stays configurable
    focus_pool=(),  # from Settings.focus_pool
    facebook_queries=("ceas", "ceasuri", "lot ceasuri", "ceas automatic", "ceas mecanic", "ceas vechi", "ceas defect",
                      "ceas sovietic", "omega", "seiko", "tissot", "longines", "rolex", "poljot", "orient", "citizen"),
    strong_words=("ceas", "ceasuri"),
    repair_ron={"japan": 250, "soviet": 200, "swiss": 600, "vintage": 500, "luxury": 1500},
    claude_checks="""- Watch tells, e.g. Rolex: no display caseback, rehaut engraving, 2.5x cyclops, crown at 6; Omega: text
     alignment, Seamaster wave pattern, caseback medallion; AP/Hublot/Patek/Richard Mille under a few thousand
     lei are fakes. A Miyota/Seagull/generic movement in a Swiss brand = fake.
   - Vintage: redials (repainted dials) and franken watches (mixed parts).""",
    claude_old="""Identify it from the dial text, logo, case, crown and any movement or caseback markings (maker,
calibre, hallmarks such as silver 800/925 or gold 14k/585, 18k/750 on pocket watches). Old Swiss makers (Omega,
Longines, Zenith, Tissot, Doxa, Cyma, Eterna, Universal...), early Seiko/Citizen automatics, Soviet rarities and
gold cases are what make these worth it.""",
)

CAMERAS = Niche(
    key="cameras", label="Cameras", icon="📷", noun="camera or lens",
    brands=camdb.BRANDS,
    valuable_segments=frozenset({"luxury", "swiss", "vintage"}),
    # 2344 lenses, 1935 compact/film/instant, 1938 DSLR, 1940 mirrorless (checked November 2026).
    categories=("2344", "1935", "1938", "1940"),
    feeds=("2344", "1935"),
    words=("aparat foto", "aparat", "camera foto", "obiectiv", "obiective", "lentila", "film", "analogic", "slr",
           "rangefinder", "telemetru", "m42", "camera", "foto"),
    not_words=("bord", "supraveghere", "masina", "telefon", "iphone", "samsung galaxy", "video in nasture",
               "copiat", "gps", "drona", "webcam", "binoclu", "telescop", "microscop", "lupa", "ochelari"),
    search_pool=(
        "aparat foto", "aparat foto film", "aparat foto analogic", "aparat foto vechi", "obiectiv foto", "obiectiv",
        "obiectiv m42", "obiectiv manual", "aparat foto de colectie", "aparat foto sovietic", "aparat foto rusesc",
        "zenit", "praktica", "helios", "jupiter 9", "carl zeiss jena", "pancolar", "flektogon", "meyer optik",
        "trioplan", "pentacon", "takumar", "canon ae-1", "canon fd", "nikon fm", "nikon f3", "olympus om",
        "olympus mju", "pentax k1000", "pentax spotmatic", "minolta", "yashica", "rolleiflex", "leica", "hasselblad",
        "contax", "mamiya", "zeiss ikon", "voigtlander", "kiev 88", "zorki", "fed", "lubitel", "smena", "polaroid",
        "exakta",
    ),
    focus_pool=(
        "lot aparate foto", "aparate foto vechi", "aparat foto vechi", "lot obiective", "obiective vechi",
        "colectie aparate foto", "aparat foto bunic", "aparate foto de colectie", "aparat foto defect",
        "aparate foto pentru piese", "vechituri aparat foto", "aparat foto pe film", "aparat foto mecanic",
        "obiectiv vechi", "aparat foto burduf", "aparat foto cu burduf", "aparat foto ddr", "aparat foto germania",
    ),
    facebook_queries=("aparat foto", "aparat foto vechi", "aparat foto film", "obiectiv foto", "lot aparate foto",
                      "zenit", "helios 44", "carl zeiss jena", "leica", "canon ae-1", "praktica", "rolleiflex"),
    strong_words=("aparat foto", "aparate foto", "aparat de fotografiat", "obiectiv", "obiective", "camera foto", "pe film"),
    repair_ron={"japan": 250, "soviet": 150, "swiss": 500, "vintage": 300, "luxury": 1200},
    lens_families=frozenset(camdb.LENS_FAMILIES),
    claude_checks="""- Cameras/lenses: fungus, haze, balsam separation and scratches on lens glass (look through the
     glass in the photos), oily or stuck aperture blades, shutter firing (does the seller say all speeds work?),
     light seals, meter working, dents. Film cameras sell on "tested with film" / "all speeds OK".
   - Fakes: Soviet FED/Zorki bodies engraved "Leica"/"Leitz" with Nazi-era markings are the classic fake Leica;
     real Leica screw-mount serials and engraving fonts can be checked. Rebadged Zenits sold as something else.
   - Prices: eBay sold listings, Kamerastore, KEH, Catawiki for camera/lens prices; OLX Romania for local.""",
    claude_old="""Identify it from the names engraved on the lens barrel and front ring (maker, name, focal length,
aperture, serial), the camera's top plate and front, lens mount (M42, Exakta, Leica M39/M, Pentacon Six...),
and any "Made in GDR/USSR/Germany" markings. Zeiss Jena (Biotar, Flektogon, Pancolar), Meyer-Optik (Trioplan,
Primoplan), Helios 40, Jupiter 3/9, Leica/Leitz, Rolleiflex, Zeiss Ikon and medium-format gear make these worth
it; Zenit E bodies and Helios 44-2 are common.""",
)

ALL: dict[str, Niche] = {n.key: n for n in (WATCHES, CAMERAS)}


def get(key: str | None) -> Niche:
    return ALL.get(key or "watches", WATCHES)
