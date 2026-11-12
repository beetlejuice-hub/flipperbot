from flipperbot.config import Settings
from flipperbot.identify import identify
from flipperbot.models import Listing
from flipperbot.tiers import judge

S = Settings()


def verdict(title, price, desc="", comps=()):
    return judge(Listing("olx", "1", "u", title, description=desc, price_ron=price), identify(title, desc), list(comps), S)


def test_smartwatch_models():
    assert identify("Apple Watch Ultra 2 49mm").model_key == "apple watch|ultra 2"
    assert identify("Garmin Fenix 7 Pro Solar").model_key == "garmin|fenix 7 pro"
    assert identify("Samsung Galaxy Watch 6 Classic 47mm").model_key == "samsung galaxy watch|watch 6 classic"
    assert identify("Ceas Garmin Forerunner 265").segment == "smart"


def test_smartwatch_priced_from_its_own_listings():
    comps = [2800, 3000, 3100, 2900, 3200, 3000]
    assert verdict("Apple Watch Ultra 2 49mm", 1300, comps=comps).tier in ("good", "real_good")


def test_clones_and_locked_watches():
    assert verdict("Apple Watch Ultra 2 HK9 Pro 49mm", 250).tier == "bad"  # a clone
    assert "replica" in identify("Smartwatch T800 Ultra").flags
    v = verdict("Apple Watch Series 8 45mm", 600, "este blocat icloud, nu stiu parola")
    assert v.tier == "bad" and "account" in v.reason
    assert verdict("Apple Watch Series 9 45mm", 250).tier == "suspect"  # far too cheap for a current model


def test_old_apple_watches_are_just_cheap_and_accessories_are_parts():
    assert verdict("Apple Watch Series 3 42mm", 300).tier != "suspect"
    assert verdict("Apple Watch Ultra 2", 285).tier == "suspect"
    assert "part" in identify("Huse antisoc Defense360 APPLE Watch Series 10 46mm").flags
    assert "part" in identify("Statie incarcare wireless compatibila Apple Watch").flags
    assert "part" not in identify("Ceas Smart-Watch OnePlus 2R, 46mm GPS Compatibil cu Android").flags
    assert "part" not in identify("Ceas Seiko 5 automatic").flags


def test_fake_rule_uses_the_model_in_the_title_only():
    v = verdict("Smartwatch Garmin Insinct 2X Solar", 800, "merge ca un fenix 8")
    assert v.tier != "suspect"
    assert "part" in identify("Husa/Carcasa Samsung Galaxy Watch Ultra").flags
    assert "part" in identify("Cabluri incarcare ceas sport garmin").flags


def test_romanian_model_names_and_title_only_models():
    assert identify("Apple watch seria 8 - 45 mm").model_key == "apple watch|series 8"
    assert identify("Apple Watch 5 / Silver / 44 mm").model_key == "apple watch|series 5"
    assert identify("Apple Watch serie 9 GPS 45 mm", "nu e ultra").model_key == "apple watch|series 9"
    assert identify("Garmin Fenix 7s, 42 mm").model_key == "garmin|fenix 7s"
    assert identify("Smartwatch Garmin Insinct 2X Solar", "mai bun ca fenix 8").model_key == "garmin"


def test_romanian_named_current_model_too_cheap_is_suspect():
    assert verdict("Apple watch seria 10", 300).tier == "suspect"
