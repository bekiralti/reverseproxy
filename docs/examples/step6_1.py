import asyncio
import docker
import uuid
import re
from asyncio import StreamReader, StreamWriter, IncompleteReadError
from pathlib import Path

d = docker.from_env()

async def client_connected_cb(client_reader: StreamReader, client_writer: StreamWriter) -> None:
    # HTTP-Request
    http_header = await client_reader.readuntil(b'\r\n\r\n')
    print(http_header)

    # Try reading the UUID4 Cookie

    # Docker-Container
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
    port = container.ports['1880/tcp'][0]['HostPort']
    print(port)

    # Forward
    while True:
        try:
            container_reader, container_writer = await asyncio.open_connection('localhost', port)
            container_writer.write(http_header)
            await container_writer.drain()

            http_header = await container_reader.readuntil(b'\r\n\r\n')
        except ConnectionResetError:
            print("ConnectionResetError")
            await asyncio.sleep(1)
            continue
        except IncompleteReadError:
            print("IncompleteReadError")
            await asyncio.sleep(1)
            continue
        break
    print(http_header)

    content_length = re.search(rb'Content-Length:\s*(\d+)', http_header, re.IGNORECASE)
    content_length = int(content_length.group(1)) if content_length else 0
    http_body = await container_reader.readexactly(content_length)
    print(http_body)
    client_writer.write(http_header + http_body)
    await client_writer.drain()

async def main():
    s = await asyncio.start_server(client_connected_cb, '0.0.0.0', 1453)
    async with s:
        await s.serve_forever()

asyncio.run(main())