import logging, socket, sys

logging.basicConfig(level=logging.DEBUG, format="%(levelname)-7s %(name)-12s %(message)s")
logger = logging.getLogger('server')

with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
    s.connect(('127.0.0.1', 3001))
    logger.debug(s.getsockname())
    message = str(sys.argv[1]) + '\n'
    s.sendall(message.encode())

    with s.makefile('rb') as f:
        while True:
            message = f.readline()
            logger.debug(f"Received message: {message.decode().strip()}")