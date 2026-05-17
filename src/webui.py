# Standard Libraries
import logging
from pathlib import Path

# 3rd Party Libraries
import aiofiles

logger = logging.getLogger(__name__)

async def get_html():
    async with aiofiles.open(Path(__file__).parent / 'webui.html', 'rb') as fh:
        html = await fh.read()
        header = ((
            "HTTP/1.1 200 OK\r\n"
            "Content-Type: text/html\r\n"
            f"Content-Length: {len(html)}\r\n"
            "\r\n").encode()
        )

    http_response = header + html

    return http_response

async def get_favicon():
    async with aiofiles.open(Path(__file__).parent / 'favicon.webp', 'rb') as fh:
        ico = await fh.read()
        header = ((
            "HTTP/1.1 200 OK\r\n"
            "Content-Type: image/webp\r\n"
            f"Content-Length: {len(ico)}\r\n"
            "\r\n").encode()
        )

    http_response = header + ico

    return http_response

async def get_webui_js():
    async with aiofiles.open(Path(__file__).parent / 'webui.js', 'rb') as fh:
        js = await fh.read()
        header = ((
            "HTTP/1.1 200 OK\r\n"
            "Content-Type: application/javascript\r\n"
            f"Content-Length: {len(js)}\r\n"
            '\r\n').encode()
        )

    http_response = header + js

    return http_response

def get_events():
    http_response = (
        b'HTTP/1.1 200 OK\r\n'
        b'Content-Type: text/event-stream\r\n'
        b'\r\n'
    )

    return http_response