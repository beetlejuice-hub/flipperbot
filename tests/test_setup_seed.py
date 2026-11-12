from flipperbot import bot, config, seed
from flipperbot.config import Settings
from flipperbot.db import DB
from flipperbot.sources import olx

from test_olx_and_bot import offer


def test_set_value_fills_the_example_and_replaces(tmp_path):
    p = tmp_path / "config.toml"
    config.set_value("telegram_token", "123:abc", p)
    config.set_value("telegram_chat_id", "42", p)
    config.set_value("telegram_token", "456:def", p)
    s = config.load(p)
    assert (s.telegram_token, s.telegram_chat_id) == ("456:def", "42")
    assert "budget_ron" in p.read_text()  # the example's other settings are kept


def test_seed_round_trip(tmp_path):
    src = DB(":memory:")
    s = Settings()
    listings = [olx.parse_offer(offer(100 + i, "Ceas Seiko SKX007", p)) for i, p in enumerate([1000, 1100, 950, 1050, 400])]
    bot.process(src, listings, s, alert=False)
    path = tmp_path / "seed.json.gz"
    assert seed.export(src, path) == 5

    dst = DB(":memory:")
    assert seed.load_if_empty(dst, path) == 5
    assert seed.load_if_empty(dst, path) == 0  # the same seed again adds nothing
    row = dst.get("olx:104")
    assert row["tier"] == "real_good" and row["notified_tier"] == "real_good" and row["in_digest"] == 1
    assert row["description"] == ""  # nothing personal shipped
    assert len(dst.comparable_prices("seiko|SKX007")) == 5


def test_a_newer_seed_adds_to_a_database_that_already_has_data(tmp_path):
    s = Settings()
    src = DB(":memory:")
    bot.process(src, [olx.parse_offer(offer(100 + i, "Ceas Seiko SKX007", p)) for i, p in enumerate([1000, 1100, 950])], s, alert=False)
    path = tmp_path / "seed.json.gz"
    seed.export(src, path)
    mine = DB(":memory:")
    bot.process(mine, [olx.parse_offer(offer(100, "Ceas Seiko SKX007", 777))], s, alert=False)  # mine already
    mine.kv_set("rules_version", 99)
    assert seed.load_if_empty(mine, path) == 2
    assert mine.get("olx:100")["price_ron"] == 777  # what you have wins
    assert mine.kv_get("rules_version") == 0  # more prices: the bot re-judges at start
    assert mine.kv_get("seeded_at") is None  # your own listings still count as fresh
    assert seed.load_if_empty(mine, path) == 0
