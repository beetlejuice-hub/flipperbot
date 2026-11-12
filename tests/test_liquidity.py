from datetime import datetime, timedelta

from flipperbot import bot
from flipperbot.config import Settings
from flipperbot.db import DB
from flipperbot.sources import olx
from flipperbot.tiers import liquidity

from test_olx_and_bot import offer


def test_labels():
    assert liquidity([2, 5, 8, 10]) == {"label": "fast", "median_days": 6, "for_sale": 4}
    assert liquidity([20, 40, 50])["label"] == "normal"
    assert liquidity([90, 120, 140])["label"] == "slow"
    assert liquidity([200, 300, 400])["label"] == "very slow"
    assert liquidity([100] * 50)["label"] == "very slow"  # a glut
    assert liquidity([5, 6]) is None  # too few to say


def market(days_up, start=100):
    out = []
    for i, d in enumerate(days_up):
        o = offer(start + i, "Ceas Seiko SKX007", [1000, 1100, 950, 1050, 1000, 1000][i % 6])
        o["created_time"] = (datetime.now().astimezone() - timedelta(days=d)).isoformat(timespec="seconds")
        out.append(olx.parse_offer(o))
    return out


def test_a_cheap_buy_that_sells_slowly_isnt_real_good():
    s = Settings()
    fast, slow = DB(":memory:"), DB(":memory:")
    deal = olx.parse_offer(offer(200, "Ceas Seiko SKX007 diver", 400))
    bot.process(fast, [*market([3, 5, 8, 10, 12])], s, alert=False)
    bot.process(fast, [deal], s, alert=False)
    row = fast.get("olx:200")
    assert row["tier"] == "real_good" and '"fast"' in row["liquidity"]
    bot.process(slow, [*market([200, 250, 300, 400, 500])], s, alert=False)
    bot.process(slow, [deal], s, alert=False)
    row = slow.get("olx:200")
    assert row["tier"] == "mid" and row["reason"].startswith("sells very slow")
