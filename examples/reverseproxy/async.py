import asyncio, logging
from asyncio import StreamReader, StreamWriter

logging.basicConfig(level=logging.DEBUG, format="%(levelname)-7s %(name)-8s %(message)s")
logger = logging.getLogger(__name__)

async def callback(reader: StreamReader, writer: StreamWriter) -> None:
    process: asyncio.subprocess.Process = await asyncio.create_subprocess_exec(
        'python',
        '../servers/sockets/echo.py',
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE
    )

    while True:
        message: bytes = await reader.read(1024)
        if not message:
            break
        process.stdin.write(message)
        await process.stdin.drain()
        message = await process.stdout.read(1024)
        writer.write(message)
        await writer.drain()

    process.kill()
    writer.close()
    await writer.wait_closed()

with asyncio.Runner(debug=True) as runner:
    server = runner.run(asyncio.start_server(callback, 'localhost', 1453))
    runner.run(server.serve_forever())