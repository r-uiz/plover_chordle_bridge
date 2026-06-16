// Chordle-side client for the plover_chordle_bridge extension.
//
// Drop into apps/chordle/lib/steno/ as a second input source alongside hid.ts.
// It connects to the localhost WebSocket the Plover extension serves and emits
// the pressed steno-key ids ("S-", "-F", "*", ...) - the same shape hid.ts
// produces, so Find-the-key's answer check is unchanged.
//
// The bridge is an enhancement, never a requirement: it auto-reconnects and the
// caller should keep working (e.g. fall back to WebHID) when it never connects.

export type BridgeStatus = "connecting" | "open" | "closed";

export interface BridgeOptions {
  port?: number; // default 8087 (matches the extension's DEFAULT_PORT)
  onStatus?: (status: BridgeStatus) => void;
  retryMs?: number; // reconnect backoff; default 1500
}

/**
 * Connect to the Plover bridge. `onStroke` fires once per committed chord with
 * the pressed steno-key ids. Returns a disposer that stops reconnecting and
 * closes the socket.
 */
export function connectPloverBridge(
  onStroke: (keys: string[]) => void,
  opts: BridgeOptions = {},
): () => void {
  const port = opts.port ?? 8087;
  const retryMs = opts.retryMs ?? 1500;
  let stopped = false;
  let ws: WebSocket | null = null;
  let retry: ReturnType<typeof setTimeout> | undefined;

  const open = () => {
    if (stopped) return;
    opts.onStatus?.("connecting");
    // Loopback is a potentially-trustworthy origin, so ws:// is allowed even
    // from an https page (verify per-browser; Chromium is reliable).
    ws = new WebSocket(`ws://127.0.0.1:${port}`);

    ws.onopen = () => opts.onStatus?.("open");

    ws.onmessage = (e) => {
      try {
        const msg = JSON.parse(e.data);
        if (msg && msg.type === "stroke" && Array.isArray(msg.keys)) {
          onStroke(msg.keys as string[]);
        }
      } catch {
        // ignore malformed frames
      }
    };

    ws.onerror = () => ws?.close();

    ws.onclose = () => {
      opts.onStatus?.("closed");
      if (!stopped) retry = setTimeout(open, retryMs);
    };
  };

  open();

  return () => {
    stopped = true;
    if (retry) clearTimeout(retry);
    ws?.close();
  };
}
