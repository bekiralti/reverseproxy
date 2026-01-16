import asyncio, logging, subprocess
from asyncio import StreamReader, StreamWriter

logging.basicConfig(level=logging.DEBUG, format="%(levelname)-7s %(name)-8s %(message)s")
logger = logging.getLogger(__name__)

async def callback(reader: StreamReader, writer: StreamWriter) -> None:
    message = await reader.read(1024)
    result = subprocess.run(
        ['python', '../../examples/echo.py', message.decode('utf-8')],
        capture_output=True,
        text=True
    )
    message = result.stdout
    writer.write(message.encode('utf-8'))
    writer.close()
    await writer.wait_closed()

with asyncio.Runner(debug=True) as runner:
    server = runner.run(asyncio.start_server(callback, 'localhost', 1453))
    runner.run(server.serve_forever())
