import asyncio, logging, subprocess, uuid
from dataclasses import dataclass

logging.basicConfig(level=logging.DEBUG, format="%(levelname)-7s %(name)-12s %(message)s")
logger = logging.getLogger('reverseproxy')

connections = {}

@dataclass
class Connection:
    client_reader: asyncio.StreamReader
    client_writer: asyncio.StreamWriter
    server_reader: asyncio.StreamReader = None
    server_writer: asyncio.StreamWriter = None

async def forward(reader, writer):
    while True:
        message = await reader.readline()
        if not message:
            break
        writer.write(message)
        await writer.drain()
    writer.close()
    await writer.wait_closed()

async def client(reader, writer):
    connection_id = uuid.uuid4()
    connections[connection_id] = Connection(reader, writer)

    subprocess.Popen(['python', '../../examples/server.py', str(connection_id)])
    for _ in range(50):
        if connections[connection_id].server_writer:
            break
        await asyncio.sleep(0.1)

    await asyncio.gather(
        forward(
            connections[connection_id].client_reader,
            connections[connection_id].server_writer
        ),
        forward(
            connections[connection_id].server_reader,
            connections[connection_id].client_writer
        )
    )

async def server(reader, writer):
    message = await reader.readline()
    message = uuid.UUID(message.decode().strip())

    if message in connections:
        connections[message].server_reader = reader
        connections[message].server_writer = writer

    try:
        await asyncio.sleep(float('inf'))  # Warte ewig
    except asyncio.CancelledError:
        pass

async def main():
    clients = await asyncio.start_server(client, '127.0.0.1', 3000)
    servers = await asyncio.start_server(server, '127.0.0.1', 3001)
    async with clients, servers:
        await asyncio.gather(clients.serve_forever(), servers.serve_forever())

asyncio.run(main(), debug=True)