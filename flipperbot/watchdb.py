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
    Brand("Luminox", "swiss", (), 0, ("navy seal", "atacama", "bear grylls", "f-117", "nighthawk")),
    Brand("Traser", "swiss", (), 0, ("p66", "p67", "p68", "p99")),
    Brand("Ball", "swiss", ("ball watch",), 0, ("engineer", "fireman", "trainmaster", "roadmaster")),
    Brand("Marathon", "swiss", (), 0, ("gsar", "jsar", "tsar", "navigator")),
    Brand("Fortis", "swiss", (), 0, ("flieger", "cosmonautis", "marinemaster")),
    Brand("Davosa", "swiss", (), 0, ("ternos",)),
    Brand("Squale", "swiss", (), 0, ("1521", "20 atmos")),
    Brand("Steinhart", "swiss", (), 0, ("ocean one", "ocean 39")),
    Brand("Christopher Ward", "swiss", ("chr. ward",), 0, ("c60", "c63", "c65")),
    Brand("Laco", "swiss", (), 0, ()),
    Brand("Stowa", "swiss", (), 0, ("flieger", "marine", "antea")),
    Brand("Sinn", "swiss", (), 0, ("556", "104", "u1", "656", "857")),
    Brand("Revue Thommen", "swiss", ("revue thommen",), 0, ()),
    Brand("Seagull", "japan", ("sea-gull", "tianjin"), 0, ("1963",)),
    Brand("Vostok Europe", "soviet", ("vostok-europe",), 0, ("anchar", "energia", "lunokhod", "expedition")),
    Brand("Swiss Military Hanowa", "fashion", ("swiss military", "hanowa"), 0, ()),
    Brand("Mondia", "vintage", (), 0, ()),
    Brand("Lorus", "fashion", (), 0, ()),
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
    Brand("Bulova", "vintage", (), 0, ("accutron", "precisionist", "lunar pilot")),
    Brand("Glycine", "vintage", (), 0, ("airman", "combat")),
    Brand("Hanhart", "vintage", (), 0, ()),
    Brand("Tutima", "vintage", (), 0, ()),
    Brand("Lemania", "vintage", (), 0, ()),
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
    # --- smartwatches: resell well when they're the real thing, unlocked ----------------
    Brand("Apple Watch", "smart", ("apple watch", "iwatch", "i watch", "applewatch"), 0,  # floors per model: tiers.SMART_FLOORS
          ("ultra 2", "ultra", "series 10", "series 9", "series 8", "series 7", "series 6", "series 5", "series 4", "se 2", "se")),
    Brand("Garmin", "smart", (), 0, ("fenix 8", "fenix 7x pro", "fenix 7s pro", "fenix 7 pro", "fenix 7x", "fenix 7s", "fenix 7",
                                     "fenix 6x pro", "fenix 6s pro", "fenix 6 pro", "fenix 6x", "fenix 6s", "fenix 6", "fenix 5",
                                     "epix pro", "epix",
                                     "forerunner 965", "forerunner 955", "forerunner 945", "forerunner 265", "forerunner 255",
                                     "forerunner 165", "forerunner 55", "venu 3", "venu 2 plus", "venu 2", "venu sq",
                                     "instinct 2x", "instinct 2", "instinct", "enduro", "vivoactive 5", "vivoactive 4",
                                     "descent", "tactix", "marq", "quatix")),
    Brand("Samsung Galaxy Watch", "smart", ("galaxy watch", "samsung watch", "samsung galaxy watch"), 0,
          ("watch ultra", "watch 7", "watch 6 classic", "watch 6", "watch 5 pro", "watch 5", "watch 4 classic", "watch 4", "active 2")),
    Brand("Google Pixel Watch", "smart", ("pixel watch",), 0, ("3", "2")),
    Brand("Huawei Watch", "smart", ("huawei watch", "huawei"), 0, ("gt 5 pro", "gt 5", "gt 4", "gt 3 pro", "gt 3", "watch 4 pro", "ultimate", "fit 3")),
    Brand("Amazfit", "smart", (), 0, ("t-rex 3", "t-rex 2", "t-rex", "balance", "gtr 4", "gts 4", "cheetah")),
    Brand("Suunto", "smart", (), 0, ("race", "vertical", "9 peak", "9 baro", "5 peak", "ocean")),
    Brand("Polar", "smart", (), 0, ("vantage v3", "vantage", "grit x2", "grit x", "pacer pro", "ignite")),
    Brand("Coros", "smart", (), 0, ("vertix 2", "vertix", "apex 2 pro", "apex 2", "pace 3", "pace 2")),
    Brand("Withings", "smart", (), 0, ("scanwatch", "steel hr")),
    Brand("Fitbit", "fashion", (), 0, ()),
    Brand("Xiaomi", "fashion", ("redmi watch", "mi band", "mi watch"), 0, ()),

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


# References, movements and dials collectors pay for, which sellers often don't recognise.
# A match (title or description) flags the listing "collectible": it goes to Interesting for a look.
# No prices here on purpose: the price book, the price-check links or Claude say what it's worth.
COLLECTIBLE: list[tuple[str, str]] = [
    # Seiko / Citizen
    ("6139", "Seiko 6139 chronograph"), ("6138", "Seiko 6138 chronograph"), ("6105", "Seiko 6105 diver"),
    ("6309", "Seiko 6309 diver"), ("6306", "Seiko 6306 diver"), ("62mas", "Seiko 62MAS"), ("6217", "Seiko 62MAS 6217"),
    ("king seiko", "King Seiko"), ("lord marvel", "Seiko Lord Marvel"), ("lord matic", "Seiko LordMatic"),
    ("lordmatic", "Seiko LordMatic"), ("7a28", "Seiko 7A28 Giugiaro chronograph"), ("7a38", "Seiko 7A38 chronograph"),
    ("bellmatic", "Seiko Bellmatic"), ("pogue", "Seiko Pogue"), ("bullhead", "Bullhead chronograph"),
    ("challenge timer", "Citizen Challenge Timer"),
    # Swiss
    ("speedmaster", "Omega Speedmaster"), ("flightmaster", "Omega Flightmaster"), ("seamaster 300", "Omega Seamaster 300"),
    ("ploprof", "Omega Ploprof"), ("pie pan", "pie-pan dial"), ("pie-pan", "pie-pan dial"), ("30ch", "Longines 30CH"),
    ("13zn", "Longines 13ZN"), ("autavia", "Heuer Autavia"), ("heuer carrera", "Heuer Carrera"), ("heuer monaco", "Heuer Monaco"),
    ("camaro", "Heuer Camaro"), ("polerouter", "Universal Polerouter"), ("tri-compax", "Universal Tri-Compax"),
    ("compax", "Universal Compax"), ("el primero", "Zenith El Primero"), ("a386", "Zenith A386"), ("pr516", "Tissot PR516"),
    ("sherpa", "Enicar Sherpa"), ("doxa sub", "Doxa Sub"), ("kontiki", "Eterna KonTiki"), ("kon-tiki", "Eterna KonTiki"),
    ("navitimer", "Breitling Navitimer"), ("top time", "Breitling Top Time"), ("airman", "Glycine Airman"),
    ("accutron", "Bulova Accutron (tuning fork)"), ("diapason", "tuning-fork movement"), ("tuning fork", "tuning-fork movement"),
    ("hamilton electric", "Hamilton Electric"),
    # chronograph movements: a vintage chronograph with one of these is worth a look
    ("valjoux", "Valjoux chronograph movement"), ("lemania", "Lemania movement"), ("landeron", "Landeron chronograph"),
    ("venus 175", "Venus 175 chronograph"), ("venus 188", "Venus 188 chronograph"),
    # Soviet
    ("3133", "Poljot 3133 chronograph"), ("3017", "Poljot 3017 chronograph"), ("strela", "Strela chronograph"),
    ("okean", "Poljot Okean"), ("sturmanskie", "Sturmanskie"), ("radio room", "Vostok radio room"),
    ("copernicus", "Raketa Copernicus"), ("big zero", "Raketa Big Zero"), ("raketa 24", "Raketa 24-hour"),
    # military and dials
    ("broad arrow", "military broad arrow"), ("bundeswehr", "Bundeswehr issue"), ("tropical", "tropical dial"),
    ("gilt dial", "gilt dial"), ("cloisonne", "cloisonne dial"), ("chronometre", "chronometer"),
]
