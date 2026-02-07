import asyncio, json, logging, subprocess, uuid
import sys
from dataclasses import dataclass
from pathlib import Path

logging.basicConfig(level=logging.DEBUG, format="%(levelname)-7s %(name)-12s %(message)s")
logger = logging.getLogger('reverseproxy')

connections = {}
# server_count = 0
# target_id = None

@dataclass
class Connection:
    client_reader: asyncio.StreamReader
    client_writer: asyncio.StreamWriter
    server_reader: asyncio.StreamReader = None
    server_writer: asyncio.StreamWriter = None

async def get_rightmost_window():
    """Finde IMMER das aktuell rechteste Fenster (kein right-Nachbar)"""
    kitty_data = json.loads(subprocess.check_output(['kitty', '@', 'ls']))
    active_tab = kitty_data[0]['tabs'][0]
    right_window = next(w for w in active_tab['windows']
                        if 'right' not in w.get('neighbors', {}))
    return right_window['id']

async def forward(reader, writer):
    while True:
        message = await reader.readline()
        if not message:
            break
        writer.write(message)
        await writer.drain()
    writer.close()
    await writer.wait_closed()

async def server(reader, writer):
    connection_id = uuid.UUID((await reader.readline()).decode().strip())

    # Wichtig, damit die Zuordnung der Clients mit den Servern stimmt!
    connections[connection_id].server_reader = reader
    connections[connection_id].server_writer = writer

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

    # At this point, the connection has been closed
    del connections[connection_id]

async def client(reader, writer):
    connection_id = uuid.uuid4()
    if connection_id in connections:
        writer.write('Fatal error: Generated UUID already exists. Please connect again.\n'.encode())
        await writer.drain()
        logger.fatal(f"Generated UUID:{connection_id} already exists")
        writer.close()
        await writer.wait_closed()
        return
    connections[connection_id] = Connection(client_reader=reader, client_writer=writer)

    subprocess.Popen([sys.executable, '../../examples/server.py', str(connection_id)])

    # global server_count, target_id
    #
    # # Kitty-Status abfragen
    # if target_id is None:
    #     target_id = await get_rightmost_window()
    #
    # # Berechne den absoluten Pfad zu server.py
    # script_dir = Path(__file__).parent.resolve()
    # server_script = script_dir / '../../examples/server.py'
    # server_script = server_script.resolve()  # Macht den Pfad absolut
    #
    # if server_count == 0:
    #     subprocess.Popen([
    #         'kitty', '@', 'send-text', '--match', f"id:{target_id}",
    #         f"python {str(server_script)} {str(connection_id)}\n"
    #     ])
    # else:
    #     # Fokus setzen
    #     proc = await asyncio.create_subprocess_exec(
    #         'kitty', '@', 'focus-window', '--match', f'id:{target_id}'
    #     )
    #     await proc.wait()
    #
    #     # Jetzt neuen server starten
    #     subprocess.Popen([
    #         'kitty', '@', 'launch', '--location=hsplit', '--match', f"id:{target_id}",
    #         'python', str(server_script), str(connection_id)
    #     ])
    # server_count += 1

async def main():
    clients = await asyncio.start_server(client, '127.0.0.1', 3000) # Handles the message forwardings
    servers = await asyncio.start_server(server, '127.0.0.1', 3001) # Handles the server registrations
    async with clients, servers:
        await asyncio.gather(clients.serve_forever(), servers.serve_forever())

asyncio.run(main(), debug=True)