import socket

HOST = 'localhost'
PORT = 1453
client = socket.socket(socket.AF_INET, socket.SOCK_STREAM) # SOCK_STREAM is basically TCP
                                                           # DGRAM would be UDP
#client.bind((HOST, PORT)) # bind is for servers to claim a port.
client.connect((HOST, PORT))
print(f"[CLIENT] Connected to {HOST}:{PORT}")

message = 'PING'
client.send(message.encode('utf-8'))
print(f"[CLIENT] Sent {message}")

message = client.recv(1024)
print(f"[CLIENT] Received {message.decode('utf-8')}")

client.close()
print('[CLIENT] Connection closed.')