import sys, time

time.sleep(5)
print(f"ECHO {' '.join(sys.argv[1:])}" if len(sys.argv) > 1 else 'ECHO No arguments were ', end='')