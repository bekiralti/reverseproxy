import asyncio, logging

logging.basicConfig(level=logging.DEBUG, format="%(levelname)-7s %(name)-8s %(message)s")
logger = logging.getLogger(__name__)

async def callback(reader, writer):
    client_addr = writer.get_extra_info('peername')
    server_addr = writer.get_extra_info('sockname')

    async def receive():
        while True:
            data = await reader.read(1024)
            if not data:
                break
            logger.info(f"[SERVER {server_addr[1]}] Received: {data.decode()}, From: Client {client_addr[1]}")

    async def send():
        while True:
            data = await asyncio.to_thread(input, 'Enter message here: ')
            writer.write(data.encode())
            await writer.drain()
            logger.info(f"[SERVER {server_addr[1]}] Sent: {data}, To: Client {client_addr[1]}")

    await asyncio.gather(receive(), send(), return_exceptions=True)

    writer.close()
    await writer.wait_closed()

with asyncio.Runner(debug=True) as runner:
    try:
        server = runner.run(asyncio.start_server(callback, 'localhost', 8384))
    except OSError:
        logger.error('Port is already in use.')
    runner.run(server.serve_forever())