import socket

HOST = 'localhost'
PORT = 1453
client = socket.socket(socket.AF_INET, socket.SOCK_STREAM) # SOCK_STREAM is basically TCP
                                                           # DGRAM would be UDP
#client.bind((HOST, PORT)) # bind is for servers to claim a port.
client.connect((HOST, PORT))
print(f"Client: Connected to {HOST}:{PORT}")

message = 'Hello'
client.send(message.encode('utf-8'))
print(f"Client: Message {message} sent")

client.close()
print("Client: Connectin closed.")

