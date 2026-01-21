import asyncio, logging
from asyncio import StreamReader, StreamWriter

logging.basicConfig(level=logging.DEBUG, format="%(levelname)-7s %(name)-8s %(message)s")
logger = logging.getLogger(__name__)

async def callback(reader: StreamReader, writer: StreamWriter) -> None:
    while True:
        message: bytes = await reader.read(1024)

        if not message:
            print('TESTOSTERON')
            break

        process: asyncio.subprocess.Process = await asyncio.create_subprocess_exec(
            'python',
            '../echo.py',
            message.decode('utf-8'),
            stdout=asyncio.subprocess.PIPE
        )
        data: tuple[bytes, bytes] = await process.communicate() # data = (stdout_data, stderr_data)
        writer.write(data[0])
    writer.close()
    await writer.wait_closed()

with asyncio.Runner(debug=True) as runner:
    server = runner.run(asyncio.start_server(callback, 'localhost', 1453))
    runner.run(server.serve_forever())