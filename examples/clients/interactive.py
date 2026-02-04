import socket

with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as client:
    client.connect(('localhost', 1453))
    while True:
        message = input('[CLIENT] Enter message: ')

        if not message:
            print('[CLIENT] Cannot send empty message, try again.')
            continue

        message += '\n'
        client.send(message.encode('utf-8'))
        message = client.recv(1024)

        if not message:
            print('[CLIENT] Server disconnected')
            break

        print(f"[CLIENT] Received: {message.decode('utf-8')}")
    client.close()