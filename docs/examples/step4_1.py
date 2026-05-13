import asyncio
import docker
import uuid
from asyncio import StreamReader, StreamWriter
from pathlib import Path

d = docker.from_env()

async def client_connected_cb(reader: StreamReader, writer: StreamWriter) -> None:
    path = Path(__file__).parent.parent / 'data' / str(uuid.uuid4())
    await asyncio.to_thread(path.mkdir)

async def main():
    s = await asyncio.start_server(client_connected_cb, '0.0.0.0', 1453)
    async with s:
        await s.serve_forever()

asyncio.run(main())