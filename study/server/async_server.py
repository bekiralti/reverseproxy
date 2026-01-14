import asyncio
import time

from asyncio import StreamReader # to make type hints more readible (StreamReader is a class)
from asyncio import StreamWriter # to make type hints more readible (StreamWriter is a class)

HOST = 'localhost'
PORT = 1453

# Has to be defined as async if you want to evaulate async methods such as reader.readline()
async def callback(reader: StreamReader, writer: StreamWriter):
    address = writer.get_extra_info('peername')
    print(f"[SERVER] Client {address} connected.")

    #message = await reader.readline() # The message actually has to contain a '\n' otherwise will be stuck her forever
    message = await reader.read(1024)
    print(f"[SERVER] Received {message.decode('utf-8')}")

    # Some heavy I/O request :P
    #time.sleep(5) # If the processing of one Client reaches this line then the entire Event Loop gets blocked, then the
                  # async server is unable to accept new connections because it is blocked by this synchronous function
    await asyncio.sleep(5)

    message = 'PONG'
    writer.write(message.encode('utf-8'))
    print(f"[SERVER] Replied {message} to {address}")

    # In the synchronous version we closed the `conn` object.
    # `conn` was the socket object establishing the connection between server and one specific client
    print(f"[SERVER] Close connection to {address}")
    writer.close()
    await writer.wait_closed()

with asyncio.Runner() as runner:
    print('[SERVER] Starting ...')
    server = runner.run(asyncio.start_server(callback, HOST, PORT))
    runner.run(server.serve_forever())