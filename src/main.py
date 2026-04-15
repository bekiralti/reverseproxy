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

def reply_with_new_uuid(browser_writer, browser_uuid):
    """Gebe dem Browser ein neues UUID-Cookie und sage ihm, dass er es gleich noch einmal versuchen soll"""
    browser_writer.write((
        "HTTP/1.1 200 OK\r\n"
        f"Set-Cookie: uuid={browser_uuid}\r\n"
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

    # Edge-Case: Zwei verschiedene Browser, die noch keine UUID haben, können einen *falschen* Docker-Container zugewiesen bekommen
    if browser_uuid is None:
        # Daher wird dieser Fall frühzeitig verlassen. Dem Browser wird eine UUID zugewiesen und aufgefordert es erneut zu versuchen
        browser_uuid = str(uuid.uuid4())
        reply_with_new_uuid(browser_writer, browser_uuid)
        await browser_writer.drain()
        browser_writer.close()
        return

    # Ist es eine gültige UUID?
    loop = asyncio.get_running_loop()
    if browser_uuid in sessions:
        # Erwarten wir für diese UUID eine Docker-Container erstellung, oder wurde bereits ein Docker-Container erstellt?
        future = sessions[browser_uuid]
        if asyncio.isfuture(future):
            # Wir erwarten noch die Docker-Container erstellung
            docker_container = await future # Hier wird noch auf die Docker-Container erstellung gewartet
        else:
            # Docker-Container wurde bereits erstellt
            docker_container = future # Hier ist future deer Docker-Container selbst. (Docker-Container sind nicht awaitable)
    else:
        # Falls nein, dann muss eine neue UUID und ein Docker-Container erstellt werden
        browser_uuid = str(uuid.uuid4())

        # Future: Merke dir, dass für diese UUID (hoffentlich) ein Docker-Container erstellt werden wird
        future = loop.create_future()
        sessions[browser_uuid] = future
        reply_with_new_uuid(browser_writer, browser_uuid)
        await browser_writer.drain()
        browser_writer.close()

        # Erinnerung: An `await` Stellen ist immer Concurrency! D.h. an dieser Stelle ist der Programmfluss NICHT mehr synchron!
        # Bis der Docker-Container (in den folgenden Zeilen) erstellt wird, kann bspw. vom selben Browser ein neuer Request kommen.
        # Dieser neue Request kann dann im if-Fall landen, da wir ja jetzt eine *gültige* UUID haben.
        logger.debug('Starte Docker-Container')
        try:
            docker_container = await loop.run_in_executor(None, functools.partial(    # run_in_executor() only allows args. To allow kwargs we use functools.partial()
                docker_client.containers.run,                                                 # type: ignore
                'my-villas-image',
                detach=True,                                                                  # -d
                ports={'1880/tcp': 0},                                                        # -p 0:1880 (0 lets the kernel choose a free port)
                volumes={os.path.abspath('../docker/data'): {'bind': '/data', 'mode': 'rw'}}  # -v ./docker/data:/data
            ))                                                                                # type: ignore
            sessions[browser_uuid] = docker_container
            future.set_result(docker_container)  # `await`s die auf dieses Ergebnis warten (await future) werden hiermit *entblockt*
        except Exception as e:
            # Nur für den Fall, dass die Docker-Container erstellung fehlschlägt
            del sessions[browser_uuid]
            future.set_exception(e) # Wenn future nicht gesetzt wird, *wartet* await future ewig
            logger.error(f"Fehler bei Docker-Container erstellung: {e}")
            raise
        logger.debug('Docker-Container gestartet')
        return

    # Ist der Docker-Container bereit?
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
            "    <meta http-equiv='refresh' content='1'>"
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