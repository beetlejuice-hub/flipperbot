import pytest

from flipperbot import bot, niches, repairs
from flipperbot.config import Settings
from flipperbot.db import DB
from flipperbot.identify import identify, normalize
from flipperbot.models import Listing
from flipperbot.sources import olx
from flipperbot.tiers import judge

from test_olx_and_bot import offer

S = Settings()


def verdict(title, price, desc="", comps=()):
    return judge(Listing("olx", "1", "u", title, description=desc, price_ron=price), identify(title, desc, "bikes"), list(comps), S)


@pytest.mark.parametrize("title, key", [
    ("Bicicleta Trek Marlin 7 2022 marime L", "trek|marlin 7"),
    ("Rockrider ST 540 29", "rockrider|st 540"),
    ("Vand MTB bicicleta Merida Big Nine 300", "merida|big nine 300"),
    ("Cursiera Triban RC 520", "triban|rc 520"),
    ("Specialized Rockhopper Comp 29", "specialized|rockhopper comp"),
    ("Brompton M6L pliabila", "brompton|m6l"),
    ("Bicicleta Peugeot cursiera vintage", "peugeot|road"),
    ("MTB devron, echipat Shimano Deore", "devron|mtb"),
    ("Bicicleta DHS 2625 26 inch", "dhs|26 inch"),
    ("Bicicleta copii Kellys 20", "kellys|kids 20"),
])
def test_brand_and_line(title, key):
    assert identify(title, "", "bikes").model_key == key


def test_parts_and_exercise_bikes_are_not_bikes():
    assert "part" in identify("Roti bicicleta 29 Shimano", "", "bikes").flags
    assert "part" in identify("Bicicleta fitness DHS", "", "bikes").flags
    assert "part" in identify("Furca RockShox Judy 29", "", "bikes").flags


def test_bikes_replace_cameras_with_a_1500_budget():
    assert "bikes" in S.niches and "cameras" not in S.niches and niches.get("bikes").icon == "🚲"
    v = verdict("Bicicleta Trek Marlin 7", 2200, "", [3000] * 6)
    assert v.tier == "bad" and "over budget" in v.reason and "1500" in v.reason
    assert S.niche_budgets.get("watches", S.budget_ron) == 5000  # other categories keep theirs


def test_stolen_bike_warnings():
    v = verdict("Specialized Rockhopper Comp 29", 900, "fara acte, urgent", [2000] * 6)
    assert v.tier == "suspect" and "stolen" in v.reason
    v = verdict("Bicicleta Trek Marlin 7", 800, "stare buna", [1900, 2000, 1800, 2100, 1950, 2000])
    assert v.tier == "mid" and "invoice" in v.reason
    v = verdict("Bicicleta Trek Marlin 7", 400, "stare buna")
    assert v.tier == "mid" and "stolen" in v.reason  # under any working Trek's price


def test_a_tired_bike_is_a_fixer_upper():
    f = repairs.diagnose("bikes", normalize("Trek Marlin 6, a stat in garaj, lant ruginit, cauciucuri crapate"), {"broken"})
    assert f.odds == "high" and f.cost[1] < 500  # one service session, not three separate jobs
    assert repairs.diagnose("bikes", normalize("MTB Cube cadru fisurat"), {"broken"}).odds == "low"
    db = DB(":memory:")
    good = [olx.parse_offer({**offer(100 + i, f"Bicicleta Trek Marlin 6 v{i}", p), "category": {"id": 987}})
            for i, p in enumerate([1500, 1600, 1550, 1450, 1500])]
    tired = olx.parse_offer({**offer(200, "Bicicleta Trek Marlin 6", 600), "category": {"id": 987},
                             "description": "A stat in garaj 2 ani, are pana la roata din spate, lantul ruginit. Marimea M."})
    for l in [*good, tired]:
        l.niche = "bikes"
    bot.process(db, [*good, tired], S, alert=False)
    r = db.get("olx:200")
    assert r["fixer"] and '"worth_it": true' in r["fixer"] and r["score"] >= 5


@pytest.mark.parametrize("title, key", [
    ("Rockrider ST530s", "rockrider|st 530"), ("Bicicleta - Trek FuelX 5.5 2009", "trek|fuelx 5.5"),
    ("Bicicleta hidraulica Trek Series 4900", "trek|4900"), ("YT Tues Comp 2.0 doar 2000", "yt|tues"),
    ("Mondraker superfoxy r 2024 M", "mondraker|superfoxy"), ("Bicicleta CTM Rambler 2.0", "ctm|rambler 2.0"),
    ("Bicicleta Elops 520 + Accesorii incluse", "elops|520"),
])
def test_more_lines(title, key):
    assert identify(title, "", "bikes").model_key == key


def test_live_parts_and_shops():
    assert "part" in identify("Stickere bicicleta Bianchi / Colnago / Trek", "", "bikes").flags
    assert "part" in identify("Dezmembrez Btwin Rockrider 340 – piese MTB", "", "bikes").flags
    assert "part" in identify("Cadre bicicleta ! VITUS 979 / Cannondale", "", "bikes").flags
    assert "lot" in identify("Biciclete gata servisate,Bianchi,Pinarello,Canyon,Cannondale", "", "bikes").flags
