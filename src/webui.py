# Standard Libraries
from pathlib import Path

# 3rd Party Libraries
import aiofiles

async def handle_request(http_header):
    if http_header.startswith(b'GET /webui HTTP/1.1'):
        async with aiofiles.open(Path(__file__).parent / 'webui.html', 'rb') as fh:
            html = await fh.read()
            header = (
                "HTTP/1.1 200 OK\r\n"
                "Content-Type: text/html\r\n"
                f"Content-Length: {len(html)}\r\n"
                "\r\n"
            )
        return header.encode() + html

    if http_header.startswith(b'GET /webui.js HTTP/1.1'):
        async with aiofiles.open(Path(__file__).parent / 'webui.js', 'rb') as fh:
            js = await fh.read()
            header = (
                "HTTP/1.1 200 OK\r\n"
                "Content-Type: application/javascript\r\n"
                f"Content-Length: {len(js)}\r\n"
                '\r\n'
            )
        return header.encode() + js

    if http_header.startswith(b'GET /favicon.ico HTTP/1.1'):
        async with aiofiles.open(Path(__file__).parent / 'favicon.webp', 'rb') as fh:
            ico = await fh.read()
            header = (
                "HTTP/1.1 200 OK\r\n"
                "Content-Type: image/webp\r\n"
                f"Content-Length: {len(ico)}\r\n"
                "\r\n"
            )
        return header.encode() + ico

    return None