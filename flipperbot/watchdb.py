"""What the bot knows about watch brands, without any AI.

Each brand has a *segment*, which drives what the bot does when it has no
price history for a model yet:

- luxury:     big money, also the most faked. A cheap one is "suspect".
- swiss:      solid resale (Tissot, Hamilton, Longines...).
- japan:      Seiko/Orient/Citizen/Casio: lots of volume, easy flips.
- vintage:    old Swiss/European makers that collectors pay for.
- soviet:     Poljot, Vostok, Raketa...: cheap to buy, steady demand.
- fashion:    Michael Kors, Guess, Daniel Wellington...: resale is poor. Skipped.

`fake_floor_ron`: below this price a listing of that brand is almost
certainly fake (or stolen, or a scam). Tune it as you learn.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Brand:
    name: str
    segment: str
    aliases: tuple[str, ...] = ()
    fake_floor_ron: int = 0
    # Model families worth recognising by name when the listing has no reference.
    families: tuple[str, ...] = field(default_factory=tuple)


BRANDS: list[Brand] = [
    # --- luxury -----------------------------------------------------------
    Brand("Rolex", "luxury", (), 15000, ("submariner", "datejust", "day-date", "gmt-master", "explorer", "oyster perpetual", "daytona", "air-king", "yacht-master", "milgauss", "sea-dweller")),
    Brand("Omega", "luxury", (), 2500, ("seamaster", "speedmaster", "constellation", "de ville", "geneve", "aqua terra", "planet ocean", "railmaster", "dynamic", "genève")),
    Brand("Tudor", "luxury", (), 4000, ("black bay", "pelagos", "ranger", "prince", "oysterdate")),
    Brand("Cartier", "luxury", (), 4000, ("tank", "santos", "ballon bleu", "pasha", "panthere")),
    Brand("Breitling", "luxury", (), 4000, ("navitimer", "superocean", "chronomat", "avenger", "colt", "aerospace")),
    Brand("TAG Heuer", "luxury", ("tag heuer", "tagheuer", "tag-heuer"), 1500, ("carrera", "aquaracer", "monaco", "formula 1", "link", "autavia")),
    Brand("IWC", "luxury", (), 6000, ("portugieser", "pilot", "portofino", "aquatimer", "ingenieur")),
    Brand("Jaeger-LeCoultre", "luxury", ("jaeger", "lecoultre", "le coultre", "jlc"), 4000, ("reverso", "master", "memovox")),
    Brand("Panerai", "luxury", (), 8000, ("luminor", "radiomir", "submersible")),
    Brand("Patek Philippe", "luxury", ("patek",), 30000, ("calatrava", "nautilus", "aquanaut")),
    Brand("Audemars Piguet", "luxury", ("audemars",), 30000, ("royal oak",)),
    Brand("Vacheron Constantin", "luxury", ("vacheron",), 20000, ()),
    Brand("Hublot", "luxury", (), 10000, ("big bang", "classic fusion")),
    Brand("Zenith", "luxury", (), 5000, ("el primero", "defy", "chronomaster")),
    Brand("Grand Seiko", "luxury", ("grand seiko",), 8000, ()),
    Brand("Chopard", "luxury", (), 6000, ("happy sport", "mille miglia")),
    Brand("Blancpain", "luxury", (), 15000, ("fifty fathoms",)),
    Brand("Bell & Ross", "luxury", ("bell ross", "bell&ross", "bell & ross"), 3000, ()),
    # --- swiss ------------------------------------------------------------
    Brand("Longines", "swiss", (), 800, ("hydroconquest", "conquest", "master collection", "spirit", "legend diver", "dolcevita", "flagship")),
    Brand("Tissot", "swiss", (), 0, ("prx", "le locle", "seastar", "visodate", "gentleman", "t-touch", "chemin des tourelles", "powermatic", "prc 200")),
    Brand("Hamilton", "swiss", (), 0, ("khaki", "jazzmaster", "ventura", "intra-matic")),
    Brand("Oris", "swiss", (), 0, ("aquis", "big crown", "divers sixty-five")),
    Brand("Rado", "swiss", (), 0, ("captain cook", "diastar", "centrix", "true")),
    Brand("Certina", "swiss", (), 0, ("ds action", "ds-1", "ds podium", "ds ph200m")),
    Brand("Mido", "swiss", (), 0, ("ocean star", "multifort", "baroncelli", "commander")),
    Brand("Frederique Constant", "swiss", ("frederique",), 0, ()),
    Brand("Raymond Weil", "swiss", (), 0, ()),
    Brand("Baume & Mercier", "swiss", ("baume", "baume mercier"), 0, ()),
    Brand("Maurice Lacroix", "swiss", (), 0, ("aikon", "pontos")),
    Brand("Sinn", "swiss", (), 0, ()),
    Brand("Nomos", "swiss", (), 0, ("tangente", "orion", "club")),
    Brand("Junghans", "swiss", (), 0, ("max bill", "meister")),
    Brand("Victorinox", "swiss", ("swiss army",), 0, ()),
    Brand("Edox", "swiss", (), 0, ()),
    Brand("Alpina", "swiss", (), 0, ()),
    # --- japan ------------------------------------------------------------
    Brand("Seiko", "japan", (), 0, ("seiko 5", "presage", "prospex", "turtle", "samurai", "sumo", "monster", "alpinist", "cocktail", "skx", "kinetic", "bellmatic", "lord matic", "actus", "sportsmatic")),
    Brand("Orient", "japan", ("orient star",), 0, ("bambino", "kamasu", "mako", "ray")),
    Brand("Citizen", "japan", (), 0, ("eco-drive", "promaster", "ny0040", "tsuyosa")),
    Brand("Casio", "japan", ("g-shock", "gshock", "g shock"), 0, ("g-shock", "edifice", "pro trek", "oceanus", "royale", "f-91w")),
    # --- vintage Swiss/European --------------------------------------------
    Brand("Heuer", "vintage", (), 0, ("autavia", "carrera", "monaco")),
    Brand("Universal Geneve", "vintage", ("universal geneve", "universal genève"), 0, ("polerouter",)),
    Brand("Enicar", "vintage", (), 0, ("sherpa",)),
    Brand("Doxa", "vintage", (), 0, ()),
    Brand("Eterna", "vintage", ("eterna-matic", "eternamatic"), 0, ()),
    Brand("Zodiac", "vintage", (), 0, ("sea wolf",)),
    Brand("Favre-Leuba", "vintage", ("favre leuba",), 0, ()),
    Brand("Cyma", "vintage", (), 0, ()),
    Brand("Roamer", "vintage", (), 0, ()),
    Brand("Lip", "vintage", (), 0, ()),
    Brand("Wittnauer", "vintage", (), 0, ()),
    Brand("Revue Thommen", "vintage", ("revue",), 0, ()),
    Brand("Glashütte", "vintage", ("glashutte", "gub"), 0, ("spezimatic",)),
    Brand("Ruhla", "vintage", (), 0, ()),
    # --- soviet -------------------------------------------------------------
    Brand("Poljot", "soviet", ("poljot", "polyot", "poliot"), 0, ("sturmanskie", "3133", "de luxe", "aviator")),
    Brand("Vostok", "soviet", ("wostok",), 0, ("amphibia", "komandirskie", "amfibia")),
    Brand("Raketa", "soviet", ("raketa", "racheta"), 0, ("copernicus", "big zero")),
    Brand("Slava", "soviet", (), 0, ()),
    Brand("Pobeda", "soviet", (), 0, ()),
    Brand("Sturmanskie", "soviet", ("shturmanskie",), 0, ()),
    Brand("Luch", "soviet", (), 0, ()),
    Brand("Molnija", "soviet", ("molnia",), 0, ()),
    Brand("Chaika", "soviet", ("ceaika",), 0, ()),
    Brand("Zim", "soviet", (), 0, ()),
    # --- fashion: resale is poor ---------------------------------------------
    *[
        Brand(n, "fashion", a)
        for n, a in [
            ("Michael Kors", ("mk",)),
            ("Guess", ()),
            ("Daniel Wellington", ()),
            ("Fossil", ()),
            ("Emporio Armani", ("armani",)),
            ("Diesel", ()),
            ("Hugo Boss", ("boss",)),
            ("Tommy Hilfiger", ("tommy",)),
            ("Festina", ()),
            ("Lotus", ()),
            ("Curren", ()),
            ("Naviforce", ()),
            ("Skmei", ()),
            ("Megir", ()),
            ("Benyar", ()),
            ("Pagani Design", ("pagani",)),
            ("Invicta", ()),
            ("Swatch", ()),
            ("Timex", ()),
            ("Q&Q", ("q&q", "qq")),
            ("Calvin Klein", ("ck",)),
            ("Police", ()),
            ("Lacoste", ()),
            ("Puma", ()),
            ("Adidas", ()),
            ("Nixon", ()),
            ("Cerruti", ()),
        ]
    ],
]

# Segments worth a human look even before we have price history.
VALUABLE_SEGMENTS = {"luxury", "swiss", "vintage"}
