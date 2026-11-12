from flipperbot.config import Settings
from flipperbot.identify import identify
from flipperbot.models import Listing
from flipperbot.tiers import judge, market_price

S = Settings()


def verdict(title, price, desc="", comps=()):
    l = Listing("olx", "1", "u", title, description=desc, price_ron=price)
    return judge(l, identify(title, desc), list(comps), S)


def test_market_price_drops_outliers():
    assert market_price([1, 900, 1000, 1000, 1100, 1200, 99999]) == 1000


def test_real_good_needs_discount_and_profit():
    comps = [1000, 1100, 1200, 1000, 900]
    assert verdict("Seiko SKX007", 400, comps=comps).tier == "real_good"
    assert verdict("Seiko SKX007", 650, comps=comps).tier == "good"
    assert verdict("Seiko SKX007", 800, comps=comps).tier == "mid"  # resale 850 after haircut: small profit
    assert verdict("Seiko SKX007", 1000, comps=comps).tier == "bad"


def test_repair_cost_eats_profit():
    comps = [1000] * 6
    v = verdict("Seiko SKX007 defect", 400, comps=comps)
    # realistic sale 1000 - 5% selling costs = 950; minus the price and ~250 to fix a broken Seiko
    assert (v.est_value_ron, v.est_high_ron, v.profit_ron) == (950, 950, 300)


def test_realistic_range_is_below_what_listings_ask():
    from flipperbot.tiers import realistic_range

    asks = [700, 800, 900, 1000, 1100, 1200, 1300, 1400]
    low, high = realistic_range(asks, exact=True)
    assert low < high < 1050  # median ask is 1050: realistic sale sits under it
    family_low, _ = realistic_range(asks, exact=False)
    assert family_low < low  # only the family known (mixes variants): more cautious


def test_too_few_comps_means_no_market():
    v = verdict("Seiko SKX007", 400, comps=[1000, 1000])
    assert v.est_value_ron is None


def test_skips():
    assert verdict("Ceas Michael Kors", 100).tier == "bad"
    assert verdict("Rolex replica AAA", 500).tier == "bad"
    assert verdict("Cumpar ceasuri", 100).tier == "bad"
    assert verdict("Omega Seamaster", 9000).tier == "bad"  # over budget


def test_cheap_luxury_is_suspect_unless_broken():
    assert verdict("Rolex Submariner", 1200).tier == "suspect"
    assert verdict("Ceas Omega Geneve defect", 1200).tier == "good"


def test_lots():
    assert verdict("Lot ceasuri Omega, Seiko, Poljot", 900).tier == "good"
    assert verdict("Lot ceasuri Seiko Poljot Vostok", 300).tier == "mid"
    assert verdict("Lot 20 buc ceasuri", 400).tier == "mid"


def test_no_history_yet():
    assert verdict("Ceas Longines automatic", 900).tier == "mid"
    assert verdict("Ceas Seiko 5 automatic", 200).tier == "mid"
    assert verdict("Ceas Seiko quartz", 600).tier == "bad"
    assert verdict("Ceas vechi automatic", 150).tier == "mid"
    assert verdict("Ceas barbatesc elegant", 150).tier == "bad"


def test_cheap_vintage_luxury_gets_a_look_not_suspect():
    assert verdict("Omega ceas buzunar an aprox 1900 cadran alb", 777).tier == "good"
    assert verdict("Ceas Omega automatic seatmaster calendar urgent", 800).tier == "suspect"


def test_brand_only_price_never_alerts():
    comps = [1150] * 6
    v = verdict("Ceas Citizen Calendar Quartz Dama", 120, comps=comps)
    assert v.tier == "mid" and "brand-level" in v.reason


def test_parts_named_in_plural():
    assert verdict("Capacitori ceas Seiko", 75).tier == "bad"
    assert verdict("Cadrane ceas Poljot 17 rubine", 50).tier == "bad"


def test_luxury_named_only_in_description_stays_suspect():
    v = verdict("Ceas Barbatesc De Firma Lux Elegant 2026", 239, desc="model Rolex, colectie noua")
    assert v.tier == "suspect"


def test_lot_needs_the_title_to_say_so():
    assert "lot" not in verdict("Ceas Stowa placat", 290, desc="Mai am 2 buc: Seiko, Citizen, Poljot, Zenith").reason


def test_too_spread_to_price_shows_no_number():
    comps = [1500, 1800, 2500, 4000, 6000, 9000, 11000, 12000, 15000]  # a family of very different models
    v = verdict("Ceas Omega Seamaster Polaris", 3000, comps=comps)
    assert v.est_value_ron is None and v.tier in ("mid", "bad") and "vary too much" in v.reason
