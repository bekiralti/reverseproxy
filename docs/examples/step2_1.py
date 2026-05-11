import socket
from socket import AF_INET, SOCK_STREAM

with socket.socket(AF_INET, SOCK_STREAM) as s:
    print("Binding socket")
    s.bind(('0.0.0.0', 1453))
    s.listen()
    print("Waiting for a connection")
    while True:
        conn, addr = s.accept()
        with conn:
            print(f"Connected by {addr}")
            while True:
                message = conn.recv(1024)
                print(message)
                if not message:
                    break