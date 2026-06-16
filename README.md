# plover_chordle_bridge

A tiny [Plover](https://www.openstenoproject.org/) **extension** that broadcasts
your strokes to the [Chordle](https://witsilog.com/code/chordle) web steno
trainer over a localhost WebSocket. It lets Chordle's "Type" drill read real
strokes from **any** Plover machine, in **any** browser - without WebHID.

```
Plover (any machine) ──stroked hook──▶ chordle_bridge extension
                                          └─ ws://127.0.0.1:8087 ──▶ Chordle (browser)
```

## Why

Chordle reads real strokes in the browser via WebHID, which is **Chromium-only**
and needs a physical Plover-HID machine plus a user gesture. This extension
sidesteps all of that: Plover already decodes strokes from every machine it
supports, so the bridge just forwards them. Chordle connects when it's running
and falls back to WebHID (or click input) when it isn't.

The frame is plain JSON - no encryption wall like the abandoned
`plover_websocket_server` route, because we own both ends.

## Protocol

One text frame per committed stroke:

```json
{ "type": "stroke", "keys": ["S-", "K-", "-T"], "steno": "SKAT" }
```

- `keys` is `stroke.steno_keys` verbatim - the same side-marked ids Chordle's
  board uses (`"S-"`, `"-F"`, `"*"`, `"#"`, `"A-"`, `"-E"`), so **no translation**
  is needed on either side.
- `steno` is the RTF/CRE outline, handy for debugging.

## Install (dev)

```bash
./dev-install.sh                 # pip-installs into Plover's plugin env
```

Then in Plover: **Configure -> Plugins -> tick `chordle_bridge`**. It auto-starts
and listens on `ws://127.0.0.1:8087`. Verify:

```bash
lsof -iTCP:8087 -sTCP:LISTEN
```

A brand-new extension must be a real install (not a file copy) so Plover finds
its `plover.extension` entry point - that's what `dev-install.sh` does.

## Use from Chordle

Copy `client/plover-bridge.ts` into `apps/chordle/lib/steno/` and wire it as a
second input source for Find-the-key's Type mode (same `string[]` of pressed
keys as `hid.ts`):

```ts
import { connectPloverBridge } from "./plover-bridge";

const stop = connectPloverBridge(
  (keys) => checkAnswer(keys),          // identical to the WebHID path
  { onStatus: (s) => setBridgeStatus(s) }
);
// later: stop();
```

Suggested policy: **Auto** - if the bridge connects, use it; otherwise fall back
to WebHID. The answer check (is the prompted key in `keys`?) is unchanged.

## Config

- **Port:** `CHORDLE_BRIDGE_PORT` env var (default `8087`).
- **Allowed origins:** the handshake only accepts Chordle origins
  (`https://witsilog.com`, `http://localhost:4321`, ...). Add more with
  `CHORDLE_BRIDGE_ORIGINS` (comma-separated).

## Notes / caveats

- Bound to `127.0.0.1` only. The origin allowlist is the guard against other
  local pages connecting; keep it tight.
- `ws://127.0.0.1` works from an https page because loopback is a
  potentially-trustworthy origin. Chromium is reliable here; **verify Firefox /
  Safari** before promising cross-browser.
- One-way (Plover -> browser). Incoming client frames are ignored; disconnects
  are detected on the next broadcast.
- Pure stdlib - no `websockets`/`aiohttp` dependency.

## Test

The WebSocket transport is testable without Plover (handshake KAT, frame
round-trip, origin rejection):

```bash
python3 - <<'PY'
import sys; sys.path.insert(0, ".")
from plover_chordle_bridge.bridge import ws_accept
assert ws_accept("dGhlIHNhbXBsZSBub25jZQ==") == "s3pPLMBiTxaQ9kYGzzhZRbK+xOo="
print("ok")
PY
```
