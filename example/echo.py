import sys
import time

time.sleep(3)
print(f"ECHO {' '.join(sys.argv[1:])}" if len(sys.argv) > 1 else 'ECHO')