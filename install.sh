#!/bin/sh
# flipperbot installer for macOS. Paste into Terminal:
#   curl -LsSf https://raw.githubusercontent.com/beetlejuice-hub/flipperbot/claude/practical-cannon-luzypm/install.sh | sh
# It installs uv (from its maker, astral.sh) if missing, installs flipperbot with it,
# then starts the guided setup. Nothing needs an admin password.
set -e
BRANCH="claude/practical-cannon-luzypm"
UV="$(command -v uv || true)"
if [ -z "$UV" ]; then
  echo "Installing uv (the tool that runs flipperbot)..."
  curl -LsSf https://astral.sh/uv/install.sh | sh
  UV="$HOME/.local/bin/uv"
fi
echo "Installing flipperbot..."
"$UV" tool install --force --python 3.13 "flipperbot[facebook] @ https://github.com/beetlejuice-hub/flipperbot/archive/refs/heads/$BRANCH.zip"
"$UV" tool update-shell >/dev/null 2>&1 || true
echo
"$HOME/.local/bin/flipperbot" setup </dev/tty
