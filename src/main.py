# Standard Libraries
import asyncio, logging, os, re, signal, shutil, sys, uuid
from asyncio import StreamReader
from typing import cast, Literal

# 3rd Party Libraries
import docker

# Logging setup
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.DEBUG, format="%(levelname)-7s %(name)-12s %(message)s")

# Global variables
docker_client = docker.from_env()
sessions = {}
invalid_sessions = set()

def shutdown_gracefully(signum, frame):
    logger.debug(f"Signal: {signum}, Frame: {frame}")
    logger.debug("Reverse-proxy fährt herunter")
    for browser_uuid, container in sessions.items():
        logger.debug(f"Stoppe und lösche Docker-Container und den zugehörigen Daten-Ordner für UUID: {browser_uuid}")
        container.stop()
        container.remove()
        shutil.rmtree(os.path.abspath(f'../docker/data-{browser_uuid}'))
    logger.info("Danke und bis bald! :)")
    sys.exit(0)

def try_again(writer, browser_uuid=None):
    if browser_uuid:
        writer.write((
            "HTTP/1.1 200 OK\r\n"
            f"Set-Cookie: uuid={browser_uuid}\r\n"
            "Refresh: 1\r\n"
            "\r\n").encode()
        )
    else:
        # UUID is None
        writer.write((
            "HTTP/1.1 200 OK\r\n"
            "Refresh: 1\r\n"
            "\r\n").encode()
        )

async def validate_uuid(browser_uuid):
    """Returns a tuple `(browser_uuid, docker_container)`.

    If a Docker-Container exists for the provided `browser_uuid`,
    then the Docker-Container is returned. Value of `browser_uuid` is not changed: `(browser_uuid, docker_container)`.

    If a Docker-Container doesn't exist for the provided `browser_uuid`,
    then a new `browser_uuid` is returned: `(browser_uuid, None)`.

    If two or more requests from the same Browser (same `browser_uuid`) arrive,
    then the duplicates return: (None, None)
    """

    if browser_uuid in sessions:
        # Ja, wird oder wurde für diese UUID ein Docker-Container erstellt?
        task = sessions[browser_uuid]
        if asyncio.isfuture(task):
            # A Docker-Container task was scheduled, it just needs to be awaited
            return browser_uuid, await task
        else:
            # Docker-Container is already ready (thus it does not need to be awaited)
            return browser_uuid, task
    elif browser_uuid not in invalid_sessions:
        # Nein, falls für diese UUID noch keine Container Erstellung in Auftrag gegeben wurde, dann tue dies jetzt
        invalid_sessions.add(browser_uuid)  # Blockiere andere Requests mit derselben UUID, damit keine doppelten Container erstellt werden!
        old_uuid = browser_uuid             # Um es später aus `invalid_sessions` entfernen zu können

        # Erstelle eine neue frische UUID
        browser_uuid = str(uuid.uuid4())
        os.makedirs(os.path.abspath(f"../docker/data-{browser_uuid}"))  # Each Browser gets its own *save-state*

        # Creating a Coroutine for the `docker run` command, because it is IO-bound
        coroutine = asyncio.to_thread(
            docker_client.containers.run,
            'my-villas-image',
            detach=cast(Literal[True], True),                                                             # -d, `cast(Literal[True], True)` instead of simply `True` just to calm down PyCharm
            ports={'1880/tcp': 0},                                                                        # -p 0:1880 (0 lets the kernel choose a free port)
            volumes={os.path.abspath(f"../docker/data-{browser_uuid}"): {'bind': '/data', 'mode': 'rw'}}  # -v ./docker/data:/data
        )

        # Scheduling the Coroutine as a Task (otherwise the Coroutine will be never ever executed)
        task = asyncio.create_task(coroutine)

        # Notification for every other request with the same UUID that the container creation is scheduled (see if-case)
        sessions[browser_uuid] = task

        # Since we added the new *valid* UUID into the global sessions dictionary, we can now safely remove the blockade
        invalid_sessions.remove(old_uuid)
        return browser_uuid, None
    else:
        # Diese UUID ist geblockt. Der Browser soll es nochmal mit der UUID, die es aus dem elif-Zweig bekommt versuchen
        return None, None

def read_uuid(http_request):
    """Returns the UUID value. Returns `None` if no `uuid` Cookie is received."""

    browser_uuid = re.search(rb"uuid=([a-f0-9-]+).*\r\n", http_request)
    return browser_uuid.group(1).decode() if browser_uuid else None

# The type hint `-> bytes | None` is there just to calm down PyCharm. While at it, I also added the other type hints
async def read_http_request(reader: StreamReader, timeout: float | None = 10) -> bytes | None:
    """Returns the HTTP-Request. Returns `None` if no message is received after `timeout` seconds."""

    # Timeout for when someone connects and doesn't send an *HTTP-Request*
    try:
        # HTTP-Request and HTTP-Body are separated by a blank line
        return await asyncio.wait_for(reader.readuntil(b"\r\n\r\n"), timeout=timeout)
    except TimeoutError:
        return None

async def client_connected_cb(browser_reader, browser_writer):
    # Read HTTP-Request
    if (browser_request := await read_http_request(browser_reader)) is None:
        logger.debug("Der Browser hat zu lange gebraucht um eine HTTP-Anfrage zu senden!")
        browser_writer.close()
        await browser_writer.wait_closed()
        return
    logger.debug(f"HTTP-Request: {browser_request}")

    # Read UUID from the HTTP-Request
    browser_uuid = read_uuid(browser_request)

    # Existiert ein Container für diese UUID oder muss ein neues erstellt werden?
    browser_uuid, docker_container = await validate_uuid(browser_uuid)
    if browser_uuid and (docker_container is None):
        # Es muss ein neues erstellt werden. Der Browser soll es mit der neuen UUID nochmal versuchen
        try_again(browser_writer, browser_uuid)
        await browser_writer.drain()
        browser_writer.close()
        await browser_writer.wait_closed()
        return
    elif browser_uuid is None:
        # Es wird ein neuer Docker-Container erstellt. Der Browser soll es nochmal versuchen.
        try_again(browser_writer)
        await browser_writer.drain()
        browser_writer.close()
        await browser_writer.wait_closed()
        return

    # Docker-Container Zustand aktualisieren
    await asyncio.to_thread(docker_container.reload)  # Annahme: Eine IO-Gebundene Operation

    # Vom Kernel zugewiesenen Port abrufen
    port = docker_container.ports['1880/tcp'][0]['HostPort']  # e.g. ports = {'1880/tcp': [{'HostIp': '0.0.0.0', 'HostPort': '32778'}, {'HostIp': '::', 'HostPort': '32778'}]}

    # TCP-Verbindung zum Docker-Container aufbauen
    docker_reader, docker_writer = await asyncio.open_connection('localhost', port)

    # HTTP-Request des Browsers an Docker-Container weiterleiten
    docker_writer.write(browser_request)
    await docker_writer.drain()

    # HTTP-Response des Docker-Containers lesen. Hier kann festgestellt werden ob der Docker-Container schon bereit ist
    try:
        # Zunächst nur HTTP-Headers lesen
        docker_response_headers = await docker_reader.readuntil(b'\r\n\r\n')
    except asyncio.exceptions.IncompleteReadError:
        # Docker-Container war noch nicht bereit
        try_again(browser_writer)
        await browser_writer.drain()
        browser_writer.close()
        await browser_writer.wait_closed()
        return

    # Mit dem Wert aus `Content-Length` kann anschließend der HTTP-Body gelesen werden
    content_length = re.search(rb"Content-Length: (\d+)", docker_response_headers)
    content_length = int(content_length.group(1)) if content_length else 0

    # HTTP-Body lesen
    docker_response_body = await docker_reader.readexactly(content_length)

    # Die Antwort des Docker-Containers (HTTP-Response) an den Browser weiterleiten
    browser_writer.write(docker_response_headers + docker_response_body)
    await browser_writer.drain()

    # Message forwarding
    async def forward_message(reader, writer):
        while True:
            message = await reader.read(4096)  # 4 KiB ist willkürlich gewählt
            if not message:
                # An *empty* message means disconnect
                break
            writer.write(message)
            await writer.drain()
        writer.close()
        await writer.wait_closed()

    await asyncio.gather(
        forward_message(browser_reader, docker_writer),
        forward_message(docker_reader, browser_writer)
    )

async def main():
    signal.signal(signal.SIGINT, shutdown_gracefully)
    server = await asyncio.start_server(client_connected_cb, '0.0.0.0', 1024)
    async with server:
        await server.serve_forever()

asyncio.run(main(), debug=True)