import json
import threading
import urllib.error
import urllib.request

import pytest

from flipperbot import bot, web
from flipperbot.config import Settings
from flipperbot.db import DB
from flipperbot.sources import olx

from test_olx_and_bot import offer


@pytest.fixture
def server(tmp_path, monkeypatch):
    monkeypatch.setenv("FLIPPERBOT_HOME", str(tmp_path))
    s = Settings()
    monkeypatch.setattr(Settings, "db_path", property(lambda self: tmp_path / "f.db"))
    s.dashboard_port = 0
    db = DB(s.db_path)
    market = [olx.parse_offer(offer(100 + i, "Ceas Seiko SKX007", p)) for i, p in enumerate([1000, 1100, 950, 1050, 1000])]
    bot.process(db, [*market, olx.parse_offer(offer(200, 'Ceas Seiko SKX007 <img src=x onerror=alert(1)>', 400))], s, alert=False)
    srv = web.ThreadingHTTPServer(("127.0.0.1", 0), web.make_handler(s))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}"
    srv.shutdown()


def get(url):
    return json.loads(urllib.request.urlopen(url).read())


def post(url, headers=None):
    req = urllib.request.Request(url, data=b"", method="POST", headers=headers or {})
    return json.loads(urllib.request.urlopen(req).read())


def test_page_and_views(server):
    assert b"flipperbot" in urllib.request.urlopen(server + "/").read()
    deals = get(server + "/api/listings?view=deals")
    assert [d["key"] for d in deals] == ["olx:200"]
    assert deals[0]["tier"] == "real_good" and deals[0]["photo"].endswith(";s=400x400")
    stats = get(server + "/api/stats")
    assert stats["counts"]["real_good"] == 1 and stats["total"] == 6


def test_star_and_hide(server):
    post(server + "/api/star/olx:200", {"X-Flipperbot": "1"})
    assert [d["key"] for d in get(server + "/api/listings?view=starred")] == ["olx:200"]
    post(server + "/api/hide/olx:200", {"X-Flipperbot": "1"})
    assert get(server + "/api/listings?view=deals") == []
    assert [d["key"] for d in get(server + "/api/listings?view=hidden")] == ["olx:200"]


def test_actions_need_the_header_and_a_local_host(server):
    with pytest.raises(urllib.error.HTTPError) as e:
        post(server + "/api/star/olx:200")
    assert e.value.code == 403
    req = urllib.request.Request(server + "/api/stats", headers={"Host": "evil.example"})
    with pytest.raises(urllib.error.HTTPError) as e:
        urllib.request.urlopen(req)
    assert e.value.code == 403


def test_page_never_uses_innerhtml():
    assert "innerHTML" not in web.PAGE and "insertAdjacentHTML" not in web.PAGE


def test_busy_port_moves_on_and_open_finds_the_real_one(tmp_path, monkeypatch):
    from http.server import HTTPServer, SimpleHTTPRequestHandler

    from flipperbot import config

    monkeypatch.setattr(config, "HOME", tmp_path)
    monkeypatch.setattr(Settings, "db_path", property(lambda self: tmp_path / "f.db"))
    vault = HTTPServer(("127.0.0.1", 0), SimpleHTTPRequestHandler)  # some other app on "our" port
    threading.Thread(target=vault.serve_forever, daemon=True).start()
    s = Settings()
    s.dashboard_port = vault.server_address[1]
    assert not web.is_flipperbot(f"http://localhost:{s.dashboard_port}")
    srv = web.serve(s, background=True)
    try:
        assert srv.server_address[1] != s.dashboard_port
        assert web.url(s) == f"http://localhost:{srv.server_address[1]}"
        assert web.is_flipperbot(web.url(s))
    finally:
        srv.shutdown()
        vault.shutdown()


def test_send_to_claude_queues_and_runs_one_at_a_time(server, monkeypatch):
    import time

    order = []

    def fake_check(db, row, s):
        order.append(row["key"])
        time.sleep(0.2)
        result = {"verdict": "buy", "authenticity": "likely_genuine", "confidence": 80,
                  "resale_ron_low": 900, "resale_ron_high": 1100, "items": [{"brand": "Seiko", "model": "SKX007"}]}
        db.set_ai(row["key"], result)
        return result

    sent = []
    monkeypatch.setattr(web.ai, "check", fake_check)
    monkeypatch.setattr(web.ai, "available", lambda s: True)
    monkeypatch.setattr(web.notify, "send", lambda s, text, photo=None: sent.append(text))
    first = post(server + "/api/ai/olx:200", {"X-Flipperbot": "1"})
    second = post(server + "/api/ai/olx:100", {"X-Flipperbot": "1"})
    assert first["ai_running"] and second["ai_queued"] == 1
    for _ in range(50):
        if get(server + "/api/listing?key=olx:100")["ai"]:
            break
        time.sleep(0.1)
    assert order == ["olx:200", "olx:100"]
    card = get(server + "/api/listing?key=olx:200")
    assert card["ai"]["verdict"] == "buy" and not card["ai_running"]
    # olx:200 is a real good deal Claude confirmed: its verdict also went to Telegram, once
    assert len(sent) == 1 and "SKX007" in sent[0]
