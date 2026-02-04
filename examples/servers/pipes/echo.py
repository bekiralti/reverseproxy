import sys

while True:
    message: str = sys.stdin.readline()

    if not message:
        message = 'No message'

    message = 'ECHO ' + message
    sys.stdout.write(message.strip())