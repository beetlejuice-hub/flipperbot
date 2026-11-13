import pytest

from flipperbot import bot, niches
from flipperbot.config import Settings
from flipperbot.db import DB
from flipperbot.identify import identify
from flipperbot.sources import olx

from test_olx_and_bot import offer

S = Settings()


@pytest.mark.parametrize("title, key", [
    ("Playstation 5 slim ps5 1000 giga joc Astro bot", "sony|ps5"),
    ("PS5 Pro 2TB ca nou", "sony|ps5 pro"),
    ("PS5 Slim Digital Edition", "sony|ps5 digital"),
    ("Nintendo swicht oled", "nintendo|switch oled"),
    ("Nintendo Switch 2 + Mario Kart World", "nintendo|switch 2"),
    ("Xbox Series S 512 GB", "microsoft|xbox series s"),
    ("Steam Deck OLED 1TB", "valve|steam deck oled"),
    ("Placa video Gigabyte RTX 3060 Eagle 12GB", "nvidia|rtx 3060 12gb"),
    ("NVIDIA RTX 3080 MSI Suprim X 10GB", "nvidia|rtx 3080"),
    ("Placa video RTX 4060 Ti 16GB", "nvidia|rtx 4060 ti 16gb"),
    ("Placa video RTX 3060 pentru pc gaming", "nvidia|rtx 3060"),
    ("Radeon RX 7800 XT Sapphire Pulse", "amd|rx 7800 xt"),
    ("Procesor AMD Ryzen 7 5800X nou", "amd|ryzen 7 5800x"),
    ("Laptop Gaming Lenovo Legion 5 | i7-14650HX | RTX 4060", "laptop|rtx 4060"),
    ("Laptop HP Probook i5-1235U 16GB", "laptop|i5 gen 12"),
    ("MacBook Pro 14 2021 M1 Pro 16 GB", "apple|macbook pro m1 pro"),
    ("Macbook Pro 13 2019 16GB 512GB SSD", "apple|macbook pro intel"),
    ("Pc gaming lian li /ryzen 7 7800x3d/ rtx 5070", "pc|rtx 5070"),
    ("PC Gaming Ryzen 9 5900X, 32GB DDR4", "pc|ryzen 9 gen 5000"),
    ("DDR5 Kit 32GB 2x16GB 6000Mhz", "ram|ddr5 32gb"),
    ("Game Boy Color galben", "nintendo|game boy"),
])
def test_exact_model_and_variant(title, key):
    assert identify(title, "", "electronics").model_key == key


def test_accessories_games_locks_and_wanted_ads():
    assert "part" in identify("Controller PS5 DualSense alb", "", "electronics").flags
    assert "part" in identify("Joc GTA 5 pentru PS5", "", "electronics").flags
    assert "part" in identify("Husa protectie pentru Steam Deck", "", "electronics").flags
    assert "locked" in identify("MacBook Air M1", "Are MDM de la firma", "electronics").flags
    assert "wanted" in identify("Caut PS5 Pro", "", "electronics").flags
    assert "broken" in identify("PS5 nu porneste", "", "electronics").flags
    assert "broken" not in identify("PS5 slim", "Toate piesele sunt noi, fara drift, livrare Banat", "electronics").flags
    assert "locked" not in identify("PS5 slim", "Ridicare din Banat", "electronics").flags


def test_a_cheap_ps5_against_other_ps5s():
    db = DB(":memory:")
    market = [olx.parse_offer({**offer(100 + i, "PlayStation 5 Slim cu disc 1TB", p), "category": {"id": 1878}})
              for i, p in enumerate([2600, 2700, 2800, 2650, 2750])]
    for l in market:
        l.niche = "electronics"
    cheap = olx.parse_offer({**offer(1, "PS5 Slim disc + 2 manete", 1500), "category": {"id": 1878}})
    cheap.niche = "electronics"
    bot.process(db, [*market, cheap], S, alert=False)
    r = db.get("olx:1")
    assert r["model_key"] == "sony|ps5" and r["niche"] == "electronics"
    assert r["tier"] in ("good", "real_good") and r["est_value_ron"] and r["score"] >= 5


def test_the_category_is_on_and_searched():
    assert "electronics" in S.niches and niches.get("electronics").icon == "🎮"
    db = DB(":memory:")
    searches = bot.pick_searches(db, S)
    assert ("1878" in {c for q, c, n in searches if n == "electronics"})
    assert sum(1 for q, c, n in searches if q and n == "electronics") == S.searches_per_poll


@pytest.mark.parametrize("title, key, flag", [
    ("Pachet PS4 Slim 500GB + 2 Manete + PS VR1 compatibil PS5", "sony|ps4", None),
    ("1Consola Magica Mai Bun Ca PS5 PlayStation 4", None, "replica"),
    ("PlayStation Portal PS5", "sony|ps portal", None),
    ("Vand volan ps 4", "sony|ps4", "part"),
    ("Panouri Laterale (Console Covers) PlayStation 5", "sony|ps5", "part"),
    ("Vand Play Staion 5 slim Digital", "sony|ps5 digital", None),
    ("Playstion 4 Slim", "sony|ps4", None),
    ("Vand Jocuri Playstation 4 & 5", "sony|ps4", "part"),
])
def test_what_the_title_really_sells(title, key, flag):
    i = identify(title, "", "electronics")
    if key:
        assert i.model_key == key
    if flag:
        assert flag in i.flags


def test_far_under_the_usual_price_is_an_accessory_or_bait():
    db = DB(":memory:")
    market = [olx.parse_offer({**offer(100 + i, "Nintendo Switch OLED alb", p), "category": {"id": 1876}}) for i, p in enumerate([1100, 1200, 1150, 1250, 1180])]
    joycon = olx.parse_offer({**offer(1, "Nintendo Switch OLED joy con stanga", 90), "category": {"id": 1876}})
    for l in [*market, joycon]:
        l.niche = "electronics"
    bot.process(db, [*market, joycon], S, alert=False)
    r = db.get("olx:1")
    assert r["tier"] == "bad" and "accessory" in r["reason"] and r["score"] == 0


def test_games_named_before_the_console_are_what_is_sold():
    assert "part" in identify("Pachet de 5 jocuri Nintendo Switch 2 noi", "", "electronics").flags
    assert "part" in identify("Lot jocuri Xbox One Series x - noi sigilate", "", "electronics").flags
    assert "part" not in identify("PS5 Slim + 3 jocuri + 2 manete", "", "electronics").flags
    assert identify("Nintendo DSi XL Super Mario", "", "electronics").model_key == "nintendo|ds"


def test_variants_anywhere_in_the_title():
    assert identify("Consolă PlayStation 5 (PS5) Digital Edition + 2 Controllere", "", "electronics").model_key == "sony|ps5 digital"
    assert identify("Nintendo Switch 2 manete + incarcator", "", "electronics").model_key == "nintendo|switch"
    assert identify("Nintendo Switch model OLED alb", "", "electronics").model_key == "nintendo|switch oled"


@pytest.mark.parametrize("title, key", [
    ("Placa video ASUS Dual GeForce® RTX™ 3060 OC V2 12GB", "nvidia|rtx 3060 12gb"),
    ("Nvidia Geforce GTX750 TI OC", "nvidia|gtx 750 ti"),
    ("Vand/schimb rtx 3060 oc v2 Asus", "nvidia|rtx 3060"),
    ("Nvidia geforce rtx 3060 12gb ram", "nvidia|rtx 3060 12gb"),
    ("ASUS TUF Gaming F15 RTX 2050 – 16GB RAM, 1TB", "laptop|rtx 2050"),
    ("Ryzen 9 5950X | RTX 4060 Ti 16GB | 64GB RAM", "pc|rtx 4060 ti 16gb"),
    ("Placa video ASUS ROG Strix RTX 3080 10GB", "nvidia|rtx 3080"),
    ("Ultra GAMING Dell XPS 15 Intel Core i9 13900H 32GB", "laptop|i9 gen 13"),
])
def test_pc_parts_and_laptops_without_the_obvious_words(title, key):
    assert identify(title, "", "electronics").model_key == key


@pytest.mark.parametrize("title, key, flag", [
    ("sony ps5 portal NOU, luat de la Altex", "sony|ps portal", None),
    ("Vr2 playstation5", "sony|ps vr2", None),
    ("Xbox Series X/S - Seagate storage Expansion 1 TB", None, "part"),
    ("Placa de baza Macbook PRO m1 si Senzor Touch ID", None, "part"),
])
def test_found_while_verifying(title, key, flag):
    i = identify(title, "", "electronics")
    if key:
        assert i.model_key == key
    if flag:
        assert flag in i.flags


def test_half_price_working_electronics_is_suspicious_and_broken_is_priced_as_broken():
    db = DB(":memory:")
    working = [olx.parse_offer({**offer(100 + i, "PlayStation 5 Slim disc", p), "category": {"id": 1878}}) for i, p in enumerate([3000, 3100, 3200, 3150, 3050])]
    cheap = olx.parse_offer({**offer(1, "Vand PlayStation 5 + maneta", 1500), "category": {"id": 1878}})
    broken = olx.parse_offer({**offer(2, "PlayStation 5 slim defect nu porneste", 900), "category": {"id": 1878}})
    for l in [*working, cheap, broken]:
        l.niche = "electronics"
    bot.process(db, [*working, cheap, broken], S, alert=False)
    c = db.get("olx:1")
    assert c["tier"] == "mid" and c["reason"].startswith("suspiciously cheap") and c["score"] <= 5
    b = db.get("olx:2")
    assert b["est_value_ron"] is None and b["score"] <= 4  # no other broken PS5s to compare with: no estimate


def test_damage_in_the_description():
    i = identify("Macbook pro m1 pro 2021 16 CITITI ANUNTUL", "A suferit o cazatura, cu ecranul indoit asa", "electronics")
    assert "broken" in i.flags
