# Standard Libraries
import asyncio, functools, logging, os, re, uuid

# 3rd Party Libraries
import docker

docker_client = docker.from_env()
sessions = {}

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
    return _uuid

async def run_new_docker_container(image):
    """Starte einen neuen VILLAScnof Docker-Container"""
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

    # If Client closes connection, then writer.close() closes the Server connection
    # If Server closes connection, then writer.close() closes the Client connection
    writer.close()
    await writer.wait_closed()

async def client_connected_cb(browser_reader, browser_writer):
    """This function is called whenever a TCP-Connection to port 1024 has been successfully established"""

    # HTTP-Request and HTTP-Body are seperated by a double newline, aka \r\n\r\n
    browser_request = await browser_reader.readuntil(b"\r\n\r\n")
    logger.debug(f"HTTP-Request: {browser_request}")

    # Lese die UUID aus dem Cookie Feld
    browser_uuid = re.search(rb"Cookie:.*uuid=([a-f0-9-]+).*\r\n", browser_request)
    logger.debug(f'Match: {browser_uuid}')
    browser_uuid = browser_uuid.group(1).decode() if browser_uuid else None
    logger.debug(f'UUID: {browser_uuid}')

    # Ist dies eine gültige UUID?
    if (browser_uuid is None) or (browser_uuid not in sessions):
        # Falls nein, dann erstelle eine neue UUID-Cookie und VILLASconf Docker-Container für diesen Browser
        browser_uuid = await reply_with_new_uuid(browser_writer)
        docker_container = await run_new_docker_container('my-villas-image')
        sessions[browser_uuid] = docker_container
        await browser_writer.drain()
        browser_writer.close()
        return
    docker_container = sessions[browser_uuid]

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
        browser_writer.close() # Der Browser soll gleich einfach noch eine Anfrage schicken, daher hier schon .close()
        return

    # TCP-Verbindung zum Docker-Container aufbauen
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
    server = await asyncio.start_server(client_connected_cb, '0.0.0.0', 1024)
    async with server:
        await server.serve_forever()

if __name__ == '__main__':
    logger = logging.getLogger(__name__)
    logging.basicConfig(level=logging.DEBUG, format="%(levelname)-7s %(name)-12s %(message)s")
    asyncio.run(main(), debug=True)