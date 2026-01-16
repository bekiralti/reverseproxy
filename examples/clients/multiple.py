import socket
import threading
import time

HOST = 'localhost'
PORT = 1453
print_lock = threading.Lock() # Just like a mutex in C

def client(i):
    with print_lock:
        print(f"[CLIENT {i+1}] Initiated")

    start = time.time()
    client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    client.connect((HOST, PORT))
    message = f"PING {i}"
    client.send(message.encode('utf-8'))

    with print_lock:
        print(f"[CLIENT {i}] Sent {message} after {time.time() - start:.2f} seconds")

    message = client.recv(1024)

    with print_lock:
        print(f"[CLIENT {i}] Received {message.decode('utf-8')} after {time.time() - start:.2f} seconds")

    client.close()

    with print_lock:
        print(f"[CLIENT {i}] Closed connection.")

threads = [threading.Thread(target=client, args=(i,)) for i in range(10)]

for thread in threads:
    thread.start()

for thread in threads:
    thread.join()