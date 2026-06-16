#!/usr/bin/env bash
# Install this extension into Plover's bundled plugin environment.
#
# Unlike a tool that's already installed, a brand-new extension must be a real
# install so Plover discovers its `plover.extension` entry point - a plain file
# copy is not enough. We pip-install the (pure-python) package into Plover's
# plugin site-packages with --no-deps (Plover itself is already there).
#
# After installing, enable it once in Plover: Configure -> Plugins -> tick
# "chordle_bridge". It auto-starts thereafter.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLUGINS_SP="$HOME/Library/Application Support/plover/plugins/mac/lib/python/site-packages"

if [ ! -d "$PLUGINS_SP" ]; then
  echo "error: Plover plugin dir not found: $PLUGINS_SP" >&2
  echo "       install any plugin once via Plover's Plugins Manager to create it." >&2
  exit 1
fi

PY=""
for c in /opt/anaconda3/bin/python3 python3 python3.13 python3.12; do
  if command -v "$c" >/dev/null 2>&1 && "$c" -m pip --version >/dev/null 2>&1; then
    PY="$c"; break
  fi
done
if [ -z "$PY" ]; then
  echo "error: no python3 with pip found to build the package" >&2
  exit 1
fi

echo "installing plover-chordle-bridge into $PLUGINS_SP (via $PY)"
"$PY" -m pip install --no-deps --upgrade --target "$PLUGINS_SP" "$HERE"

echo
echo "Done. Now in Plover:"
echo "  Configure -> Plugins -> tick 'chordle_bridge' (it auto-starts)."
echo "  Verify it is listening:  lsof -iTCP:8087 -sTCP:LISTEN"
