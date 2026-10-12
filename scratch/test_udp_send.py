import socket
import json
import time

s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
payload = {
    "hand": "RIGHT",
    "id": 1,
    "ip": "192.168.1.50",
    "ts": int(time.time() * 1000),
    "seq": 1,
    "flex": [2500, 2400, 2600, 2550, 2480],
    "accel": [100, 200, 9800],
    "gyro": [10, -5, 2],
    "mag": [50, 20, -10]
}
msg = (json.dumps(payload) + "\n").encode("utf-8")
s.sendto(msg, ("127.0.0.1", 5005))
print("Packet sent successfully!")
s.close()
