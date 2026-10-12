"""
Dual Glove Receiver Module
Listens for Wi-Fi UDP (and Bluetooth/Serial) telemetry from both Left and Right ESP32 gloves,
time-synchronizes readings, applies calibration scaling, and generates 28-dimensional feature vectors.
"""
import socket
import json
import time
import math
import threading
import logging
from typing import Dict, Any, Optional, Tuple, List
import numpy as np
import config

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("GloveReceiver")

class PalmOrientationTracker:
    """
    Computes real-time Palm Orientation using a 6-DOF / 9-DOF Complementary Filter.
    Mounting configuration on dorsal side of the hand:
    - +Y axis points AWAY from finger tips (towards wrist / forearm)
    - +X axis points to the LEFT side of the right hand (towards thumb on right hand)
    - +Z axis points UP away from the dorsal surface of the hand
    """
    def __init__(self, hand: str = "RIGHT"):
        self.hand = hand.upper()
        self.pitch_deg = 0.0
        self.roll_deg = 0.0
        self.yaw_deg = 0.0
        self.last_ts = time.time()
        self.alpha = 0.94  # 94% gyro rate integration, 6% gravity reference
        self.initialized = False

    def update(self, accel: list, gyro: list, mag: list) -> Tuple[float, float, float, str]:
        now = time.time()
        dt = max(0.001, min(0.1, now - self.last_ts))
        self.last_ts = now

        ax, ay, az = float(accel[0]), float(accel[1]), float(accel[2])
        gx, gy, gz = float(gyro[0]), float(gyro[1]), float(gyro[2])
        mx, my, mz = float(mag[0]), float(mag[1]), float(mag[2])

        # 1. Accelerometer Tilt (Gravity vector reference)
        # At flat rest: az ~ +1g (+16384), ax ~ 0, ay ~ 0
        a_norm = math.sqrt(ax * ax + ay * ay + az * az)
        if a_norm > 100.0:
            # +Y points towards wrist: when fingers tilt up, normal force pushes -Y -> ay is negative.
            # Thus -ay is positive for fingers UP.
            acc_pitch = math.degrees(math.atan2(-ay, math.sqrt(ax * ax + az * az)))
            # Roll around Y axis:
            # When palm faces left (thumb UP on right hand), +X points up -> ax is positive.
            acc_roll = math.degrees(math.atan2(ax, az if abs(az) > 1.0 else (1.0 if az >= 0 else -1.0)))
        else:
            acc_pitch = self.pitch_deg
            acc_roll = self.roll_deg

        if not self.initialized:
            self.pitch_deg = acc_pitch
            self.roll_deg = acc_roll
            self.initialized = True
            desc = self.get_palm_orientation_desc(self.pitch_deg, self.roll_deg)
            return self.pitch_deg, self.roll_deg, self.yaw_deg, desc

        # 2. Gyroscope Angular Rate (131.0 LSB per deg/s for MPU-9250 +-250dps)
        gx_dps = gx / 131.0
        gy_dps = gy / 131.0
        gz_dps = gz / 131.0

        # Integration:
        # gx = pitch rate (fingers tilting up/down)
        # gy = roll rate (palm twisting inward/outward)
        # gz = yaw rate (waving hand left/right)
        gyro_pitch = self.pitch_deg + gx_dps * dt
        gyro_roll = self.roll_deg + gy_dps * dt
        gyro_yaw = self.yaw_deg + gz_dps * dt

        # 3. Complementary Fusion
        self.pitch_deg = self.alpha * gyro_pitch + (1.0 - self.alpha) * acc_pitch
        self.roll_deg = self.alpha * gyro_roll + (1.0 - self.alpha) * acc_roll

        # Heading / Yaw from magnetometer if active, else gyro
        m_norm = math.sqrt(mx * mx + my * my + mz * mz)
        if m_norm > 15.0:
            mag_yaw = math.degrees(math.atan2(mx, -my))
            dyaw = (mag_yaw - gyro_yaw + 180.0) % 360.0 - 180.0
            self.yaw_deg = gyro_yaw + (1.0 - self.alpha) * dyaw
        else:
            self.yaw_deg = (gyro_yaw + 180.0) % 360.0 - 180.0

        # Constrain pitch and roll
        self.pitch_deg = max(-90.0, min(90.0, self.pitch_deg))
        self.roll_deg = (self.roll_deg + 180.0) % 360.0 - 180.0

        desc = self.get_palm_orientation_desc(self.pitch_deg, self.roll_deg)
        return self.pitch_deg, self.roll_deg, self.yaw_deg, desc

    def zero_to_vertical(self) -> Tuple[float, float, float, str]:
        """Tare orientation to vertical calibration pose: fingertips pointing UP at 90°, palm facing PC."""
        self.pitch_deg = 90.0
        self.roll_deg = 0.0
        self.yaw_deg = 0.0
        self.initialized = True
        return 90.0, 0.0, 0.0, "PALM FORWARD (Vertical)"

    def get_palm_orientation_desc(self, pitch: float, roll: float) -> str:
        """Classifies semantic palm facing direction for sign language analysis."""
        if pitch > 50.0:
            if -40.0 <= roll <= 40.0:
                return "PALM FORWARD (Vertical)"
            elif 40.0 < roll < 140.0:
                return "PALM INWARD / LEFT"
            elif -140.0 < roll < -40.0:
                return "PALM OUTWARD / RIGHT"
            else:
                return "PALM TOWARD CHEST"
        elif pitch < -50.0:
            return "PALM DOWNWARD (Vert)"
        else:
            # Approximately horizontal (pitch between -50° and +50°)
            if -45.0 <= roll <= 45.0:
                return "PALM DOWN (Flat Rest)"
            elif 45.0 < roll < 135.0:
                return "PALM LEFT (Edge-on / Thumb Up)"
            elif -135.0 < roll < -45.0:
                return "PALM RIGHT (Edge-on / Thumb Down)"
            else:
                return "PALM UP (Supine)"

class DualGloveReceiver:
    def __init__(self, port: int = config.DEFAULT_UDP_PORT):
        self.port = port
        self.running = False
        self.socket: Optional[socket.socket] = None
        self.thread: Optional[threading.Thread] = None
        self.lock = threading.Lock()

        # Orientation Trackers per hand
        self.left_orientation = PalmOrientationTracker("LEFT")
        self.right_orientation = PalmOrientationTracker("RIGHT")

        # Calibration data (min/max raw ADC per finger for normalization: 0=flat, 1=bent)
        self.calibration = self.load_default_calibration()

        # Telemetry State per hand
        self.left_state: Dict[str, Any] = self._empty_hand_state("LEFT")
        self.right_state: Dict[str, Any] = self._empty_hand_state("RIGHT")

        # Packet counters for FPS calculation
        self.left_packet_count = 0
        self.right_packet_count = 0
        self.left_fps = 0.0
        self.right_fps = 0.0
        self.last_fps_calc = time.time()

        # Simulation Mode (for testing without physical hardware)
        self.simulation_mode = False
        self.sim_thread: Optional[threading.Thread] = None

        # Track explicit user connection state per hand (No auto-connect on boot)
        self.active_connections = {"LEFT": False, "RIGHT": False}
        self.connected_ips = {"LEFT": None, "RIGHT": None}

        # Track Ping RTT per hand
        self.ping_results = {
            "LEFT": {"success": False, "rtt_ms": 0.0, "last_ping": 0.0, "status": "Idle"},
            "RIGHT": {"success": False, "rtt_ms": 0.0, "last_ping": 0.0, "status": "Idle"}
        }

    def _empty_hand_state(self, hand: str) -> Dict[str, Any]:
        return {
            "hand": hand,
            "connected": False,
            "last_seen": 0.0,
            "seq": 0,
            "flex_raw": [2800, 2800, 2800, 2800, 2800],
            "flex_norm": [0.0, 0.0, 0.0, 0.0, 0.0],  # Neutral/flat rest position (0.0)
            "accel": [0.0, 0.0, 9.81],
            "gyro": [0.0, 0.0, 0.0],
            "mag": [0.0, 0.0, 0.0],
            "pitch_deg": 0.0,
            "roll_deg": 0.0,
            "yaw_deg": 0.0,
            "palm_orientation": "PALM DOWN (Flat Rest)",
            "ip_addr": None
        }

    def load_default_calibration(self) -> Dict[str, Any]:
        """Load saved calibration or fallback to defaults."""
        if config.CALIBRATION_JSON_PATH.exists():
            try:
                with open(config.CALIBRATION_JSON_PATH, "r") as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"Could not load calibration file: {e}")

        # Default: ADC raw ~2800 flat, ~1200 bent
        return {
            "LEFT": {
                "flex_flat": [2800, 2800, 2800, 2800, 2800],
                "flex_bent": [1200, 1200, 1200, 1200, 1200]
            },
            "RIGHT": {
                "flex_flat": [2800, 2800, 2800, 2800, 2800],
                "flex_bent": [1200, 1200, 1200, 1200, 1200]
            }
        }

    def save_calibration(self, new_cal: Dict[str, Any]):
        """Persist calibration parameters."""
        self.calibration = new_cal
        try:
            with open(config.CALIBRATION_JSON_PATH, "w") as f:
                json.dump(new_cal, f, indent=2)
            logger.info("Saved calibration profile.")
        except Exception as e:
            logger.error(f"Failed to save calibration: {e}")

    def normalize_flex(self, hand: str, raw_flex: list) -> list:
        """Map raw ADC counts to [0.0 (flat), 1.0 (fully bent)]."""
        cal = self.calibration.get(hand, {})
        flat = cal.get("flex_flat", [2800] * 5)
        bent = cal.get("flex_bent", [1200] * 5)

        norm = []
        for i in range(5):
            f_val = flat[i]
            b_val = bent[i]
            diff = f_val - b_val
            if abs(diff) < 50:
                diff = 1000  # Avoid division by zero
            # In our voltage divider, higher resistance (bent) = lower voltage = lower ADC
            ratio = (f_val - raw_flex[i]) / float(diff)
            norm.append(float(np.clip(ratio, 0.0, 1.0)))
        return norm

    def start(self):
        """Start UDP listener socket thread."""
        if self.running:
            return

        self.running = True
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            except Exception:
                pass
            if hasattr(socket, "SIO_UDP_CONNRESET"):
                try:
                    self.socket.ioctl(socket.SIO_UDP_CONNRESET, False)
                except Exception:
                    pass
            self.socket.bind((config.DEFAULT_UDP_HOST, self.port))
            self.socket.settimeout(0.5)
            logger.info(f"UDP Receiver listening on 0.0.0.0:{self.port}")
        except Exception as e:
            logger.error(f"Failed to bind UDP socket on port {self.port}: {e}")
            self.running = False
            return

        self.thread = threading.Thread(target=self._listen_loop, daemon=True)
        self.thread.start()

    def stop(self):
        """Stop receiver thread and release socket."""
        self.running = False
        if self.thread:
            self.thread.join(timeout=1.0)
        if self.socket:
            try:
                self.socket.close()
            except Exception:
                pass
        self.stop_simulation()
        logger.info("UDP Receiver stopped.")

    def _listen_loop(self):
        while self.running:
            try:
                data, addr = self.socket.recvfrom(config.UDP_BUFFER_SIZE)
                text = data.decode("utf-8", errors="ignore").strip()
                self._process_raw_packet(text, addr[0])
            except socket.timeout:
                pass
            except Exception as e:
                if self.running:
                    logger.debug(f"Packet read error: {e}")

            self._update_connection_status()

    def _process_raw_packet(self, text: str, ip_addr: str):
        # Handle cases where multiple JSON objects arrive concatenated
        lines = text.split("\n")
        for line in lines:
            line = line.strip()
            if not line.startswith("{") or not line.endswith("}"):
                continue
            try:
                packet = json.loads(line)
                hand = packet.get("hand", "").upper()
                if hand not in ["LEFT", "RIGHT"]:
                    continue

                # Check for PONG / CONNECTED reply
                if packet.get("pong") or packet.get("cmd") in ["PONG", "CONNECTED"]:
                    with self.lock:
                        sent_ts = packet.get("echo_ts", 0.0)
                        rtt = (time.time() - sent_ts) * 1000.0 if sent_ts > 0 else 5.0
                        self.ping_results[hand]["success"] = True
                        self.ping_results[hand]["rtt_ms"] = max(1.0, rtt)
                        self.ping_results[hand]["last_ping"] = time.time()
                        self.ping_results[hand]["status"] = f"Connected ({rtt:.1f}ms)"
                        if self.active_connections[hand]:
                            target_state = self.left_state if hand == "LEFT" else self.right_state
                            target_state["connected"] = True
                            target_state["last_seen"] = time.time()
                            target_state["ip_addr"] = packet.get("ip", ip_addr)
                    continue

                raw_flex = packet.get("flex", [2800]*5)
                accel = packet.get("accel", [0, 0, 0])
                gyro = packet.get("gyro", [0, 0, 0])
                mag = packet.get("mag", [0, 0, 0])
                seq = packet.get("seq", 0)

                # Normalize flex values
                norm_flex = self.normalize_flex(hand, raw_flex)

                # Compute real-time Palm Orientation with complementary filter
                tracker = self.left_orientation if hand == "LEFT" else self.right_orientation
                pitch_d, roll_d, yaw_d, palm_desc = tracker.update(accel, gyro, mag)

                with self.lock:
                    # Do not auto-accept packets if user has not clicked Connect for this glove
                    if not self.active_connections[hand]:
                        continue

                    target_state = self.left_state if hand == "LEFT" else self.right_state
                    target_state["connected"] = True
                    target_state["last_seen"] = time.time()
                    target_state["seq"] = seq
                    target_state["flex_raw"] = raw_flex
                    target_state["flex_norm"] = norm_flex
                    target_state["accel"] = accel
                    target_state["gyro"] = gyro
                    target_state["mag"] = mag
                    target_state["pitch_deg"] = pitch_d
                    target_state["roll_deg"] = roll_d
                    target_state["yaw_deg"] = yaw_d
                    target_state["palm_orientation"] = palm_desc
                    target_state["ip_addr"] = packet.get("ip", ip_addr)

                    if hand == "LEFT":
                        self.left_packet_count += 1
                    else:
                        self.right_packet_count += 1

            except Exception as e:
                logger.debug(f"JSON decode failure: {e}")

    def send_udp_cmd(self, ip: str, port: int, payload: dict):
        """Send a JSON command packet to a glove IP."""
        if not ip:
            return
        try:
            msg = json.dumps(payload).encode("utf-8") + b"\n"
            # Prefer using our listening socket so the source port is 5005,
            # allowing ESP32 to reply directly to the same port.
            if self.socket and self.running:
                self.socket.sendto(msg, (ip, port))
            else:
                sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                try:
                    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
                except Exception:
                    pass
                sock.sendto(msg, (ip, port))
                sock.close()
        except Exception as e:
            logger.error(f"Failed to send UDP command to {ip}:{port}: {e}")

    def connect_glove(self, hand: str, ip: str, port: int = config.DEFAULT_UDP_PORT, timeout: float = 4.0) -> Tuple[bool, str]:
        """Send connection handshake to glove IP and wait for incoming telemetry or PONG."""
        hand = hand.upper()
        if not ip or not ip.strip():
            return False, "IP address is empty"

        ip_clean = ip.strip()
        now = time.time()
        with self.lock:
            self.ping_results[hand]["status"] = "Connecting..."
            self.ping_results[hand]["success"] = False
            self.active_connections[hand] = True
            self.connected_ips[hand] = ip_clean

        # Send CONNECT command directly to glove IP and subnet broadcast
        payload = {"cmd": "CONNECT", "hand": hand, "ts": now, "echo_ts": now}
        self.send_udp_cmd(ip_clean, port, payload)
        try:
            parts = ip_clean.split(".")
            if len(parts) == 4:
                self.send_udp_cmd(f"{parts[0]}.{parts[1]}.{parts[2]}.255", port, payload)
        except Exception:
            pass

        start_time = time.time()
        last_retry = start_time
        while time.time() - start_time < timeout:
            with self.lock:
                target_state = self.left_state if hand == "LEFT" else self.right_state
                # Check if telemetry is arriving or handshake confirmation arrived
                if target_state["connected"] and (time.time() - target_state["last_seen"] < 2.0):
                    fps = self.left_fps if hand == "LEFT" else self.right_fps
                    status_str = f"Active ({fps:.0f} Hz)" if fps > 0 else "Active (Connected)"
                    self.ping_results[hand]["success"] = True
                    self.ping_results[hand]["status"] = status_str
                    return True, status_str
                if self.ping_results[hand]["success"] and (time.time() - self.ping_results[hand]["last_ping"] < 2.5):
                    rtt = self.ping_results[hand]["rtt_ms"]
                    target_state["connected"] = True
                    target_state["last_seen"] = time.time()
                    target_state["ip_addr"] = ip_clean
                    status_str = f"Connected ({rtt:.1f}ms)"
                    return True, status_str

            # Retry handshake packet every 0.4s
            if time.time() - last_retry >= 0.4:
                self.send_udp_cmd(ip_clean, port, payload)
                try:
                    parts = ip_clean.split(".")
                    if len(parts) == 4:
                        self.send_udp_cmd(f"{parts[0]}.{parts[1]}.{parts[2]}.255", port, payload)
                except Exception:
                    pass
                last_retry = time.time()

            time.sleep(0.04)

        with self.lock:
            self.ping_results[hand]["success"] = False
            self.ping_results[hand]["status"] = "Connection Failed"
            self.active_connections[hand] = False
            self.connected_ips[hand] = None
            target_state = self.left_state if hand == "LEFT" else self.right_state
            target_state["connected"] = False
        return False, f"No response from {ip_clean}:{port} (Check ESP32 power & Wi-Fi)"

    def disconnect_glove(self, hand: str) -> None:
        """Manually mark glove as disconnected and send DISCONNECT command."""
        hand = hand.upper()
        ip = self.connected_ips.get(hand)
        if ip:
            self.send_udp_cmd(ip, config.DEFAULT_UDP_PORT, {"cmd": "DISCONNECT", "hand": hand})
        with self.lock:
            self.active_connections[hand] = False
            self.connected_ips[hand] = None
            target_state = self.left_state if hand == "LEFT" else self.right_state
            target_state["connected"] = False
            target_state["last_seen"] = 0.0
            self.ping_results[hand]["success"] = False
            self.ping_results[hand]["status"] = "Disconnected"
        logger.info(f"{hand} glove disconnected.")


    def tare_orientation_vertical(self, hand: str = "RIGHT") -> None:
        """Tare orientation tracker for a glove to vertical reference pose (fingertips UP at 90°, palm facing PC)."""
        hand = hand.upper()
        tracker = self.left_orientation if hand == "LEFT" else self.right_orientation
        p, r, y, desc = tracker.zero_to_vertical()
        with self.lock:
            target_state = self.left_state if hand == "LEFT" else self.right_state
            target_state["pitch_deg"] = p
            target_state["roll_deg"] = r
            target_state["yaw_deg"] = y
            target_state["palm_orientation"] = desc
        logger.info(f"{hand} glove orientation tared to Vertical reference (Pitch: +90°, Roll: 0°).")

    def ping_glove(self, hand: str, ip: str, port: int = config.DEFAULT_UDP_PORT, timeout: float = 1.0) -> Tuple[bool, str]:
        """Send a Ping command to the glove and check network reachability."""
        hand = hand.upper()
        if not ip or not ip.strip():
            return False, "IP address is empty"

        ip_clean = ip.strip()
        now = time.time()
        with self.lock:
            self.ping_results[hand]["status"] = "Pinging..."
            self.ping_results[hand]["success"] = False

        payload = {"cmd": "PING", "hand": hand, "ts": now}
        self.send_udp_cmd(ip_clean, port, payload)
        try:
            parts = ip_clean.split(".")
            if len(parts) == 4:
                self.send_udp_cmd(f"{parts[0]}.{parts[1]}.{parts[2]}.255", port, payload)
        except Exception:
            pass

        start_time = time.time()
        while time.time() - start_time < timeout:
            with self.lock:
                target_state = self.left_state if hand == "LEFT" else self.right_state
                if target_state["connected"] and target_state.get("ip_addr") == ip_clean:
                    fps = self.left_fps if hand == "LEFT" else self.right_fps
                    status = f"Online ({fps:.0f} Hz)" if fps > 0 else "Online"
                    self.ping_results[hand]["success"] = True
                    self.ping_results[hand]["status"] = status
                    return True, status
                elif self.ping_results[hand]["success"] and (time.time() - self.ping_results[hand]["last_ping"] < 2.0):
                    return True, f"Online ({self.ping_results[hand]['rtt_ms']:.1f}ms)"
            time.sleep(0.05)

        with self.lock:
            self.ping_results[hand]["success"] = False
            self.ping_results[hand]["status"] = "No Response"
        return False, "No Response"

    def blink_glove_led(self, hand: str, ip: str, port: int = config.DEFAULT_UDP_PORT):
        """Send a BLINK command to trigger physical ESP32 onboard LED flashing."""
        if not ip or not ip.strip():
            return
        payload = {"cmd": "BLINK", "hand": hand.upper()}
        self.send_udp_cmd(ip.strip(), port, payload)
        logger.info(f"Sent BLINK LED command to {hand} glove at {ip}:{port}")


    def _update_connection_status(self):
        now = time.time()
        # FPS Calculation
        dt = now - self.last_fps_calc
        if dt >= 1.0:
            with self.lock:
                self.left_fps = self.left_packet_count / dt
                self.right_fps = self.right_packet_count / dt
                self.left_packet_count = 0
                self.right_packet_count = 0
                self.last_fps_calc = now

                # Timeout disconnection check
                if now - self.left_state["last_seen"] > config.TELEMETRY_TIMEOUT_SEC:
                    self.left_state["connected"] = False
                if now - self.right_state["last_seen"] > config.TELEMETRY_TIMEOUT_SEC:
                    self.right_state["connected"] = False

    def get_latest_states(self) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """Return thread-safe snapshot of both hand telemetry states."""
        with self.lock:
            return dict(self.left_state), dict(self.right_state)

    def get_synchronized_feature_vector(self, hand_mode: str = "both") -> np.ndarray:
        """
        Produce feature vector according to hand_mode:
        - "both" / "dual": 28 features (14 Left + 14 Right)
        - "right" / "one_hand_right": 14 features (Right Glove only)
        - "left" / "one_hand_left": 14 features (Left Glove only)
        """
        with self.lock:
            l = self.left_state
            r = self.right_state

            l_vec = [
                *l["flex_norm"],
                l["accel"][0] / 16384.0, l["accel"][1] / 16384.0, l["accel"][2] / 16384.0,
                l["gyro"][0] / 131.0,   l["gyro"][1] / 131.0,   l["gyro"][2] / 131.0,
                l["mag"][0] / 100.0,    l["mag"][1] / 100.0,    l["mag"][2] / 100.0,
            ]
            r_vec = [
                *r["flex_norm"],
                r["accel"][0] / 16384.0, r["accel"][1] / 16384.0, r["accel"][2] / 16384.0,
                r["gyro"][0] / 131.0,   r["gyro"][1] / 131.0,   r["gyro"][2] / 131.0,
                r["mag"][0] / 100.0,    r["mag"][1] / 100.0,    r["mag"][2] / 100.0
            ]

            mode_lower = str(hand_mode).lower().strip()
            if mode_lower in ["right", "right_hand", "one_hand_right", "1_hand_right", "1-hand (right)", "1_hand"]:
                return np.array(r_vec, dtype=np.float32)
            elif mode_lower in ["left", "left_hand", "one_hand_left", "1_hand_left", "1-hand (left)"]:
                return np.array(l_vec, dtype=np.float32)
            else:
                return np.array(l_vec + r_vec, dtype=np.float32)

    def get_motion_metrics(self, hand_mode: str = "right") -> Dict[str, Any]:
        """
        Calculate real-time kinematic motion metrics (angular velocity and dynamic acceleration)
        to determine whether the hand is holding a static pose or performing dynamic gesture motion.
        """
        with self.lock:
            l = self.left_state
            r = self.right_state

            mode_lower = str(hand_mode).lower().strip()
            if mode_lower in ["left", "left_hand", "one_hand_left", "1_hand_left"]:
                gx, gy, gz = l["gyro"]
                ax, ay, az = l["accel"]
            elif mode_lower in ["right", "right_hand", "one_hand_right", "1_hand"]:
                gx, gy, gz = r["gyro"]
                ax, ay, az = r["accel"]
            else:
                # dual / both: take maximum motion energy between the two hands
                lg_norm = math.sqrt(l["gyro"][0]**2 + l["gyro"][1]**2 + l["gyro"][2]**2)
                rg_norm = math.sqrt(r["gyro"][0]**2 + r["gyro"][1]**2 + r["gyro"][2]**2)
                if lg_norm > rg_norm:
                    gx, gy, gz = l["gyro"]
                    ax, ay, az = l["accel"]
                else:
                    gx, gy, gz = r["gyro"]
                    ax, ay, az = r["accel"]

            omega = math.sqrt(gx*gx + gy*gy + gz*gz) / 131.0
            a_mag = math.sqrt(ax*ax + ay*ay + az*az)
            lin_accel_g = abs(a_mag - 16384.0) / 16384.0 if a_mag > 100 else 0.0

            # Kinematic motion thresholds:
            # Steady rest / pose: omega < 28 deg/s and lin_accel_g < 0.22g
            is_moving = (omega > 28.0) or (lin_accel_g > 0.22)

            return {
                "angular_velocity_dps": round(omega, 1),
                "linear_accel_g": round(lin_accel_g, 2),
                "is_moving": is_moving,
                "motion_category": "DYNAMIC" if is_moving else "STATIC",
                "motion_desc": f"In Motion ({omega:.1f}°/s)" if is_moving else f"Steady Pose ({omega:.1f}°/s)"
            }

    # ==========================================
    # Simulation Support (for quick testing/demo)
    # ==========================================
    def start_simulation(self):
        """Simulate active gloves with synthetic waving/bending signals."""
        if self.simulation_mode:
            return
        self.simulation_mode = True
        self.sim_thread = threading.Thread(target=self._sim_loop, daemon=True)
        self.sim_thread.start()
        logger.info("Hardware Simulation mode started.")

    def stop_simulation(self):
        self.simulation_mode = False
        if self.sim_thread:
            self.sim_thread.join(timeout=0.5)

    def _sim_loop(self):
        t = 0.0
        while self.simulation_mode and self.running:
            time.sleep(0.02) # 50Hz
            t += 0.02
            # Synthesize oscillating finger and IMU signals
            l_flex_norm = [
                0.2 + 0.3 * np.sin(t * 1.5 + 0),
                0.5 + 0.4 * np.sin(t * 2.0 + 1),
                0.4 + 0.4 * np.sin(t * 2.1 + 2),
                0.3 + 0.3 * np.sin(t * 1.8 + 3),
                0.2 + 0.2 * np.sin(t * 1.9 + 4)
            ]
            r_flex_norm = [
                0.1 + 0.4 * np.cos(t * 1.7 + 0),
                0.6 + 0.3 * np.cos(t * 2.2 + 1),
                0.5 + 0.4 * np.cos(t * 2.0 + 2),
                0.2 + 0.3 * np.cos(t * 1.6 + 3),
                0.1 + 0.2 * np.cos(t * 1.5 + 4)
            ]

            now = time.time()
            l_p, l_r, l_y, l_desc = self.left_orientation.update(
                [int(2000 * np.sin(t)), int(1000 * np.cos(t)), 16000],
                [int(500 * np.sin(t * 3)), int(400 * np.cos(t * 2)), 0],
                [120, -80, 240]
            )
            r_p, r_r, r_y, r_desc = self.right_orientation.update(
                [int(-1500 * np.cos(t)), int(1800 * np.sin(t)), 16200],
                [int(300 * np.cos(t * 2)), int(-500 * np.sin(t * 2)), 0],
                [-90, 140, 210]
            )

            with self.lock:
                self.left_state["connected"] = True
                self.left_state["last_seen"] = now
                self.left_state["flex_norm"] = [float(np.clip(v, 0, 1)) for v in l_flex_norm]
                self.left_state["flex_raw"] = [int(2800 - v * 1600) for v in self.left_state["flex_norm"]]
                self.left_state["accel"] = [int(2000 * np.sin(t)), int(1000 * np.cos(t)), 16000]
                self.left_state["gyro"] = [int(500 * np.sin(t * 3)), int(400 * np.cos(t * 2)), 0]
                self.left_state["mag"] = [120, -80, 240]
                self.left_state["pitch_deg"] = l_p
                self.left_state["roll_deg"] = l_r
                self.left_state["yaw_deg"] = l_y
                self.left_state["palm_orientation"] = l_desc
                self.left_state["ip_addr"] = "127.0.0.1 (SIM)"

                self.right_state["connected"] = True
                self.right_state["last_seen"] = now
                self.right_state["flex_norm"] = [float(np.clip(v, 0, 1)) for v in r_flex_norm]
                self.right_state["flex_raw"] = [int(2800 - v * 1600) for v in self.right_state["flex_norm"]]
                self.right_state["accel"] = [int(-1500 * np.cos(t)), int(1800 * np.sin(t)), 16200]
                self.right_state["gyro"] = [int(300 * np.cos(t * 2)), int(-500 * np.sin(t * 2)), 0]
                self.right_state["mag"] = [-90, 140, 210]
                self.right_state["pitch_deg"] = r_p
                self.right_state["roll_deg"] = r_r
                self.right_state["yaw_deg"] = r_y
                self.right_state["palm_orientation"] = r_desc
                self.right_state["ip_addr"] = "127.0.0.1 (SIM)"

                self.left_packet_count += 1
                self.right_packet_count += 1
