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
