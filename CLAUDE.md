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

- **Historical stats for all drills (Chordle-side).** Today Chordle keeps only a single best per
  scope (`apps/chordle/lib/score.ts`, `getBest`/`setBest`); this logs *every* run so you can see
  progress over time, not just your record. Sketch:
  - **Storage:** `localStorage`, web-first / per-device (matches Chordle's no-backend stance). An
    append-only, capped list of runs keyed by the existing **scope** string
    (`find-the-key:<mode>:<prefill>`, and steno-order's own scope). Version the schema (`v1`); cap
    to ~200 runs per scope so it never bloats. Export/sync later is additive, no rewrite.
  - **Run record:** `{ ts, drill, mode, layout, scope, timeMs, perfect, good, miss, maxCombo,
    accuracy }` - a timestamped snapshot of what `useScore` already produces at finish, written
    once on completion alongside the existing best-score update.
  - **Per-key weak spots (the real payoff):** also accumulate a per-key tally `{ correct, wrong,
    avgMs }` across runs. That's what tells you *which keys you fumble*, and it feeds directly into
    the v2 Leitner / spaced-repetition idea already on Chordle's roadmap.
  - **Views:** a small history surface - list of past runs, a best-over-time sparkline, and a
    per-key accuracy heatmap rendered on the shared board component (colour cells by accuracy).
  - **Home for the code:** extend `apps/chordle/lib/stats.ts` (it already holds the unused
    `getStreak`/`bumpStreak` helpers) with `saveRun` / `getHistory` / `aggregate`; add a history
    view component. Keep the per-run write in the drills' finish path.
  - **Bridge tie-in (later, keep separate):** with the bridge feeding real strokes, the same
    per-key store could log *real Plover writing*, not just drill runs - an ambient practice log
    that surfaces weak chords from actual use. That's the distinct "weak-spot trainer" idea; do
    NOT fold it into drill-history v1.

## Current state

v0.1.0, repo created + pushed. Transport verified in isolation (RFC 6455 accept KAT, frame
round-trip, broadcast, origin rejection). Installed + enabled in Plover (listening on 8087), and
the Chordle client is wired in (Witsilog commit `8be3b5d` - Find-the-key Type mode auto-connects).

**Known limitation + decision (https).** `ws://127.0.0.1` works from `http://localhost` (dev) in
every browser, but from the live **https** site it's blocked as mixed content in
Firefox/Zen/Safari; only Chromium exempts loopback (verified: Zen on witsilog.com can't connect,
the footer now says so honestly).

**Recommended path: practice on localhost (any browser), and use Chrome on the live site.** Costs
nothing, exposes nothing. The cross-browser-on-https fix (`wss://` via a loopback-resolving name +
trusted cert, e.g. `bridge.witsilog.com` -> 127.0.0.1 + Let's Encrypt) is **deliberately NOT
pursued**: a public CA cert means shipping a TLS private key in this public repo, which violates
Let's Encrypt's terms and is revocation-prone. The actual security risk is low (the cert only
guards a loopback connection), but it's fragile and not worth it for a personal trainer. If *you
personally* want Zen-on-live, trust a self-signed `mkcert` cert whose key never leaves your
machine - safe, but not distributable.

The bridge is loopback-only regardless of transport, so it never exposes your machine. The thing
that stops other websites from reading your strokes is the **origin allowlist** in the handshake
(`ALLOWED_ORIGINS`) - keep it tight; that's the real safety control, not the cert.
