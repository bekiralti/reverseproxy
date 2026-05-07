# Standard Libraries
import asyncio, json, logging, re, signal, shutil, sys, time, uuid
from asyncio import StreamReader
from asyncio.exceptions import IncompleteReadError
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import cast, Literal

# 3rd Party Libraries (eventually also rewrite the HTTP parsing logic with aiohttp)
import docker
from docker.models.containers import Container

# Local Libraries
import webui

# Global variables
docker_client = docker.from_env()
counter = 0    # Used to mask the actual UUID4 (for the WebUI, I didn't want to expose IP-Addresses or the UUID4s)
free_ids = deque()
logger = logging.getLogger(__name__)
sessions = {}  # Look-up-table

# Store necessary information for each session
@dataclass(slots=True)
class Session:
    docker_container: Container
    path: Path
    last_seen: float
    id: int

def new_id() -> int:
    global counter

    if free_ids:
        new_id = free_ids.popleft()
    else:
        counter += 1
        new_id = counter

    return new_id

def shutdown_gracefully(signum, frame):
    logger.info(f"Signal: {signum}, Frame: {frame}")
    logger.info("Reverse-proxy shuts down")
    for session in sessions.values():
        logger.info(f"Stop and remove Docker-Container {session.docker_container} and delete its associated data at path: {session.path}")
        shutil.rmtree(session.path)
        session.docker_container.stop()
        session.docker_container.remove()
    logger.info("Thank you and see you soon! :)")
    sys.exit(0)

async def poll_sessions():
    while True:
        logger.info('Checking for expired sessions')
        for uuid4, session in list(sessions.items()):
            elapsed_time = time.time() - session.last_seen
            logger.info(f"Elapsed Time: {elapsed_time} seconds for {session}")

            # A *too tight* window leads to the deletion of the container before it can be even used
            if elapsed_time > 60:
                logger.info(f"The Session is expired and will be deleted now")
                await asyncio.to_thread(shutil.rmtree, session.path, ignore_errors=False, onerror=None)
                await asyncio.to_thread(session.docker_container.stop)    # IO-Bound
                await asyncio.to_thread(session.docker_container.remove)  # IO-Bound
                free_ids.append(session.id)
                del sessions[uuid4]
        await asyncio.sleep(60)  # Polling every 60 seconds. Node-RED heartbeat happens about every 15 seconds.

def try_again(uuid4=None):
    """Returns an HTTP-Response template string with the `Refresh` Header and sets Cookie with the given UUID4."""
    if uuid4:
        return (
            "HTTP/1.1 200 OK\r\n"
            f"Set-Cookie: uuid4={uuid4}\r\n"
            "Refresh: 5\r\n"
            "\r\n"
        )
    else:
        return (
            "HTTP/1.1 200 OK\r\n"
            "Refresh: 5\r\n"
            "\r\n"
        )

# Type annotation to calm down the type checker
async def get_or_create_docker_container(uuid4: str) -> Container | None:
    """Checks if a Docker-Container exists in the global `sessions` dictionary for the given `uuid4`.

    Returns the Docker-Container if it exists.

    Returns None if the Docker-Container is being created.
    You have to *retry* with the same `uuid4` to get the created Docker-Container.
    """

    # Eventually also rate-limit by IP, because a malicious client can send multiple requests with different UUID4s to create multiple unused Docker-Containers.
    if uuid4 in sessions:
        session = sessions[uuid4]
    else:
        # Dummy to prevent someone who sends multiple requests with the same UUID from creating multiple containers
        sessions[uuid4] = None  # Now, `uuid4 in sessions` evaluates to `True`

        # Each Browser has to get its own data folder, otherwise they will conflict each other!
        path = Path(__file__).parent.parent / 'data' / uuid4
        await asyncio.to_thread(path.mkdir)
        docker_container = await asyncio.to_thread(
            docker_client.containers.run,
            'nodered/node-red',
            detach=cast(Literal[True], True),                # -d, `cast(Literal[True], True)` instead of simply `True` to calm down the type checker
            ports={'1880/tcp': 0},                           # -p 0:1880 (0 lets the kernel choose a free port)
            volumes={path: {'bind': '/data', 'mode': 'rw'}}  # -v ./docker/data:/data
        )

        # Update the above Dummy with the actual Session object
        sessions[uuid4] = Session(docker_container=docker_container, path=path, last_seen=time.time(), id=new_id())

        return docker_container

    if session is None:
        return None
    else:
        return session.docker_container

def parse_uuid4(text):
    """Returns the UUID4 value for the given input (`text`). Returns `None` if no valid UUID4 exists in `text`."""

    # Source for the UUID4 regex: https://stackoverflow.com/a/18516125
    uuid4 = re.search(
        rb"uuid4=([a-f0-9]{8}-[a-f0-9]{4}-4[a-f0-9]{3}-[89ab][a-f0-9]{3}-[a-f0-9]{12})",
        text
    )

    return uuid4.group(1).decode() if uuid4 else None

# Type annotations to calm down the type checker
async def read_http_header_and_body(reader: StreamReader) -> tuple[bytes, bytes]:
    """Returns a tuple: `(http_header, http_body)`.

    Returns `(http_header, b'')` if no `Content-Length` is specified.

    Returns the tuple `(b'', b'')` if no message is received after 10 seconds.
    """

    # Timeout for when someone connects and doesn't send an *HTTP-Request* or just blocks the line
    http_header = await asyncio.wait_for(reader.readuntil(b'\r\n\r\n'), 10)  # Change timeout value if necessary

    # As of now, only Content-Length is supported. Might have to add Chunked support as well later on.
    content_length = re.search(
        rb"Content-Length: (\d+)",
        http_header,
        re.IGNORECASE  # HTTP-Headers are case-insensitive (see RFC 9110)
    )
    content_length = int(content_length.group(1)) if content_length else 0

    http_body = await reader.readexactly(content_length)

    return http_header, http_body

async def reverseproxy_handler(client_reader, client_writer):
    # Upon a successful connection immediately try to read the HTTP-Request
    try:
        client_http_header, client_http_body = await read_http_header_and_body(client_reader)
    except IncompleteReadError:
        logger.info("Client closed the connection immediately or just couldn't fully send a proper HTTP-Request")
        client_writer.close()
        await client_writer.wait_closed()
        return
    except TimeoutError:
        logger.info("The Client took too long to send an HTTP-Request!")
        client_writer.close()
        await client_writer.wait_closed()
        return
    logger.info(f"HTTP-Request-Header: {client_http_header}")
    logger.info(f"HTTP-Request-Body: {client_http_body}")

    # This is basically the branching point: WebUI (SSE) or Docker-Container
    if client_http_header.startswith(b'GET /events'):
        client_writer.write((
            b'HTTP/1.1 200 OK\r\n'
            b'Content-Type: text/event-stream\r\n'
            b'\r\n'
        ))
        while True:
            data = [{f"connection_id": session.id} for session in sessions.values()]
            data = f"data: {json.dumps(data)}\n\n"
            client_writer.write(data.encode())

            # Diese Exceptions treten i.d.R. auf, wenn die Verbindung unterbrochen wurde (Bsp.: Client hat Tab geschlossen)
            try:
                await client_writer.drain()
            except ConnectionResetError:
                logger.info("Client disconnected from the WebUI")
                client_writer.close()
                # An dieser Stelle ist der Socket sowieso tot, await client_writer.wait_closed() wirft BrokenPipeError
                # Fehlermeldung aus "/usr/lib/python3.14/asyncio/selector_events.py" ist hier nicht zu vermeiden
                return
            await asyncio.sleep(1)
    elif webui_response := await webui.handle_request(client_http_header):
        client_writer.write(webui_response)
        await client_writer.drain()
        client_writer.close()
        await client_writer.wait_closed()
        return

    # At this point we know the Client wants a Docker-Container. Continue by reading its UUID4-Cookie.
    session_uuid4 = parse_uuid4(client_http_header)

    # Prevent multiple docker-container creations by someone who for example simply spams: curl my-proxy.net
    if session_uuid4 is None:
        session_uuid4 = uuid.uuid4()  # Assumption: UUID4 is unique enough that collisions won't happen
        client_writer.write(try_again(session_uuid4).encode())
        await client_writer.drain()
        client_writer.close()
        await client_writer.wait_closed()
        return

    # At this point we can be sure that the UUID-Cookie is truly in UUID4 format.
    docker_container = await get_or_create_docker_container(session_uuid4)
    if docker_container is None:
        # For this UUID a Docker-Container is already being created. Tell the client to try again soon.
        client_writer.write(try_again().encode())
        await client_writer.drain()
        client_writer.close()
        await client_writer.wait_closed()
        return

    # Docker-Container Zustand aktualisieren und den Port abrufen
    await asyncio.to_thread(docker_container.reload)
    port = docker_container.ports['1880/tcp'][0]['HostPort']  # e.g. ports = {'1880/tcp': [{'HostIp': '0.0.0.0', 'HostPort': '32778'}, {'HostIp': '::', 'HostPort': '32778'}]}

    # TCP-Verbindung zum Docker-Container aufbauen und HTTP-Request des Browsers weiterleiten
    docker_reader, docker_writer = await asyncio.open_connection('localhost', port)
    docker_writer.write(client_http_header + client_http_body)
    await docker_writer.drain()

    # HTTP-Response des Docker-Containers lesen. Wenn es fehlschlägt, dann ist der Docker-Container noch nicht bereit.
    try:
        docker_http_header, docker_http_body = await read_http_header_and_body(docker_reader)
    except ConnectionResetError, IncompleteReadError:
        logger.info("The Docker-Container is not ready yet. Telling the Client to try again.")
        client_writer.write(try_again().encode())
        await client_writer.drain()
        client_writer.close()
        await client_writer.wait_closed()
        return
    logger.info(f"HTTP-Response-Header: {docker_http_header}")
    logger.debug(f"HTTP-Response-Body: {docker_http_body}")

    # HTTP-Response des Docker-Containers an den Browser weiterleiten
    client_writer.write(docker_http_header + docker_http_body)
    await client_writer.drain()

    # Actual message forwarding. I placed the function here because aesthetically it suits here better than outside
    async def forward_message(reader, writer):
        while True:
            message = await reader.read(4096)                # 4 KiB (angelehnt an Pages) ist hier willkürlich gewählt
            logger.debug(f"Forward message: {message}")
            if not message:
                break                                        # *empty* `message` bedeutet die Verbindung wurde beendet
            sessions[session_uuid4].last_seen = time.time()  # *Heartbeat*
            writer.write(message)
            await writer.drain()
        writer.close()
        await writer.wait_closed()

    await asyncio.gather(
        forward_message(client_reader, docker_writer),
        forward_message(docker_reader, client_writer)
    )

# TODO: Use port 443 for HTTPS instead of a *random* one like 3000. HTTPS needs TLS and whatnot.
async def main():
    signal.signal(signal.SIGINT, shutdown_gracefully)
    reverseproxy = await asyncio.start_server(reverseproxy_handler, '0.0.0.0', 1071)
    async with reverseproxy:
        await asyncio.gather(reverseproxy.serve_forever(), poll_sessions())

if __name__ == '__main__':
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s.%(msecs)03d %(levelname)-7s %(name)-12s %(message)s",
        datefmt="%H:%M:%S"
    )
    asyncio.run(main(), debug=True)