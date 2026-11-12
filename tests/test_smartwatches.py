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
    assert verdict("Apple Watch Series 9 45mm", 250).tier == "suspect"  # far too cheap for a real one
