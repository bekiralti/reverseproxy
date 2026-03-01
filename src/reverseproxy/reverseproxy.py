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

async def run_reverseproxy(ui_callback=None):
    connections = {} # Keeps track of active client-server connections

    async def forward_message(reader, writer, direction, connection_id):
        while True:
            message = await reader.readline()

            # Empty `message` means the client disconnected
            if not message:
                break

            if ui_callback:
                await ui_callback(direction, connection_id, message.decode().strip())

            writer.write(message)
            await writer.drain()
        address = writer.get_extra_info('peername')
        logger.debug(f"Closing {address[0]}:{address[1]}")
        logger.debug('=' * 100)
        writer.close()
        await writer.wait_closed()

    async def server_callback(reader, writer):
        connection_id = uuid.UUID((await reader.readline()).decode().strip())

        # Wichtig, damit die Zuordnung der Clients mit den Servern stimmt!
        connection = connections[connection_id]
        connection.server_reader = reader
        connection.server_writer = writer

        client_address = connection.client_writer.get_extra_info('peername')
        server_address = connection.server_writer.get_extra_info('peername')
        logger.debug(f"Fully initialized Client {client_address[0]}:{client_address[1]} <-> Server {server_address[0]}:{server_address[1]} connection")
        logger.debug('=' * 100)

        await asyncio.gather(
            forward_message(
                connection.client_reader,
                connection.server_writer,
                'client_to_server',
                connection_id
            ),
            forward_message(
                connection.server_reader,
                connection.client_writer,
                'server_to_client',
                connection_id
            )
        )

        # At this point, the connection has been closed
        if ui_callback:
            await ui_callback('delete_connection', connection_id)
        del connections[connection_id]

    async def client_callback(reader, writer):
        client_address = writer.get_extra_info('peername')
        logger.debug(f"Client {client_address[0]}:{client_address[1]} connected")
        connection_id = uuid.uuid4()
        if connection_id in connections:
            writer.write('Randomly generated UUID already exists. Please connect again.\n'.encode())
            await writer.drain()
            logger.fatal('Randomly generated UUID already exists.')
            writer.close()
            await writer.wait_closed()
            return
        connections[connection_id] = Connection(client_reader=reader, client_writer=writer)
        logger.debug(f"A new Connection with the connection ID {connection_id} has been created")

        if ui_callback:
            await ui_callback('new_connection', connection_id)

        subprocess.Popen([
            sys.executable,
            (Path(__file__).parent.parent.parent / 'examples/server.py').resolve(),
            str(connection_id)
        ])
        logger.debug(f"A server for the client {client_address[0]}:{client_address[1]} has been started")

    logger.debug("Starte Reverseproxy")
    logger.debug('=' * 100)
    clients = await asyncio.start_server(client_callback, '127.0.0.1', 3000)
    servers = await asyncio.start_server(server_callback, '127.0.0.1', 3001)
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