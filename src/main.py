# Standard Libraries
import asyncio, functools, logging, os, re, signal, shutil, sys, uuid

# 3rd Party Libraries
import docker

docker_client = docker.from_env()
sessions = {}
invalid_sessions = set()

def graceful_shutdown(signum, frame):
    logger.debug(f"Signal: {signum}, Frame: {frame}")
    logger.info("Reverseproxy fährt herunter. Stoppe und lösche alle Docker-Container")
    for _uuid, container in sessions.items():
        logger.debug(f"Stoppe Container für Seesion {_uuid}")
        container.stop()
        logger.debug(f"Lösche Container für Seesion {_uuid}")
        container.remove()
        shutil.rmtree(os.path.abspath(f'../docker/data-{_uuid}'))
    logger.info("Danke und bis bald! :)")
    sys.exit(0)

def try_again(writer, _uuid=None):
    """A *try-again* message to send to the Browser"""
    if _uuid:
        writer.write((
            "HTTP/1.1 200 OK\r\n"
            f"Set-Cookie: uuid={_uuid}\r\n"
            "Content-Type: text/html\r\n"
            "\r\n"
            "<html>"
            "  <head>"
            "    <meta http-equiv='refresh' content='1'>"
            "  </head>"
            "</html>").encode()
        )
    else:
        # UUID is None
        writer.write((
            "HTTP/1.1 200 OK\r\n"
            "Content-Type: text/html\r\n"
            "\r\n"
            "<html>"
            "  <head>"
            "    <meta http-equiv='refresh' content='1'>"
            "  </head>"
            "</html>").encode()
        )

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

    loop = asyncio.get_running_loop()

    # Ist es eine gültige UUID?
    if browser_uuid in sessions:
        # Falls ja, dann wurde (oder wird) für diese UUID ein Docker-Container erstellt?
        future = sessions[browser_uuid]
        if asyncio.isfuture(future):
            # Falls der Docker-Container erstellt wird, dann warte bis das Ergebnis verfügbar ist
            docker_container = await future
        else:
            # Falls der Docker-Container erstellt wurde, dann übernimm es einfach
            docker_container = future # Hinweis: Docker-Container sind nicht awaitable
    elif browser_uuid not in invalid_sessions:
        # Falls nein und falls diese UUID nicht bereits *durch einen anderen Request* bearbeitet wird
        invalid_sessions.add(browser_uuid) # *Blockiere* andere Requests mit derselben UUID, damit keine doppelten Docker-Container erstellt werden!
        old_uuid = browser_uuid            # Um es später aus `invalid_sessions` entfernen zu können

        # Erstelle eine neue UUID
        browser_uuid = str(uuid.uuid4())

        # Markiere, dass für diese UUID ein Docker-Container erstellt werden wird (s. if-Zweig)
        future = loop.create_future()
        sessions[browser_uuid] = future

        # Gib dem Browser bescheid, dass eine neue UUID zugewiesen wurde und er es gleich noch mal versuchen soll
        try_again(browser_writer, browser_uuid)
        await browser_writer.drain()
        browser_writer.close()
        await browser_writer.wait_closed()

        # Erstelle für diesen Browser einen Docker-Container
        os.makedirs(os.path.abspath(f"../docker/data-{browser_uuid}")) # Each Browser gets his own save-state
        try:
            docker_container = await loop.run_in_executor(None, functools.partial(                    # run_in_executor() only allows args. To allow kwargs we use functools.partial()
                docker_client.containers.run,                                                                 # type: ignore
                'my-villas-image',
                detach=True,                                                                                  # -d
                ports={'1880/tcp': 0},                                                                        # -p 0:1880 (0 lets the kernel choose a free port)
                volumes={os.path.abspath(f"../docker/data-{browser_uuid}"): {'bind': '/data', 'mode': 'rw'}}  # -v ./docker/data:/data
            ))                                                                                                # type: ignore
            sessions[browser_uuid] = docker_container
            future.set_result(docker_container)  # `await`s die auf dieses Ergebnis warten (await future) werden hiermit *entblockt*
        except Exception as e:
            # Nur für den Fall, dass die Docker-Container erstellung fehlschlägt
            del sessions[browser_uuid]
            invalid_sessions.remove(old_uuid)
            future.set_exception(e) # Setze ein Ergebnis, damit `await future` nicht *ewig* wartet
            logger.error(f"Fehler bei Docker-Container erstellung: {e}")
            raise
        invalid_sessions.remove(old_uuid)
        logger.debug('Docker-Container wurde erfolgreich erstellt')
        return
    else:
        # Für diesen Browser wird bereits ein Docker-Container erstellt. Dieser Browser soll sich erneut verbinden
        try_again(browser_writer, None)
        await browser_writer.drain()
        browser_writer.close()
        await browser_writer.wait_closed()
        return

    # TCP-Verbindung zum entsprechenden Docker-Container aufbauen
    await loop.run_in_executor(None, docker_container.reload) # type: ignore
    port = docker_container.ports['1880/tcp'][0]['HostPort'] # e.g. ports = {'1880/tcp': [{'HostIp': '0.0.0.0', 'HostPort': '32778'}, {'HostIp': '::', 'HostPort': '32778'}]}
    docker_reader, docker_writer = await asyncio.open_connection('localhost', port)

    # Initialen Browser-Request an Docker-Container weiterleiten
    docker_writer.write(browser_request)
    await docker_writer.drain()

    # Initiale Antwort des Docker-Container an Browser weiterleiten
    try:
        docker_response_headers = await docker_reader.readuntil(b"\r\n\r\n")
    except asyncio.exceptions.IncompleteReadError:
        # Docker-Container war noch nicht bereit
        try_again(browser_writer, None)
        await browser_writer.drain()
        browser_writer.close()
        await browser_writer.wait_closed()
        return
    content_length = re.search(rb"Content-Length: (\d+)", docker_response_headers)
    content_length = int(content_length.group(1)) if content_length else 0
    docker_response_body = await docker_reader.readexactly(content_length)
    browser_writer.write(docker_response_headers + docker_response_body)
    await browser_writer.drain()

    # Message forwarding
    logger.debug('Beginn Message-Forwarding')
    await asyncio.gather(
        forward_message(browser_reader, docker_writer),
        forward_message(docker_reader, browser_writer)
    )
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