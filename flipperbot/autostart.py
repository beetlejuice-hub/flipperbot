"""Run flipperbot in the background on a Mac, from login on (a launchd agent),
so there's no Terminal window to keep open. `caffeinate -i` stops idle sleep
while it runs; closing the lid still pauses it."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

from .config import HOME

LABEL = "ro.flipperbot"
PLIST = Path.home() / "Library" / "LaunchAgents" / f"{LABEL}.plist"
LOG = HOME / "bot.log"


def plist(exe: str) -> str:
    path = ":".join([str(Path.home() / ".local" / "bin"), "/opt/homebrew/bin", "/usr/local/bin", "/usr/bin", "/bin", "/usr/sbin", "/sbin"])
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>{LABEL}</string>
  <key>ProgramArguments</key>
  <array><string>/usr/bin/caffeinate</string><string>-i</string><string>{exe}</string><string>run</string></array>
  <key>EnvironmentVariables</key>
  <dict><key>PATH</key><string>{path}</string><key>PYTHONUNBUFFERED</key><string>1</string></dict>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><true/>
  <key>ThrottleInterval</key><integer>60</integer>
  <key>StandardOutPath</key><string>{LOG}</string>
  <key>StandardErrorPath</key><string>{LOG}</string>
</dict>
</plist>
"""


def enable() -> None:
    if sys.platform != "darwin":
        sys.exit("Autostart is for macOS. Elsewhere, run: flipperbot run")
    exe = shutil.which("flipperbot") or str(Path.home() / ".local" / "bin" / "flipperbot")
    HOME.mkdir(parents=True, exist_ok=True)
    PLIST.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["launchctl", "unload", str(PLIST)], capture_output=True)
    PLIST.write_text(plist(exe))
    subprocess.run(["launchctl", "load", str(PLIST)], check=True)
    print(f"flipperbot is running in the background and starts again whenever you log in.\nIts log: {LOG}")


def disable() -> None:
    if PLIST.exists():
        subprocess.run(["launchctl", "unload", str(PLIST)], capture_output=True)
        PLIST.unlink()
    print("Stopped. flipperbot won't start by itself any more.")


def running() -> bool:
    if sys.platform != "darwin":
        return False
    return subprocess.run(["launchctl", "list", LABEL], capture_output=True).returncode == 0
