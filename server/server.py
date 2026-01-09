import socket

HOST = 'localhost'
PORT = 1453
server = socket.socket(socket.AF_INET, socket.SOCK_STREAM) # SOCK_STREAM is basically TCP
                                                           # DGRAM would be UDP
server.bind((HOST, PORT))
print(f"Server: Bound on {HOST}:{PORT}")

server.listen()
print(f"Server: Listening")

while True:
    conn, address = server.accept()
    message = conn.recv(1024) # Buffersize set to 1024 Bytes.
                              # Receive up to 1024 Bytes.
    conn.close()
    print(f"Server: Message {message.decode('utf-8')} received from {address}")