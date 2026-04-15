# Standard Libraries
import asyncio, functools, logging, os, re, signal, sys, uuid

# 3rd Party Libraries
import docker

docker_client = docker.from_env()
sessions = {}
locks = {}

def graceful_shutdown(signum, frame):
    logger.debug(f"Signal: {signum}, Frame: {frame}")
    logger.info("Reverseproxy fährt herunter. Stoppe und lösche alle Docker-Container")
    for _uuid, container in sessions.items():
        logger.debug(f"Stoppe Container für Seesion {_uuid}")
        container.stop()
        logger.debug(f"Lösche Container für Seesion {_uuid}")
        container.remove()
    logger.info("Danke und bis bald! :)")
    sys.exit(0)

async def reply_with_new_uuid(writer):
    """Gebe dem Browser ein neues UUID-Cookie und sage ihm, dass er es gleich noch einmal versuchen soll"""
    _uuid = str(uuid.uuid4()) # UUID4 ist einzigartig genug. Es reicht (vorerst) zur eindeutigen Identifikation
    logger.debug(f"New UUID: {_uuid}")
    writer.write((
        "HTTP/1.1 200 OK\r\n"
        f"Set-Cookie: uuid={_uuid}\r\n"
        "Content-Type: text/html\r\n"
        "\r\n"
        "<html>"
        "  <head>"
        "    <meta http-equiv='refresh' content='3'>"
        "  </head>"
        "</html>").encode()
    )
    await writer.drain()
    return _uuid

async def run_new_docker_container(image):
    """Starte einen neuen VILLASconf Docker-Container"""
    loop = asyncio.get_running_loop()
    logger.debug('Starte Docker-Container')
    docker_container = await loop.run_in_executor(None, functools.partial(   # run_in_executor() only allows args. To allow kwargs we use functools.partial()
        docker_client.containers.run,                                                # type: ignore
        image,
        detach=True,                                                                 # -d
        ports={'1880/tcp': 0},                                                       # -p 0:1880 (0 lets the kernel choose a free port)
        volumes={os.path.abspath('../docker/data'): {'bind': '/data', 'mode': 'rw'}} # -v ./docker/data:/data
    ))                                                                               # type: ignore
    logger.debug('Docker-Container gestartet')
    return docker_container

async def forward_message(reader, writer):
    while True:
        message = await reader.read(4096) # 4 KiB, willkürlich gewählt.

        # An *empty* message signals that the connection has been closed (either intentionally or unintentionally)
        if not message:
            break

        # Forward message
        writer.write(message)
        await writer.drain()

    # If Client (Server) closes connection, then writer.close() closes the Server (Client) connection
    writer.close()
    await writer.wait_closed()

async def client_connected_cb(browser_reader, browser_writer):
    """This function is called whenever a TCP-Connection to port 1024 has been successfully established"""

    # HTTP-Request and HTTP-Body are seperated by a double newline, aka \r\n\r\n
    browser_request = await browser_reader.readuntil(b"\r\n\r\n")
    logger.debug(f"HTTP-Request: {browser_request}")

    # Lese die UUID aus dem Cookie Feld
    browser_uuid = re.search(rb"Cookie:.*uuid=([a-f0-9-]+).*\r\n", browser_request)
    browser_uuid = browser_uuid.group(1).decode() if browser_uuid else None

    # Edge-Case: Es können zwei verschiedene Browser, mit browser_uuid == None einen *falschen* Docker-Container zugewiesen bekommen
    if browser_uuid is None:
        # Daher wird dieser Fall frühzeitig verlassen. Dem Browser wird eine UUID zugewiesen und aufgefordert es erneut zu versuchen
        await reply_with_new_uuid(browser_writer)
        browser_writer.close()
        return

    # Existiert bereits ein Lock für diesen UUID?
    if browser_uuid not in locks:
        # Falls nein, dann erstelle eins
        locks[browser_uuid] = asyncio.Lock()

    # Ist es eine gültige UUID?
    old_uuid = browser_uuid
    if browser_uuid in sessions:
        # Falls ja, dann existiert hierfür schon ein Docker-Container
        docker_container = sessions[browser_uuid]
    else:
        # Falls nein, dann muss eine neue UUID und ein Docker-Container erstellt werden
        # Jedoch kann hier eine Racing-Condition entstehen, wenn ein Browser zwei Requests *zu schnell* hintereinanderschickt
        # Die Racing-Condition führt dazu, dass zwei oder sogar mehr Docker-Container für einen Browser erstellt werden
        # Dadurch können mehrere Docker-Container entstehen, die verwaisen
        # Zur Auflösung der Racing-Condition wird hier für die Cookie-UUID ein Lock erstellt
        # Innerhalb des gelockten Bereichs wird geprüft, ob nicht schon eine vorausgehende TCP-Verbindung vom selben Browser bereits einen Docker-Container erstellt hat
        # Wenn ein Docker-Container für diesen Browser bereits erstellt worden ist, dann gilt: old_uuid != browser_uuid
        async with locks[browser_uuid]:
            if old_uuid == browser_uuid:
                # Es wurde für diesen Browser noch kein Docker-Container erstellt
                browser_uuid = await reply_with_new_uuid(browser_writer)
                docker_container = await run_new_docker_container('my-villas-image')
                sessions[browser_uuid] = docker_container
            else:
                # Es wurde für diesen Browser bereits ein Docker-Container erstellt
                docker_container = sessions[browser_uuid]
            locks.pop(old_uuid)

    # Ist der Docker-Container bereit?
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, docker_container.reload) # type: ignore
    logger.debug(docker_container.health)
    if docker_container.health != 'healthy':
        # Falls nicht, teile dem Browser mit, dass er es gleich noch einmal versuchen soll
        browser_writer.write((
            "HTTP/1.1 200 OK\r\n"
            "Content-Type: text/html\r\n"
            "\r\n"
            "<html>"
            "  <head>"
            "    <meta http-equiv='refresh' content='3'>"
            "  </head>"
            "</html>").encode()
        )
        await browser_writer.drain()
        browser_writer.close()
        return

    # TCP-Verbindung zum entsprechenden Docker-Container aufbauen
    port = docker_container.ports['1880/tcp'][0]['HostPort'] # e.g. ports = {'1880/tcp': [{'HostIp': '0.0.0.0', 'HostPort': '32778'}, {'HostIp': '::', 'HostPort': '32778'}]}
    docker_reader, docker_writer = await asyncio.open_connection('localhost', port)

    # Browser-Request an Docker-Container weiterleiten
    docker_writer.write(browser_request)
    await docker_writer.drain()

    # Message forwarding
    logger.debug('Beginn Message-Forwarding')
    await asyncio.gather(forward_message(browser_reader, docker_writer), forward_message(docker_reader, browser_writer))
    logger.debug('Ende Message-Forwarding')

async def main():
    """Actually serves as a wrapper for asyncio.run(). Other solutions exist, but this seems to be straightforward"""
    signal.signal(signal.SIGINT, graceful_shutdown)
    server = await asyncio.start_server(client_connected_cb, '0.0.0.0', 1024)
    async with server:
        await server.serve_forever()

if __name__ == '__main__':
    logger = logging.getLogger(__name__)
    logging.basicConfig(level=logging.DEBUG, format="%(levelname)-7s %(name)-12s %(message)s")
    asyncio.run(main(), debug=True)