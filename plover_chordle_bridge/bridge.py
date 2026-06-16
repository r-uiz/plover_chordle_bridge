"""Broadcast Plover strokes to the Chordle web trainer over a localhost WebSocket.

A Plover *extension* plugin (background, no GUI). On each committed stroke it
sends a small JSON frame to any connected browser:

    {"type": "stroke", "keys": ["S-", "K-", "-T"], "steno": "SKAT"}

`keys` is `stroke.steno_keys` verbatim - the same side-marked ids Chordle's
board already uses ("S-", "-F", "*", "#", "A-", "-E"), so no translation is
needed on either side.

Transport is a dependency-free WebSocket server bound to 127.0.0.1. A browser on
an https page may connect because loopback counts as a potentially-trustworthy
origin. The handshake only accepts the Chordle origins (ALLOWED_ORIGINS).
"""

import os
import json
import socket
import struct
import base64
import hashlib
import threading
from typing import TYPE_CHECKING, List

if TYPE_CHECKING:
    from plover.engine import StenoEngine

try:  # Plover's logger when running inside Plover; stdlib logging in tests.
    from plover import log
except Exception:  # pragma: no cover
    import logging as log


HOST = "127.0.0.1"
DEFAULT_PORT = 8087
PORT = int(os.environ.get("CHORDLE_BRIDGE_PORT", DEFAULT_PORT))

WS_GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"

# Origins allowed through the WebSocket handshake. Chordle dev (Astro :4321) +
# the live site. Add your own dev origin via CHORDLE_BRIDGE_ORIGINS (comma list).
ALLOWED_ORIGINS = {
    "https://witsilog.com",
    "http://localhost:4321",
    "http://localhost:3000",
    "http://127.0.0.1:4321",
}
ALLOWED_ORIGINS.update(
    o.strip() for o in os.environ.get("CHORDLE_BRIDGE_ORIGINS", "").split(",") if o.strip()
)


def ws_accept(key: str) -> str:
    """Sec-WebSocket-Accept value for a client's Sec-WebSocket-Key."""
    digest = hashlib.sha1((key + WS_GUID).encode("ascii")).digest()
    return base64.b64encode(digest).decode("ascii")


def ws_frame(text: str) -> bytes:
    """A single unmasked server->client text frame (FIN set)."""
    payload = text.encode("utf-8")
    header = bytearray([0x81])  # FIN + opcode 0x1 (text)
    n = len(payload)
    if n < 126:
        header.append(n)
    elif n < 65536:
        header.append(126)
        header += struct.pack(">H", n)
    else:
        header.append(127)
        header += struct.pack(">Q", n)
    return bytes(header) + payload


class StrokeBridgeServer:
    """The transport, with no Plover dependency so it can be tested in isolation."""

    def __init__(self, host: str = HOST, port: int = PORT) -> None:
        self.host, self.port = host, port
        self._server: socket.socket = None
        self._clients: List[socket.socket] = []
        self._lock = threading.Lock()
        self._accept_thread: threading.Thread = None

    def start(self) -> bool:
        try:
            self._server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self._server.bind((self.host, self.port))
            self._server.listen(8)
        except OSError as e:
            log.error("chordle_bridge: could not bind %s:%s (%s)", self.host, self.port, e)
            self._server = None
            return False

        self._accept_thread = threading.Thread(target=self._accept_loop, daemon=True)
        self._accept_thread.start()
        log.info("chordle_bridge: listening on ws://%s:%s", self.host, self.port)
        return True

    def stop(self) -> None:
        srv, self._server = self._server, None
        if srv is not None:
            try:
                srv.close()
            except OSError:
                pass
        with self._lock:
            for c in self._clients:
                try:
                    c.close()
                except OSError:
                    pass
            self._clients.clear()

    def _accept_loop(self) -> None:
        while self._server is not None:
            try:
                conn, _ = self._server.accept()
            except OSError:
                return  # server closed
            threading.Thread(target=self._handshake, args=(conn,), daemon=True).start()

    def _handshake(self, conn: socket.socket) -> None:
        try:
            data = b""
            while b"\r\n\r\n" not in data:
                chunk = conn.recv(2048)
                if not chunk:
                    conn.close()
                    return
                data += chunk
                if len(data) > 16384:  # don't read unbounded junk
                    conn.close()
                    return

            headers = {}
            for line in data.decode("latin1").split("\r\n")[1:]:
                if ":" in line:
                    k, v = line.split(":", 1)
                    headers[k.strip().lower()] = v.strip()

            origin = headers.get("origin")
            if origin is not None and origin not in ALLOWED_ORIGINS:
                log.info("chordle_bridge: rejected origin %s", origin)
                conn.close()
                return

            key = headers.get("sec-websocket-key")
            if not key:
                conn.close()
                return

            conn.sendall((
                "HTTP/1.1 101 Switching Protocols\r\n"
                "Upgrade: websocket\r\n"
                "Connection: Upgrade\r\n"
                "Sec-WebSocket-Accept: %s\r\n\r\n" % ws_accept(key)
            ).encode("ascii"))
        except OSError:
            try:
                conn.close()
            except OSError:
                pass
            return

        with self._lock:
            self._clients.append(conn)

    def broadcast(self, payload: dict) -> None:
        frame = ws_frame(json.dumps(payload))
        with self._lock:
            for conn in list(self._clients):
                try:
                    conn.sendall(frame)
                except OSError:
                    self._clients.remove(conn)
                    try:
                        conn.close()
                    except OSError:
                        pass

    def client_count(self) -> int:
        with self._lock:
            return len(self._clients)


class ChordleBridge:
    """Plover extension entry point. Wires the engine's `stroked` hook to the server."""

    def __init__(self, engine: "StenoEngine") -> None:
        self._engine = engine
        self._server = StrokeBridgeServer(HOST, PORT)

    def start(self) -> None:
        if self._server.start():
            self._engine.hook_connect("stroked", self._on_stroked)

    def stop(self) -> None:
        try:
            self._engine.hook_disconnect("stroked", self._on_stroked)
        except Exception:
            pass
        self._server.stop()

    def _on_stroked(self, stroke) -> None:
        self._server.broadcast({
            "type": "stroke",
            "keys": list(stroke.steno_keys),
            "steno": stroke.rtfcre,
        })
