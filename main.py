# Standard Libraries
import asyncio, functools, logging, os

# 3rd Party Libraries
import docker

docker_client = docker.from_env()

async def forward_message(reader, writer):
    while True:
        message = await reader.read(4096) # 4 KiB, willkürlich gewählt

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

async def client_connected_cb(browser_reader: asyncio.StreamReader, browser_writer: asyncio.StreamWriter) -> None:
    """This function is called whenever a TCP-Connection to port 1024 has been successfully established"""

    # Für's debuggen
    # logger.debug(await browser_reader.read(1024))

    # Prüfe ob die Anfrage der Erwartung entspricht: GET / HTTP/1.1\r\n
    # request_line = await stream_reader.readuntil(b"\r\n")
    # logger.debug(f"Request Line: {request_line}")
    # if request_line != b"GET / HTTP/1.1\r\n":
    #     stream_writer.close()
    #     return
    browser_request = await browser_reader.readuntil(b"\r\n\r\n")
    logger.debug(f"Request Line: {browser_request}")

    # Beruhige den Browser, damit er nicht ganz viele TCP-Verbindungen aufeinmal aufruft!
    # stream_writer.write(b"HTTP/1.1 200 OK\r\n\r\n")
    # await stream_writer.drain()

    # Keep-alive
    # browser_writer.write(b'HTTP/1.1 102 Processing\r\n\r\n')
    # await browser_writer.drain()

    # Starte den VILLASconf Docker-Container
    loop = asyncio.get_running_loop()
    # logger.debug('Starte Docker-Container')
    # docker_container = await loop.run_in_executor(None, functools.partial(
    #     docker_client.containers.run,                                                # type: ignore
    #     'my-villas-image',
    #     detach=True,                                                                 # -d
    #     ports={'1880/tcp': 0},                                                       # -p 0:1880 (0 lets the kernel choose a free port)
    #     volumes={os.path.abspath('./docker/data'): {'bind': '/data', 'mode': 'rw'}}  # -v ./docker/data:/data
    # ))                                                                               # type: ignore
    # logger.debug('Docker-Container gestartet')

    # Warte bis der Docker-Container bereit ist
    # while True:
    #     await loop.run_in_executor(None, docker_container.reload)
    #     logger.debug(docker_container.health)
    #     if docker_container.health == 'healthy':
    #         break
    #     await asyncio.sleep(1)

    # TCP-Verbindung zum Docker-Container aufbauen
    # port = docker_container.ports['1880/tcp'][0]['HostPort'] # e.g. ports = {'1880/tcp': [{'HostIp': '0.0.0.0', 'HostPort': '32778'}, {'HostIp': '::', 'HostPort': '32778'}]}
    docker_reader, docker_writer = await asyncio.open_connection('localhost', 1880)

    # Browser-Request an Docker-Container schicken
    docker_writer.write(browser_request)
    await docker_writer.drain()

    # Message forwarding
    logger.debug('Beginne Message-Forwarding')
    await asyncio.gather(forward_message(browser_reader, docker_writer), forward_message(docker_reader, browser_writer))
    logger.debug('Ende Message-Forwarding')

async def main():
    server = await asyncio.start_server(client_connected_cb, '0.0.0.0', 1024)
    async with server:
        await server.serve_forever()

if __name__ == '__main__':
    logger = logging.getLogger(__name__)
    logging.basicConfig(level=logging.DEBUG, format="%(levelname)-7s %(name)-12s %(message)s")
    asyncio.run(main(), debug=True)