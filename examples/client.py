import asyncio, logging

logging.basicConfig(level=logging.DEBUG, format="%(levelname)-7s %(name)-12s %(message)s")
logger = logging.getLogger('client')

async def read(reader):
    while True:
        message = await reader.readline()
        if not message:
            break

async def write(writer):
    loop = asyncio.get_running_loop()
    while True:
        message = await loop.run_in_executor(None, input, 'Send: ')
        writer.write((message + '\n').encode())
        await writer.drain()

async def main():
    reader, writer = await asyncio.open_connection('127.0.0.1', 3000)
    await asyncio.gather(read(reader), write(writer))
    print("HMMMMMMMMMM!")

asyncio.run(main(), debug=True)