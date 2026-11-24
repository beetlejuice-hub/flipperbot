from flipperbot import bot, repairs
from flipperbot.config import Settings
from flipperbot.db import DB
from flipperbot.identify import identify, normalize
from flipperbot.sources import olx

from test_olx_and_bot import offer

S = Settings()


def test_the_fault_is_read_from_the_listing():
    f = repairs.diagnose("electronics", normalize("PS5 slim defect, nu da imagine, port HDMI rupt"), {"broken"})
    assert f.name.startswith("no picture") and f.odds == "high" and f.cost == (150, 300)
    f = repairs.diagnose("phones", normalize("iPhone 13 ecran spart, in rest merge perfect"), {"broken"})
    assert f.name.startswith("cracked") and f.how == "service"
    # several faults: the riskiest counts
    f = repairs.diagnose("phones", normalize("ecran spart, a cazut in apa, nu porneste"), {"broken"})
    assert f.odds == "low"
    # faulty but nothing says what: an unknown fault, a gamble
    assert repairs.diagnose("electronics", normalize("Xbox Series S defect"), {"broken"}).odds == "low"
    # a working phone's "baterie 85%" isn't a fault; a locked phone is never "fixable"
    assert repairs.diagnose("phones", normalize("iPhone 14, baterie 85%"), set()) is None
    assert repairs.diagnose("phones", normalize("iPhone 14 ecran spart, blocat icloud"), {"broken", "locked"}) is None


def test_no_defects_is_not_a_defect():
    assert "broken" not in identify("Iphone 14", "82% baterie, nu are defecte", "phones").flags
    assert "broken" not in identify("PS5 slim", "merge perfect, niciun defect", "electronics").flags
    assert "broken" not in identify("Seiko 5", "fara zgarieturi sau defecte, merge perfect").flags
    assert "broken" in identify("iPhone 13", "ecran spart, in rest fara probleme", "phones").flags


def test_a_fixable_ps5_is_a_fixer_upper():
    db = DB(":memory:")
    working = [olx.parse_offer({**offer(100 + i, f"PS5 slim v{i}", p), "category": {"id": 1878}})
               for i, p in enumerate([1900, 2000, 1950, 2100, 2000])]
    broken = olx.parse_offer({**offer(200, "PS5 slim defect", 700), "category": {"id": 1878},
                              "description": "Nu da imagine, portul HDMI e rupt. In rest merge, se aude cum porneste."})
    for l in [*working, broken]:
        l.niche = "electronics"
    bot.process(db, [*working, broken], S, alert=False)
    r = db.get("olx:200")
    import json

    fx = json.loads(r["fixer"])
    assert fx["fault"].startswith("no picture") and fx["worth_it"] and fx["profit_if_fixed"] > 500
    assert r["score"] >= 5 and "fixer-upper" in r["score_why"] and "🔧" in r["reason"]
    from flipperbot import web

    assert [x["key"] for x in web.query(db, "fixers")] == ["olx:200"]


def test_a_dead_board_is_not_worth_fixing():
    db = DB(":memory:")
    working = [olx.parse_offer({**offer(100 + i, f"PS5 slim v{i}", p), "category": {"id": 1878}})
               for i, p in enumerate([1900, 2000, 1950, 2100, 2000])]
    broken = olx.parse_offer({**offer(200, "PS5 slim defect", 700), "category": {"id": 1878},
                              "description": "Blue light of death, nu porneste."})
    for l in [*working, broken]:
        l.niche = "electronics"
    bot.process(db, [*working, broken], S, alert=False)
    import json

    fx = json.loads(db.get("olx:200")["fixer"])
    assert fx["odds"] == "low" and not fx["worth_it"]


def test_several_faults_add_up_and_the_worst_odds_count():
    t = normalize("iPhone 15 Pro Max, Buton on/Off blocat, Ecran spart, pixeli morti, Probleme semnal")
    f = repairs.diagnose("phones", t, {"broken"})
    assert "cracked" in f.name and "signal" in f.name and "button" in f.name
    assert f.odds == "low" and f.cost[1] >= 900 + 600 + 200


def test_a_smartwatch_for_parts_is_a_gamble_not_a_deal():
    f = repairs.diagnose("smartwatches", normalize("Apple watch ULTRA 2 pentru piese"), {"broken"})
    assert f.odds == "low"
    from flipperbot.models import Listing

    db = DB(":memory:")
    for i, p in enumerate([1900, 2000, 1850, 1950, 2000]):
        w = Listing("olx", str(100 + i), "u", f"Apple Watch Ultra 2 49mm v{i}", price_ron=p)
        db.upsert(w)
        bot.evaluate(db, w, S)
    l = Listing("olx", "200", "u", "Apple watch ULTRA 2 pentru piese", price_ron=600)
    db.upsert(l)
    r = bot.evaluate(db, l, S)
    assert r["tier"] == "mid" and "🔧" in r["reason"]
