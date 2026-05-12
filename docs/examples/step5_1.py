import asyncio
import docker
import uuid
from asyncio import StreamReader, StreamWriter
from pathlib import Path

d = docker.from_env()

async def forward(reader, writer):
    while True:
        message = await reader.read(4096)
        print(message)
        if not message:
            break
        writer.write(message)
        await writer.drain()
    writer.close()
    await writer.wait_closed()

async def client_connected_cb(client_reader: StreamReader, client_writer: StreamWriter) -> None:
    path = Path(__file__).parent.parent.parent / 'data' / uuid.uuid4().hex
    print(path)
    await asyncio.to_thread(path.mkdir)
    container = await asyncio.to_thread(
        d.containers.run,
        'nodered/node-red',
        detach=True,                                     # -d
        ports={'1880/tcp': 0},                           # -p 0:1880 (0 lets the kernel choose a free port)
        volumes={path: {'bind': '/data', 'mode': 'rw'}}  # -v ./docker/data:/data
    )
    await asyncio.to_thread(container.reload)
    port = container.ports['1880/tcp'][0]['HostPort']
    print(port)
    container_reader, container_writer = await asyncio.open_connection('localhost', port)
    await asyncio.gather(
        forward(client_reader, container_writer),
        forward(container_reader, client_writer)
    )

async def main():
    s = await asyncio.start_server(client_connected_cb, '0.0.0.0', 1453)
    async with s:
        await s.serve_forever()

asyncio.run(main())