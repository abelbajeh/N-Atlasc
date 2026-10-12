"""
3D Hand Skeleton Visualizer for Dual-Glove ASL System.
Renders real-time 3D hand skeleton kinematics and MPU-9250 orientation.
Orientation accounts for MPU-9250 mounting where the +Y axis points away from fingers (towards the wrist).
"""
import math
import time
import tkinter as tk
from typing import Dict, Any, List, Tuple, Optional
import numpy as np


class OrientationCalculator:
    """
    Computes 3D orientation (Pitch, Roll, Yaw) and rotation matrix from MPU-9250 9-DOF readings.
    Mounting configuration:
    - Sensor flat on dorsal side (back of hand)
    - +Y axis points AWAY from the fingers (towards the wrist / forearm)
    - +Z axis points UP away from the dorsal surface
    - +X axis points lateral
    """
    def __init__(self):
        self.pitch = 0.0  # radians
        self.roll = 0.0   # radians
        self.yaw = 0.0    # radians
        self.last_ts = time.time()
        self.initialized = False

        # Low-pass filter smoothing factors
        self.smooth_pitch = 0.0
        self.smooth_roll = 0.0
        self.smooth_yaw = 0.0

    def update(self, accel: List[float], gyro: List[float], mag: List[float]) -> Tuple[float, float, float]:
        """
        Update orientation estimates using complementary filter fusing gyroscope rates
        and accelerometer gravity vector.
        Mounting:
        - +Y axis points away from finger tips (towards wrist)
        - +X axis points to left side of right hand (towards thumb)
        - +Z axis points UP away from dorsal surface
        """
        now = time.time()
        dt = max(0.001, min(0.1, now - self.last_ts))
        self.last_ts = now

        ax, ay, az = float(accel[0]), float(accel[1]), float(accel[2])
        gx, gy, gz = float(gyro[0]), float(gyro[1]), float(gyro[2])
        mx, my, mz = float(mag[0]), float(mag[1]), float(mag[2])

        # 1. Accelerometer tilt
        a_norm = math.sqrt(ax * ax + ay * ay + az * az)
        if a_norm > 100.0:
            # When fingers point UP, ay is negative -> -ay is positive
            acc_pitch = math.atan2(-ay, math.sqrt(ax * ax + az * az))
            acc_roll = math.atan2(ax, az if abs(az) > 1.0 else (1.0 if az >= 0 else -1.0))
        else:
            acc_pitch = self.pitch
            acc_roll = self.roll

        if not self.initialized:
            self.pitch = acc_pitch
            self.roll = acc_roll
            self.initialized = True
            return self.pitch, self.roll, self.yaw

        # 2. Gyroscope integration (rad/s)
        gx_rad = (gx / 131.0) * (math.pi / 180.0)
        gy_rad = (gy / 131.0) * (math.pi / 180.0)
        gz_rad = (gz / 131.0) * (math.pi / 180.0)

        gyro_pitch = self.pitch + gx_rad * dt
        gyro_roll = self.roll + gy_rad * dt
        gyro_yaw = self.yaw + gz_rad * dt

        # 3. Complementary filter (94% gyro rate, 6% gravity reference)
        alpha = 0.94
        self.pitch = alpha * gyro_pitch + (1.0 - alpha) * acc_pitch
        self.roll = alpha * gyro_roll + (1.0 - alpha) * acc_roll

        # Heading / Yaw from magnetometer if available
        m_norm = math.sqrt(mx * mx + my * my + mz * mz)
        if m_norm > 15.0:
            mag_yaw = math.atan2(mx, -my)
            dyaw = (mag_yaw - gyro_yaw + math.pi) % (2 * math.pi) - math.pi
            self.yaw = gyro_yaw + (1.0 - alpha) * dyaw
        else:
            self.yaw = (gyro_yaw + math.pi) % (2 * math.pi) - math.pi

        return self.pitch, self.roll, self.yaw

    def zero_to_vertical(self) -> Tuple[float, float, float]:
        """Tare orientation to vertical reference pose: fingertips UP at 90°, palm facing PC."""
        self.pitch = math.radians(90.0)
        self.roll = 0.0
        self.yaw = 0.0
        self.initialized = True
        return self.pitch, self.roll, self.yaw

    def get_palm_orientation_desc(self, pitch_deg: float, roll_deg: float) -> str:
        """Classifies semantic palm facing direction for sign language analysis."""
        if pitch_deg > 50.0:
            if -40.0 <= roll_deg <= 40.0:
                return "PALM FORWARD (Vertical)"
            elif 40.0 < roll_deg < 140.0:
                return "PALM INWARD / LEFT"
            elif -140.0 < roll_deg < -40.0:
                return "PALM OUTWARD / RIGHT"
            else:
                return "PALM TOWARD CHEST"
        elif pitch_deg < -50.0:
            return "PALM DOWNWARD (Vert)"
        else:
            if -45.0 <= roll_deg <= 45.0:
                return "PALM DOWN (Flat Rest)"
            elif 45.0 < roll_deg < 135.0:
                return "PALM LEFT (Edge-on / Thumb Up)"
            elif -135.0 < roll_deg < -45.0:
                return "PALM RIGHT (Edge-on / Thumb Down)"
            else:
                return "PALM UP (Supine)"

    def get_rotation_matrix(self, pitch_override: Optional[float] = None,
                            roll_override: Optional[float] = None,
                            yaw_override: Optional[float] = None) -> np.ndarray:
        """
        Build 3x3 rotation matrix for the hand in world space.
        Rotates from hand local coordinate frame to world frame.
        """
        p = self.pitch if pitch_override is None else pitch_override
        r = self.roll if roll_override is None else roll_override
        y = self.yaw if yaw_override is None else yaw_override

        # Rotation matrices: Yaw (Z), Pitch (X), Roll (Y)
        cos_y, sin_y = math.cos(y), math.sin(y)
        R_z = np.array([
            [cos_y, -sin_y, 0],
            [sin_y,  cos_y, 0],
            [0,      0,     1]
        ], dtype=float)

        cos_p, sin_p = math.cos(p), math.sin(p)
        R_x = np.array([
            [1, 0,      0],
            [0, cos_p, -sin_p],
            [0, sin_p,  cos_p]
        ], dtype=float)

        cos_r, sin_r = math.cos(r), math.sin(r)
        R_y = np.array([
            [ cos_r, 0, sin_r],
            [ 0,     1, 0],
            [-sin_r, 0, cos_r]
        ], dtype=float)

        # Combined rotation: R = R_z * R_x * R_y
        return R_z @ R_x @ R_y


class HandKinematics:
    """
    Computes 3D joint and bone positions for a human hand skeleton.
    Takes 5 normalized flex readings (Thumb, Index, Middle, Ring, Pinky) [0.0 = Flat, 1.0 = Bent]
    and computes anatomical 3D coordinates for wrist, carpals, metacarpals, and phalanges.
    """
    def __init__(self):
        pass

    def compute_skeleton(self, hand_type: str, flex_norm: List[float]) -> Dict[str, Any]:
        """
        Returns dictionary of 3D points and bone connectivity.
        hand_type: "LEFT" or "RIGHT"
        flex_norm: 5 floats in [0.0, 1.0] for [Thumb, Index, Middle, Ring, Pinky]
        """
        is_left = (hand_type.upper() == "LEFT")
        # Lateral mirror multiplier: Left hand has thumb on -X, Right hand has thumb on +X
        x_sign = -1.0 if is_left else 1.0

        f_thumb  = max(0.0, min(1.0, flex_norm[0]))
        f_index  = max(0.0, min(1.0, flex_norm[1]))
        f_middle = max(0.0, min(1.0, flex_norm[2]))
        f_ring   = max(0.0, min(1.0, flex_norm[3]))
        f_pinky  = max(0.0, min(1.0, flex_norm[4]))

        points: Dict[str, np.ndarray] = {}
        bones: List[Tuple[str, str, str]] = []  # (start_key, end_key, bone_type)

        # -------------------------------------------------------------
        # 1. Wrist & Carpal Base (Origin at center of wrist)
        # -------------------------------------------------------------
        wrist_center = np.array([0.0, -25.0, 0.0])
        wrist_left   = np.array([-20.0, -32.0, 0.0])
        wrist_right  = np.array([ 20.0, -32.0, 0.0])
        carpal_mid   = np.array([0.0, -5.0, 2.0])

        points["wrist_center"] = wrist_center
        points["wrist_left"]   = wrist_left
        points["wrist_right"]  = wrist_right
        points["carpal_mid"]   = carpal_mid

        bones.append(("wrist_left", "wrist_center", "wrist"))
        bones.append(("wrist_center", "wrist_right", "wrist"))
        bones.append(("wrist_center", "carpal_mid", "carpal"))

        # -------------------------------------------------------------
        # 2. Metacarpophalangeal (MCP) Knuckle Positions
        # -------------------------------------------------------------
        # Knuckle root positions for each finger
        mcp_positions = {
            "thumb":  np.array([x_sign * 32.0,  18.0, -6.0]),
            "index":  np.array([x_sign * 18.0,  55.0,  0.0]),
            "middle": np.array([x_sign * 0.0,   60.0,  1.0]),
            "ring":   np.array([x_sign * -17.0, 55.0, -1.0]),
            "pinky":  np.array([x_sign * -32.0, 46.0, -3.0]),
        }

        # Thumb CMC base
        thumb_cmc = np.array([x_sign * 18.0, -2.0, -3.0])
        points["thumb_cmc"] = thumb_cmc
        bones.append(("carpal_mid", "thumb_cmc", "metacarpal"))
        bones.append(("thumb_cmc", "thumb_mcp", "metacarpal"))

        # Connect carpals to knuckles
        for name in ["index", "middle", "ring", "pinky"]:
            points[f"{name}_mcp"] = mcp_positions[name]
            bones.append(("carpal_mid", f"{name}_mcp", "metacarpal"))

        points["thumb_mcp"] = mcp_positions["thumb"]

        # Connect knuckles across the palm arch
        bones.append(("pinky_mcp", "ring_mcp", "palm_arch"))
        bones.append(("ring_mcp", "middle_mcp", "palm_arch"))
        bones.append(("middle_mcp", "index_mcp", "palm_arch"))

        # -------------------------------------------------------------
        # 3. Finger Kinematics (Phalanges bending)
        # -------------------------------------------------------------
        # 4 Main fingers: Index, Middle, Ring, Pinky
        finger_specs = [
            ("index",  f_index,  30.0, 20.0, 14.0, x_sign * 4.0),
            ("middle", f_middle, 34.0, 22.0, 15.0, x_sign * 0.0),
            ("ring",   f_ring,   30.0, 19.0, 14.0, x_sign * -3.0),
            ("pinky",  f_pinky,  24.0, 15.0, 12.0, x_sign * -7.0),
        ]

        for fname, flex, l1, l2, l3, splay_deg in finger_specs:
            mcp = mcp_positions[fname]

            # Bend angles at MCP, PIP, DIP joints
            # flex = 0.0 -> straight out (0 deg)
            # flex = 1.0 -> curled fist (75 deg, 85 deg, 60 deg)
            ang1 = math.radians(flex * 75.0)
            ang2 = math.radians(flex * 85.0)
            ang3 = math.radians(flex * 60.0)

            splay = math.radians(splay_deg)

            # Cumulative flexion down towards palm (-Z)
            # Joint 1: PIP (Proximal Interphalangeal)
            # Vector from MCP -> PIP
            v1 = np.array([
                math.sin(splay) * l1,
                math.cos(splay) * math.cos(ang1) * l1,
                -math.sin(ang1) * l1
            ])
            pip = mcp + v1
            points[f"{fname}_pip"] = pip
            bones.append((f"{fname}_mcp", f"{fname}_pip", "finger"))

            # Joint 2: DIP (Distal Interphalangeal)
            cum_ang2 = ang1 + ang2
            v2 = np.array([
                math.sin(splay) * l2,
                math.cos(splay) * math.cos(cum_ang2) * l2,
                -math.sin(cum_ang2) * l2
            ])
            dip = pip + v2
            points[f"{fname}_dip"] = dip
            bones.append((f"{fname}_pip", f"{fname}_dip", "finger"))

            # Joint 3: Tip
            cum_ang3 = cum_ang2 + ang3
            v3 = np.array([
                math.sin(splay) * l3,
                math.cos(splay) * math.cos(cum_ang3) * l3,
                -math.sin(cum_ang3) * l3
            ])
            tip = dip + v3
            points[f"{fname}_tip"] = tip
            bones.append((f"{fname}_dip", f"{fname}_tip", "finger"))

        # -------------------------------------------------------------
        # 4. Thumb Kinematics (Opposable flexion & adduction)
        # -------------------------------------------------------------
        t_mcp = mcp_positions["thumb"]
        l_t1, l_t2 = 22.0, 18.0

        # Thumb bends into palm (-Z) and adducts across towards the palm center (towards -x_sign)
        t_flex_ang = math.radians(f_thumb * 65.0)
        t_oppose_ang = math.radians(f_thumb * 38.0)

        # MCP -> IP (Interphalangeal)
        t_v1 = np.array([
            -x_sign * math.sin(t_oppose_ang) * l_t1 + x_sign * math.cos(math.radians(20)) * l_t1 * 0.7,
            math.cos(t_flex_ang) * l_t1 * 0.7,
            -math.sin(t_flex_ang) * l_t1 - 4.0
        ])
        t_ip = t_mcp + t_v1
        points["thumb_ip"] = t_ip
        bones.append(("thumb_mcp", "thumb_ip", "finger"))

        # IP -> Tip
        t_cum_flex = math.radians(f_thumb * 115.0)
        t_v2 = np.array([
            -x_sign * math.sin(t_oppose_ang + math.radians(15)) * l_t2,
            math.cos(t_cum_flex) * l_t2 * 0.6,
            -math.sin(t_cum_flex) * l_t2 - 2.0
        ])
        t_tip = t_ip + t_v2
        points["thumb_tip"] = t_tip
        bones.append(("thumb_ip", "thumb_tip", "finger"))

        return {
            "points": points,
            "bones": bones,
            "hand_type": hand_type,
            "flex_norm": flex_norm
        }


class HandSkeletonCanvas(tk.Canvas):
    """
    Tkinter Canvas widget that renders the 3D hand skeleton, MPU-9250 orientation gimbal,
    and interactive orbit/zoom controls.
    """
    def __init__(self, parent, width=620, height=520, bg="#0d131f", **kwargs):
        super().__init__(parent, width=width, height=height, bg=bg, highlightthickness=0, **kwargs)

        self.width = width
        self.height = height

        # Camera & View settings
        self.cam_dist = 360.0
        self.cam_pitch = math.radians(25.0)  # Camera elevation
        self.cam_yaw = math.radians(-15.0)   # Camera azimuth
        self.zoom = 1.45

        # Mouse interaction state
        self.drag_start_x = 0
        self.drag_start_y = 0
        self.is_dragging = False

        self.bind("<ButtonPress-1>", self._on_mouse_down)
        self.bind("<B1-Motion>", self._on_mouse_drag)
        self.bind("<ButtonRelease-1>", self._on_mouse_up)
        self.bind("<MouseWheel>", self._on_mouse_wheel)  # Windows wheel

        # Visualizer Engines
        self.kinematics = HandKinematics()
        self.orientation_calc = OrientationCalculator()
        self.orient_calc = self.orientation_calc

        # Telemetry State
        self.active_hand = "LEFT"
        self.current_flex = [0.0, 0.0, 0.0, 0.0, 0.0]
        self.current_accel = [0.0, 0.0, 16384.0]
        self.current_gyro = [0.0, 0.0, 0.0]
        self.current_mag = [0.0, 0.0, 0.0]

        self.auto_orient_enabled = True

        # Render cache
        self.cached_euler = (0.0, 0.0, 0.0)

    def _on_mouse_down(self, event):
        self.drag_start_x = event.x
        self.drag_start_y = event.y
        self.is_dragging = True

    def _on_mouse_drag(self, event):
        if not self.is_dragging:
            return
        dx = event.x - self.drag_start_x
        dy = event.y - self.drag_start_y
        self.drag_start_x = event.x
        self.drag_start_y = event.y

        # Orbit camera
        self.cam_yaw += dx * 0.01
        self.cam_pitch = max(math.radians(-80.0), min(math.radians(80.0), self.cam_pitch + dy * 0.01))
        self.render()

    def _on_mouse_up(self, event):
        self.is_dragging = False

    def _on_mouse_wheel(self, event):
        # Zoom in / out
        factor = 1.1 if event.delta > 0 else 0.9
        self.zoom = max(0.5, min(3.5, self.zoom * factor))
        self.render()

    def reset_view(self, preset: str = "perspective"):
        """Reset camera view angle."""
        if preset == "top":
            self.cam_pitch = math.radians(85.0)
            self.cam_yaw = 0.0
        elif preset == "front":
            self.cam_pitch = 0.0
            self.cam_yaw = 0.0
        elif preset == "side":
            self.cam_pitch = 0.0
            self.cam_yaw = math.radians(90.0)
        else:  # perspective
            self.cam_pitch = math.radians(25.0)
            self.cam_yaw = math.radians(-15.0)
        self.zoom = 1.45
        self.render()

    def update_telemetry(self, hand: str, flex_norm: List[float],
                         accel: List[float], gyro: List[float], mag: List[float]):
        """Feed new telemetry packet to the visualizer."""
        self.active_hand = hand.upper()
        self.current_flex = list(flex_norm)
        self.current_accel = list(accel)
        self.current_gyro = list(gyro)
        self.current_mag = list(mag)

        # Update sensor orientation
        if self.auto_orient_enabled:
            p, r, y = self.orientation_calc.update(accel, gyro, mag)
            self.cached_euler = (p, r, y)

        self.render()

    def _project_point(self, p_world: np.ndarray, cx: float, cy: float) -> Tuple[float, float, float]:
        """
        Transform world 3D point into Camera View space and perspective project to Canvas.
        Returns: (screen_x, screen_y, depth_z)
        """
        # Camera orbit rotation: First around World Z (yaw), then around Camera X (pitch)
        cp, sp = math.cos(self.cam_pitch), math.sin(self.cam_pitch)
        cyaw, syaw = math.cos(self.cam_yaw), math.sin(self.cam_yaw)

        # Orbit yaw
        x1 =  p_world[0] * cyaw + p_world[1] * syaw
        y1 = -p_world[0] * syaw + p_world[1] * cyaw
        z1 =  p_world[2]

        # Orbit pitch
        x_cam = x1
        y_cam = y1 * cp - z1 * sp
        z_cam = y1 * sp + z1 * cp

        # Camera distance offset
        z_eff = z_cam + self.cam_dist
        if z_eff <= 10.0:
            z_eff = 10.0

        scale = (self.cam_dist * self.zoom) / z_eff
        screen_x = cx + x_cam * scale
        screen_y = cy - y_cam * scale  # Invert Y for screen

        return screen_x, screen_y, z_cam

    def render(self):
        """Draw the 3D Hand Skeleton, orientation gimbal, and status overlays."""
        self.delete("all")
        cx = self.winfo_width() / 2.0 or (self.width / 2.0)
        cy = self.winfo_height() / 2.0 or (self.height / 2.0)

        # 1. Background Grid / Tech Ring
        self._draw_grid_and_backdrop(cx, cy)

        # 2. Compute 3D Skeleton in Local Frame
        skeleton_data = self.kinematics.compute_skeleton(self.active_hand, self.current_flex)
        local_points = skeleton_data["points"]
        bones = skeleton_data["bones"]

        # 3. Apply Hand Orientation Rotation Matrix from MPU-9250
        # Mounting: +Y points away from fingers (towards wrist).
        # Local hand frame has fingers pointing along +Y, so Hand Local Y = -Sensor Y.
        if self.auto_orient_enabled:
            R = self.orientation_calc.get_rotation_matrix()
        else:
            R = np.eye(3)

        world_points: Dict[str, np.ndarray] = {}
        screen_points: Dict[str, Tuple[float, float, float]] = {}

        for k, pt in local_points.items():
            # Align local hand geometry to sensor coordinate convention:
            # Local hand forward (+Y_local) = -Y_sensor
            # Local hand dorsal normal (+Z_local) = +Z_sensor
            # Local hand lateral (+X_local) = -X_sensor
            pt_sensor_aligned = np.array([-pt[0], -pt[1], pt[2]])
            w_pt = R @ pt_sensor_aligned
            world_points[k] = w_pt
            screen_points[k] = self._project_point(w_pt, cx, cy)

        # 4. Draw Translucent Palm Flesh / Metacarpal Webbing
        self._draw_palm_webbing(screen_points)

        # 5. Sort and Render Bones (Painter's Algorithm by depth)
        drawable_bones = []
        for p1_k, p2_k, b_type in bones:
            s1 = screen_points[p1_k]
            s2 = screen_points[p2_k]
            avg_z = (s1[2] + s2[2]) / 2.0
            drawable_bones.append((avg_z, p1_k, p2_k, b_type, s1, s2))

        drawable_bones.sort(key=lambda item: item[0])  # Sort back-to-front

        # Hand color palette
        is_left = (self.active_hand == "LEFT")
        primary_color = "#38bdf8" if is_left else "#10b981"    # Cyan for Left, Emerald for Right
        secondary_color = "#0284c7" if is_left else "#059669"
        glow_color = "#0369a1" if is_left else "#047857"

        for _, p1_k, p2_k, b_type, s1, s2 in drawable_bones:
            x1, y1, _ = s1
            x2, y2, _ = s2

            if b_type == "wrist":
                self.create_line(x1, y1, x2, y2, fill="#a855f7", width=5, capstyle=tk.ROUND)
                self.create_line(x1, y1, x2, y2, fill="#c084fc", width=2, capstyle=tk.ROUND)
            elif b_type == "metacarpal":
                self.create_line(x1, y1, x2, y2, fill="#334155", width=4, capstyle=tk.ROUND)
                self.create_line(x1, y1, x2, y2, fill="#64748b", width=1.5, capstyle=tk.ROUND)
            elif b_type == "palm_arch":
                self.create_line(x1, y1, x2, y2, fill="#fbbf24", width=2, dash=(3, 3))
            elif b_type == "finger":
                # Outer glow line
                self.create_line(x1, y1, x2, y2, fill=glow_color, width=6, capstyle=tk.ROUND)
                # Middle bold bone
                self.create_line(x1, y1, x2, y2, fill=secondary_color, width=4, capstyle=tk.ROUND)
                # Core bright line
                self.create_line(x1, y1, x2, y2, fill="#f8fafc", width=1.5, capstyle=tk.ROUND)

        # 6. Render Joints & Nodes (sorted by depth)
        drawable_nodes = []
        for k, s in screen_points.items():
            drawable_nodes.append((s[2], k, s[0], s[1]))
        drawable_nodes.sort(key=lambda item: item[0])

        for _, k, x, y in drawable_nodes:
            if "tip" in k:
                # Fingertip - Glowing emerald/cyan node
                r = 6
                self.create_oval(x - r - 2, y - r - 2, x + r + 2, y + r + 2, fill="", outline="#34d399", width=2)
                self.create_oval(x - r, y - r, x + r, y + r, fill="#10b981", outline="#ffffff", width=1)
            elif "mcp" in k:
                # Knuckle joint - Gold
                r = 5
                self.create_oval(x - r, y - r, x + r, y + r, fill="#fbbf24", outline="#ffffff", width=1)
            elif "pip" in k or "dip" in k or "ip" in k:
                # Interphalangeal joint - Primary cyan/emerald
                r = 4.5
                self.create_oval(x - r, y - r, x + r, y + r, fill=primary_color, outline="#ffffff", width=1)
            elif "wrist" in k or "carpal" in k:
                # Wrist joint - Purple
                r = 4
                self.create_oval(x - r, y - r, x + r, y + r, fill="#a855f7", outline="#ffffff", width=1)

        # 7. Fingertip Labels with Bend Percentage
        self._draw_fingertip_labels(screen_points)

        # 8. MPU-9250 Orientation Gimbal & Coordinate Gizmo (Bottom-Left)
        self._draw_mpu_orientation_gizmo(R)

        # 9. Top-Left / Top-Right HUD & Calibration Cues
        self._draw_hud_badges()

    def _draw_grid_and_backdrop(self, cx: float, cy: float):
        """Subtle perspective floor grid and concentric target circles."""
        # Draw tech concentric circles
        for rad in [140, 220]:
            self.create_oval(cx - rad, cy - rad + 40, cx + rad, cy + rad + 40,
                             outline="#1e293b", width=1, dash=(4, 6))

        # Crosshairs
        self.create_line(cx - 30, cy + 40, cx + 30, cy + 40, fill="#1e293b", width=1)
        self.create_line(cx, cy + 10, cx, cy + 70, fill="#1e293b", width=1)

    def _draw_palm_webbing(self, screen_points: Dict[str, Tuple[float, float, float]]):
        """Draw translucent polygon mesh representing palm palm surface."""
        poly_keys = ["wrist_center", "thumb_cmc", "thumb_mcp", "index_mcp", "middle_mcp", "ring_mcp", "pinky_mcp", "wrist_center"]
        poly_pts = []
        for k in poly_keys:
            if k in screen_points:
                poly_pts.extend([screen_points[k][0], screen_points[k][1]])

        if len(poly_pts) >= 6:
            self.create_polygon(poly_pts, fill="#162235", outline="#1e293b", width=1)

    def _draw_fingertip_labels(self, screen_points: Dict[str, Tuple[float, float, float]]):
        """Draw floating tags showing flex percentages near each fingertip."""
        tips = [
            ("thumb_tip", "Thumb", self.current_flex[0]),
            ("index_tip", "Index", self.current_flex[1]),
            ("middle_tip", "Middle", self.current_flex[2]),
            ("ring_tip", "Ring", self.current_flex[3]),
            ("pinky_tip", "Pinky", self.current_flex[4]),
        ]

        for tip_key, name, val in tips:
            if tip_key in screen_points:
                x, y, _ = screen_points[tip_key]
                pct = int(val * 100)
                tag_text = f"{name}: {pct}%"
                color = "#34d399" if pct < 30 else ("#f59e0b" if pct < 70 else "#ef4444")

                # Small tag box
                self.create_rectangle(x + 10, y - 10, x + 85, y + 8, fill="#0f172a", outline=color, width=1)
                self.create_text(x + 47, y - 1, text=tag_text, font=("Segoe UI", 8, "bold"), fill=color)

    def _draw_mpu_orientation_gizmo(self, R: np.ndarray):
        """
        Draws 3D Coordinate Frame Gizmo in the bottom-left corner showing the MPU-9250 orientation.
        Highlights:
        - +Y (GREEN): Points AWAY from fingers (towards the wrist / forearm)
        - +X (RED): Lateral
        - +Z (BLUE): Normal out of dorsal back
        """
        gx, gy = 85.0, self.winfo_height() - 85.0 if self.winfo_height() > 150 else 430.0

        # Background box
        self.create_rectangle(gx - 75, gy - 75, gx + 85, gy + 75, fill="#0a101d", outline="#1e293b", width=1)
        self.create_text(gx - 70, gy - 62, text="MPU-9250 AXES", font=("Segoe UI", 8, "bold"), fill="#94a3b8", anchor=tk.W)

        axis_len = 46.0

        # Camera view rotation for gizmo
        cp, sp = math.cos(self.cam_pitch), math.sin(self.cam_pitch)
        cyaw, syaw = math.cos(self.cam_yaw), math.sin(self.cam_yaw)
        R_cam = np.array([
            [cyaw, syaw, 0],
            [-syaw * cp, cyaw * cp, -sp],
            [-syaw * sp, cyaw * sp, cp]
        ], dtype=float)

        # Axes in sensor frame:
        # X: Red, Y: Green (Away from fingers), Z: Blue (Normal)
        axes = [
            (np.array([axis_len, 0.0, 0.0]), "#ef4444", "+X"),
            (np.array([0.0, axis_len, 0.0]), "#10b981", "+Y (Away/Wrist)"),
            (np.array([0.0, 0.0, axis_len]), "#38bdf8", "+Z (Up)"),
        ]

        # Draw origin
        self.create_oval(gx - 3, gy - 3, gx + 3, gy + 3, fill="#f8fafc", outline="")

        for vec, color, label in axes:
            # Rotate vector by sensor orientation R then camera view
            v_rot = R_cam @ (R @ (vec / axis_len)) * axis_len
            vx = gx + v_rot[0]
            vy = gy - v_rot[1]

            # Thicker line for +Y to emphasize the user's specific orientation mounting
            w = 3 if "+Y" in label else 2
            self.create_line(gx, gy, vx, vy, fill=color, width=w, arrow=tk.LAST, arrowshape=(8, 10, 4))
            self.create_text(vx + (8 if v_rot[0] >= 0 else -8), vy - 6,
                             text=label, font=("Segoe UI", 7, "bold"), fill=color)

    def _draw_hud_badges(self):
        """Draw live angle readouts and posture calibration feedback."""
        p_deg = math.degrees(self.cached_euler[0])
        r_deg = math.degrees(self.cached_euler[1])
        y_deg = math.degrees(self.cached_euler[2])

        # Euler Readout (Top-Left)
        is_left = (self.active_hand == "LEFT")
        hand_color = "#38bdf8" if is_left else "#10b981"

        self.create_text(16, 18, text=f"● {self.active_hand} HAND 3D SKELETON",
                         font=("Segoe UI", 11, "bold"), fill=hand_color, anchor=tk.W)

        angles_txt = f"Pitch: {p_deg:+.1f}°  |  Roll: {r_deg:+.1f}°  |  Heading: {y_deg:+.1f}°"
        self.create_text(16, 38, text=angles_txt, font=("Consolas", 9), fill="#94a3b8", anchor=tk.W)

        palm_desc = self.orientation_calc.get_palm_orientation_desc(p_deg, r_deg)
        self.create_text(16, 56, text=f"Palm Orientation: {palm_desc}", font=("Segoe UI", 9, "bold"), fill="#fbbf24", anchor=tk.W)

        # Pose Recognition Cue (Top-Right)
        avg_flex = sum(self.current_flex) / 5.0
        w = self.winfo_width() or self.width

        if avg_flex < 0.20:
            pose_text = "🖐 FLAT HAND DETECTED (0° Ready)"
            pose_color = "#10b981"
        elif avg_flex > 0.70:
            pose_text = "✊ CLOSED FIST DETECTED (90° Ready)"
            pose_color = "#ef4444"
        else:
            pose_text = f"✋ FREE BEND: {int(avg_flex*100)}%"
            pose_color = "#fbbf24"

        self.create_rectangle(w - 245, 12, w - 12, 38, fill="#0f172a", outline=pose_color, width=1.5)
        self.create_text(w - 128, 25, text=pose_text, font=("Segoe UI", 9, "bold"), fill=pose_color)

        # Navigation hint at bottom right
        self.create_text(w - 15, self.winfo_height() - 15 if self.winfo_height() > 50 else 500,
                         text="Drag: Orbit Camera | Scroll: Zoom",
                         font=("Segoe UI", 8), fill="#64748b", anchor=tk.SE)


class HandVisualizerWidget(tk.Frame):
    """
    Complete composite UI Widget containing:
    - 3D Skeleton Canvas
    - Hand Selector (Left Glove / Right Glove)
    - Camera preset buttons (Perspective, Top, Front, Side)
    - Auto-orient toggle
    - Calibration action controls and status feedback
    """
    def __init__(self, parent, receiver=None, on_cal_flat=None, on_cal_bent=None, on_cal_reset=None, **kwargs):
        super().__init__(parent, bg="#121820", **kwargs)

        self.receiver = receiver
        self.on_cal_flat_cb = on_cal_flat
        self.on_cal_bent_cb = on_cal_bent
        self.on_cal_reset_cb = on_cal_reset

        self.selected_hand = tk.StringVar(value="LEFT")

        self._build_ui()

    def _build_ui(self):
        # 1. Top Control Bar
        toolbar = tk.Frame(self, bg="#162235", padx=10, pady=6)
        toolbar.pack(fill=tk.X, padx=2, pady=(0, 6))

        # Hand Selector Buttons
        tk.Label(toolbar, text="Target Hand:", font=("Segoe UI", 9, "bold"), fg="#f8fafc", bg="#162235").pack(side=tk.LEFT, padx=(0, 6))

        self.btn_left_hand = tk.Button(
            toolbar,
            text="● LEFT HAND",
            font=("Segoe UI", 9, "bold"),
            bg="#2563eb",
            fg="white",
            padx=10,
            pady=2,
            command=lambda: self.set_hand("LEFT")
        )
        self.btn_left_hand.pack(side=tk.LEFT, padx=3)

        self.btn_right_hand = tk.Button(
            toolbar,
            text="● RIGHT HAND",
            font=("Segoe UI", 9, "bold"),
            bg="#1e293b",
            fg="#94a3b8",
            padx=10,
            pady=2,
            command=lambda: self.set_hand("RIGHT")
        )
        self.btn_right_hand.pack(side=tk.LEFT, padx=3)

        # Separator
        tk.Label(toolbar, text="|", font=("Segoe UI", 11), fg="#334155", bg="#162235").pack(side=tk.LEFT, padx=8)

        # Camera View Presets
        tk.Label(toolbar, text="Camera:", font=("Segoe UI", 9), fg="#94a3b8", bg="#162235").pack(side=tk.LEFT, padx=(2, 4))

        tk.Button(toolbar, text="3D Perspective", font=("Segoe UI", 8), bg="#1e293b", fg="white", padx=6, pady=1,
                  command=lambda: self.canvas.reset_view("perspective")).pack(side=tk.LEFT, padx=2)
        tk.Button(toolbar, text="Top View", font=("Segoe UI", 8), bg="#1e293b", fg="white", padx=6, pady=1,
                  command=lambda: self.canvas.reset_view("top")).pack(side=tk.LEFT, padx=2)
        tk.Button(toolbar, text="Front", font=("Segoe UI", 8), bg="#1e293b", fg="white", padx=6, pady=1,
                  command=lambda: self.canvas.reset_view("front")).pack(side=tk.LEFT, padx=2)
        tk.Button(toolbar, text="Side", font=("Segoe UI", 8), bg="#1e293b", fg="white", padx=6, pady=1,
                  command=lambda: self.canvas.reset_view("side")).pack(side=tk.LEFT, padx=2)

        # Auto Orient Checkbox
        self.auto_orient_var = tk.BooleanVar(value=True)
        chk_orient = tk.Checkbutton(
            toolbar,
            text="Auto-Orient (MPU-9250)",
            variable=self.auto_orient_var,
            command=self._toggle_auto_orient,
            bg="#162235",
            fg="#38bdf8",
            selectcolor="#0f172a",
            activebackground="#162235",
            activeforeground="#38bdf8",
            font=("Segoe UI", 9, "bold")
        )
        chk_orient.pack(side=tk.RIGHT, padx=6)

        # 2. Main 3D Canvas
        self.canvas = HandSkeletonCanvas(self, width=600, height=480)
        self.canvas.pack(fill=tk.BOTH, expand=True)

        # 3. Bottom Calibration Bar
        cal_bar = tk.Frame(self, bg="#1a2332", padx=12, pady=8, bd=1, relief="ridge")
        cal_bar.pack(fill=tk.X, padx=2, pady=(6, 0))

        tk.Label(cal_bar, text="CALIBRATION ACTION:", font=("Segoe UI", 9, "bold"), fg="#fbbf24", bg="#1a2332").pack(side=tk.LEFT, padx=(0, 10))

        btn_flat = tk.Button(
            cal_bar,
            text="🖐 Calibrate Flat (0° Straight)",
            font=("Segoe UI", 9, "bold"),
            bg="#0284c7",
            fg="white",
            padx=10,
            pady=3,
            command=self._action_cal_flat
        )
        btn_flat.pack(side=tk.LEFT, padx=4)

        btn_bent = tk.Button(
            cal_bar,
            text="✊ Calibrate Closed Fist (90° Bent)",
            font=("Segoe UI", 9, "bold"),
            bg="#e11d48",
            fg="white",
            padx=10,
            pady=3,
            command=self._action_cal_bent
        )
        btn_bent.pack(side=tk.LEFT, padx=4)

        btn_reset = tk.Button(
            cal_bar,
            text="↺ Reset Defaults",
            font=("Segoe UI", 9),
            bg="#475569",
            fg="white",
            padx=8,
            pady=3,
            command=self._action_cal_reset
        )
        btn_reset.pack(side=tk.LEFT, padx=4)

        self.lbl_cal_status = tk.Label(
            cal_bar,
            text="Status: Ready to calibrate",
            font=("Segoe UI", 9, "italic"),
            fg="#94a3b8",
            bg="#1a2332"
        )
        self.lbl_cal_status.pack(side=tk.RIGHT, padx=8)

    def set_hand(self, hand: str):
        """Switch active hand visualization."""
        hand = hand.upper()
        self.selected_hand.set(hand)
        if hand == "LEFT":
            self.btn_left_hand.config(bg="#2563eb", fg="white")
            self.btn_right_hand.config(bg="#1e293b", fg="#94a3b8")
        else:
            self.btn_left_hand.config(bg="#1e293b", fg="#94a3b8")
            self.btn_right_hand.config(bg="#059669", fg="white")

        self.canvas.active_hand = hand
        self.canvas.render()

    def _toggle_auto_orient(self):
        self.canvas.auto_orient_enabled = self.auto_orient_var.get()
        self.canvas.render()

    def _action_cal_flat(self):
        if self.on_cal_flat_cb:
            msg = self.on_cal_flat_cb(self.selected_hand.get())
            self.lbl_cal_status.config(text=msg or "Flat hand (0°) saved!", fg="#10b981")

    def _action_cal_bent(self):
        if self.on_cal_bent_cb:
            msg = self.on_cal_bent_cb(self.selected_hand.get())
            self.lbl_cal_status.config(text=msg or "Closed fist (90°) saved!", fg="#10b981")

    def _action_cal_reset(self):
        if self.on_cal_reset_cb:
            msg = self.on_cal_reset_cb(self.selected_hand.get())
            self.lbl_cal_status.config(text=msg or "Defaults restored.", fg="#94a3b8")

    def update_frame(self, left_state: Dict[str, Any], right_state: Dict[str, Any]):
        """Feed telemetry frame to the visualizer."""
        active = self.selected_hand.get()
        st = left_state if active == "LEFT" else right_state

        flex_norm = st.get("flex_norm", [0.0]*5)
        accel = st.get("accel", [0.0, 0.0, 16384.0])
        gyro = st.get("gyro", [0.0, 0.0, 0.0])
        mag = st.get("mag", [0.0, 0.0, 0.0])

        self.canvas.update_telemetry(active, flex_norm, accel, gyro, mag)
