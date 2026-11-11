import pytest

from flipperbot.identify import find_brands, find_refs, identify, normalize
from flipperbot.watchdb import BRANDS

B = {b.name: b for b in BRANDS}


def test_normalize_strips_diacritics():
    assert normalize("Ceas  Bărbătesc ȘȚ") == "ceas barbatesc st"


@pytest.mark.parametrize(
    "title, brand",
    [
        ("Ceas Omega automatic Seamaster calendar URGENT", "Omega"),
        ("Grand Seiko SBGA211 snowflake", "Grand Seiko"),
        ("Ceas TAG Heuer Carrera", "TAG Heuer"),
        ("Heuer Autavia vintage", "Heuer"),
        ("Casio G-Shock GA-2100", "Casio"),
        ("Ceas sovietic Poljot de luxe", "Poljot"),
        ("ceas rusesc POLYOT 17 rubine", "Poljot"),
        ("Ceas dama Michael Kors", "Michael Kors"),
        ("ceas barbatesc automatic", None),
    ],
)
def test_brand(title, brand):
    i = identify(title)
    assert (i.brand.name if i.brand else None) == brand


def test_casio_dw_ref_is_not_daniel_wellington():
    i = identify("Casio DW-5600 original")
    assert i.brand.name == "Casio"
    assert "DW-5600" in i.refs


@pytest.mark.parametrize(
    "title, brand, ref",
    [
        ("Seiko SKX007 diver automatic", "Seiko", "SKX007"),
        ("Seiko 6139-6002 pogue chronograph", "Seiko", "6139-6002"),
        ("Omega Seamaster 166.0202 cal 565", "Omega", "166.0202"),
        ("Rolex Submariner 16610 2005", "Rolex", "16610"),
        ("Tissot PRX T137.407 40mm", "Tissot", "T137.407"),
        ("Poljot 3133 cronograf", "Poljot", "3133"),
    ],
)
def test_refs(title, brand, ref):
    i = identify(title)
    assert i.brand.name == brand
    assert i.refs[0] == ref


def test_units_and_years_are_not_refs():
    assert find_refs("ceas 42mm 10atm din 2015 18k", B["Rolex"]) == []
    assert find_refs("rezistent 100m, 21 rubine", None) == []


def test_model_key_prefers_ref_then_family():
    assert identify("Seiko SKX007").model_key == "seiko|SKX007"
    assert identify("Ceas Omega Seamaster automatic").model_key == "omega|seamaster"
    assert identify("Ceas Omega vechi").model_key == "omega"


def test_description_brand_only_when_title_has_none():
    i = identify("Ceas automatic Tissot", "arata ca un Rolex")
    assert i.brand.name == "Tissot"
    i = identify("Ceas automatic vechi", "este un Doxa din anii 60")
    assert i.brand.name == "Doxa"


@pytest.mark.parametrize(
    "title, desc, flag",
    [
        ("Ceas Seiko defect", "", "broken"),
        ("Ceas Orient", "nu functioneaza, pentru piese", "broken"),
        ("Ceas Citizen", "merge, necesita baterie", "battery"),
        ("Lot ceasuri vechi", "", "lot"),
        ("15 buc ceasuri diverse", "", "lot"),
        ("Rolex Submariner replica AAA", "", "replica"),
        ("Cumpar ceasuri vechi", "", "wanted"),
        ("Curea piele pentru Seiko", "", "part"),
        ("Ceas aur 18k", "carcasa din aur 750", "solid_gold"),
        ("Ceas Omega full set", "", "box_papers"),
    ],
)
def test_flags(title, desc, flag):
    assert flag in identify(title, desc).flags


def test_gold_plated_is_not_solid_gold():
    assert "solid_gold" not in identify("Ceas placat cu aur 18k").flags


def test_lot_names_several_brands():
    i = identify("Lot ceasuri Seiko, Orient, Poljot, Casio")
    assert "lot" in i.flags
    assert [b.name for b in i.brands] == ["Seiko", "Orient", "Poljot", "Casio"]
