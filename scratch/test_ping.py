import socket
import json
import time

target_ip = "192.168.205.82"
target_port = 5005

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
sock.settimeout(2.5)

# Test 1: Sending from ephemeral port
payload = json.dumps({"cmd": "PING", "action": "CONNECT", "hand": "RIGHT", "ts": time.time()}).encode("utf-8") + b"\n"
print(f"Sending PING to {target_ip}:{target_port}...")
sock.sendto(payload, (target_ip, target_port))
print(f"Sent from local port {sock.getsockname()[1]}")

try:
    data, addr = sock.recvfrom(2048)
    print(f"REPLY from {addr}: {data.decode('utf-8', errors='ignore')}")
except socket.timeout:
    print("No reply received on ephemeral port.")

sock.close()
