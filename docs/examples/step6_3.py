import asyncio
import docker
import logging
import uuid
import re
import shutil
import signal
import sys
from asyncio import StreamReader, StreamWriter, IncompleteReadError
from dataclasses import dataclass
from docker.models.containers import Container
from pathlib import Path
from signal import SIGINT

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
formatter = logging.Formatter(
    fmt="%(asctime)s.%(msecs)03d %(levelname)-7s %(name)-12s %(message)s",
    datefmt="%H:%M:%S"
)

file_handler = logging.FileHandler("step6_3.log")
file_handler.setLevel(logging.DEBUG)
file_handler.setFormatter(formatter)

console_handler = logging.StreamHandler()
console_handler.setLevel(logging.DEBUG)
console_handler.setFormatter(formatter)

logger.addHandler(file_handler)
logger.addHandler(console_handler)

@dataclass(slots=True)
class Session:
    container: Container
    path: Path  # Needed for cleanup

d = docker.from_env()
sessions = {}

def graceful_shutdown(signum, frame):
    logger.debug(f"Signal: {signum}, Frame: {frame}")
    for session in sessions.values():
        logger.debug(f"Stop and Remove Docker-Container: {session.docker_container}")
        session.docker_container.stop()
        session.docker_container.remove()
        shutil.rmtree(session.path)
    sys.exit(0)

async def forward(reader: StreamReader, writer: StreamWriter) -> None:
    while True:
        message = await reader.read(4096)
        if not message:
            break
        writer.write(message)
        await writer.drain()
    writer.close()
    await writer.wait_closed()

async def client_connected_cb(client_reader: StreamReader, client_writer: StreamWriter) -> None:
    # Try reading the UUID4 Cookie from the HTTP-Request
    http_header = await client_reader.readuntil(b'\r\n\r\n')
    logger.debug(f"HTTP-Request Header: {http_header}")

    uuid4 = re.search(rb'uuid4=([a-f0-9]{8}-[a-f0-9]{4}-4[a-f0-9]{3}-[89ab][a-f0-9]{3}-[a-f0-9]{12})', http_header)
    uuid4 = uuid4.group(1).decode() if uuid4 else None
    logger.debug(f"UUID4: {uuid4}")

    if uuid4 in sessions:
        port = sessions[uuid4].container.ports['1880/tcp'][0]['HostPort']
        container_reader, container_writer = await asyncio.open_connection('localhost', port)

        # Forward HTTP-Request: Client -> Container
        container_writer.write(http_header)
        await container_writer.drain()

        # Forward HTTP-Response: Container -> Client
        http_header = await container_reader.readuntil(b'\r\n\r\n')
        logger.debug(f"HTTP-Response Header: {http_header}")

        content_length = re.search(rb'Content-Length:\s*(\d+)', http_header, re.IGNORECASE)
        content_length = int(content_length.group(1)) if content_length else 0
        http_body = await container_reader.readexactly(content_length)
        logger.debug(f"HTTP-Response Body: {http_body}")

        client_writer.write(http_header + http_body)
        await client_writer.drain()

        # Client <-> Container
        await asyncio.gather(
            forward(client_reader, container_writer),
            forward(container_reader, client_writer)
        )
    else:
        # Docker-Container
        uuid4 = str(uuid.uuid4())
        logger.debug(f"UUID4: {uuid4}")
        path = Path(__file__).parent.parent.parent / 'data' / uuid4
        await asyncio.to_thread(path.mkdir)
        container = await asyncio.to_thread(
            d.containers.run,
            'nodered/node-red',
            detach=True,                                     # -d
            ports={'1880/tcp': 0},                           # -p 0:1880 (0 lets the kernel choose a free port)
            volumes={path: {'bind': '/data', 'mode': 'rw'}}  # -v ./docker/data:/data
        )
        sessions[uuid4] = Session(container, path)
        await asyncio.to_thread(container.reload)
        port = container.ports['1880/tcp'][0]['HostPort']
        logger.debug(f"Port: {port}")

        # Forward
        while True:
            try:
                container_reader, container_writer = await asyncio.open_connection('localhost', port)
                container_writer.write(http_header)
                await container_writer.drain()

                http_header = await container_reader.readuntil(b'\r\n\r\n')
            except ConnectionResetError as e:
                logger.error(f"ConnectionResetError: {e}")
                await asyncio.sleep(3)
                continue
            except IncompleteReadError as e:
                logger.error(f"IncompleteReadError: {e}")
                await asyncio.sleep(3)
                continue
            break

        # Inject UUID4 Cookie inside Node-RED's HTTP-Response
        http_header = http_header.replace(b'\r\n\r\n', f"\r\nSet-Cookie: uuid4={uuid4}\r\n\r\n".encode(), 1)
        logger.debug(f"HTTP-Response Header: {http_header}")

        # Read HTTP-Body
        content_length = re.search(rb'Content-Length:\s*(\d+)', http_header, re.IGNORECASE)
        content_length = int(content_length.group(1)) if content_length else 0
        http_body = await container_reader.readexactly(content_length)
        logger.debug(f"HTTP-Response Body: {http_body}")

        # Forward HTTP-Response: Container -> Client
        client_writer.write(http_header + http_body)
        await client_writer.drain()

async def main():
    signal.signal(SIGINT, graceful_shutdown)
    s = await asyncio.start_server(client_connected_cb, '0.0.0.0', 1453)
    async with s:
        await s.serve_forever()

asyncio.run(main(), debug=True)