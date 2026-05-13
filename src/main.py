# Standard libraries
import asyncio, logging, uuid, re, shutil, signal, sys, time
from asyncio import StreamReader, StreamWriter, IncompleteReadError
from dataclasses import dataclass
from pathlib import Path
from signal import SIGINT

# 3rd party libraries
import docker
from docker.models.containers import Container


@dataclass(slots=True)
class Session:
    container: Container
    path: Path
    last_seen: float

# Global variables
d = docker.from_env()
logger = logging.getLogger(__name__)
sessions = {}

def graceful_shutdown(signum, frame):
    logger.info(f"Signal: {signum}, Frame: {frame}")
    for session in sessions.values():
        logger.info(f"Stop and Remove Docker-Container: {session.container}")
        session.container.stop()
        session.container.remove()
        shutil.rmtree(session.path)
    sys.exit(0)

async def poll_sessions():
    while True:
        logger.info('Checking for expired sessions')

        # A *too tight* window leads to the deletion of the container before it can be even used
        for uuid4, session in list(sessions.items()):
            elapsed_time = time.time() - session.last_seen
            logger.info(f"Elapsed Time: {elapsed_time} seconds for {session}")
            if elapsed_time > 60:
                logger.info(f"This session is expired and will be deleted now.")
                await asyncio.to_thread(shutil.rmtree, session.path, ignore_errors=False, onerror=None)
                await asyncio.to_thread(session.container.stop)
                await asyncio.to_thread(session.container.remove)
                del sessions[uuid4]
        await asyncio.sleep(60)

async def client_connected_cb(client_reader: StreamReader, client_writer: StreamWriter) -> None:
    # Try reading the UUID4 Cookie from the HTTP-Request
    http_header = await client_reader.readuntil(b'\r\n\r\n')
    logger.info(f"HTTP-Request Header: {http_header}")

    # Source for the UUID4 regex: https://stackoverflow.com/a/18516125
    uuid4 = re.search(rb'uuid4=([a-f0-9]{8}-[a-f0-9]{4}-4[a-f0-9]{3}-[89ab][a-f0-9]{3}-[a-f0-9]{12})', http_header)
    uuid4 = uuid4.group(1).decode() if uuid4 else None
    logger.info(f"UUID4: {uuid4}")

    session = sessions.get(uuid4)
    if session:
        port = sessions[uuid4].container.ports['1880/tcp'][0]['HostPort']
        container_reader, container_writer = await asyncio.open_connection('localhost', port)

        # Forward HTTP-Request: Client -> Container
        container_writer.write(http_header)
        await container_writer.drain()

        # Forward HTTP-Response: Container -> Client
        http_header = await container_reader.readuntil(b'\r\n\r\n')
        logger.info(f"HTTP-Response Header: {http_header}")

        content_length = re.search(rb'Content-Length:\s*(\d+)', http_header, re.IGNORECASE)
        content_length = int(content_length.group(1)) if content_length else 0
        http_body = await container_reader.readexactly(content_length)
        logger.info(f"HTTP-Response Body: {http_body}")

        client_writer.write(http_header + http_body)
        await client_writer.drain()

        # Client <-> Container
        async def forward(reader: StreamReader, writer: StreamWriter) -> None:
            while True:
                session.last_seen = time.time()
                message = await reader.read(4096)
                logger.debug(f"Forward: {message}")
                if not message:
                    break
                writer.write(message)
                await writer.drain()
            writer.close()
            await writer.wait_closed()
        await asyncio.gather(
            forward(client_reader, container_writer),
            forward(container_reader, client_writer)
        )
    else:
        uuid4 = str(uuid.uuid4())
        logger.info(f"UUID4: {uuid4}")
        path = Path(__file__).parent.parent.parent / 'data' / uuid4
        await asyncio.to_thread(path.mkdir)
        container = await asyncio.to_thread(
            d.containers.run,
            'nodered/node-red',
            detach=True,                                     # -d
            ports={'1880/tcp': 0},                           # -p 0:1880 (0 lets the kernel choose a free port)
            volumes={path: {'bind': '/data', 'mode': 'rw'}}  # -v ./docker/data:/data
        )
        sessions[uuid4] = Session(container, path, time.time())
        await asyncio.to_thread(container.reload)
        port = container.ports['1880/tcp'][0]['HostPort']
        logger.info(f"Port: {port}")

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
        logger.info(f"HTTP-Response Header: {http_header}")

        # Read HTTP-Body
        content_length = re.search(rb'Content-Length:\s*(\d+)', http_header, re.IGNORECASE)
        content_length = int(content_length.group(1)) if content_length else 0
        http_body = await container_reader.readexactly(content_length)
        logger.info(f"HTTP-Response Body: {http_body}")

        # Forward HTTP-Response: Container -> Client
        client_writer.write(http_header + http_body)
        await client_writer.drain()

async def main():
    signal.signal(SIGINT, graceful_shutdown)
    s = await asyncio.start_server(client_connected_cb, '0.0.0.0', 1453)
    async with s:
        await asyncio.gather(s.serve_forever(), poll_sessions())

if __name__ == '__main__':
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s.%(msecs)03d %(levelname)-7s %(name)-12s %(message)s",
        datefmt="%H:%M:%S",
        handlers=[logging.FileHandler("main.log"), logging.StreamHandler()]
    )
    asyncio.run(main(), debug=True)
