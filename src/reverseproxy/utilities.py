PORT = 0

def get_freeport():
    global PORT
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    while PORT <= 65_535:
        print(f"PORT: {PORT}")
        try:
            print(sock.connect(('127.0.0.1', PORT)))
            break
        # except ConnectionRefusedError:
        except:
            PORT += 1
    print(f"PORT: {PORT}")
    return PORT

if __name__ == '__main__':
    import time, socket

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect(('127.0.0.1', 8384))

    # get_freeport()