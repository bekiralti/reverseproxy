import asyncio, logging, os

# logging.basicConfig(level=logging.DEBUG, format="%(levelname)-7s %(name)-12s %(message)s")
logger = logging.getLogger('server')

async def read(client_reader, ui_writer):
    while True:
        message = await client_reader.readline()

        # *empty* message means disconnection
        if not message:
            break

        ui_writer.write(f"Receives: {message.decode().strip()}\n".encode())
        await ui_writer.drain()

    ui_writer.close()
    await ui_writer.wait_closed()

async def write(ui_reader, client_writer):
    while True:
        message = await ui_reader.readline()

        # *empty* message means disconnection
        if not message:
            break

        client_writer.write(message)
        await client_writer.drain()

    # ui_reader.readline() returns empty when either the client or the reverseproxy disconnects.
    # When the client disconnects then client_reader, here client_writer will be closed by the reverseproxy.
    # When the reverseproxy disconnects then the client_reader, here client_writer will be closed by the reverseproxy.
    # Nonetheless
    client_writer.close()
    await client_writer.wait_closed()

async def main():
    connection_id = os.environ.get('CONNECTION_ID')

    # Establish connection with the reverseproxy!
    client_reader, client_writer = await asyncio.open_connection('host.docker.internal', 3001)
    client_writer.write(f"{connection_id}\n".encode())
    await client_writer.drain()

    # Also register the UI *connection*
    ui_reader, ui_writer = await asyncio.open_connection('host.docker.internal', 3002)
    ui_writer.write(f"{connection_id}\n".encode())
    await ui_writer.drain()

    # Start
    await asyncio.gather(read(client_reader, ui_writer), write(ui_reader, client_writer))

asyncio.run(main(), debug=False)