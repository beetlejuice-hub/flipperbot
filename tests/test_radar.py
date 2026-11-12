import json
import subprocess
from datetime import date, timedelta

from flipperbot import bot, radar
from flipperbot.config import Settings
from flipperbot.db import DB
from flipperbot.models import Listing

from test_olx_and_bot import offer
from flipperbot.sources import olx

S = Settings()


def entry(eid):
    return next(e for e in radar.watchlist(DB(":memory:")) if e["id"] == eid)


def test_watchlist_matches_the_item_not_its_games_and_accessories():
    ps5 = entry("ps5-pro")
    assert radar.matches(ps5, "Consolă PS5 Pro 2TB, garanție")
    assert radar.matches(ps5, "PlayStation 5 Pro + 2 manete")
    assert not radar.matches(ps5, "Joc GTA 6 pentru PS5 Pro")
    assert not radar.matches(ps5, "Cumpăr PS5 Pro")
    assert not radar.matches(entry("ps5"), "PS5 Pro 2TB")  # the Pro has its own entry
    lego = entry("lego-75192")
    assert radar.matches(lego, "LEGO Star Wars Millennium Falcon UCS 75192 sigilat")
    assert not radar.matches(lego, "LEGO Star Wars X-Wing")
    assert radar.matches(entry("ccd-sony"), "Aparat foto Sony Cyber-shot DSC-W55")


def fake_search(listings):
    def search(query, **kw):
        return [l for l in listings if query.split()[0] in l.title.lower()]
    return search


def lst(i, title, price):
    return Listing(source="olx", source_id=str(i), url=f"https://olx.ro/{i}", title=title, price_ron=price)


def test_a_hot_item_well_under_the_usual_price_is_flagged(monkeypatch):
    monkeypatch.setattr(radar.time, "sleep", lambda x: None)
    s = Settings()
    s.radar_per_poll = 20
    db = DB(":memory:")
    ps5 = [lst(i, "PS5 Pro 2TB ca nou", p) for i, p in enumerate([3800, 4000, 4100, 3900, 4200, 4050])]
    ps5.append(lst(99, "PS5 Pro, vând urgent", 2600))
    ps5.append(lst(98, "Joc GTA 6 PS5 Pro", 300))  # a game: not the console
    radar.poll(db, s, search=fake_search(ps5), log=lambda m: None)
    r = radar.report(db)
    item = next(e for e in r["watchlist"] if e["id"] == "ps5-pro")
    assert item["n"] == 7 and item["median"] == 4000
    assert [c["key"] for c in r["cheap"]] == ["olx:99"]
    assert r["cheap"][0]["under_pct"] == 35 and "median of 7" in r["cheap"][0]["ref_from"]


def test_rising_models_and_wanted_ads_from_our_own_data():
    db = DB(":memory:")
    old = [olx.parse_offer(offer(100 + i, "Ceas Seiko SKX007", p)) for i, p in enumerate([800, 820, 780, 800, 810])]
    bot.process(db, old, S, alert=False)
    db.conn.execute("UPDATE listings SET first_seen = ?", (radar._ago(40),))
    new = [olx.parse_offer(offer(200 + i, "Ceas Seiko SKX007", p)) for i, p in enumerate([1000, 1050, 980, 1020])]
    wanted = [olx.parse_offer(offer(300 + i, "Cumpăr ceas Seiko SKX007", 500)) for i in range(2)]
    bot.process(db, new + wanted, S, alert=False)
    m = radar.movers(db)
    assert m["rising"][0]["model"] == "seiko SKX007" and m["rising"][0]["change_pct"] >= 25
    assert m["wanted"] == [{"model": "seiko SKX007", "wanted_ads": 2}]


RSS = b"""<?xml version="1.0" encoding="UTF-8"?><rss xmlns:ht="https://trends.google.com/trending/rss" version="2.0">
<channel><item><title>gta 6</title><ht:approx_traffic>50000+</ht:approx_traffic></item>
<item><title>meteo</title><ht:approx_traffic>10000+</ht:approx_traffic></item></channel></rss>"""


def test_google_trends_and_wikipedia_attention():
    assert radar.google_trends(lambda url: RSS) == [{"title": "gta 6", "traffic": "50000+"}, {"title": "meteo", "traffic": "10000+"}]
    views = [{"views": 1000}] * 31 + [{"views": 3000}] * 7
    got = radar.wiki_attention("Grand_Theft_Auto_VI", lambda url: json.dumps({"items": views}).encode())
    assert got["ratio"] == 3.0 and got["per_day"] == 3000
    db = DB(":memory:")

    def get(url):
        return RSS if "trends.google" in url else json.dumps({"items": views}).encode()

    radar.outside_signals(db, radar.watchlist(db), get=get, log=lambda m: None)
    r = radar.report(db)
    assert r["google_trends"][0]["title"] == "gta 6"
    assert next(e for e in r["watchlist"] if e["id"] == "ps5-pro")["wiki"]["ratio"] == 3.0
    radar.outside_signals(db, [], get=lambda url: 1 / 0, log=lambda m: None)  # once a day: no second fetch


def test_claude_adds_trending_items_and_bad_ones_are_dropped(monkeypatch):
    monkeypatch.setattr(radar.ai, "available", lambda s: True)
    monkeypatch.setattr(radar.ai, "log_call", lambda *a: None)
    until = (date.today() + timedelta(days=60)).isoformat()
    answer = [
        {"id": "Steam-Deck OLED", "name": "Steam Deck OLED", "query": "steam deck oled", "must": ["steam deck"],
         "not": ["husa"], "min_price": 1500, "value_low": 2600, "value_high": 3000, "why": "x", "until": until},
        {"id": "", "query": "nothing"},  # no id: dropped
        {"id": "old", "query": "x", "must": ["x"], "until": "2020-01-01"},  # already over: not shown
        "not even an object",
    ]
    seen = []

    def run(args, **kw):
        seen.append(args)
        return subprocess.CompletedProcess(args, 0, json.dumps({"result": json.dumps(answer)}), "")

    db = DB(":memory:")
    assert radar.refresh_due(db, S)
    assert radar.refresh_with_claude(db, S, run=run, log=lambda m: None) == 1
    args = seen[0]
    assert "WebSearch" in args and args[args.index("--disallowedTools") + 1:].count("Bash") == 1
    assert "Read" in args[args.index("--disallowedTools"):]  # no file access at all for this one
    ids = {e["id"] for e in radar.watchlist(db)}
    assert "steam-deckoled" in ids and "old" not in ids
    assert not radar.refresh_due(db, S)  # once a week
