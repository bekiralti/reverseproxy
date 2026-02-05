import asyncio, logging
from prompt_toolkit import PromptSession
from prompt_toolkit.patch_stdout import patch_stdout

logging.basicConfig(level=logging.DEBUG, format="%(levelname)-7s %(name)-12s %(message)s")
logger = logging.getLogger('client')

async def read(reader):
    while True:
        message = await reader.readline()
        if not message:
            break

async def write(writer):
    # TODO: Eventually rewrite the input mechanism with own looper.add_reader() logic
    session = PromptSession()
    while True:
        with patch_stdout():
            message = await session.prompt_async("Send message: ")
        writer.write((message + '\n').encode())
        await writer.drain()

async def main():
    reader, writer = await asyncio.open_connection('127.0.0.1', 3000)

    # wait() returns `done` and `pending` tasks, however these are not needed at the moment
    await asyncio.wait(
        (asyncio.create_task(read(reader)), asyncio.create_task(write(writer))),
        return_when=asyncio.FIRST_COMPLETED
    )

    writer.close()
    await writer.wait_closed()

asyncio.run(main(), debug=True)