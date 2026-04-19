import asyncio, logging

logger = logging.getLogger(__name__)

async def client_connected_cb(stream_reader, stream_writer):
    pass

async def main():
    server = await asyncio.start_server(client_connected_cb, 'localhost', 3000)

    logger.info(f"Serving on {address}")

    async with server:
        await server.serve_forever()

if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG, format="%(levelname)-7s %(name)-12s %(message)s")
    asyncio.run(main(), debug=True)