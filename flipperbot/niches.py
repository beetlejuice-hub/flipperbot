"""The kinds of things flipperbot hunts: watches, for now. Everything that would differ for another
kind (sneakers, old games...) lives here: brands, OLX categories, searches, what makes a listing
relevant, repair costs, what Claude is told to look for. The rest of the bot (tiers, lots, Claude,
dashboard, Telegram, Facebook) is shared, so a new kind is a new block here plus its brand list.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from . import watchdb
from .watchdb import Brand


@dataclass(frozen=True)
class Niche:
    key: str
    label: str
    icon: str
    noun: str  # "watch"
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
    claude_checks: str = ""  # authenticity, condition, where prices are
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

ALL: dict[str, Niche] = {n.key: n for n in (WATCHES,)}


def get(key: str | None) -> Niche:
    return ALL.get(key or "watches", WATCHES)
