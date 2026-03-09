import asyncio, collections, logging
from dataclasses import dataclass

logger = logging.getLogger('reverseproxy')

@dataclass
class Connection:
    client_reader: asyncio.StreamReader
    client_writer: asyncio.StreamWriter
    server_reader: asyncio.StreamReader = None
    server_writer: asyncio.StreamWriter = None
    control_writer: asyncio.StreamWriter = None
    server_process: asyncio.subprocess.Process = None

async def run_reverseproxy(ui_callback=None, register_callback=None) -> None:
    connections = {}                              # Look-Up-Table (LUT)
    new_connection_id = 0                         # connection ID counter
    reusable_connection_ids = collections.deque() # connection IDs of closed connections are stored here for reuse

    async def forward_message(reader, writer, direction, connection_id) -> None:
        while True:
            message = await reader.readline()

            # An *empty* message signals that the connection has been closed (either intentionally or unintentionally)
            if not message:
                break

            # Inform UI
            if callable(ui_callback):
                # decode() message from bytes to string. strip() final `\n` which just signals the end of transmission
                ui_callback(direction, connection_id, message.decode().strip())

            writer.write(message)
            await writer.drain()

        # If Client closes connection, then writer.close() closes the Server connection
        # If Server closes connection, then writer.close() closes the Client connection
        writer.close()
        await writer.wait_closed()

    async def client_callback(client_reader, client_writer) -> None:
        # Assign a unique ID
        nonlocal new_connection_id
        if reusable_connection_ids:
            connection_id = reusable_connection_ids.popleft()
        else:
            connection_id = new_connection_id
            new_connection_id += 1

        # Create Connection. Create Server. Save Connection in the LUT
        connection = Connection(client_reader=client_reader, client_writer=client_writer)
        connection.server_process = await asyncio.create_subprocess_exec(
            'docker', 'run', '--init', '--rm', '--add-host=host.docker.internal:host-gateway',
            '-e', f"CONNECTION_ID={str(connection_id)}", 'server'
        )
        connections[connection_id] = connection

    async def server_callback(server_reader, server_writer) -> None:
        # decode() message from bytes to string. strip() final `\n` which just marks the end of the transmission
        connection_id = int((await server_reader.readline()).decode().strip())

        # Ordne diesen Server zu dem entsprechenden Client zu!
        connection = connections[connection_id]
        connection.server_reader = server_reader
        connection.server_writer = server_writer

        client_ip, client_port = connection.client_writer.get_extra_info('peername')
        server_ip, server_port = connection.server_writer.get_extra_info('peername')
        logger.debug(f"Reverseproxy is ready: Client {client_ip}:{client_port} <-> Server {server_ip}:{server_port}")

        # Inform UI
        if callable(ui_callback):
            ui_callback('new_connection', connection_id, (client_ip, client_port), (server_ip, server_port))

        # `register_callback` making it possible for the UI to interact with the server
        # e.g. sending messages from the server through the UI
        if callable(register_callback):
            register_callback(send_to_server)

        try:
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

        # If the UI gets closed first, we ensure that the Docker processes are being stopped
        finally:
            logger.debug(f"Closed connection: Client {client_ip}:{client_port} <-X-> Server {server_ip}:{server_port}")

            connection.server_process.terminate()
            await connection.server_process.wait()

        # Inform UI
        if callable(ui_callback):
            ui_callback('delete_connection', connection_id)

        reusable_connection_ids.append(connection_id)
        del connections[connection_id]

    async def control_callback(control_reader, control_writer):
        connection_id = int((await control_reader.readline()).decode().strip())
        connections[connection_id].control_writer = control_writer
        while True:
            message = await control_reader.readline()

            # If the server closes it will send an empty message to this reader too
            if not message:
                break

            if callable(ui_callback):
                ui_callback('server_log', connection_id, message.decode().strip())

        control_writer.close()
        await control_writer.wait_closed()

    async def send_to_server(connection_id, message):
        connection = connections[connection_id]
        connection.control_writer.write(f"{message}\n".encode())
        await connection.control_writer.drain()

    # Start TCP-Sockets
    # To avoid timing issues, there is one Port for client side connections and one Port for server side connections
    logger.debug("Start TCP-Socket for client connections")
    logger.debug("Start TCP-Socket for server connections")
    logger.debug("Start TCP-Socket for controller connections")

    # 0.0.0.0 because of the Docker namespace
    # `control_socket` is a way for the UI and server to interact with each other through this reverseproxy
    # Eventually: Only start the controllers_socket if `ui_callback` is not None, might be overly-complicating though.
    servers_socket = await asyncio.start_server(server_callback, '0.0.0.0', 3001)
    control_socket = await asyncio.start_server(control_callback, '0.0.0.0', 3002)
    clients_socket = await asyncio.start_server(client_callback, '127.0.0.1', 3000)

    async with clients_socket, servers_socket, control_socket:
        try:
            await asyncio.gather(
                clients_socket.serve_forever(),
                servers_socket.serve_forever(),
                control_socket.serve_forever()
            )

        # Ensure proper closing in case the UI shuts down first while there are still active connections
        finally:
            for connection in connections.values():
                # It is enough to only close client_writer here.
                # The EOF chain reaction will close every other connection as well. Nonetheless
                connection.client_writer.close()
                await connection.client_writer.wait_closed()
                connection.server_writer.close()
                await connection.server_writer.wait_closed()
                connection.control_writer.close()
                await connection.control_writer.wait_closed()

if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG, format="%(levelname)-7s %(name)-12s %(message)s")
    asyncio.run(run_reverseproxy(), debug=True)