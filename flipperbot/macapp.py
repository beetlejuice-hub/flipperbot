"""Flipperbot.app: one click to make sure the bot is running and open the dashboard.

A minimal app bundle (an Info.plist and a two-line script) made on the Mac by
`flipperbot setup` / `flipperbot make-app`, in /Applications if that's writable,
else ~/Applications. Made locally, so macOS doesn't quarantine it. Drag it to the
Dock to keep it there.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

ICON = Path(__file__).parent / "assets" / "icon.png"
NAME = "Flipperbot.app"

INFO_PLIST = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleName</key><string>Flipperbot</string>
  <key>CFBundleDisplayName</key><string>Flipperbot</string>
  <key>CFBundleIdentifier</key><string>ro.flipperbot.app</string>
  <key>CFBundleVersion</key><string>1</string>
  <key>CFBundlePackageType</key><string>APPL</string>
  <key>CFBundleExecutable</key><string>flipperbot-app</string>
  <key>CFBundleIconFile</key><string>AppIcon</string>
  <key>LSUIElement</key><true/>
</dict>
</plist>
"""


def script(exe: str) -> str:
    return f"""#!/bin/sh
# Start flipperbot in the background if it isn't running, then open the dashboard.
exec "{exe}" app >> "$HOME/.flipperbot/app.log" 2>&1
"""


def make(exe: str | None = None) -> Path:
    if sys.platform != "darwin":
        raise SystemExit("The one-click app is for macOS.")
    exe = exe or shutil.which("flipperbot") or str(Path.home() / ".local" / "bin" / "flipperbot")
    folder = Path("/Applications") if os.access("/Applications", os.W_OK) else Path.home() / "Applications"
    app = folder / NAME
    if app.exists():
        shutil.rmtree(app)
    (app / "Contents" / "MacOS").mkdir(parents=True)
    (app / "Contents" / "Resources").mkdir()
    (app / "Contents" / "Info.plist").write_text(INFO_PLIST)
    run = app / "Contents" / "MacOS" / "flipperbot-app"
    run.write_text(script(exe))
    run.chmod(0o755)
    try:  # sips is built into macOS; without it the app just has the generic icon
        if ICON.exists():
            subprocess.run(["sips", "-s", "format", "icns", str(ICON), "--out", str(app / "Contents" / "Resources" / "AppIcon.icns")],
                           capture_output=True, timeout=60)
        os.utime(app)  # so Finder picks up the icon
    except (OSError, subprocess.SubprocessError):
        pass
    return app
