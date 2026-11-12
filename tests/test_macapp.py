import plistlib
import subprocess

from flipperbot import macapp


def test_app_bundle(tmp_path, monkeypatch):
    monkeypatch.setattr(macapp.sys, "platform", "darwin")
    monkeypatch.setattr(macapp.os, "access", lambda p, m: False)  # /Applications not writable here
    monkeypatch.setattr(macapp.Path, "home", staticmethod(lambda: tmp_path))
    app = macapp.make("/Users/arnold/.local/bin/flipperbot")
    assert app == tmp_path / "Applications" / "Flipperbot.app"
    info = plistlib.loads((app / "Contents" / "Info.plist").read_bytes())
    assert info["CFBundleExecutable"] == "flipperbot-app" and info["CFBundleName"] == "Flipperbot"
    run = app / "Contents" / "MacOS" / "flipperbot-app"
    assert run.stat().st_mode & 0o111
    assert '"/Users/arnold/.local/bin/flipperbot" app' in run.read_text()
    assert subprocess.run(["sh", "-n", str(run)]).returncode == 0  # valid shell
    assert macapp.make("/x/flipperbot") == app  # remaking replaces it
