import pytest

from flipperbot.identify import identify


@pytest.mark.parametrize("niche, title, key, flag", [
    ("phones", "Apple iPhone 13 Pro 256GB Sierra Blue neverlock", "apple|iphone 13 pro 256gb", None),
    ("phones", "iPhone 15 Pro Max 512 GB", "apple|iphone 15 pro max 512gb", None),
    ("phones", "Samsung Galaxy S23 Ultra 256GB", "samsung|galaxy s23 ultra 256gb", None),
    ("phones", "Samsung Galaxy Z Flip 5", "samsung|galaxy z flip 5", None),
    ("phones", "Google Pixel 8 Pro", "google|pixel 8 pro", None),
    ("phones", "iPhone 14 blocat icloud", "apple|iphone 14", "locked"),
    ("phones", "IPhone 16 Pro Max 256 gb neverlock sticla fisurata", "apple|iphone 16 pro max 256gb", "broken"),
    ("phones", "Husa iPhone 15 Pro silicon", "apple|iphone 15 pro", "part"),
    ("tools", "Masina de gaurit si insurubat Makita DHP485 doar corp", "makita|dhp485 solo", None),
    ("tools", "Milwaukee M18 FUEL FPD2 percutie", "milwaukee|m18 fpd2", None),
    ("tools", "Milwaukee M12 FID", "milwaukee|m12 fid", None),
    ("phones", "Iohone 17 Pro Max 256 gb", "apple|iphone 17 pro max 256gb", None),
    ("phones", "18 pro max burgundy 256gb - CA NOU", "apple|iphone 18 pro max 256gb", None),
    ("phones", "Iphone Air / Sky Blue / sigilat / 256 GB", "apple|iphone air 256gb", None),
    ("tools", "Rotopercutor SDS Plus Milwaukee M18 BLHX impecabil", "milwaukee|m18 blhx", None),
    ("tools", "Rotopercutor Hilti TE 30-A36", "hilti|te30 a36", None),  # the cordless one: not a TE 30
    ("tools", "Rotopercutor Hilti TE 30", "hilti|te30", None),
    ("tools", "Acumulator Makita 18V 5Ah original", "makita|battery 5ah", None),
    ("tools", "Polizor unghiular, Flex Makita GA5040CF01 125", "makita|ga5040cf01", None),
    ("tools", "Surubelnita Makita 48V cu 2 acumulatori", None, "replica"),
    ("tools", "Cuie pt Hilti BX3", None, "part"),
    ("lego", "LEGO Star Wars UCS Millennium Falcon 75192 sigilat", "lego|75192 sealed", None),
    ("lego", "Lego Technic 42143 Ferrari Daytona SP3", "lego|42143", None),
    ("lego", "NOU Tip lego masina Ferrari Daytona SP3 42143", None, "replica"),
    ("lego", "Lot lego 5 kg piese amestecate", None, "lot"),
    ("sneakers", "Nike Air Jordan 4 Retro Military Blue marime 43", "nike|jordan 4", None),
    ("sneakers", "Adidasi AIR JORDAN 1 Retro High OG", "nike|jordan 1 high", None),
    ("sneakers", "Nike Dunk Low Panda 42", "nike|dunk low", None),
    ("sneakers", "Adidași New Balance 550 Albi, marimea 38", "new balance|550", None),
    ("sneakers", "adidas Samba OG", "adidas|samba", None),
    ("sneakers", "Adidași Air Jordan Retro 12 Low GS Wolf Grey", "nike|jordan 12", None),
    ("sneakers", "Adidasi Nike Jordan Air 1 Albi", "nike|jordan 1", None),
    ("sneakers", "Nike Dunk SB Low Pigeon 43", "nike|dunk low", None),
    ("sneakers", "Nike Dunk Safari Golden Moss - 45.5 EU", "nike|dunk low", None),
    ("sneakers", "REDUCE DE SEZON Nike Tn Air Max negrii", "nike|air max plus", None),
    ("tools", "Flex cu variator Bosch GWS 7-115 E", "bosch|gws7115", None),
    ("tools", "Masina de gaurit si insurubat cu acumulatori, Makita 8434D", "makita|8434d", None),
    ("sneakers", "Jordan 4 calitate premium cutie+eticheta", "nike|jordan 4", "replica"),
])
def test_new_categories(niche, title, key, flag):
    i = identify(title, "", niche)
    if key:
        assert i.model_key == key
    if flag:
        assert flag in i.flags


def test_sneaker_floors_keep_replicas_out():
    from flipperbot import bot
    from flipperbot.config import Settings
    from flipperbot.db import DB
    from flipperbot.sources import olx
    from test_olx_and_bot import offer

    s = Settings()
    db = DB(":memory:")
    pairs = [olx.parse_offer(offer(100 + i, "Nike Air Jordan 4 Retro marime 43", p)) for i, p in enumerate([800, 850, 900, 820, 880])]
    fakes = [olx.parse_offer(offer(150 + i, "Jordan 4 Retro marime 42", 220)) for i in range(6)]
    new_cheap = olx.parse_offer(offer(1, "Jordan 4 noi in cutie sigilat", 250))
    worn_cheap = olx.parse_offer(offer(2, "Jordan 4 purtati marime 44", 300))
    for l in [*pairs, *fakes, new_cheap, worn_cheap]:
        l.niche = "sneakers"
    bot.process(db, [*pairs, *fakes, new_cheap, worn_cheap], s, alert=False)
    assert db.get("olx:1")["tier"] == "suspect" and db.get("olx:1")["score"] == 0
    assert db.get("olx:2")["reason"].startswith("cheap for a jordan 4") and db.get("olx:2")["score"] <= 4
    probe = olx.parse_offer(offer(3, "Nike Air Jordan 4 Retro Military Blue 44", 700))
    probe.niche = "sneakers"
    bot.process(db, [probe], s, alert=False)
    assert db.get("olx:3")["est_value_ron"] >= 700  # the six 220-lei fakes don't drag the market down
