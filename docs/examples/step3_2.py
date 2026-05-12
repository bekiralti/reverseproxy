import asyncio
from asyncio import StreamReader, StreamWriter

async def client_connected_cb(reader: StreamReader, writer: StreamWriter) -> None:
    print("A Client has connected")
    while True:
        message = await reader.read(1024)
        print(message)
        if not message:
            break

async def main():
    s = await asyncio.start_server(client_connected_cb, '0.0.0.0', 1453)
    async with s:
        await s.serve_forever()

asyncio.run(main())