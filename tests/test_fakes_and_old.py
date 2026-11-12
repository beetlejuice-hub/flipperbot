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


def test_most_searches_go_to_lots_and_old_watches():
    s = Settings()
    db = DB(":memory:")
    runs = [bot.pick_searches(db, s) for _ in range(50)]
    watch_focus = sum(1 for r in runs for q, c, n in r if q in s.focus_pool)
    assert watch_focus >= 50 * 2  # 2 of the 3 random searches each time
    feeds = {(c, n) for r in runs for q, c, n in r if c}
    assert feeds == {("1677", "watches"), ("1676", "watches")}


def test_luxury_needs_a_surer_claude():
    r = {"verdict": "buy", "authenticity": "likely_genuine", "confidence": 55}
    assert bot.confirmed(r, S, "japan")[0]
    ok, why = bot.confirmed(r, S, "luxury")
    assert not ok and "needs 60" in why


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
