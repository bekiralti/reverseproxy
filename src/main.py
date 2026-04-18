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
    for uuid4, container in sessions.items():
        logger.debug(f"Stoppe und lösche Docker-Container {container} und lösche den zugehörigen Ordner für UUID4: {uuid4}")
        container.stop()
        container.remove()
        shutil.rmtree(os.path.abspath(f'../docker/data-{uuid4}'))
    logger.info("Danke und bis bald! :)")
    sys.exit(0)

def try_again(writer, browser_uuid4=None):
    if browser_uuid4:
        writer.write((
            "HTTP/1.1 200 OK\r\n"
            f"Set-Cookie: uuid4={browser_uuid4}\r\n"
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

async def resolve_uuid4(uuid4):
    """Returns a tuple: `(uuid4, docker_container)`

    If a Docker-Container exists for the provided `uuid4`,
    then the Docker-Container is returned. Value of `uuid4` is not changed: `(uuid4, docker_container)`.

    If a Docker-Container doesn't exist for the provided `uuid4`,
    then a new `uuid4` is returned: `(uuid4, None)`.

    If two or more requests from the same Browser (same `uuid4`) arrive,
    then the duplicate requests return: `(None, None)`
    """

    # Ist die mitgegebene UUID (`uuid4`) *gültig*?
    if uuid4 in sessions:
        # Ja, wird oder wurde für diese UUID ein Docker-Container erstellt?
        task = sessions[uuid4]
        if asyncio.isfuture(task):
            # Case: Docker-Container task was scheduled, it just needs to be awaited
            sessions[uuid4] = await task  # *Replace* the Task object with the actual (awaited) Docker-Container

            return uuid4, sessions[uuid4]
        else:
            # Case: Docker-Container is already ready (thus it does not need to be awaited)
            return uuid4, task
    elif uuid4 not in invalid_sessions:
        # Nein, falls für diese UUID4 noch keine Container Erstellung in Auftrag gegeben wurde, dann tue dies jetzt
        invalid_sessions.add(uuid4)  # Blockiere Requests mit derselben UUID, sonst werden doppelten Container erstellt!
        old_uuid4 = uuid4            # Um es später aus `invalid_sessions` entfernen zu können

        # Erstelle eine neue frische UUID
        uuid4 = str(uuid.uuid4())
        os.makedirs(os.path.abspath(f"../docker/data-{uuid4}"))  # Each Browser gets its own *save-state*

        # Creating a Coroutine for the `docker run` command, because it is IO-bound
        coroutine = asyncio.to_thread(
            docker_client.containers.run,
            'my-villas-image',
            detach=cast(Literal[True], True),                                                      # -d, `cast(Literal[True], True)` instead of simply `True` just to calm down PyCharm
            ports={'1880/tcp': 0},                                                                 # -p 0:1880 (0 lets the kernel choose a free port)
            volumes={os.path.abspath(f"../docker/data-{uuid4}"): {'bind': '/data', 'mode': 'rw'}}  # -v ./docker/data:/data
        )

        # Scheduling the Coroutine as a Task (otherwise the Coroutine will be never ever executed)
        task = asyncio.create_task(coroutine)

        # Notification for every other request with the same UUID that the container creation is scheduled (see if-case)
        sessions[uuid4] = task

        # Since we added the new *valid* UUID into the global sessions dictionary, we can now safely remove the blockade
        invalid_sessions.remove(old_uuid4)

        return uuid4, None
    else:
        # Für diese UUID wurde eine Containererstellung in Auftrag gegeben, daher ist diese UUID vorerst geblockt.
        return None, None

def parse_uuid4(text):
    """Returns the UUID4 value for the given input (`text`). Returns `None` if no valid UUID4 exists in `text`."""

    # Source for the UUID4 regex: https://stackoverflow.com/a/18516125
    uuid4 = re.search(
        rb"uuid4=([a-f0-9]{8}-[a-f0-9]{4}-4[a-f0-9]{3}-[89ab][a-f0-9]{3}-[a-f0-9]{12})",
        text
    )

    return uuid4.group(1).decode() if uuid4 else None

# I initially added the type-hints to calm down PyCharm. They changed. I don't know if they are still necessary.
async def read_http_request_and_body(
        reader: StreamReader,
        timeout: float | None = 10
) -> tuple[bytes, bytes]:
    """Returns a tuple: `(http_request, http_body)`.

    Returns `(http_request, b'')` if no `Content-Length` is specified.

    Returns the tuple `(b'', b'')` if no message is received after `timeout` seconds.
    """

    # Timeout for when someone connects and doesn't send an *HTTP-Request*
    try:
        # HTTP-Request and HTTP-Body are separated by a blank line
        http_request = await asyncio.wait_for(reader.readuntil(b"\r\n\r\n"), timeout=timeout)
    except TimeoutError:
        return b'', b''

    # Based on Content-Length, read the HTTP-Body
    content_length = re.search(
        rb"Content-Length: (\d+)",  # HTTP-Headers are case-insensitive (see RFC 9110)
        http_request,
        re.IGNORECASE
    )
    content_length = int(content_length.group(1)) if content_length else 0
    http_body = await reader.readexactly(content_length)

    return http_request, http_body

async def client_connected_cb(browser_reader, browser_writer):
    # Read HTTP-Request, HTTP-Body and UUID (set by this reverse-proxy after the initial HTTP-Request)
    browser_http_request, browser_http_body = await read_http_request_and_body(browser_reader)
    logger.debug(browser_http_request)
    logger.debug(browser_http_body)
    if (browser_http_request == b'') and (browser_http_body == b''):
        logger.debug("Der Browser hat zu lange gebraucht um eine HTTP-Anfrage zu senden!")
        browser_writer.close()
        await browser_writer.wait_closed()
        return
    browser_uuid4 = parse_uuid4(browser_http_request)

    # Falls der Docker-Container für diese UUID noch nicht existiert, dann soll der Browser es gleich nochmal versuchen
    browser_uuid4, docker_container = await resolve_uuid4(browser_uuid4)
    if browser_uuid4 and (docker_container is None):
        # Es muss ein neues erstellt werden. Der Browser soll es mit der neuen UUID nochmal versuchen
        try_again(browser_writer, browser_uuid4)
        await browser_writer.drain()
        browser_writer.close()
        await browser_writer.wait_closed()
        return
    elif browser_uuid4 is None:
        # Es wird gerade ein neuer Docker-Container erstellt. Der Browser soll es gleich nochmal versuchen.
        try_again(browser_writer)
        await browser_writer.drain()
        browser_writer.close()
        await browser_writer.wait_closed()
        return

    # Docker-Container Zustand aktualisieren und den vom Kernel zugewiesenen Port abrufen
    await asyncio.to_thread(docker_container.reload)          # Annahme: `reload()` ist eine IO-Gebundene Operation
    port = docker_container.ports['1880/tcp'][0]['HostPort']  # e.g. ports = {'1880/tcp': [{'HostIp': '0.0.0.0', 'HostPort': '32778'}, {'HostIp': '::', 'HostPort': '32778'}]}

    # TCP-Verbindung zum Docker-Container aufbauen und HTTP-Request des Browsers weiterleiten
    docker_reader, docker_writer = await asyncio.open_connection('localhost', port)
    docker_writer.write(browser_http_request + browser_http_body)
    await docker_writer.drain()

    # HTTP-Response des Docker-Containers lesen. Hier kann festgestellt werden ob der Docker-Container schon bereit ist
    try:
        docker_http_headers, docker_http_body = await read_http_request_and_body(docker_reader)
    except asyncio.exceptions.IncompleteReadError:
        logger.debug("Docker-Container ist noch nicht bereit. Der Browser wird benachrichtigt es nochmal zu versuchen")
        try_again(browser_writer)
        await browser_writer.drain()
        browser_writer.close()
        await browser_writer.wait_closed()
        return

    # HTTP-Response (des Docker-Containers) an den Browser weiterleiten
    browser_writer.write(docker_http_headers + docker_http_body)
    await browser_writer.drain()

    # Actual message forwarding. I placed the function here because aesthetically it suits here better than outside
    async def forward_message(reader, writer):
        while True:
            message = await reader.read(4096)  # 4 KiB ist willkürlich gewählt
            if not message:
                break  # An *empty* message means disconnect
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