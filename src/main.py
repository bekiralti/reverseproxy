# Standard Libraries
import asyncio, logging, os, re, signal, shutil, sys, time, uuid
from asyncio import StreamReader
from asyncio.exceptions import IncompleteReadError
from dataclasses import dataclass
from typing import cast, Literal

# 3rd Party Libraries
import docker
from docker.models.containers import Container

# Global variables
docker_client = docker.from_env()
logger = logging.getLogger(__name__)
sessions = {}  # Look-up-table

# Store necessary information for each session
@dataclass(slots=True)
class Session:
    docker_container: Container
    last_seen: float

def shutdown_gracefully(signum, frame):
    logger.debug(f"Signal: {signum}, Frame: {frame}")
    logger.debug("Reverse-proxy shuts down")
    for uuid4, session in sessions.items():
        logger.debug(f"Stop and remove Docker-Container {session.docker_container} and delete its associated data: ./docker/data-{uuid4}")
        if session.docker_container:
            session.docker_container.stop()
            session.docker_container.remove()
        shutil.rmtree(os.path.abspath(f'../docker/data-{uuid4}'))
    logger.info("Thank you and see you soon! :)")
    sys.exit(0)

# Alternativ: Inaktive Container nicht über dieses Polling, sondern über WebSocket-Close-Codes erkennen. Oder beides.
async def poll_sessions():
    while True:
        for uuid4, session in list(sessions.items()):
            elapsed_time = time.time() - session.last_seen
            if elapsed_time > 60:
                await asyncio.to_thread(session.docker_container.stop)    # IO-Bound
                await asyncio.to_thread(session.docker_container.remove)  # IO-Bound
                shutil.rmtree(os.path.abspath(f'../docker/data-{uuid4}'))
                del sessions[uuid4]
        await asyncio.sleep(60)  # Polling every 1 minute (60 seconds). Node-RED heartbeat happens every ~15 seconds

def try_again(writer, uuid4=None):
    if uuid4:
        writer.write((
            "HTTP/1.1 200 OK\r\n"
            f"Set-Cookie: uuid4={uuid4}\r\n"
            "Refresh: 5\r\n"
            "\r\n").encode()
        )
    else:
        # UUID is None
        writer.write((
            "HTTP/1.1 200 OK\r\n"
            "Refresh: 5\r\n"
            "\r\n").encode()
        )

# Type annotation to calm down PyCharm
async def get_or_create_docker_container(uuid4: str) -> Container | None:
    """Checks if a Docker-Container exists in the global `sessions` dictionary for the given `uuid4`.

    Returns the Docker-Container if it exists.

    Returns None if the Docker-Container is being created.
    You have to *retry* with the same `uuid4` to get the created Docker-Container.

    TODO: A malicious client can spam randomly generated uuid4 cookies and thus create multiple Docker-Containers.
          One solution is to remember the IP address and limit the amount of Docker-Containers this IP address can spawn.
          E.g. 1 Docker-Container every 60 seconds.
    """

    if uuid4 in sessions:
        session = sessions[uuid4]
    else:
        # Dummy to prevent someone who sends multiple requests with the same UUID from creating multiple containers
        sessions[uuid4] = None  # Now, `uuid4 in sessions` evaluates to `True`

        # Each Browser has to get its own data folder, otherwise they will conflict each other!
        os.makedirs(os.path.abspath(f"../docker/data-{uuid4}"))

        # Create a coroutine out of the synchronous IO-Bound method call run() and schedule it as a task
        docker_container = await asyncio.to_thread(
            docker_client.containers.run,
            'my-villas-image',
            detach=cast(Literal[True], True),                                                      # -d, `cast(Literal[True], True)` instead of simply `True` just to calm down PyCharm
            ports={'1880/tcp': 0},                                                                 # -p 0:1880 (0 lets the kernel choose a free port)
            volumes={os.path.abspath(f"../docker/data-{uuid4}"): {'bind': '/data', 'mode': 'rw'}}  # -v ./docker/data:/data
        )

        # Update the above Dummy with the actual Session object
        sessions[uuid4] = Session(docker_container=docker_container, last_seen=time.time())

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

# Initially added these type-hints to calm down PyCharm. Meanwhile, code changed. Not sure if they are still necessary.
async def read_http_header_and_body(
        reader: StreamReader,
) -> tuple[bytes, bytes]:
    """Returns a tuple: `(http_header, http_body)`.

    Returns `(http_header, b'')` if no `Content-Length` is specified.

    Returns the tuple `(b'', b'')` if no message is received after `timeout` seconds.

    TODO: Eventually tighten the timeout value. Maybe 1 seconds instead of 10 seconds.
    """

    # Timeout for when someone connects and doesn't send an *HTTP-Request* or just blocks the line
    try:
        # HTTP-Header and HTTP-Body are separated by a blank line
        http_header = await asyncio.wait_for(reader.readuntil(b'\r\n\r\n'), 10)
    except TimeoutError:
        return b'', b''

    # Based on Content-Length read the HTTP-Body
    content_length = re.search(
        rb"Content-Length: (\d+)",
        http_header,
        re.IGNORECASE  # HTTP-Headers are case-insensitive (see RFC 9110)
    )
    content_length = int(content_length.group(1)) if content_length else 0
    http_body = await reader.readexactly(content_length)

    return http_header, http_body

async def reverseproxy_handler(client_reader, client_writer):
    # Read UUID-Cookie
    client_http_header, client_http_body = await read_http_header_and_body(client_reader)
    logger.debug(f"HTTP-Request: {client_http_header}")
    logger.debug(f"HTTP-Request: {client_http_body}")
    if not client_http_header and not client_http_body:
        logger.debug("The Client took too long to send an HTTP-Request!")
        client_writer.close()
        await client_writer.wait_closed()
        return
    session_uuid4 = parse_uuid4(client_http_header)

    # Prevent multiple docker-container creations by someone who for example simply spams: curl my-proxy.net
    if session_uuid4 is None:
        session_uuid4 = uuid.uuid4()
        try_again(client_writer, session_uuid4)
        await client_writer.drain()
        client_writer.close()
        await client_writer.wait_closed()
        return

    # At this point we can be sure that the UUID-Cookie is truly in UUID4 format.
    docker_container = await get_or_create_docker_container(session_uuid4)
    if docker_container is None:
        # For this UUID a Docker-Container is already being created. Tell the client to try again soon.
        try_again(client_writer)
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
        logger.debug("The Docker-Container is not ready yet. Tell the Client to try again.")
        try_again(client_writer)
        await client_writer.drain()
        client_writer.close()
        await client_writer.wait_closed()
        return
    logger.debug(f"HTTP-Response: {docker_http_header}")
    logger.debug(f"HTTP-Response: {docker_http_body}")

    # HTTP-Response des Docker-Containers an den Browser weiterleiten
    client_writer.write(docker_http_header + docker_http_body)
    await client_writer.drain()

    # Actual message forwarding. I placed the function here because aesthetically it suits here better than outside
    async def forward_message(reader, writer):
        while True:
            message = await reader.read(4096)                # 4 KiB (angelehnt an Pages) ist hier willkürlich gewählt
            logger.debug(f"Forward message: {message}")
            if not message:
                break                                        # An *empty* message means disconnect
            sessions[session_uuid4].last_seen = time.time()  # *Heartbeat*
            writer.write(message)
            await writer.drain()
        writer.close()
        await writer.wait_closed()

    await asyncio.gather(
        forward_message(client_reader, docker_writer),
        forward_message(docker_reader, client_writer)
    )

async def webui_handler(reader, writer):
    # Read HTTP-Request and HTTP-Body
    http_header, http_body = await read_http_header_and_body(reader)

    # Send JS with SSE
    writer.write((
        'HTTP/1.1 200 OK\r\n'
        'Content-Type: application/javascript\r\n'
        '\r\n'
        '<html>'
        '  <head>'
        '    <script src="/webui.js"></script>'
        '  </head>'
        '</html>'
    ))

# The `port` parameter is soon going to become constant 443 for HTTPS
async def main():
    signal.signal(signal.SIGINT, shutdown_gracefully)
    reverseproxy = await asyncio.start_server(reverseproxy_handler, '0.0.0.0', 3000)
    webui = await asyncio.start_server(webui_handler, 'localhost', 4000)
    async with reverseproxy:
        await asyncio.gather(reverseproxy.serve_forever(), poll_sessions(), webui.serve_forever())

if __name__ == '__main__':
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s.%(msecs)03d %(levelname)-7s %(name)-12s %(message)s",
        datefmt="%H:%M:%S"
    )
    asyncio.run(main(), debug=None)