import socket
import json
import time

target_ip = "192.168.205.82"
target_port = 5005

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
sock.settimeout(2.0)

payload = {"cmd": "PING", "action": "CONNECT", "hand": "RIGHT", "ts": time.time()}
msg = json.dumps(payload).encode("utf-8") + b"\n"

print(f"Sending PING to {target_ip}:{target_port}...")
sock.sendto(msg, (target_ip, target_port))

try:
    data, addr = sock.recvfrom(2048)
    print(f"SUCCESS! Received response from {addr}: {data.decode('utf-8', errors='ignore')}")
except socket.timeout:
    print(f"TIMED OUT! No response received on port {sock.getsockname()[1]} within 2 seconds.")
finally:
    sock.close()
