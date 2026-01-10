import socket
import time

HOST = 'localhost'
PORT = 1453

with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
    server.bind((HOST, PORT))
    print(f"[SERVER] Bound on {HOST}:{PORT}")

    server.listen()
    print('[SERVER] Listening ...')

    while True:
        print('\n[SERVER] Waiting for a client ...')
        start = time.time()
        conn, address = server.accept()
        print(f"[SERVER] A client connected after {time.time() - start:.2f} seconds")

        start = time.time()
        with conn:
            message = conn.recv(1024) # Buffersize set to 1024 Bytes.
            print(f"[SERVER] Client {address} sent {message.decode('utf-8')}. Processing Time {time.time() - start:.2f} seconds")

            # Processing client's request ... assume it is a heavy I/O operation and client is waiting for a response
            time.sleep(5)

            message = 'Ve Aleykümselam'
            conn.sendall(message.encode('utf-8'))
            print(f"[SERVER] Replied {message} to client after {time.time() - start:.2f} seconds")