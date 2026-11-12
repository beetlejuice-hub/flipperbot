import pytest

from flipperbot import bot
from flipperbot.config import Settings
from flipperbot.identify import identify
from flipperbot.models import Listing
from flipperbot.sources import facebook, olx
from flipperbot.tiers import judge

from test_olx_and_bot import offer

S = Settings()


@pytest.mark.parametrize("title, key, segment", [
    ("Obiectiv Helios 44-2 58mm f2 M42", "helios|44 2|58", "soviet"),
    ("Carl Zeiss Jena Pancolar 50mm 1.8 MC", "carl zeiss jena|pancolar|50", "soviet"),
    ("Meyer Optik Gorlitz Trioplan 100mm f2.8", "meyer-optik|trioplan|100", "soviet"),
    ("Jupiter-9 85mm f2", "jupiter|jupiter 9|85", "soviet"),
    ("Obiectiv Nikon Nikkor 50mm f2 AI", "nikon|nikkor|50", "japan"),
    ("Canon AE-1 Program + Canon FD 50mm 1.8", "canon|ae 1 program", "japan"),
    ("Leica IIIf Elmar 50mm 3.5", "leica|iiif", "luxury"),
    ("Aparat foto Smena 8M", "smena|smena 8m", "soviet"),
])
def test_identify_cameras_and_lenses(title, key, segment):
    i = identify(title, "", "cameras")
    assert (i.model_key, i.segment) == (key, segment)


def test_same_lens_written_differently_is_one_model():
    a = identify("Jupiter 9 85mm", "", "cameras").model_key
    b = identify("Obiectiv Jupiter-9 2/85 85 mm", "", "cameras").model_key
    assert a == b == "jupiter|jupiter 9|85"


def test_camera_flags():
    assert "broken" in identify("Obiectiv Canon EF 50mm", "are ciuperca pe lentila", "cameras").flags
    assert "part" in identify("Parasolar Canon EW-63C", "", "cameras").flags
    i = identify("Lot aparate foto vechi 6 buc", "de la bunicul, nu stiu daca merg", "cameras")
    assert {"lot", "naive", "vintage"} <= i.flags


def test_fake_leica_is_suspect():
    l = Listing("olx", "1", "u", "Aparat foto Leica FED 2", price_ron=700, niche="cameras")
    v = judge(l, identify(l.title, "", "cameras"), [], S)
    assert v.tier == "suspect"


def test_watch_brands_dont_leak_into_cameras():
    assert identify("Ceas Omega Seamaster", "", "cameras").brand is None
    assert identify("Obiectiv Helios 44", "", "watches").brand is None


def L(title, cat, niche="cameras", source="olx"):
    l = olx.parse_offer(offer(1, title, 300, cat=cat))
    l.niche, l.source = niche, source
    return l


def test_camera_relevance():
    assert bot.is_relevant(L("Obiectiv Canon EF 50mm", "2344"))
    assert bot.is_relevant(L("Aparat foto Zenit E", "431"))  # antiques category: brand + "aparat foto"
    assert not bot.is_relevant(L("Camera supraveghere WiFi", "999"))
    assert not bot.is_relevant(L("Ceas bord Audi", "3561"))
    assert not bot.is_relevant(L("Binoclu Praktica 10x50", "1604"))
    assert bot.is_relevant(L("Vand aparat foto vechi", "x", source="facebook"))  # Facebook: the words do


def test_cameras_priced_and_judged_like_watches():
    s = Settings()
    from flipperbot.db import DB

    db = DB(":memory:")
    market = [olx.parse_offer(offer(100 + i, "Obiectiv Helios 44-2 58mm", p, cat=2344)) for i, p in enumerate([250, 300, 280, 260, 300])]
    deal = olx.parse_offer(offer(200, "Obiectiv Helios 44-2 58mm M42", 60, cat=2344))
    for l in [*market, deal]:
        l.niche = "cameras"
    bot.process(db, [*market, deal], s)
    row = db.get("olx:200")
    assert row["niche"] == "cameras" and row["model_key"] == "helios|44 2|58"
    assert row["tier"] in ("good", "real_good")


def test_facebook_queries_carry_their_niche(monkeypatch):
    seen = []

    def fake_search(queries, **kw):
        seen.extend(queries)
        return iter(())

    from flipperbot.db import DB

    db = DB(":memory:")
    db.kv_set("facebook", {"state": "ok", "next_at": 0})
    monkeypatch.setattr(facebook, "installed", lambda: True)
    monkeypatch.setattr(facebook, "search", fake_search)
    s = Settings()
    s.facebook_searches_per_run = 40
    bot.poll_facebook(db, s, log=lambda m: None)
    assert {n for q, n in seen} == {"watches", "cameras"}
