import io
import urllib.error

import pytest

from flipperbot import cli, config, notify
from flipperbot.config import Settings

GOOD = "7123456789:AAHdqTcvCH1vGWJxfSeofSAs0K5PALDsaw"
BOTFATHER = f"""Done! Congratulations on your new bot. You will find it at t.me/arnold_flipper_bot.
Use this token to access the HTTP API:
{GOOD}
Keep your token secure and store it safely."""


def test_find_token_in_whole_botfather_message():
    assert notify.find_token(BOTFATHER) == GOOD
    assert notify.find_token(f"  {GOOD}\n") == GOOD
    assert notify.find_token("Use this token to access the HTTP API:") is None


def fake_telegram(valid_token):
    def call(s, method, **kw):
        if s.telegram_token != valid_token:
            raise urllib.error.HTTPError("u", 401, "Unauthorized", {}, io.BytesIO(b""))
        if method == "getMe":
            return {"result": {"username": "arnold_flipper_bot"}}
        if method == "getUpdates":
            return {"result": [{"message": {"chat": {"id": 42}}}]}
        return {"result": {}}
    return call


def test_setup_retries_until_the_token_works(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(config, "HOME", tmp_path)
    monkeypatch.setattr(notify, "_call", fake_telegram(GOOD))
    monkeypatch.setattr("sys.platform", "linux")  # skip the autostart question
    answers = iter(["Use this token to access the HTTP API:", "7123456789:AAHdqTcvCH1vGWJxfSeofSAs0K5PALDsXX", BOTFATHER])
    monkeypatch.setattr("builtins.input", lambda *_: next(answers))
    cli._setup(Settings())
    out = capsys.readouterr().out
    assert "doesn't look like a token" in out
    assert "token is wrong" in out
    assert "your bot is @arnold_flipper_bot" in out
    s = config.load(tmp_path / "config.toml")
    assert (s.telegram_token, s.telegram_chat_id) == (GOOD, "42")


def test_setup_says_when_it_is_the_connection(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(config, "HOME", tmp_path)

    def offline(s, method, **kw):
        raise urllib.error.URLError("nodename nor servname provided")

    monkeypatch.setattr(notify, "_call", offline)
    monkeypatch.setattr("builtins.input", lambda *_: GOOD)
    with pytest.raises(SystemExit):
        cli._setup(Settings())
    out = capsys.readouterr().out
    assert "Couldn't reach Telegram" in out and "connection problem, not your token" in out
