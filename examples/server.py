import asyncio, logging, os
from prompt_toolkit import PromptSession
from prompt_toolkit.patch_stdout import patch_stdout
from prompt_toolkit.shortcuts import print_formatted_text

logging.basicConfig(level=logging.DEBUG, format="%(levelname)-7s %(name)-12s %(message)s")
logger = logging.getLogger('server')

async def read(reader):
    while True:
        message = await reader.readline()
        if not message:
            break
        # print_formatted_text(f"Received message: {message.decode().strip()}")

async def write(writer):
    connection_id = os.environ.get('CONNECTION_ID')
    logger.debug(f"CONNECTION_ID: {connection_id}")
    writer.write(f"{os.environ.get('CONNECTION_ID')}\n".encode())
    await writer.drain()

    # TODO: Eventually rewrite the input mechanism with own looper.add_reader() logic
    # session = PromptSession()
    while True:
        pass
        # with patch_stdout():
            # message = await session.prompt_async("Send message: ")

        # `\n` is added for the receiving side, so that they can identify the end of the message
        # writer.write((message + '\n').encode())
        # await writer.drain()

async def main():
    reader, writer = await asyncio.open_connection('host.docker.internal', 3001)

    # wait() returns `done` and `pending` tasks, however these are not needed at the moment
    await asyncio.wait(
        (asyncio.create_task(read(reader)), asyncio.create_task(write(writer))),
        return_when=asyncio.FIRST_COMPLETED
    )

    writer.close()
    await writer.wait_closed()

asyncio.run(main(), debug=True)