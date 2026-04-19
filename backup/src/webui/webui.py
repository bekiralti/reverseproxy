from reverseproxy.reverseproxy import run_reverseproxy

import asyncio
import json
import logging
from pathlib import Path

from aiohttp import web
import aiohttp

logger = logging.getLogger("webui")

# ─── Websocket Clients ────────────────────────────────────────────────────────

websocket_clients: set[web.WebSocketResponse] = set()

async def broadcast(event: str, **kwargs) -> None:
    if not websocket_clients:
        return
    message = json.dumps({"event": event, **kwargs})
    for ws in set(websocket_clients):
        await ws.send_str(message)

# ─── HTTP Handler ─────────────────────────────────────────────────────────────

async def handle_index(request: web.Request) -> web.Response:
    index = Path(__file__).parent / "index.html"
    return web.Response(text=index.read_text(), content_type="text/html")

async def handle_websocket(request: web.Request) -> web.WebSocketResponse:
    ws = web.WebSocketResponse()
    await ws.prepare(request)
    websocket_clients.add(ws)

    logger.debug("Browser verbunden – öffne TCP-Verbindung zu Reverseproxy ...")
    await ws.send_str(json.dumps({"event": "status", "message": "Verbindung zu Reverseproxy wird aufgebaut ..."}))

    try:
        reader, writer = await asyncio.open_connection("127.0.0.1", 3000)
    except ConnectionRefusedError:
        await ws.send_str(json.dumps({"event": "error", "message": "Reverseproxy nicht erreichbar"}))
        websocket_clients.discard(ws)
        return ws

    await ws.send_str(json.dumps({"event": "status", "message": "Verbindung hergestellt"}))

    async def tcp_to_ws():
        while True:
            message = await reader.readline()
            if not message:
                break
            await ws.send_str(json.dumps({
                "event": "server_to_client",
                "message": message.decode().strip()
            }))
        await ws.send_str(json.dumps({"event": "status", "message": "Verbindung getrennt"}))
        await ws.close()

    async def ws_to_tcp():
        async for msg in ws:
            if msg.type == aiohttp.WSMsgType.TEXT:
                data = json.loads(msg.data)
                if data["event"] == "send":
                    writer.write((data["message"] + "\n").encode())
                    await writer.drain()
            elif msg.type == aiohttp.WSMsgType.ERROR:
                break
        writer.close()
        await writer.wait_closed()

    try:
        await asyncio.gather(tcp_to_ws(), ws_to_tcp())
    finally:
        websocket_clients.discard(ws)

    return ws

# ─── UI Callbacks ─────────────────────────────────────────────────────────────

def ui_callback(event: str, connection_id: int, *args) -> None:
    match event:
        case "new_connection":
            asyncio.create_task(broadcast("new_connection", connection_id=connection_id, client_addr=args[0], server_addr=args[1]))
        case "client_to_server":
            asyncio.create_task(broadcast("client_to_server", connection_id=connection_id, message=args[0]))
        case "server_log":
            asyncio.create_task(broadcast("server_log", connection_id=connection_id, message=args[0]))
        case "delete_connection":
            asyncio.create_task(broadcast("delete_connection", connection_id=connection_id))

def register_callback(send_to_server) -> None:
    pass  # Hier nicht gebraucht – Browser schickt direkt über TCP

# ─── Logging ──────────────────────────────────────────────────────────────────

class WebLogHandler(logging.Handler):
    def emit(self, record: logging.LogRecord) -> None:
        asyncio.create_task(broadcast("log", message=self.format(record)))

# ─── Main ─────────────────────────────────────────────────────────────────────

async def main() -> None:
    logging.basicConfig(level=logging.DEBUG, format="%(levelname)-7s %(name)-12s %(message)s")

    handler = WebLogHandler()
    handler.setFormatter(logging.Formatter("%(levelname)-7s %(name)-12s %(message)s"))
    logging.getLogger("reverseproxy").addHandler(handler)
    logging.getLogger("reverseproxy").setLevel(logging.DEBUG)

    app = web.Application()
    app.router.add_get("/",   handle_index)
    app.router.add_get("/ws", handle_websocket)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", 8000)
    await site.start()

    print("WebUI läuft auf http://127.0.0.1:8000")

    await run_reverseproxy(ui_callback, register_callback)

    await runner.cleanup()

asyncio.run(main())
