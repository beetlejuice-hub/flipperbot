import pytest

from flipperbot import bot, niches
from flipperbot.clothdb import floor, size, split_brand
from flipperbot.config import Settings
from flipperbot.db import DB
from flipperbot.identify import identify, normalize
from flipperbot.models import Listing
from flipperbot.sources import olx
from flipperbot.tiers import judge

from test_olx_and_bot import offer

S = Settings()


def verdict(title, price, desc="", comps=()):
    return judge(Listing("olx", "1", "u", title, description=desc, price_ron=price), identify(title, desc, "clothing"),
                 list(comps), S)


@pytest.mark.parametrize("title, key", [
    ("Geaca puffer Stone Island", "stone island|puffer"),
    ("geaca stone island marimea S", "stone island|jacket"),
    ("Hanorac Stone Island", "stone island|hoodie"),
    ("Stone Island Shadow Project Pantaloni", "stone island|shadow project pants"),
    ("Arc'teryx Alpha SV Jacket, Gore-Tex Pro", "arc'teryx|alpha sv"),
    ("Arcteryx Atom LT hoody", "arc'teryx|atom"),
    ("Geaca Moncler Maya", "moncler|maya"),
    ("Canada Goose Expedition parka", "canada goose|expedition"),
    ("geci de iarna the north face 1996 nuptse 700", "the north face|nuptse 700"),
    ("Carharrt WIP DOUBLE KNEE PANT - Pantaloni", "carhartt|double knee pants"),
    ("Jacheta Carhartt Detroit", "carhartt|detroit jacket"),
    ("Pulover Polo Ralph Lauren polo bear", "ralph lauren|polo bear"),
    ("GEACA POLO RALPH LAUREN marimea M", "ralph lauren|jacket"),
    ("Blugi LEVIS 501 vintage", "levi's|501"),
    ("Supreme box logo hoodie", "supreme|box logo hoodie"),
    ("Hanorac CP Company goggle", "c.p. company|goggle hoodie"),
    ("Stoneisland hanorac", "stone island|hoodie"),
    ("Geaca de blugi Levi's trucker", "levi's|trucker"),
])
def test_brand_line_and_kind(title, key):
    assert identify(title, "", "clothing").model_key == key


def test_sizes():
    assert size(normalize("Geaca de blugi Levi's trucker marimea L")) == "L"  # not the "s" of Levi's
    assert size(normalize("Tricou Stone Island - M")) == "M" and size(normalize("Jacheta Carhartt Detroit XL")) == "XL"


def test_disguised_brand_names_are_replicas():
    for t in ["bluza mo n cler super calitate", "Tricou b@lenciaga", "g.u.c.c.i tricou", "Hanorac s t o n e island"]:
        assert split_brand(normalize(t)), t
    for t in ["Geaca Stone Island", "Stoneisland hanorac", "Off-White tricou", "Hanorac CP Company", "Arc'teryx Beta"]:
        assert split_brand(normalize(t)) is None, t
    v = verdict("bluza mo n cler super calitate", 150)
    assert v.tier == "bad" and "disguised" in v.reason and "Moncler" in v.reason


def test_replica_talk_shops_fast_fashion_womens():
    assert verdict("Hanorac Balenciaga premium", 250).tier == "bad"
    assert verdict("Hanorac Balenciaga", 250, "calitate premium, toate marimile").tier == "bad"
    v = verdict("Hanorac Balenciaga negru marimea L", 300, "toate marimile, livrare gratuita, plata ramburs")
    assert v.tier == "suspect" and "shop" in v.reason
    assert "fast fashion" in verdict("Tricou Zara", 30).reason
    assert "women" in verdict("Geaca Moncler dama", 900).reason
    assert verdict("Badge Stone Island original", 80).tier == "bad"  # the badge alone, not the jacket


def test_no_stains_is_not_a_stain():
    assert "broken" not in identify("Geaca Stone Island", "stare impecabila, fara pete, fara gauri, fara defecte", "clothing").flags
    assert "broken" in identify("Geaca Stone Island", "are o pata pe maneca", "clothing").flags


def test_price_floors_catch_replicas():
    v = verdict("Geaca Moncler Maya marimea M", 500, "noua cu eticheta")
    assert v.tier == "suspect" and "replica" in v.reason
    assert verdict("Geaca Moncler Maya marimea M", 700, "purtata un sezon").tier == "mid"
    assert floor("Arc'teryx", "premium", "alpha sv") == 900 and floor("The North Face", "premium", "nuptse 700") == 250


def test_a_third_of_the_market_is_a_replica_and_far_under_needs_claude():
    comps = [1200, 1100, 1300, 1000, 1250, 1150]
    assert verdict("Geaca Stone Island marimea L", 350, "purtata", comps).tier == "suspect"
    v = verdict("Geaca Stone Island marimea L", 450, "purtata, stare buna", comps)  # 60%+ under an often-faked brand
    assert v.tier == "mid" and "labels" in v.reason
    assert verdict("Arc'teryx Beta LT M", 1000, "purtata", [1700, 1600, 1800, 1500, 1650]).tier == "good"


def test_the_category_is_searched_every_poll():
    assert niches.get("clothing").icon == "👕" and "clothing" in S.niches and "clothing" in S.every_poll
    db = DB(":memory:")
    searches = bot.pick_searches(db, S)
    assert "2071" in {c for q, c, n in searches if n == "clothing"}


def test_only_branded_mens_clothes_are_kept():
    db = DB(":memory:")
    ls = [olx.parse_offer({**offer(1, "Geaca Stone Island marimea L", 900), "category": {"id": 2075}}),
          olx.parse_offer({**offer(2, "Geaca barbati iarna", 100), "category": {"id": 2075}}),  # no brand
          olx.parse_offer({**offer(3, "Geaca Moncler dama", 900), "category": {"id": 2075}})]  # women's
    for l in ls:
        l.niche = "clothing"
    assert [bot.is_relevant(l) for l in ls] == [True, False, False]


def test_the_fake_hunt_runs_on_often_faked_clothes():
    from flipperbot import ai

    row = {"niche": "clothing", "brand": "Stone Island", "segment": "premium", "flags": "[]", "price_ron": 800,
           "est_value_ron": 1200}
    assert ai.needs_fake_hunt(row, {"verdict": "buy", "authenticity": "likely_genuine"})
    row = {**row, "brand": "Carhartt"}
    assert not ai.needs_fake_hunt(row, {"verdict": "buy", "authenticity": "likely_genuine"})


def _jpeg_data_url():
    import base64

    return "data:image/jpeg;base64," + base64.b64encode(b"\xff\xd8\xff\xe0" + b"0" * 100).decode()


def test_a_vinted_item_pasted_by_hand(monkeypatch, tmp_path):
    from flipperbot import manual

    s = Settings()
    monkeypatch.setattr(Settings, "photos_dir", property(lambda self: tmp_path))
    db = DB(":memory:")
    row = manual.add(db, s, {"url": "https://www.vinted.ro/items/7412345678-geaca-stone-island", "title": "Geaca Stone Island Ghost",
                             "price": "450", "size": "L", "description": "purtata putin", "niche": "clothing",
                             "photos": [_jpeg_data_url(), _jpeg_data_url()]})
    assert row["key"] == "vinted:7412345678" and row["model_key"] == "stone island|ghost jacket"
    assert (tmp_path / "vinted_7412345678" / "2.jpg").read_bytes().startswith(b"\xff\xd8")
    assert manual.photo_path(s, "vinted:7412345678", "1") and manual.photo_path(s, "olx:1", "1") is None
    assert manual.photo_path(s, "vinted:../../etc", "1") is None
    assert "Marime: L" in row["description"]
    # pasted again without photos: same listing, photos kept
    row = manual.add(db, s, {"url": "https://www.vinted.ro/items/7412345678-x", "title": "Geaca Stone Island Ghost", "price": 420})
    assert row["price_ron"] == 420 and len(__import__("json").loads(row["photos"])) == 2


@pytest.mark.parametrize("data, why", [
    ({"title": "x", "price": 10}, "title"), ({"title": "Geaca Moncler", "price": "abc"}, "price"),
    ({"title": "Geaca Moncler", "price": 10, "url": "javascript:alert(1)"}, "https"),
    ({"title": "Geaca Moncler", "price": 10, "photos": ["data:image/png;base64,AAAA"]}, "JPEG"),
])
def test_pasted_listings_are_checked(data, why, monkeypatch, tmp_path):
    from flipperbot import manual

    monkeypatch.setattr(Settings, "photos_dir", property(lambda self: tmp_path))
    with pytest.raises(manual.Invalid, match=why):
        manual.add(DB(":memory:"), Settings(), data)


@pytest.mark.parametrize("title, key, flag", [
    ("Rick Owens Geobasket 43", "rick owens|geobasket", None),
    ("Maison Margiela GAT replica 42", "maison margiela|gat", None),  # "Replica" is Margiela's line, not a confession
    ("Margiela Replica sneakers 43", "maison margiela|gat", None),
    ("Adidasi Jordan 4 replica", "nike|jordan 4", "replica"),
    ("Balenciaga Triple S", "balenciaga|triple s", None),
    ("Adidasi Dior B22", "dior|b22", None),
    ("Air Jordan 4 Retro Military Black, calitate premium", "nike|jordan 4", "replica"),
])
def test_designer_sneakers(title, key, flag):
    i = identify(title, "", "sneakers")
    assert i.model_key == key
    assert (flag in i.flags) if flag else not i.flags & {"replica", "dealer"}


def test_sneaker_shops_selling_every_size():
    assert "dealer" in identify("Balenciaga Triple S", "marimi 40 41 42 43 44", "sneakers").flags
    assert "dealer" in identify("Nike Dunk Low Panda", "disponibile 39-45, livrare gratuita", "sneakers").flags
    assert "dealer" not in identify("Nike Dunk Low Panda 43", "purtati de 2 ori, marimea 43", "sneakers").flags
    v = judge(Listing("olx", "1", "u", "Balenciaga Triple S", description="marimi 40 41 42 43 44", price_ron=450),
              identify("Balenciaga Triple S", "marimi 40 41 42 43 44", "sneakers"), [], S)
    assert v.tier == "suspect" and "shop" in v.reason


def test_shop_listings_of_clothes():
    for t, d in [("Hanorac Balenciaga Off White Amiri, Boss, Armani", ""), ("Tricouri LV-din bumbac 100%", ""),
                 ("Geaca Burberry neagra marimi S,M,L", ""), ("Hoodie Off White", "Masuri disponibile in momentul postarii")]:
        assert "dealer" in identify(t, d, "clothing").flags, t
    for t, d in [("Geaca Stone Island marimea L", "stare buna, m"), ("Geaca Moncler", "marime: L / 50")]:
        assert "dealer" not in identify(t, d, "clothing").flags, t
