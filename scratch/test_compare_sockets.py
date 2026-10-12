import socket
import json
import time

target_ip = "192.168.205.82"
target_port = 5005
payload = json.dumps({"cmd": "PING", "action": "CONNECT", "hand": "RIGHT", "ts": time.time()}).encode("utf-8") + b"\n"

print("--- Test A: Unbound socket (ephemeral port) ---")
s_a = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
s_a.settimeout(2.0)
s_a.sendto(payload, (target_ip, target_port))
print(f"s_a sent from {s_a.getsockname()}")
try:
    data, addr = s_a.recvfrom(2048)
    print(f"s_a RECEIVED: {data[:60]} from {addr}")
except Exception as e:
    print(f"s_a failed: {e}")
s_a.close()

print("\n--- Test B: Socket bound to 0.0.0.0:5005 ---")
s_b = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
s_b.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
s_b.bind(("0.0.0.0", 5005))
s_b.settimeout(2.0)
s_b.sendto(payload, (target_ip, target_port))
print(f"s_b sent from {s_b.getsockname()}")
try:
    data, addr = s_b.recvfrom(2048)
    print(f"s_b RECEIVED: {data[:60]} from {addr}")
except Exception as e:
    print(f"s_b failed: {e}")
s_b.close()
