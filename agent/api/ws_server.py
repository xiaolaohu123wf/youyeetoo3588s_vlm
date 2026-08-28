"""Minimal WebSocket broadcast server (stdlib asyncio only)."""
from __future__ import annotations

from collections.abc import Awaitable, Callable
import asyncio
import base64
import contextlib
import hashlib
import logging
import struct

from api.event_bus import EventBus

LOG = logging.getLogger(__name__)
WS_GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"


def _ws_accept_key(key: str) -> str:
    digest = hashlib.sha1((key + WS_GUID).encode("ascii")).digest()
    return base64.b64encode(digest).decode("ascii")


def _encode_text_frame(text: str) -> bytes:
    data = text.encode("utf-8")
    n = len(data)
    if n < 126:
        return struct.pack("!BB", 0x81, n) + data
    if n < 65536:
        return struct.pack("!BBH", 0x81, 126, n) + data
    return struct.pack("!BBQ", 0x81, 127, n) + data


async def _send_text(writer: asyncio.StreamWriter, text: str) -> None:
    writer.write(_encode_text_frame(text))
    await writer.drain()


async def _read_frame(reader: asyncio.StreamReader) -> int | str | None:
    """Return text payload, empty str for pong handled, None on close."""
    head = await reader.readexactly(2)
    b1, b2 = head[0], head[1]
    masked = (b2 >> 7) & 1
    length = b2 & 0x7F
    if length == 126:
        length = struct.unpack("!H", await reader.readexactly(2))[0]
    elif length == 127:
        length = struct.unpack("!Q", await reader.readexactly(8))[0]
    mask = await reader.readexactly(4) if masked else None
    payload = await reader.readexactly(length)
    if mask:
        payload = bytes(b ^ mask[i % 4] for i, b in enumerate(payload))
    opcode = b1 & 0x0F
    if opcode == 0x8:
        return None
    if opcode == 0x9:
        writer.write(b"\x8A\x00")
        await writer.drain()
        return ""
    if opcode == 0x1:
        return payload.decode("utf-8", errors="replace")
    return ""


async def _handle_client(
    reader: asyncio.StreamReader,
    writer: asyncio.StreamWriter,
    bus: EventBus,
    on_message: Callable[[str], Awaitable[None]] | None = None,
) -> None:
    peer = writer.get_extra_info("peername")
    q: asyncio.Queue[str] | None = None
    try:
        req_line = await reader.readline()
        if not req_line or b"GET" not in req_line:
            return
        headers: dict[str, str] = {}
        while True:
            line = await reader.readline()
            if line in (b"\r\n", b"\n", b""):
                break
            if b":" in line:
                k, v = line.decode("latin1").split(":", 1)
                headers[k.strip().lower()] = v.strip()
        if headers.get("upgrade", "").lower() != "websocket":
            return
        key = headers.get("sec-websocket-key", "")
        if not key:
            return
        accept = _ws_accept_key(key)
        resp = (
            "HTTP/1.1 101 Switching Protocols\r\n"
            "Upgrade: websocket\r\n"
            "Connection: Upgrade\r\n"
            f"Sec-WebSocket-Accept: {accept}\r\n\r\n"
        )
        writer.write(resp.encode("ascii"))
        await writer.drain()

        q = await bus.subscribe()
        LOG.info("[api] ws client connected %s", peer)
        await _send_text(writer, '{"type":"hello","path":"/ws"}')

        async def pump_out() -> None:
            assert q is not None
            while True:
                msg = await q.get()
                await _send_text(writer, msg)

        async def pump_in() -> None:
            while True:
                msg = await _read_frame(reader)
                if msg is None:
                    return
                if msg and on_message:
                    try:
                        await on_message(msg)
                    except Exception as exc:
                        LOG.warning("[api] ws inbound handler failed: %s", exc)

        out_task = asyncio.create_task(pump_out())
        in_task = asyncio.create_task(pump_in())
        done, pending = await asyncio.wait(
            [out_task, in_task],
            return_when=asyncio.FIRST_COMPLETED,
        )
        for t in pending:
            t.cancel()
        for t in done:
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await t
    except (asyncio.IncompleteReadError, ConnectionResetError, BrokenPipeError):
        pass
    finally:
        if q is not None:
            await bus.unsubscribe(q)
        with contextlib.suppress(Exception):
            writer.close()
        LOG.info("[api] ws client disconnected %s", peer)


async def run_ws_server(
    bus: EventBus,
    host: str = "127.0.0.1",
    port: int = 8765,
    *,
    on_message=None,
) -> asyncio.Server:
    server = await asyncio.start_server(
        lambda r, w: _handle_client(r, w, bus, on_message),
        host,
        port,
    )
    LOG.info("[api] WebSocket ws://%s:%d/ws", host, port)
    return server
