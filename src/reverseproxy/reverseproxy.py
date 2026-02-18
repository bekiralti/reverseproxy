import asyncio, logging, subprocess, sys, uuid
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

@dataclass
class Connection:
    client_reader: asyncio.StreamReader
    client_writer: asyncio.StreamWriter
    server_reader: asyncio.StreamReader = None
    server_writer: asyncio.StreamWriter = None

async def forward_message(reader, writer):
    while True:
        message = await reader.readline()
        if not message:
            break
        writer.write(message)
        await writer.drain()
    writer.close()
    await writer.wait_closed()

async def run_reverseproxy(ui_callback=None):
    logger.debug('TEST')
    connections = {} # Keeps track of active client-server connections

    async def server_callback(reader, writer):
        connection_id = uuid.UUID((await reader.readline()).decode().strip())

        # Wichtig, damit die Zuordnung der Clients mit den Servern stimmt!
        connections[connection_id].server_reader = reader
        connections[connection_id].server_writer = writer

        await asyncio.gather(
            forward_message(
                connections[connection_id].client_reader,
                connections[connection_id].server_writer
            ),
            forward_message(
                connections[connection_id].server_reader,
                connections[connection_id].client_writer
            )
        )

        # At this point, the connection has been closed
        if ui_callback:
            await ui_callback('del_connection', connection_id)

        del connections[connection_id]

    async def client_callback(reader, writer):
        connection_id = uuid.uuid4()
        if connection_id in connections:
            writer.write('Randomly generated UUID already exists. Please connect again.\n'.encode())
            await writer.drain()
            logger.fatal('Randomly generated UUID already exists.')
            writer.close()
            await writer.wait_closed()
            return
        connections[connection_id] = Connection(client_reader=reader, client_writer=writer)

        if ui_callback:
            await ui_callback('new_connection', connection_id)

        subprocess.Popen([
            sys.executable,
            (Path(__file__).parent.parent.parent / 'examples/server.py').resolve(),
            str(connection_id)
        ])

    clients = await asyncio.start_server(client_callback, '127.0.0.1', 3000) # Handles the message forwardings
    servers = await asyncio.start_server(server_callback, '127.0.0.1', 3001) # Handles the server registrations
    async with clients, servers:
        try:
            await asyncio.gather(clients.serve_forever(), servers.serve_forever())
        finally:
            for connection in connections.values():
                # Cleanup / Closing sockets for when the UI closes first
                connection.client_writer.close()
                await connection.client_writer.wait_closed()
                connection.server_writer.close()
                await connection.server_writer.wait_closed()

if __name__ == '__main__':
    asyncio.run(run_reverseproxy(), debug=True)