import socket

HOST = 'localhost'
PORT = 1453
server = socket.socket(socket.AF_INET, socket.SOCK_STREAM) # SOCK_STREAM is basically TCP
                                                           # DGRAM would be UDP

server.bind((HOST, PORT))
print(f"Server bound on {HOST}:{PORT}")

server.listen()
print(f"Server: Listening on {HOST}:{PORT}")

conn, address = server.accept()
message = conn.recv(1024) # Buffersize set to 1024 Bytes.
                          # Receivve up to 1024 Bytes.
print(f"Server: Message {message.decode('utf-8')} received from {address}")

conn.close()
print("Server: Connection closed")

server.close()
print("Server: closed")