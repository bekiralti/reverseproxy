import socket

with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as client:
    client.connect(('localhost', 1453))
    while True:
        client.send(input('[CLIENT] Enter message: ').encode('utf-8'))
        print(f"[CLIENT] Received: {client.recv(1024).decode('utf-8')}, from proc-id")