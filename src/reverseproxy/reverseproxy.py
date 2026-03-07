import asyncio, logging, subprocess, uuid
from dataclasses import dataclass

logger = logging.getLogger('reverseproxy')

@dataclass
class Connection:
    client_reader: asyncio.StreamReader
    client_writer: asyncio.StreamWriter
    server_reader: asyncio.StreamReader = None
    server_writer: asyncio.StreamWriter = None

async def run_reverseproxy(ui_callback=None):
    connections = {}  # LUT mapping clients to their respective servers

    async def forward_message(reader, writer, direction, connection_id):
        while True:
            message = await reader.readline()

            # Empty `message` means the client disconnected
            if not message:
                break

            if ui_callback is not None:
                await ui_callback(direction, connection_id, message.decode().strip())

            writer.write(message)
            await writer.drain()

        # If Client closes connection, then writer.close() closes the Server connection.
        # If Server closes connection, then writer.close() closes the Client connection.
        writer.close()
        await writer.wait_closed()

    # Handles new clients
    async def client_callback(reader, writer):
        """ Creates a new entry in the LUT `connections` and starts a new server for this new client."""

        # A newly generated uuid colliding with an already existing one is negligible (~1 in 2^122)
        connection_id = uuid.uuid4()
        connections[connection_id] = Connection(client_reader=reader, client_writer=writer)

        if ui_callback is not None:
            await ui_callback('new_connection', connection_id)

        # TODO: Make this in the asyncio style
        # Make sure to regularly delete logs
        subprocess.Popen([
            'docker', 'run',
            '-it', '--add-host=host.docker.internal:host-gateway', '-e', f"CONNECTION_ID={str(connection_id)}",
            'server'],
            stdout=open(f"/tmp/docker_out.log", 'w'), # TODO: FIX
            stderr=open(f"/tmp/docker_err.log", 'w')  # TODO: FIX
        )

    async def server_callback(reader, writer):
        """ Maps the server with its corresponding client and starts the message forwarding for this Connection """

        # Newly created server has to send back the uuid that has been created in client_callback()
        connection_id = uuid.UUID((await reader.readline()).decode().strip())

        # Ordne diesen Server zu dem entsprechenden Client zu!
        connection = connections[connection_id]
        connection.server_reader = reader
        connection.server_writer = writer

        # Getting address information for logging purposes
        client_ip, client_port = connection.client_writer.get_extra_info('peername')
        server_ip, server_port = connection.server_writer.get_extra_info('peername')
        logger.debug(f"Reverseproxy is ready for: Client {client_ip}:{client_port} <-> Server {server_ip}:{server_port}")

        # Start the actual message forwarding: Client->Server and Server->Client.
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
        if ui_callback is not None:
            await ui_callback('delete_connection', connection_id)

        logger.debug(f"Client {client_ip}:{client_port} <-> Server {server_ip}:{server_port} has been closed.")

        del connections[connection_id]

    logger.debug("TCP-Socket für Client-Verbindungen wird aktiviert.")
    clients = await asyncio.start_server(client_callback, '127.0.0.1', 3000)

    logger.debug("TCP-Socket für Server-Verbindungen wird aktiviert.")
    servers = await asyncio.start_server(server_callback, '0.0.0.0', 3001)

    # Run both TCP sockets asynchronously
    async with clients, servers:
        try:
            await asyncio.gather(clients.serve_forever(), servers.serve_forever())

        # Ensure proper closing in case the UI shuts down first while there are still active connections
        finally:
            for connection in connections.values():
                connection.client_writer.close()
                await connection.client_writer.wait_closed()
                connection.server_writer.close()
                await connection.server_writer.wait_closed()

if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG, format="%(levelname)-7s %(name)-12s %(message)s")
    asyncio.run(run_reverseproxy(), debug=False)