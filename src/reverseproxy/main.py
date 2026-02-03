import asyncio, logging, subprocess, uuid
from dataclasses import dataclass

logging.basicConfig(level=logging.DEBUG, format="%(levelname)-7s %(name)-12s %(message)s")
logger = logging.getLogger('reverseproxy')

async def client(reader, writer):
    subprocess.Popen(['python', '../../examples/server.py'])

async def server(reader, writer):
    pass

async def main():
    clients = await asyncio.start_server(client, '127.0.0.1', 3000)
    servers = await asyncio.start_server(server, '127.0.0.1', 3001)
    async with clients, servers:
        await asyncio.gather(clients.serve_forever(), servers.serve_forever())

asyncio.run(main(), debug=True)