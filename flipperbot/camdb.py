"""What the bot knows about cameras and lenses, without AI. Same segments as watches,
so the tiers work the same way:

- luxury:  Leica, Hasselblad, Contax, Rolleiflex...: big money, and faked (Soviet FED/Zorki
           bodies engraved "Leica" are the classic).
- swiss:   solid resale: Voigtlander, Mamiya, Bronica, West German Zeiss, medium format.
- japan:   Canon, Nikon, Pentax, Olympus, Minolta...: volume, easy flips, film bodies in demand.
- vintage: old European makers collectors buy: Zeiss Ikon, Exakta, Kodak Retina, Robot...
- soviet:  East German and Soviet: Zenit, Praktica, Helios, Jupiter, Carl Zeiss Jena, Meyer-Optik.
           Cheap and in every attic; Trioplan, Helios 40, Biotar and Flektogon hide in here.
- fashion: digital point-and-shoots and toy cameras: poor resale.

Families include lens names: with a focal length they make the model key ("helios|44 2|58").
Body names that clash with lens apertures ("F2") are written with the brand ("nikon f2").
"""

from __future__ import annotations

from .watchdb import Brand

BRANDS: list[Brand] = [
    # --- luxury ----------------------------------------------------------------
    Brand("Leica", "luxury", ("leitz", "ernst leitz", "leica camera"), 600,
          ("m3", "m2", "m4", "m6", "m7", "mp", "m10", "m240", "iiif", "iiic", "iiig", "iif", "iii", "ii", "r6", "r7", "r4",
           "cl", "minilux", "summicron", "summilux", "summaron", "elmar", "elmarit", "noctilux", "summar", "hektor")),
    Brand("Hasselblad", "luxury", (), 1000, ("500c/m", "500cm", "503cx", "501c", "x1d", "xpan", "planar", "sonnar", "distagon")),
    Brand("Contax", "luxury", (), 0, ("g1", "g2", "t2", "t3", "rts", "aria", "139", "167mt", "rx", "planar", "sonnar", "distagon")),
    Brand("Rolleiflex", "luxury", ("rollei", "rolleicord", "rolleiflex"), 0, ("2.8f", "3.5f", "2.8e", "3.5e", "sl35", "35 s", "35s", "35 t", "35t", "35se")),
    Brand("Alpa", "luxury", (), 3000, ()),
    Brand("Linhof", "luxury", (), 1500, ("technika",)),
    # --- swiss (solid resale) ------------------------------------------------------
    Brand("Voigtlander", "swiss", ("voigtländer",), 0, ("bessa", "vito", "vitessa", "prominent", "nokton", "ultron", "color-skopar", "heliar")),
    Brand("Mamiya", "swiss", (), 0, ("rb67", "rz67", "645", "m645", "c330", "c220", "7ii", "mamiya 7", "6")),
    Brand("Bronica", "swiss", ("zenza bronica",), 0, ("sq-a", "sqa", "etrs", "etrsi", "gs-1")),
    Brand("Carl Zeiss", "swiss", ("zeiss",), 0, ("planar", "sonnar", "distagon", "tessar", "makro-planar", "batis", "otus")),
    Brand("Plaubel", "swiss", (), 0, ("makina",)),
    # --- japan ------------------------------------------------------------------------
    Brand("Canon", "japan", (), 0, ("ae-1 program", "ae-1", "a-1", "av-1", "at-1", "ftb", "ft ql", "canon f-1", "t70", "t90", "eos 1",
                                    "canonet", "fd", "fl", "ef-s", "ef", "rf", "l")),
    Brand("Nikon", "japan", ("nikkor", "nikkormat"), 0, ("nikon f2", "nikon f3", "nikon fm2", "nikon fm3a", "nikon fm", "nikon fe2",
                                                          "nikon fe", "nikon f100", "nikon f80", "nikkormat", "ai-s", "ais", "af-d", "af-s", "nikkor")),
    Brand("Pentax", "japan", ("asahi", "asahi pentax", "takumar"), 0, ("k1000", "me super", "mx", "lx", "spotmatic", "67", "6x7", "645",
                                                                         "super takumar", "smc takumar", "takumar", "espio", "smc")),
    Brand("Olympus", "japan", ("zuiko",), 0, ("om-1", "om-2", "om-4", "om10", "om-10", "xa", "xa2", "mju ii", "mju-ii", "mju", "trip 35",
                                              "pen f", "pen", "35 rc", "zuiko")),
    Brand("Minolta", "japan", ("rokkor",), 0, ("x-700", "x-300", "xd7", "xd-7", "srt 101", "srt", "xe", "hi-matic", "cle", "rokkor", "md")),
    Brand("Konica", "japan", ("hexanon",), 0, ("hexar", "c35", "autoreflex", "hexanon")),
    Brand("Yashica", "japan", (), 0, ("electro 35", "mat 124", "mat-124", "t4", "t5", "fx-3", "fr", "lynx")),
    Brand("Fujifilm", "japan", ("fujica", "fuji"), 0, ("gw690", "gsw690", "ga645", "gf670", "klasse", "natura", "x100", "st801", "fujinon")),
    Brand("Ricoh", "japan", (), 0, ("gr1", "gr", "kr-5", "xr", "500g")),
    Brand("Mamiya-Sekor", "japan", ("sekor",), 0, ()),
    Brand("Topcon", "japan", ("topcor",), 0, ()),
    Brand("Miranda", "japan", (), 0, ()),
    Brand("Chinon", "japan", (), 0, ()),
    Brand("Cosina", "japan", (), 0, ()),
    Brand("Sony", "japan", (), 0, ()),
    Brand("Panasonic", "japan", ("lumix",), 0, ()),
    Brand("Tamron", "japan", (), 0, ("adaptall",)),
    Brand("Sigma", "japan", (), 0, ("art",)),
    # --- vintage European ------------------------------------------------------------------
    Brand("Zeiss Ikon", "vintage", ("zeiss-ikon",), 0, ("contessa", "ikonta", "super ikonta", "contaflex", "contarex", "icarex", "nettar", "ikoflex")),
    Brand("Exakta", "vintage", ("ihagee", "exa"), 0, ("varex", "vx", "rtl 1000", "exa 1a", "exa ii")),
    Brand("Kodak", "vintage", (), 0, ("retina", "retinette", "instamatic", "brownie", "ektar")),
    Brand("Robot", "vintage", (), 0, ()),
    Brand("Agfa", "vintage", (), 0, ("karat", "silette", "isolette", "optima", "click", "clack")),
    Brand("Balda", "vintage", (), 0, ()),
    Brand("Franka", "vintage", (), 0, ()),
    Brand("Polaroid", "vintage", (), 0, ("sx-70", "sx70", "600", "spectra", "land camera", "go")),
    # --- east German / Soviet ------------------------------------------------------------------
    Brand("Carl Zeiss Jena", "soviet", ("zeiss jena", "aus jena", "cz jena", "c.z. jena"), 0,
          ("pancolar", "flektogon", "biotar", "biometar", "sonnar", "tessar", "prakticar", "mc sonnar", "jena t")),
    Brand("Meyer-Optik", "soviet", ("meyer optik", "meyer-optik gorlitz", "meyer gorlitz", "meyer"), 0,
          ("trioplan", "primoplan", "domiplan", "oreston", "orestor", "lydith", "primotar", "telemegor")),
    Brand("Pentacon", "soviet", (), 0, ("six", "auto", "electric")),
    Brand("Praktica", "soviet", (), 0, ("mtl 5", "mtl 3", "mtl", "ltl", "plc", "bx20", "b200", "super tl", "nova", "fx")),
    Brand("Helios", "soviet", ("гелиос",), 0, ("44-2", "44m-4", "44m", "44", "40-2", "40", "81")),
    Brand("Jupiter", "soviet", ("юпитер",), 0, ("jupiter 9", "jupiter 37", "jupiter 8", "jupiter 11", "jupiter 12", "jupiter 21")),
    Brand("Industar", "soviet", (), 0, ("50-2", "61", "26m", "69")),
    Brand("Mir", "soviet", (), 0, ("mir 1", "mir 1b", "mir 24")),
    Brand("Tair", "soviet", (), 0, ("tair 11", "tair 3")),
    Brand("Zenit", "soviet", ("zenith camera",), 0, ("zenit e", "zenit et", "zenit 11", "zenit 12xp", "zenit 122", "zenit ttl", "zenit 19", "zenit b")),
    Brand("Zorki", "soviet", ("zorkiy",), 0, ("zorki 4", "zorki 4k", "zorki 6", "zorki 1", "zorki c")),
    Brand("FED", "soviet", (), 0, ("fed 2", "fed 3", "fed 5", "fed 1")),
    Brand("Kiev", "soviet", ("kiev-88", "kiev 88"), 0, ("kiev 4", "kiev 88", "kiev 60")),
    Brand("Lomo", "soviet", ("lomography",), 0, ("lc-a", "lca", "lubitel")),
    Brand("Smena", "soviet", (), 0, ("smena 8m", "symbol")),
    Brand("Lubitel", "soviet", (), 0, ("lubitel 2", "lubitel 166")),
    Brand("Certo", "soviet", (), 0, ()),
    # --- low resale ---------------------------------------------------------------------------
    *[Brand(n, "fashion", a) for n, a in [
        ("Samsung", ()), ("Vivitar", ()), ("Kodak EasyShare", ("easyshare",)), ("Prestigio", ()), ("Rollei digital", ()),
        ("GoPro", ()), ("Instax", ("instax",)), ("Hama", ()), ("Benq", ()),
    ]],
]

# Which camera families are lenses: with a focal length they become the model key.
LENS_FAMILIES = {
    "summicron", "summilux", "summaron", "elmar", "elmarit", "noctilux", "summar", "hektor", "planar", "sonnar",
    "distagon", "tessar", "makro-planar", "nokton", "ultron", "color-skopar", "heliar", "fd", "fl", "ef-s", "ef", "rf", "l",
    "nikkor", "ai-s", "ais", "af-d", "af-s", "super takumar", "smc takumar", "takumar", "smc", "zuiko", "rokkor", "md",
    "hexanon", "fujinon", "pancolar", "flektogon", "biotar", "biometar", "prakticar", "mc sonnar", "jena t", "trioplan",
    "primoplan", "domiplan", "oreston", "orestor", "lydith", "primotar", "telemegor", "44-2", "44m-4", "44m", "44",
    "40-2", "40", "81", "jupiter 9", "jupiter 37", "jupiter 8", "jupiter 11", "jupiter 12", "jupiter 21", "50-2", "61",
    "26m", "69", "mir 1", "mir 1b", "mir 24", "tair 11", "tair 3", "adaptall", "art",
}
