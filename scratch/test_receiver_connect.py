import sys
sys.path.insert(0, 'software')
from receiver import DualGloveReceiver
import time

r = DualGloveReceiver()
r.start()
print("Started receiver on 0.0.0.0:5005")

print("Connecting to RIGHT glove 192.168.205.82...")
success, msg = r.connect_glove("RIGHT", "192.168.205.82", timeout=3.0)
print(f"connect_glove result: success={success}, msg={msg}")

print("Listening for 2 seconds to see incoming telemetry packets...")
time.sleep(2.0)
l_s, r_s = r.get_latest_states()
print(f"Right connected: {r_s['connected']}, last_seen: {r_s['last_seen']}, fps: {r.right_fps}")
print(f"Flex raw: {r_s['flex_raw']}, Accel: {r_s['accel']}, Gyro: {r_s['gyro']}")
print(f"Orientation: Pitch={r_s['pitch_deg']:.1f}, Roll={r_s['roll_deg']:.1f}, Palm={r_s['palm_orientation']}")

r.stop()
