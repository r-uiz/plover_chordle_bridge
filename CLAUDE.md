# CLAUDE.md

A tiny **Plover extension plugin** that broadcasts steno strokes to the
[Chordle](https://witsilog.com/code/chordle) web trainer over a localhost
WebSocket. It lets Chordle's "Type" drill read real strokes from **any** Plover
machine in **any** browser, without WebHID (which is Chromium-only and needs a
physical HID machine + user gesture).

- **Repo:** `origin` = `git@github.com:r-uiz/plover_chordle_bridge` (public). Push to `main`.
- **Born from:** a "should Chordle be a Plover plugin?" discussion (2026-06-16). Decision: **keep
  Chordle web-first**; the one thing the web can't do well is read strokes universally, so this
  bridge is the input-only companion - not a port. Chordle stays untouched.
- **Siblings:** Chordle web app (Witsilog repo, `~/Desktop/Projects/Witsilog/apps/chordle`, served
  at `witsilog.com/code/chordle`) and the SVG layout-display fork
  (`~/Desktop/Projects/plover_svg_layout_display`).

## Architecture

```
Plover (any machine) ──stroked hook──▶ chordle_bridge extension
                                          └─ ws://127.0.0.1:8087 ──▶ Chordle (browser)
```

- **Extension, not a tool.** No GUI. Registered via the `plover.extension` entry point
  (`setup.cfg`): `chordle_bridge = plover_chordle_bridge.bridge:ChordleBridge`. Enabled by the
  user in Plover's Configure -> Plugins tab; `start()`/`stop()` manage the server and the hook.
- **`ChordleBridge`** wires the engine's `stroked` hook to **`StrokeBridgeServer`** (a stdlib
  WebSocket server: handshake + frame encoding, origin allowlist, bound to `127.0.0.1`).
  `StrokeBridgeServer` has **no Plover import**, so the transport is unit-testable on its own.
- **Protocol** (one text frame per committed stroke):
  `{"type":"stroke","keys":[...stroke.steno_keys],"steno":<rtfcre>}`. `keys` are the same
  side-marked ids Chordle's board uses (`"S-"`, `"-F"`, `"*"`, `"#"`, `"A-"`, `"-E"`) - **no
  translation** on either side. One-way (Plover -> browser); incoming client frames are ignored.
- **`client/plover-bridge.ts`** is the Chordle-side input source (same `string[]`-of-pressed-keys
  shape as `apps/chordle/lib/steno/hid.ts`). It ships here as a reference; copy it into Chordle and
  wire as an Auto source (bridge first, WebHID fallback) when ready.

## Dev workflow

No standalone run; it runs inside Plover. Edit -> install -> restart/re-enable in Plover.

```bash
./dev-install.sh   # pip-installs (--no-deps --target) into Plover's plugin site-packages
```

A brand-new extension must be a **real install**, not a file copy: Plover discovers it via the
`plover.extension` entry point (importlib.metadata over the plugin dir), which only exists if a
proper dist-info is written. After installing: **Plover -> Configure -> Plugins -> tick
`chordle_bridge`** (auto-starts thereafter). Confirm it is up: `lsof -iTCP:8087 -sTCP:LISTEN`.

**Test (no Plover needed)** - the transport is verifiable standalone:
```bash
python3 - <<'PY'
import sys; sys.path.insert(0, ".")
from plover_chordle_bridge.bridge import ws_accept
assert ws_accept("dGhlIHNhbXBsZSBub25jZQ==") == "s3pPLMBiTxaQ9kYGzzhZRbK+xOo="   # RFC 6455 KAT
print("ok")
PY
```
`bridge.py` imports without Plover (a `TYPE_CHECKING` guard on the `StenoEngine` hint + a
`logging` fallback for `plover.log`), so you can drive a full loopback test: start the server, do
the WS handshake from a raw socket, `broadcast(...)`, decode the frame. See the commit's test for
the pattern.

Useful paths:
- Plover plugin install dir: `~/Library/Application Support/plover/plugins/mac/lib/python/site-packages/`
- Plover log: `~/Library/Application Support/plover/plover.log`
- Plover's bundled python: `/Applications/Plover.app/Contents/Frameworks/Python.framework/Versions/3.13/bin/python3.13`

## Config

- **Port:** `CHORDLE_BRIDGE_PORT` (default `8087`). Picked to dodge `plover_websocket_server`.
- **Origins:** handshake allowlist in `bridge.py` (`ALLOWED_ORIGINS`); extend via
  `CHORDLE_BRIDGE_ORIGINS` (comma list).

## Caveats

- Bound to `127.0.0.1`; the origin allowlist is the guard against other local pages connecting.
- `ws://127.0.0.1` works from an https page because loopback is a potentially-trustworthy origin.
  Chromium is reliable; **verify Firefox/Safari** before claiming cross-browser (the whole point is
  to escape Chromium-only WebHID, so this matters).
- The bridge is an enhancement, never a requirement: Chordle must keep working when it's not
  running (auto-reconnect + WebHID/click fallback).

## Conventions (Ruiz's)

- **No em dashes** in prose/UI - regular hyphen `-`.
- **No comments unless explaining a non-obvious WHY.**
- Pure stdlib; don't add `websockets`/`aiohttp` deps.
- End commits with the `Co-Authored-By: Claude ...` trailer; push to `origin`.

## TODO / Ideas

- **Historical stats for all drills.** Save every drill run over time (trends, per-key weak
  spots, history), not just a single best score. Chordle-side feature, but noted here because the
  bridge's real per-stroke data is what makes richer history possible.

## Current state

v0.1.0, repo created + pushed. Transport verified in isolation (RFC 6455 accept KAT, frame
round-trip, broadcast, origin rejection). Installed + enabled in Plover (listening on 8087), and
the Chordle client is wired in (Witsilog commit `8be3b5d` - Find-the-key Type mode auto-connects).

**Known limitation:** `ws://127.0.0.1` works from `http://localhost` (dev) in every browser, but
from the live **https** site it's blocked as mixed content in Firefox/Zen/Safari; only Chromium
exempts loopback. Cross-browser on https needs `wss://` via a loopback-resolving name with a
trusted cert (e.g. `bridge.witsilog.com` -> 127.0.0.1 + Let's Encrypt) - not yet built.
