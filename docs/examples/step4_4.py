import asyncio
import docker
import uuid
from asyncio import StreamReader, StreamWriter
from pathlib import Path

d = docker.from_env()

async def client_connected_cb(reader: StreamReader, writer: StreamWriter) -> None:
    path = Path(__file__).parent.parent.parent / 'data' / str(uuid.uuid4())
    await asyncio.to_thread(path.mkdir)
    container = await asyncio.to_thread(
        d.containers.run,
        'nodered/node-red',
        detach=True,                                     # -d
        ports={'1880/tcp': 0},                           # -p 0:1880 (0 lets the kernel choose a free port)
        volumes={path: {'bind': '/data', 'mode': 'rw'}}  # -v ./docker/data:/data
    )
    await asyncio.to_thread(container.reload)
    print(container.ports)
    port = container.ports['1880/tcp'][0]['HostPort']
    print(port)

async def main():
    s = await asyncio.start_server(client_connected_cb, '0.0.0.0', 1453)
    async with s:
        await s.serve_forever()

asyncio.run(main())