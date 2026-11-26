from flipperbot import ai, market, messages, web
from flipperbot.config import Settings
from flipperbot.db import DB
from flipperbot.models import Listing

S = Settings()


def sale(db, i, model, price, *, days_up, sold_days_ago, first=None, niche="electronics", title="Xbox Series X"):
    db.upsert(Listing("olx", str(i), "u", f"{title} {i}", price_ron=first or price))
    if first:
        db.conn.execute("UPDATE prices SET seen_at=datetime('now', ?) WHERE key=?", (f"-{sold_days_ago + days_up} days", f"olx:{i}"))
        db.conn.execute("INSERT INTO prices VALUES (?, ?, datetime('now', ?))", (f"olx:{i}", price, f"-{sold_days_ago + 1} days"))
    db.conn.execute("""UPDATE listings SET model_key=?, niche=?, price_ron=?, flags='[]', gone_reason='sold',
                       gone_at=datetime('now', ?), created_at=datetime('now', ?) WHERE key=?""",
                    (model, niche, price, f"-{sold_days_ago} days", f"-{sold_days_ago + days_up} days", f"olx:{i}"))
    db.conn.commit()


def market_db():
    db = DB(":memory:")
    # Xbox Series X: sold at 1,500-1,700; the quick ones cheaper; sellers dropped ~10% from their first price
    for i, (price, up, ago, first) in enumerate([(1500, 3, 5, 1650), (1550, 5, 10, 1700), (1600, 12, 45, 1800),
                                               (1700, 20, 60, 1900), (1650, 8, 50, None)]):
        sale(db, i, "microsoft|xbox series x", price, days_up=up, sold_days_ago=ago, first=first)
    return db


def test_the_market_from_sales():
    m = market.summary(market_db(), "microsoft|xbox series x")
    assert m["n"] == 5 and m["median"] == 1600 and m["days"] == 8
    assert m["quick_price"] == 1525  # the two that went within a week
    assert 8 <= m["cut_pct"] <= 12  # sellers dropped ~10% before it sold
    assert m["trend_pct"] < 0  # this month's sales are cheaper than before
    assert 1600 <= m["resell_ask"] <= 1900
    line = market.line(m)
    assert "5 sold" in line and "within ~8 days" in line and "dropped" in line


def test_speed_from_the_brand_when_the_model_has_few_sales():
    db = market_db()
    for i in range(5):
        sale(db, 100 + i, f"microsoft|xbox one s v{i}", 600, days_up=4, sold_days_ago=10)
    m = market.summary(db, "microsoft|xbox series s", niche="electronics")
    assert m["brand_days"] <= 8 and m["brand_n"] >= 5 and "this brand" in market.line(m)


def test_what_sells_and_the_cheapest_now():
    db = market_db()
    db.upsert(Listing("olx", "500", "u", "Xbox Series X 1TB", price_ron=1300))
    db.conn.execute("UPDATE listings SET model_key='microsoft|xbox series x', niche='electronics' WHERE key='olx:500'")
    db.conn.commit()
    hot = market.hot(db)
    assert hot[0]["model"] == "microsoft|xbox series x" and hot[0]["for_sale"] == 1 and hot[0]["cheapest"] == 1300
    assert hot[0]["cheapest_vs_median_pct"] < -15
    card = web.listing_json(db.get("olx:500"), db)
    assert card["market"]["n"] == 5 and card["market"]["line"]


def test_offers_follow_how_much_sellers_drop():
    row = {"price_ron": 1000, "est_value_ron": 700, "score": 6, "ai": None}
    assert messages.offer(row, None) == 600  # no history: never under 60% of the asking price
    assert messages.offer(row, None, cut_pct=8) == 800  # sellers drop ~8%: open ~16% under, not 40%


def test_claude_is_told_what_really_sold():
    db = market_db()
    db.upsert(Listing("olx", "500", "u", "Xbox Series X", price_ron=1300))
    db.conn.execute("UPDATE listings SET model_key='microsoft|xbox series x', niche='electronics' WHERE key='olx:500'")
    db.conn.commit()
    assert "REALLY sold" in ai.sold_line(db, db.get("olx:500")) and "middle 1600" in ai.sold_line(db, db.get("olx:500"))
