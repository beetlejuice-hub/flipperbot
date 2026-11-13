from flipperbot import ai, bot
from flipperbot.config import Settings
from flipperbot.db import DB
from flipperbot.identify import identify
from flipperbot.models import Listing
from flipperbot.sources import olx
from flipperbot.tiers import judge

from test_olx_and_bot import offer

S = Settings()


def verdict(title, price, desc=""):
    return judge(Listing("olx", "1", "u", title, description=desc, price_ron=price), identify(title, desc), [], S)


def test_replica_factory_words_are_replicas():
    assert verdict("Rolex Submariner noob factory", 2500).tier == "bad"
    assert verdict("Ceas Omega Seamaster", 3000, "calitate 1:1, mecanism automatic").tier == "bad"


def test_replica_shop_talk_on_luxury_is_suspect():
    v = verdict("Ceas Tag Heuer Carrera", 3000, "Mecanism japonez Miyota, cutie cadou. Avem si alte modele.")
    assert verdict("Ceas Rado Coupole automatic", 2500, "calitate superioara, mai multe modele").tier != "suspect"  # Swiss + shop talk: fine
    assert v.tier == "suspect" and "replicas" in v.reason
    # the same words on a Seiko mean nothing
    assert verdict("Ceas Seiko 5 automatic", 200, "mecanism japonez, cutie cadou").tier != "suspect"


def test_seller_who_doesnt_know():
    v = verdict("Ceas vechi de la bunicul", 150, "Nu stiu ce marca e, nu stiu daca merge.")
    assert "naive" not in identify("Ceas Doxa", "nu cunosc istoric service, starea cum se vede in poze").flags
    assert v.tier == "mid" and "doesn't seem to know" in v.reason
    assert verdict("Ceas Longines vechi", 900, "mostenire, nu ma pricep").tier == "good"


def test_search_mix_old_modern_general():
    from flipperbot import niches

    s = Settings()
    db = DB(":memory:")
    runs = [bot.pick_searches(db, s) for _ in range(50)]
    watch_terms = [q for r in runs for q, c, n in r if q and n == "watches"]
    cam_terms = [q for r in runs for q, c, n in r if q and n == "cameras"]
    assert sum(q in s.focus_pool for q in watch_terms) >= 50  # one lots/old search each poll
    assert sum(q in s.modern_pool for q in watch_terms) >= 50  # one modern search each poll
    assert len(watch_terms) == len(cam_terms) == 50 * 3
    assert sum(q in niches.CAMERAS.focus_pool for q in cam_terms) >= 50
    feeds = {(c, n) for r in runs for q, c, n in r if c}
    assert feeds == {("1677", "watches"), ("1676", "watches"), ("1943", "watches"), ("2344", "cameras"), ("1935", "cameras"),
                     ("1878", "electronics"), ("1876", "electronics"), ("2130", "electronics"), ("1882", "electronics")}


def test_luxury_needs_a_surer_claude():
    r = {"verdict": "buy", "authenticity": "likely_genuine", "confidence": 65}
    assert bot.confirmed(r, S, "japan")[0]
    ok, why = bot.confirmed(r, S, "luxury")
    assert not ok and "needs 70" in why
    assert not bot.confirmed({**r, "confidence": 55}, S, "japan")[0]  # half sure isn't sure


def test_claude_sees_the_sellers_other_listings():
    db = DB(":memory:")
    ls = [olx.parse_offer(offer(i, t, p)) for i, (t, p) in enumerate([("Rolex Daytona", 1500), ("AP Royal Oak", 2000), ("Ceas Rolex Submariner", 1400)])]
    for l in ls:
        l.seller_id = "dealer"
    bot.process(db, ls, S)
    text = ai.seller_listings(db, db.get("olx:2"))
    assert "Rolex Daytona (1500 lei)" in text and "AP Royal Oak" in text and "Submariner" not in text


def test_old_broken_swiss_goes_to_claude_not_the_brand_average():
    l = Listing("olx", "1", "u", "Ceas de colectie Doxa, anii 40, nefunctional", price_ron=350)
    i = identify(l.title)
    v = judge(l, i, [700, 800, 650, 900, 750], S)  # brand-level Doxa prices don't apply to a 1940s piece
    assert v.tier == "good" and "Claude will look" in v.reason
    # a known model is still priced normally
    l2 = Listing("olx", "2", "u", "Seiko SKX007 vechi", price_ron=400)
    assert judge(l2, identify(l2.title), [1000] * 6, S).est_value_ron


def test_collectible_references():
    v = verdict("Ceas Seiko automatic cronograf", 600, "cal. 6139, merge")
    assert v.tier == "good" and "6139" in v.reason
    assert "collectible" in identify("Ceas vechi cronograf Valjoux 7733").flags
    assert verdict("Ceas Omega Flightmaster", 3500).tier == "good"


def test_quartz_old_unclear_isnt_sent_to_claude():
    assert "quartz" in identify("Ceas vechi quartz", "functioneaza cu baterie").flags
    assert verdict("Ceas Longines vechi quartz", 900).tier != "good"
    assert "mechanical" in identify("Ceas Doxa vechi", "mecanic, 17 rubine").flags


def test_collectible_not_from_keyword_stuffing_or_mods():
    assert "collectible" not in identify("Casio G Shock GA-100", "stil king seiko, rolex, omega").flags
    assert "collectible" not in identify("Ceas Tutima Glashutte Sky", "Referinta: 6105-56").flags
    assert "collectible" not in identify("Ceas Seiko automatic modificat in stil Pilot", "cadran tropical").flags
    assert "collectible" in identify("Ceas Seiko automatic", "calibru 6139, cronograf").flags  # its own brand
    assert "collectible" in identify("Ceas vechi cronograf", "mecanism Valjoux 7733").flags  # a movement, unbranded


def test_trade_talk_in_description_isnt_the_watch():
    title = "Luminox Adventurer Atacama 1760 H3 Tritiu"
    desc = "Ceas in stare foarte buna, functioneaza perfect. Accept schimb cu Omega sau Rolex plus diferenta."
    i = identify(title, desc)
    assert i.brand.name == "Luminox"
    v = verdict(title, 600, desc)
    assert v.tier != "suspect" and "Omega" not in v.reason
    # unknown brand in the title, a luxury name only in the description: never "likely fake"
    v = verdict("Ceas barbatesc Atlantic", 600, "Mai am un Rolex de vanzare")
    assert v.tier != "suspect"


def test_sleeper_brands_and_brand_bound_references():
    assert identify("Ceas Vulcain Cricket vechi").brand.name == "Vulcain"
    assert "collectible" in identify("Ceas Vulcain Cricket vechi").flags
    assert identify("Ceas Eberhard Scafograf").brand.segment == "vintage"
    assert "collectible" not in identify("Ceas Marathon Navigator").flags  # a Tissot reference, not this brand


def test_a_too_cheap_seiko_gets_a_skeptical_second_check_that_finds_the_fake(monkeypatch, tmp_path):
    import json
    import subprocess

    from flipperbot import ai
    from flipperbot.scoring import claude_score

    s = Settings()
    monkeypatch.setattr(Settings, "photos_dir", property(lambda self: tmp_path))
    monkeypatch.setattr(ai, "log_call", lambda *a: None)
    monkeypatch.setattr(ai, "available", lambda s_: True)
    db = DB(":memory:")
    market = [olx.parse_offer(offer(100 + i, "Ceas Seiko Presage Cocktail Time automatic", p)) for i, p in enumerate([2300, 2400, 2500, 2400, 2350])]
    bot.process(db, [*market, olx.parse_offer(offer(1, "Ceas barbatesc automatic Seiko Presage", 300))], s, alert=False)
    row = db.get("olx:1")
    first = {"verdict": "buy", "authenticity": "likely_genuine", "confidence": 82, "resale_ron_low": 1700,
             "resale_ron_high": 2100, "watches": [], "summary": "Seiko Presage, buy"}
    hunt = {"verdict": "fake", "confidence": 90, "reference": "SSA405J1",
            "evidence": ["caseback reads MADW IN JAPAN", "case code 4R35-01T0 is a closed-dial date-only case",
                         "21 jewels on the rotor; a 4R38 has 24", "no black-dial open heart on a bracelet exists"]}
    prompts = []

    def run(args, input, **kw):
        prompts.append(input)
        answer = first if len(prompts) == 1 else hunt
        return subprocess.CompletedProcess(args, 0, json.dumps({"result": json.dumps(answer)}), "")

    monkeypatch.setattr(ai.subprocess, "run", run)
    result = ai.check(db, row, s)
    assert "TOO CHEAP TO BE TRUE" in prompts[0] and "LETTER BY LETTER" in prompts[0]
    assert "skeptical" in prompts[1] and "Seiko Presage" in prompts[1]
    assert result["authenticity"] == "likely_fake" and result["verdict"] == "skip" and "MADW" in result["authenticity_notes"]
    assert db.get("olx:1")["score"] == 0
    assert not bot.confirmed(result, s, row["segment"], row["price_ron"])[0]
    # Can't confirm it's real: no 8+. Not even checked by the skeptic: too cheap to trust.
    assert claude_score(ai.apply_fake_hunt(first, {**hunt, "verdict": "unsure"}), 300)[0] <= 7
    assert claude_score(first, 300)[0] <= 7
    assert claude_score({**first, "verified": True}, 300)[0] == 10


def test_prompts_and_models():
    from flipperbot import ai

    assert "several watches" in ai.LOT_BLOCK and "cameras" in ai.CAMERA_LOT_BLOCK
    assert Settings().ai_model == "haiku" and Settings().fake_hunt_model == "sonnet"
