import asyncio
import json
import logging
from pathlib import Path

from aiohttp import web
import aiohttp

logger = logging.getLogger("webui")

# ─── HTTP Handler ─────────────────────────────────────────────────────────────

async def handle_index(request: web.Request) -> web.Response:
    index = Path(__file__).parent / "index.html"
    return web.Response(text=index.read_text(), content_type="text/html")

async def handle_websocket(request: web.Request) -> web.WebSocketResponse:
    ws = web.WebSocketResponse()
    await ws.prepare(request)

    logger.debug("Browser verbunden – öffne TCP-Verbindung zu Reverseproxy ...")

    try:
        reader, writer = await asyncio.open_connection("127.0.0.1", 3000)
    except ConnectionRefusedError:
        logger.error("Reverseproxy nicht erreichbar auf Port 3000")
        await ws.send_str(json.dumps({"event": "error", "message": "Reverseproxy nicht erreichbar"}))
        return ws

    logger.debug("TCP-Verbindung zu Reverseproxy hergestellt")
    await ws.send_str(json.dumps({"event": "status", "message": "Verbindung zu Reverseproxy hergestellt"}))

    async def tcp_to_ws():
        """Liest vom Reverseproxy (TCP) und schickt an den Browser (WebSocket)"""
        while True:
            message = await reader.readline()
            if not message:
                break
            await ws.send_str(json.dumps({
                "event": "server_to_client",
                "message": message.decode().strip()
            }))
        # Reverseproxy hat Verbindung geschlossen → Browser informieren
        await ws.send_str(json.dumps({"event": "status", "message": "Verbindung getrennt"}))
        await ws.close()

    async def ws_to_tcp():
        """Liest vom Browser (WebSocket) und schickt an Reverseproxy (TCP)"""
        async for msg in ws:
            if msg.type == aiohttp.WSMsgType.TEXT:
                data = json.loads(msg.data)
                if data["event"] == "send":
                    writer.write((data["message"] + "\n").encode())
                    await writer.drain()
            elif msg.type == aiohttp.WSMsgType.ERROR:
                break

        # Browser hat Verbindung geschlossen → TCP schließen
        writer.close()
        await writer.wait_closed()

    await asyncio.gather(tcp_to_ws(), ws_to_tcp())

    return ws

# ─── Main ─────────────────────────────────────────────────────────────────────

async def main() -> None:
    logging.basicConfig(level=logging.DEBUG, format="%(levelname)-7s %(name)-12s %(message)s")

    app = web.Application()
    app.router.add_get("/",   handle_index)
    app.router.add_get("/ws", handle_websocket)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", 8000)
    await site.start()

    print("WebUI läuft auf http://127.0.0.1:8000")

    await asyncio.Event().wait()  # läuft bis Ctrl+C

    await runner.cleanup()

asyncio.run(main())
