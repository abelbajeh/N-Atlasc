"""
ASL to Nigerian Languages Translator - Desktop GUI Application
Integrates dual-glove wireless telemetry, live dataset collection, model training,
real-time gesture inference, N-Atlas translation (Yoruba, Igbo, Hausa), and multilingual TTS.
"""
import os
import sys
import time
import threading
import logging
from typing import Dict, Any, Optional

import tkinter as tk
from tkinter import ttk, messagebox

import numpy as np

import config
from receiver import DualGloveReceiver
from dataset_recorder import DatasetRecorder
from train_model import train_classifier
from gesture_recognizer import GestureRecognizer
from sentence_builder import SentenceBuilder
from translator import NAtlasTranslator
from tts_engine import TTSEngine
from hand_visualizer import HandVisualizerWidget

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("ASLTranslatorApp")

class ASLTranslatorApp(tk.Tk):
    def __init__(self):
        super().__init__()

        self.title("N-Atlas: ASL Glove Translator to Nigerian Languages")
        self.geometry("1100x800")
        self.minsize(980, 720)

        # Style configuration (Modern Dark Palette)
        self.configure(bg="#121820")
        self._init_styles()

        # Core Backend Modules
        self.receiver = DualGloveReceiver()
        self.recorder = DatasetRecorder(self.receiver)
        self.recognizer = GestureRecognizer()
        self.builder = SentenceBuilder()
        self.translator = NAtlasTranslator()
        self.tts = TTSEngine()

        # UI State Variables
        self.target_lang_var = tk.StringVar(value="Yoruba")
        self.neural_mode_var = tk.BooleanVar(value=False)
        self.auto_speak_var = tk.BooleanVar(value=False)
        self.sim_mode_var = tk.BooleanVar(value=False)
        self.live_recognition_active = tk.BooleanVar(value=True)
        self.dataset_hand_mode_var = tk.StringVar(value="right")  # "right", "left", "both"
        self.train_hand_mode_var = tk.StringVar(value="auto")    # "auto", "right", "left", "dual"

        # Build UI Layout
        self._build_header()
        self._build_connection_bar()
        self._build_tabs()

        # Start Receiver & Background GUI Refresh Loop
        self.receiver.start()
        self.after(100, self._telemetry_refresh_loop)

        # Handle clean exit
        self.protocol("WM_DELETE_WINDOW", self.on_close)

    def _init_styles(self):
        self.style = ttk.Style(self)
        try:
            self.style.theme_use("clam")
        except Exception:
            pass

        # Dark theme palette
        bg_dark = "#121820"
        card_bg = "#1a2332"
        accent_blue = "#2563eb"
        text_light = "#f8fafc"
        text_dim = "#94a3b8"

        self.style.configure(".", background=bg_dark, foreground=text_light, font=("Segoe UI", 10))
        self.style.configure("TNotebook", background=bg_dark, borderwidth=0)
        self.style.configure("TNotebook.Tab", background="#1e293b", foreground=text_dim, padding=[16, 8], font=("Segoe UI", 10, "bold"))
        self.style.map("TNotebook.Tab", background=[("selected", accent_blue)], foreground=[("selected", text_light)])
        self.style.configure("TFrame", background=bg_dark)
        self.style.configure("Card.TFrame", background=card_bg, relief="flat")
        self.style.configure("TLabel", background=bg_dark, foreground=text_light)
        self.style.configure("Card.TLabel", background=card_bg, foreground=text_light)
        self.style.configure("TButton", padding=[10, 6], background="#1e293b", foreground=text_light, borderwidth=1)
        self.style.map("TButton", background=[("active", "#334155")])

        # Treeview styling: Crisp black text on clean white background so dataset entries are clearly visible
        self.style.configure(
            "Treeview",
            background="#ffffff",
            foreground="#000000",
            fieldbackground="#ffffff",
            rowheight=24,
            font=("Segoe UI", 10)
        )
        self.style.configure(
            "Treeview.Heading",
            background="#e2e8f0",
            foreground="#000000",
            font=("Segoe UI", 9, "bold")
        )
        self.style.map(
            "Treeview",
            background=[("selected", "#0284c7")],
            foreground=[("selected", "#ffffff")]
        )

    def _build_header(self):
        header_frame = tk.Frame(self, bg="#0f172a", height=70, padx=20, pady=10)
        header_frame.pack(fill=tk.X)

        title_label = tk.Label(
            header_frame,
            text="N-ATLAS : DUAL-GLOVE ASL TRANSLATOR",
            font=("Segoe UI", 14, "bold"),
            fg="#38bdf8",
            bg="#0f172a"
        )
        title_label.pack(side=tk.LEFT)

        subtitle_label = tk.Label(
            header_frame,
            text=" (ASL -> English -> Yorùbá / Igbo / Hausa)",
            font=("Segoe UI", 10),
            fg="#94a3b8",
            bg="#0f172a"
        )
        subtitle_label.pack(side=tk.LEFT, padx=5)

        # Hardware Status indicators
        status_box = tk.Frame(header_frame, bg="#0f172a")
        status_box.pack(side=tk.RIGHT)

        # Simulation Toggle
        sim_chk = tk.Checkbutton(
            status_box,
            text="Simulation Mode",
            variable=self.sim_mode_var,
            command=self._toggle_simulation,
            bg="#0f172a",
            fg="#cbd5e1",
            selectcolor="#1e293b",
            activebackground="#0f172a",
            activeforeground="#38bdf8",
            font=("Segoe UI", 9)
        )
        sim_chk.pack(side=tk.LEFT, padx=12)

        # Left Hand Pill
        self.left_indicator = tk.Label(
            status_box,
            text="● LEFT GLOVE: OFF",
            font=("Segoe UI", 9, "bold"),
            fg="#ef4444",
            bg="#1e293b",
            padx=10,
            pady=4,
            relief="flat"
        )
        self.left_indicator.pack(side=tk.LEFT, padx=6)

        # Right Hand Pill
        self.right_indicator = tk.Label(
            status_box,
            text="● RIGHT GLOVE: OFF",
            font=("Segoe UI", 9, "bold"),
            fg="#ef4444",
            bg="#1e293b",
            padx=10,
            pady=4,
            relief="flat"
        )
        self.right_indicator.pack(side=tk.LEFT, padx=6)

        # Active Model / Hand Mode Indicator
        self.lbl_model_indicator = tk.Label(
            status_box,
            text="● MODEL: LOADING...",
            font=("Segoe UI", 9, "bold"),
            fg="#fbbf24",
            bg="#1e293b",
            padx=10,
            pady=4,
            relief="flat"
        )
        self.lbl_model_indicator.pack(side=tk.LEFT, padx=6)

    def _build_connection_bar(self):
        conn_frame = tk.Frame(self, bg="#161f2e", padx=16, pady=8, bd=1, relief="ridge")
        conn_frame.pack(fill=tk.X, padx=15, pady=(8, 0))

        # Title & Info Button
        title_box = tk.Frame(conn_frame, bg="#161f2e")
        title_box.pack(side=tk.LEFT, padx=(0, 10))
        tk.Label(
            title_box,
            text="HARDWARE LINK:",
            font=("Segoe UI", 9, "bold"),
            fg="#fbbf24",
            bg="#161f2e"
        ).pack(side=tk.LEFT)
        tk.Button(
            title_box,
            text="ℹ️ How It Works",
            font=("Segoe UI", 8),
            bg="#334155",
            fg="#38bdf8",
            padx=4,
            pady=0,
            command=self._show_connection_help
        ).pack(side=tk.LEFT, padx=5)

        # --- LEFT GLOVE SECTION ---
        l_box = tk.Frame(conn_frame, bg="#161f2e")
        l_box.pack(side=tk.LEFT, padx=8)

        # Inbuilt LED for Left Glove
        self.led_left = tk.Label(
            l_box,
            text="● INBUILT LED: OFF",
            font=("Segoe UI", 8, "bold"),
            fg="#64748b",
            bg="#0f172a",
            padx=7,
            pady=3,
            relief="groove"
        )
        self.led_left.pack(side=tk.LEFT, padx=4)

        tk.Label(l_box, text="Left IP:", font=("Segoe UI", 9, "bold"), fg="#38bdf8", bg="#161f2e").pack(side=tk.LEFT, padx=(4, 2))
        self.entry_left_ip = tk.Entry(l_box, width=13, font=("Segoe UI", 9), bg="#0f172a", fg="#f8fafc", insertbackground="white")
        self.entry_left_ip.insert(0, "192.168.205.81")
        self.entry_left_ip.pack(side=tk.LEFT, padx=2)
        self.entry_left_ip.bind("<Return>", lambda e: self._connect_left_glove())

        self.btn_left_connect = tk.Button(
            l_box,
            text="🔗 Connect",
            font=("Segoe UI", 8, "bold"),
            bg="#0284c7",
            fg="white",
            padx=7,
            pady=1,
            command=self._connect_left_glove
        )
        self.btn_left_connect.pack(side=tk.LEFT, padx=3)

        tk.Button(
            l_box,
            text="⚡ Ping",
            font=("Segoe UI", 8, "bold"),
            bg="#2563eb",
            fg="white",
            padx=6,
            pady=1,
            command=self._ping_left_glove
        ).pack(side=tk.LEFT, padx=3)

        tk.Button(
            l_box,
            text="💡 Flash LED",
            font=("Segoe UI", 8),
            bg="#334155",
            fg="white",
            padx=5,
            pady=1,
            command=self._blink_left_glove
        ).pack(side=tk.LEFT, padx=2)

        self.lbl_left_conn_status = tk.Label(
            l_box,
            text="Standby (Click Connect)",
            font=("Segoe UI", 8),
            fg="#94a3b8",
            bg="#161f2e"
        )
        self.lbl_left_conn_status.pack(side=tk.LEFT, padx=6)

        # Separator
        tk.Label(conn_frame, text="|", font=("Segoe UI", 12), fg="#334155", bg="#161f2e").pack(side=tk.LEFT, padx=8)

        # --- RIGHT GLOVE SECTION ---
        r_box = tk.Frame(conn_frame, bg="#161f2e")
        r_box.pack(side=tk.LEFT, padx=8)

        # Inbuilt LED for Right Glove
        self.led_right = tk.Label(
            r_box,
            text="● INBUILT LED: OFF",
            font=("Segoe UI", 8, "bold"),
            fg="#64748b",
            bg="#0f172a",
            padx=7,
            pady=3,
            relief="groove"
        )
        self.led_right.pack(side=tk.LEFT, padx=4)

        tk.Label(r_box, text="Right IP:", font=("Segoe UI", 9, "bold"), fg="#10b981", bg="#161f2e").pack(side=tk.LEFT, padx=(4, 2))
        self.entry_right_ip = tk.Entry(r_box, width=13, font=("Segoe UI", 9), bg="#0f172a", fg="#f8fafc", insertbackground="white")
        self.entry_right_ip.insert(0, "192.168.205.82")
        self.entry_right_ip.pack(side=tk.LEFT, padx=2)
        self.entry_right_ip.bind("<Return>", lambda e: self._connect_right_glove())

        self.btn_right_connect = tk.Button(
            r_box,
            text="🔗 Connect",
            font=("Segoe UI", 8, "bold"),
            bg="#059669",
            fg="white",
            padx=7,
            pady=1,
            command=self._connect_right_glove
        )
        self.btn_right_connect.pack(side=tk.LEFT, padx=3)

        tk.Button(
            r_box,
            text="⚡ Ping",
            font=("Segoe UI", 8, "bold"),
            bg="#059669",
            fg="white",
            padx=6,
            pady=1,
            command=self._ping_right_glove
        ).pack(side=tk.LEFT, padx=3)

        tk.Button(
            r_box,
            text="💡 Flash LED",
            font=("Segoe UI", 8),
            bg="#334155",
            fg="white",
            padx=5,
            pady=1,
            command=self._blink_right_glove
        ).pack(side=tk.LEFT, padx=2)

        self.lbl_right_conn_status = tk.Label(
            r_box,
            text="Standby (Click Connect)",
            font=("Segoe UI", 8),
            fg="#94a3b8",
            bg="#161f2e"
        )
        self.lbl_right_conn_status.pack(side=tk.LEFT, padx=6)

        # Connection Guidance Sub-Banner
        hint_frame = tk.Frame(self, bg="#0f172a", padx=16, pady=5, bd=1, relief="flat")
        hint_frame.pack(fill=tk.X, padx=15, pady=(2, 0))
        tk.Label(
            hint_frame,
            text="💡 Step 1: Turn on ESP32  ➔  Step 2: Note IP in Arduino Serial Monitor (e.g. 192.168.205.82)  ➔  Step 3: Enter IP above & Click '🔗 Connect'",
            font=("Segoe UI", 9, "bold"),
            fg="#38bdf8",
            bg="#0f172a"
        ).pack(side=tk.LEFT)
        tk.Label(
            hint_frame,
            text="   (ESP32 does NOT need Host PC IP! It waits quietly in Standby until you click Connect)",
            font=("Segoe UI", 8, "italic"),
            fg="#94a3b8",
            bg="#0f172a"
        ).pack(side=tk.LEFT)

    def _show_connection_help(self):
        """Displays explanation modal about zero-config ESP32 connection architecture."""
        help_win = tk.Toplevel(self)
        help_win.title("How ESP32 Glove Connection Works")
        help_win.geometry("560x420")
        help_win.configure(bg="#0f172a")
        help_win.resizable(False, False)
        help_win.transient(self)
        help_win.grab_set()

        card = tk.Frame(help_win, bg="#1a2332", padx=20, pady=16, bd=2, relief="groove")
        card.pack(fill=tk.BOTH, expand=True, padx=14, pady=14)

        tk.Label(
            card,
            text="📡 ZERO-CONFIG ESP32 WIRELESS LINK",
            font=("Segoe UI", 12, "bold"),
            fg="#fbbf24",
            bg="#1a2332"
        ).pack(pady=(0, 8))

        info_text = (
            "1. NO HOST PC IP CONFIGURATION NEEDED:\n"
            "   Your ESP32 glove does NOT need to know your laptop's IP address.\n"
            "   You never have to run 'ipconfig' or hardcode IPs in Arduino!\n\n"
            "2. HOW THE ESP32 BOOTS UP:\n"
            "   • Powers on and connects to Wi-Fi ('KINGDOM').\n"
            "   • Receives its own IP from the router (e.g. 192.168.205.82).\n"
            "   • Prints: 'GLOVE IP: 192.168.205.82 | STATUS: STANDBY' in Serial Monitor.\n"
            "   • Sits silently in STANDBY with a gentle blue LED blink.\n\n"
            "3. HOW THE PYTHON GUI CONNECTS:\n"
            "   • The Python app waits until YOU enter the ESP32 IP and click '🔗 Connect'.\n"
            "   • Python sends a handshake message directly to the glove's IP.\n"
            "   • The ESP32 receives it, turns its LED solid ON, and starts streaming at 50 Hz.\n\n"
            "4. ZERO INTERFERENCE:\n"
            "   • The Python app will never auto-connect on startup.\n"
            "   • You have full manual control over when gloves connect or disconnect."
        )

        msg_box = tk.Label(
            card,
            text=info_text,
            font=("Segoe UI", 9),
            fg="#f8fafc",
            bg="#1a2332",
            justify=tk.LEFT,
            wraplength=510
        )
        msg_box.pack(fill=tk.BOTH, expand=True, pady=4)

        tk.Button(
            card,
            text="Got it!",
            font=("Segoe UI", 9, "bold"),
            bg="#0284c7",
            fg="white",
            padx=16,
            pady=4,
            command=help_win.destroy
        ).pack(pady=(8, 0))

    def _show_connect_orientation_prompt(self, hand: str, ip: str, on_proceed):
        """
        Display instructional modal prompting user to hold hand vertically:
        - Fingertips pointing straight upward at 90°
        - Palm facing the PC monitor (dorsal side with sensor facing user)
        Ensures accurate zeroing and reference orientation when glove connects.
        """
        dialog = tk.Toplevel(self)
        dialog.title(f"{hand} Glove Orientation Setup")
        dialog.geometry("520x430")
        dialog.configure(bg="#0f172a")
        dialog.resizable(False, False)
        dialog.transient(self)
        dialog.grab_set()

        # Center dialog over main app window
        try:
            x = self.winfo_x() + (self.winfo_width() // 2) - 260
            y = self.winfo_y() + (self.winfo_height() // 2) - 215
            dialog.geometry(f"+{x}+{y}")
        except Exception:
            pass

        card = tk.Frame(dialog, bg="#1a2332", padx=20, pady=16, bd=2, relief="groove")
        card.pack(fill=tk.BOTH, expand=True, padx=14, pady=14)

        # Header Badge
        header_color = "#38bdf8" if hand == "LEFT" else "#10b981"
        tk.Label(
            card,
            text=f"🖐 {hand} GLOVE ORIENTATION SETUP",
            font=("Segoe UI", 13, "bold"),
            fg=header_color,
            bg="#1a2332"
        ).pack(pady=(0, 4))

        tk.Label(
            card,
            text=f"Position your hand before connecting to {ip}:",
            font=("Segoe UI", 9),
            fg="#94a3b8",
            bg="#1a2332"
        ).pack(pady=(0, 10))

        # Instructions Frame
        inst_box = tk.Frame(card, bg="#0f172a", padx=14, pady=10, bd=1, relief="ridge")
        inst_box.pack(fill=tk.X, pady=(0, 10))

        steps = [
            ("1. Hand Posture:", "Raise hand up vertically in front of your chest."),
            ("2. Fingertips (90°):", "Point fingertips straight UPWARD toward the ceiling."),
            ("3. Palm Facing PC:", "Face palm towards PC monitor (back of hand faces YOU)."),
            ("4. Hold Steady:", "Keep hand still for 2 sec while connection zeroes IMU.")
        ]

        for title, detail in steps:
            row = tk.Frame(inst_box, bg="#0f172a")
            row.pack(fill=tk.X, pady=2)
            tk.Label(row, text=title, font=("Segoe UI", 9, "bold"), fg="#fbbf24", bg="#0f172a", width=18, anchor=tk.W).pack(side=tk.LEFT)
            tk.Label(row, text=detail, font=("Segoe UI", 9), fg="#f8fafc", bg="#0f172a", anchor=tk.W).pack(side=tk.LEFT)

        # Visual ASCII Cue Box
        art_box = tk.Frame(card, bg="#162235", padx=10, pady=6, bd=1, relief="sunken")
        art_box.pack(fill=tk.X, pady=(0, 10))

        ascii_art = (
            "           ▲ [90° Vertical Fingertips]\n"
            "           │ \n"
            "     [ 🖐  PALM FACING PC MONITOR  ]\n"
            "     [   Dorsal Sensor Faces You  ]\n"
            "           │ \n"
            "           ▼ [Wrist & Forearm]"
        )
        tk.Label(
            art_box,
            text=ascii_art,
            font=("Consolas", 8, "bold"),
            fg="#38bdf8" if hand == "LEFT" else "#10b981",
            bg="#162235",
            justify=tk.CENTER
        ).pack()

        # Action Buttons
        btn_row = tk.Frame(card, bg="#1a2332")
        btn_row.pack(fill=tk.X, pady=(4, 0))

        def _on_confirm():
            dialog.destroy()
            on_proceed()

        def _on_cancel():
            dialog.destroy()

        btn_confirm = tk.Button(
            btn_row,
            text="✓ Ready - Connect & Calibrate",
            font=("Segoe UI", 10, "bold"),
            bg="#0284c7" if hand == "LEFT" else "#059669",
            fg="white",
            padx=14,
            pady=6,
            command=_on_confirm
        )
        btn_confirm.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(0, 6))

        btn_cancel = tk.Button(
            btn_row,
            text="✕ Cancel",
            font=("Segoe UI", 10),
            bg="#334155",
            fg="white",
            padx=10,
            pady=6,
            command=_on_cancel
        )
        btn_cancel.pack(side=tk.RIGHT, padx=(6, 0))

    def _connect_left_glove(self):
        if self.receiver.left_state["connected"]:
            self.receiver.disconnect_glove("LEFT")
            self.btn_left_connect.config(text="🔗 Connect", bg="#0284c7")
            self.lbl_left_conn_status.config(text="Standby (Click Connect)", fg="#94a3b8")
            return

        ip = self.entry_left_ip.get().strip()
        if not ip:
            messagebox.showwarning(
                "Missing IP",
                "Please enter the Left Glove ESP32 IP address.\n\n"
                "Look at the Arduino Serial Monitor when the ESP32 boots up to find its IP (e.g. 192.168.205.81).\n"
                "Note: Your ESP32 does NOT need your PC IP — entering the glove IP here links them automatically."
            )
            return

        def _do_connect():
            self.btn_left_connect.config(text="Connecting...", bg="#d97706", state=tk.DISABLED)
            self.lbl_left_conn_status.config(text=f"Connecting to {ip}...", fg="#f59e0b")

            def _worker():
                success, msg = self.receiver.connect_glove("LEFT", ip)
                def _update():
                    self.btn_left_connect.config(state=tk.NORMAL)
                    if success:
                        self.btn_left_connect.config(text="✕ Disconnect", bg="#b91c1c")
                        self.lbl_left_conn_status.config(text=f"{msg} (90° Tared)", fg="#10b981")
                        self.receiver.tare_orientation_vertical("LEFT")
                        if hasattr(self, "hand_visualizer"):
                            self.hand_visualizer.canvas.orientation_calc.zero_to_vertical()
                    else:
                        self.btn_left_connect.config(text="🔗 Connect", bg="#0284c7")
                        self.lbl_left_conn_status.config(text=f"Failed: {msg}", fg="#ef4444")
                        messagebox.showerror(
                            "Connection Failed",
                            f"Could not connect to Left Glove at {ip}:5005.\n\n"
                            "Troubleshooting Checklist:\n"
                            "1. Confirm you uploaded the updated sketch (esp32_glove_left.ino) to the ESP32.\n"
                            "2. Check Arduino Serial Monitor — it should show:\n"
                            f"   'GLOVE IP: {ip} | STATUS: STANDBY'.\n"
                            "3. Confirm your PC and ESP32 are both connected to Wi-Fi 'KINGDOM'.\n"
                            "4. The ESP32 does NOT look for your PC IP — clicking Connect sends the link from your PC directly to the glove."
                        )
                self.after(0, _update)

            threading.Thread(target=_worker, daemon=True).start()

        self._show_connect_orientation_prompt("LEFT", ip, _do_connect)

    def _connect_right_glove(self):
        if self.receiver.right_state["connected"]:
            self.receiver.disconnect_glove("RIGHT")
            self.btn_right_connect.config(text="🔗 Connect", bg="#059669")
            self.lbl_right_conn_status.config(text="Standby (Click Connect)", fg="#94a3b8")
            return

        ip = self.entry_right_ip.get().strip()
        if not ip:
            messagebox.showwarning(
                "Missing IP",
                "Please enter the Right Glove ESP32 IP address.\n\n"
                "Look at the Arduino Serial Monitor when the ESP32 boots up to find its IP (e.g. 192.168.205.82).\n"
                "Note: Your ESP32 does NOT need your PC IP — entering the glove IP here links them automatically."
            )
            return

        def _do_connect():
            self.btn_right_connect.config(text="Connecting...", bg="#d97706", state=tk.DISABLED)
            self.lbl_right_conn_status.config(text=f"Connecting to {ip}...", fg="#f59e0b")

            def _worker():
                success, msg = self.receiver.connect_glove("RIGHT", ip)
                def _update():
                    self.btn_right_connect.config(state=tk.NORMAL)
                    if success:
                        self.btn_right_connect.config(text="✕ Disconnect", bg="#b91c1c")
                        self.lbl_right_conn_status.config(text=f"{msg} (90° Tared)", fg="#10b981")
                        self.receiver.tare_orientation_vertical("RIGHT")
                        if hasattr(self, "hand_visualizer"):
                            self.hand_visualizer.canvas.orientation_calc.zero_to_vertical()
                    else:
                        self.btn_right_connect.config(text="🔗 Connect", bg="#059669")
                        self.lbl_right_conn_status.config(text=f"Failed: {msg}", fg="#ef4444")
                        messagebox.showerror(
                            "Connection Failed",
                            f"Could not connect to Right Glove at {ip}:5005.\n\n"
                            "Troubleshooting Checklist:\n"
                            "1. Confirm you uploaded the updated sketch (esp32_glove_right.ino) to the ESP32.\n"
                            "2. Check Arduino Serial Monitor — it should show:\n"
                            f"   'GLOVE IP: {ip} | STATUS: STANDBY'.\n"
                            "3. Confirm your PC and ESP32 are both connected to Wi-Fi 'KINGDOM'.\n"
                            "4. The ESP32 does NOT look for your PC IP — clicking Connect sends the link from your PC directly to the glove."
                        )
                self.after(0, _update)

            threading.Thread(target=_worker, daemon=True).start()

        self._show_connect_orientation_prompt("RIGHT", ip, _do_connect)

    def _ping_left_glove(self):
        ip = self.entry_left_ip.get().strip()
        self.lbl_left_conn_status.config(text="Pinging...", fg="#f59e0b")
        def _worker():
            success, msg = self.receiver.ping_glove("LEFT", ip)
            color = "#10b981" if success else "#ef4444"
            self.after(0, lambda: self.lbl_left_conn_status.config(text=msg, fg=color))
        threading.Thread(target=_worker, daemon=True).start()

    def _blink_left_glove(self):
        ip = self.entry_left_ip.get().strip()
        self.receiver.blink_glove_led("LEFT", ip)

    def _ping_right_glove(self):
        ip = self.entry_right_ip.get().strip()
        self.lbl_right_conn_status.config(text="Pinging...", fg="#f59e0b")
        def _worker():
            success, msg = self.receiver.ping_glove("RIGHT", ip)
            color = "#10b981" if success else "#ef4444"
            self.after(0, lambda: self.lbl_right_conn_status.config(text=msg, fg=color))
        threading.Thread(target=_worker, daemon=True).start()

    def _blink_right_glove(self):
        ip = self.entry_right_ip.get().strip()
        self.receiver.blink_glove_led("RIGHT", ip)

    def _build_tabs(self):

        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=15, pady=15)

        # Tab 1: Live Sign Recognition & Multilingual Translation
        self.tab_translate = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_translate, text="  Live ASL Translation & TTS  ")
        self._build_translate_tab(self.tab_translate)

        # Tab 2: Glove Telemetry & Hardware Calibration
        self.tab_telemetry = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_telemetry, text="  Sensor Monitor & Calibration  ")
        self._build_telemetry_tab(self.tab_telemetry)

        # Tab 3: Dataset Studio
        self.tab_dataset = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_dataset, text="  Dataset Studio  ")
        self._build_dataset_tab(self.tab_dataset)

        # Tab 4: Model Training
        self.tab_train = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_train, text="  Model Training & Evaluation  ")
        self._build_train_tab(self.tab_train)

    # =========================================================================
    # TAB 1: Live Translation & TTS
    # =========================================================================
    def _build_translate_tab(self, parent):
        grid = tk.Frame(parent, bg="#121820")
        grid.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Top Section: Real-time detected sign and confidence
        top_card = tk.Frame(grid, bg="#1a2332", bd=1, relief="ridge", padx=15, pady=12)
        top_card.pack(fill=tk.X, pady=(0, 10))

        tk.Label(top_card, text="LIVE ASL SIGN DETECTOR", font=("Segoe UI", 9, "bold"), fg="#94a3b8", bg="#1a2332").pack(anchor=tk.W)

        det_row = tk.Frame(top_card, bg="#1a2332")
        det_row.pack(fill=tk.X, pady=5)

        self.lbl_current_sign = tk.Label(det_row, text="WAITING FOR GESTURE...", font=("Segoe UI", 26, "bold"), fg="#38bdf8", bg="#1a2332")
        self.lbl_current_sign.pack(side=tk.LEFT)

        self.lbl_confidence = tk.Label(det_row, text="Confidence: 0.0%", font=("Segoe UI", 12), fg="#10b981", bg="#1a2332")
        self.lbl_confidence.pack(side=tk.RIGHT, padx=10)

        self.prob_bar = ttk.Progressbar(top_card, orient=tk.HORIZONTAL, length=400, mode="determinate")
        self.prob_bar.pack(fill=tk.X, pady=4)

        # Kinematics & Gesture Classification Bar (Static vs. Dynamic Workshop)
        kinematics_row = tk.Frame(top_card, bg="#1a2332")
        kinematics_row.pack(fill=tk.X, pady=(2, 6))

        self.lbl_gesture_type = tk.Label(
            kinematics_row,
            text="TYPE: STATIC POSE ✋",
            font=("Segoe UI", 9, "bold"),
            fg="#38bdf8",
            bg="#0f172a",
            padx=8,
            pady=3,
            relief="groove"
        )
        self.lbl_gesture_type.pack(side=tk.LEFT, padx=(0, 6))

        self.lbl_motion_state = tk.Label(
            kinematics_row,
            text="KINEMATICS: STEADY (0.0°/s)",
            font=("Segoe UI", 9),
            fg="#10b981",
            bg="#0f172a",
            padx=8,
            pady=3,
            relief="groove"
        )
        self.lbl_motion_state.pack(side=tk.LEFT, padx=6)

        self.lbl_latch_status = tk.Label(
            kinematics_row,
            text="LATCH: READY FOR SIGN",
            font=("Segoe UI", 9, "bold"),
            fg="#94a3b8",
            bg="#0f172a",
            padx=8,
            pady=3,
            relief="groove"
        )
        self.lbl_latch_status.pack(side=tk.LEFT, padx=6)

        # Active Model Info Badge
        self.lbl_model_status_badge = tk.Label(
            top_card,
            text="Active Model: Detecting...",
            font=("Segoe UI", 8),
            fg="#94a3b8",
            bg="#1a2332"
        )
        self.lbl_model_status_badge.pack(anchor=tk.W, pady=(2, 0))

        # Middle Section: English Sentence Construction
        mid_card = tk.Frame(grid, bg="#1a2332", bd=1, relief="ridge", padx=15, pady=12)
        mid_card.pack(fill=tk.X, pady=5)

        tk.Label(mid_card, text="CONSTRUCTED ENGLISH SENTENCE", font=("Segoe UI", 9, "bold"), fg="#94a3b8", bg="#1a2332").pack(anchor=tk.W)

        self.txt_english_sentence = tk.Text(mid_card, height=3, bg="#0f172a", fg="#f8fafc", font=("Segoe UI", 13), relief="flat", wrap=tk.WORD, padx=8, pady=8)
        self.txt_english_sentence.pack(fill=tk.X, pady=8)

        btn_row = tk.Frame(mid_card, bg="#1a2332")
        btn_row.pack(fill=tk.X)

        tk.Button(btn_row, text="⌫ Backspace", bg="#334155", fg="white", font=("Segoe UI", 9), command=self._action_backspace).pack(side=tk.LEFT, padx=3)
        tk.Button(btn_row, text="✕ Clear Sentence", bg="#475569", fg="white", font=("Segoe UI", 9), command=self._action_clear_sentence).pack(side=tk.LEFT, padx=3)
        tk.Button(btn_row, text="🔊 Speak English", bg="#2563eb", fg="white", font=("Segoe UI", 9, "bold"), command=self._speak_english).pack(side=tk.LEFT, padx=8)
        tk.Button(btn_row, text="✓ Translate Now", bg="#059669", fg="white", font=("Segoe UI", 9, "bold"), command=self._trigger_translation).pack(side=tk.RIGHT, padx=3)

        # Bottom Section: N-Atlas Nigerian Languages Translation Card
        bot_card = tk.Frame(grid, bg="#1e293b", bd=2, relief="groove", padx=18, pady=14)
        bot_card.pack(fill=tk.BOTH, expand=True, pady=(10, 0))

        lang_control_row = tk.Frame(bot_card, bg="#1e293b")
        lang_control_row.pack(fill=tk.X, pady=(0, 10))

        tk.Label(
            lang_control_row,
            text="N-ATLAS NIGERIAN TRANSLATION",
            font=("Segoe UI", 11, "bold"),
            fg="#fbbf24",
            bg="#1e293b"
        ).pack(side=tk.LEFT)

        tk.Button(
            lang_control_row,
            text="ℹ️ N-Atlas Model Details",
            font=("Segoe UI", 8, "bold"),
            bg="#334155",
            fg="#38bdf8",
            padx=6,
            pady=1,
            command=self._show_natlas_model_info
        ).pack(side=tk.LEFT, padx=10)

        # Neural Engine Toggle Checkbox
        chk_neural = tk.Checkbutton(
            lang_control_row,
            text="Use Deep Neural Transformer",
            variable=self.neural_mode_var,
            command=self._toggle_neural_model,
            bg="#1e293b",
            fg="#cbd5e1",
            selectcolor="#0f172a",
            activebackground="#1e293b",
            activeforeground="#38bdf8",
            font=("Segoe UI", 9)
        )
        chk_neural.pack(side=tk.LEFT, padx=6)

        # Language Radio Buttons
        lang_pill_box = tk.Frame(lang_control_row, bg="#1e293b")
        lang_pill_box.pack(side=tk.RIGHT)

        for lang in ["Yoruba", "Igbo", "Hausa"]:
            r = tk.Radiobutton(
                lang_pill_box,
                text=lang,
                variable=self.target_lang_var,
                value=lang,
                command=self._trigger_translation,
                bg="#1e293b",
                fg="#f8fafc",
                selectcolor="#0f172a",
                activebackground="#1e293b",
                activeforeground="#38bdf8",
                font=("Segoe UI", 10, "bold")
            )
            r.pack(side=tk.LEFT, padx=8)

        # Translation Output Box
        self.lbl_translation_output = tk.Label(
            bot_card,
            text="[Translation will appear here]",
            font=("Segoe UI", 18, "bold"),
            fg="#f8fafc",
            bg="#1e293b",
            wraplength=800,
            justify=tk.LEFT
        )
        self.lbl_translation_output.pack(anchor=tk.W, pady=10)

        # Phonetics Guide
        self.lbl_phonetics = tk.Label(
            bot_card,
            text="Pronunciation: -",
            font=("Segoe UI", 11, "italic"),
            fg="#94a3b8",
            bg="#1e293b"
        )
        self.lbl_phonetics.pack(anchor=tk.W, pady=(0, 10))

        # Bottom Actions & Engine Status
        bot_action_row = tk.Frame(bot_card, bg="#1e293b")
        bot_action_row.pack(fill=tk.X, side=tk.BOTTOM)

        self.btn_speak_nigerian = tk.Button(
            bot_action_row,
            text="🔊 Speak Translated Version (TTS)",
            font=("Segoe UI", 11, "bold"),
            bg="#d97706",
            fg="white",
            padx=16,
            pady=6,
            command=self._speak_nigerian
        )
        self.btn_speak_nigerian.pack(side=tk.LEFT)

        self.lbl_engine_info = tk.Label(
            bot_action_row,
            text="Engine: N-Atlas Lexicon | Diacritics: Active",
            font=("Segoe UI", 9),
            fg="#94a3b8",
            bg="#1e293b"
        )
        self.lbl_engine_info.pack(side=tk.RIGHT, padx=10)

    # =========================================================================
    # =========================================================================
    # TAB 2: Telemetry & Calibration with 3D Skeleton Visualizer
    # =========================================================================
    def _build_telemetry_tab(self, parent):
        container = tk.Frame(parent, bg="#121820")
        container.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Split: Left side = 3D Hand Skeleton Visualizer, Right side = Telemetry Sidebar
        left_pane = tk.Frame(container, bg="#121820")
        left_pane.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 8))

        right_pane = tk.Frame(container, bg="#121820", width=420)
        right_pane.pack(side=tk.RIGHT, fill=tk.BOTH, expand=False, padx=(8, 0))
        right_pane.pack_propagate(False)

        # 1. 3D Hand Skeleton Visualizer with MPU-9250 Orientation Tracking (+Y pointing away from fingers)
        self.hand_visualizer = HandVisualizerWidget(
            left_pane,
            receiver=self.receiver,
            on_cal_flat=self._cal_set_flat,
            on_cal_bent=self._cal_set_bent,
            on_cal_reset=self._cal_reset
        )
        self.hand_visualizer.pack(fill=tk.BOTH, expand=True)

        # 2. Right Pane: Detailed Telemetry Bars & Diagnostics
        finger_names = ["Thumb", "Index", "Middle", "Ring", "Pinky"]
        self.l_bars = []
        self.l_bar_labels = []
        self.r_bars = []
        self.r_bar_labels = []

        # Left Hand Panel
        self.l_hand_frame = tk.LabelFrame(
            right_pane,
            text=" Left Glove Telemetry (ADC & IMU) ",
            font=("Segoe UI", 9, "bold"),
            fg="#38bdf8",
            bg="#1a2332",
            padx=10,
            pady=8
        )
        self.l_hand_frame.pack(fill=tk.X, pady=(0, 6))

        for fname in finger_names:
            row = tk.Frame(self.l_hand_frame, bg="#1a2332")
            row.pack(fill=tk.X, pady=2)
            lbl = tk.Label(row, text=f"{fname}: 0%", width=16, anchor=tk.W, font=("Segoe UI", 8), bg="#1a2332", fg="#f8fafc")
            lbl.pack(side=tk.LEFT)
            bar = ttk.Progressbar(row, orient=tk.HORIZONTAL, length=140, mode="determinate")
            bar.pack(side=tk.RIGHT, fill=tk.X, expand=True)
            self.l_bars.append(bar)
            self.l_bar_labels.append(lbl)

        self.l_imu_label = tk.Label(self.l_hand_frame, text="IMU: Ax:0 Ay:0 Az:0 | Gx:0 Gy:0 Gz:0", font=("Consolas", 8), fg="#94a3b8", bg="#1a2332", justify=tk.LEFT)
        self.l_imu_label.pack(fill=tk.X, pady=(4, 0))

        self.l_orient_label = tk.Label(self.l_hand_frame, text="Orientation: Pitch: 0.0° | Roll: 0.0° | Yaw: 0.0°", font=("Consolas", 8), fg="#94a3b8", bg="#1a2332", justify=tk.LEFT)
        self.l_orient_label.pack(fill=tk.X, pady=(2, 0))

        self.l_palm_badge = tk.Label(self.l_hand_frame, text="PALM: PALM DOWN (Flat Rest)", font=("Segoe UI", 9, "bold"), fg="#38bdf8", bg="#0f172a", padx=6, pady=3, relief="groove")
        self.l_palm_badge.pack(fill=tk.X, pady=(3, 0))

        # Right Hand Panel
        self.r_hand_frame = tk.LabelFrame(
            right_pane,
            text=" Right Glove Telemetry (ADC & IMU) ",
            font=("Segoe UI", 9, "bold"),
            fg="#10b981",
            bg="#1a2332",
            padx=10,
            pady=8
        )
        self.r_hand_frame.pack(fill=tk.X, pady=6)

        for fname in finger_names:
            row = tk.Frame(self.r_hand_frame, bg="#1a2332")
            row.pack(fill=tk.X, pady=2)
            lbl = tk.Label(row, text=f"{fname}: 0%", width=16, anchor=tk.W, font=("Segoe UI", 8), bg="#1a2332", fg="#f8fafc")
            lbl.pack(side=tk.LEFT)
            bar = ttk.Progressbar(row, orient=tk.HORIZONTAL, length=140, mode="determinate")
            bar.pack(side=tk.RIGHT, fill=tk.X, expand=True)
            self.r_bars.append(bar)
            self.r_bar_labels.append(lbl)

        self.r_imu_label = tk.Label(self.r_hand_frame, text="IMU: Ax:0 Ay:0 Az:0 | Gx:0 Gy:0 Gz:0", font=("Consolas", 8), fg="#94a3b8", bg="#1a2332", justify=tk.LEFT)
        self.r_imu_label.pack(fill=tk.X, pady=(4, 0))

        self.r_orient_label = tk.Label(self.r_hand_frame, text="Orientation: Pitch: 0.0° | Roll: 0.0° | Yaw: 0.0°", font=("Consolas", 8), fg="#94a3b8", bg="#1a2332", justify=tk.LEFT)
        self.r_orient_label.pack(fill=tk.X, pady=(2, 0))

        self.r_palm_badge = tk.Label(self.r_hand_frame, text="PALM: PALM DOWN (Flat Rest)", font=("Segoe UI", 9, "bold"), fg="#10b981", bg="#0f172a", padx=6, pady=3, relief="groove")
        self.r_palm_badge.pack(fill=tk.X, pady=(3, 0))

        # Calibration Controls Panel in Sidebar
        cal_panel = tk.LabelFrame(right_pane, text=" Dual Glove ADC Calibration ", font=("Segoe UI", 9, "bold"), fg="#fbbf24", bg="#1e293b", padx=10, pady=8)
        cal_panel.pack(fill=tk.X, pady=(6, 0))

        cal_btns = tk.Frame(cal_panel, bg="#1e293b")
        cal_btns.pack(fill=tk.X)

        tk.Button(cal_btns, text="Both Flat (0°)", bg="#0284c7", fg="white", font=("Segoe UI", 8, "bold"), command=lambda: self._cal_set_flat(None)).pack(side=tk.LEFT, padx=3)
        tk.Button(cal_btns, text="Both Fist (90°)", bg="#e11d48", fg="white", font=("Segoe UI", 8, "bold"), command=lambda: self._cal_set_bent(None)).pack(side=tk.LEFT, padx=3)
        tk.Button(cal_btns, text="Reset", bg="#475569", fg="white", font=("Segoe UI", 8), command=lambda: self._cal_reset(None)).pack(side=tk.LEFT, padx=3)

        self.lbl_cal_status = tk.Label(cal_panel, text="Status: Ready", fg="#94a3b8", bg="#1e293b", font=("Segoe UI", 8))
        self.lbl_cal_status.pack(fill=tk.X, pady=(4, 0))

    # =========================================================================
    # TAB 3: Dataset Studio
    # =========================================================================
    def _build_dataset_tab(self, parent):
        container = tk.Frame(parent, bg="#121820")
        container.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        top_controls = tk.Frame(container, bg="#1a2332", padx=15, pady=12, bd=1, relief="ridge")
        top_controls.pack(fill=tk.X, pady=(0, 10))

        # Row 0: Target Gesture & Hand Mode Selection
        row0 = tk.Frame(top_controls, bg="#1a2332")
        row0.pack(fill=tk.X, pady=(0, 6))

        tk.Label(row0, text="Target ASL Gesture:", font=("Segoe UI", 10, "bold"), bg="#1a2332", fg="#f8fafc").pack(side=tk.LEFT)
        self.cmb_gestures = ttk.Combobox(row0, values=config.DEFAULT_GESTURES, width=16, font=("Segoe UI", 10))
        self.cmb_gestures.set("A")
        self.cmb_gestures.pack(side=tk.LEFT, padx=(6, 4))
        self.cmb_gestures.bind("<<ComboboxSelected>>", self._on_gesture_combo_change)

        self.lbl_gesture_type = tk.Label(row0, text="[STATIC POSE]", font=("Segoe UI", 8, "bold"), fg="#38bdf8", bg="#032b43", padx=8, pady=3, relief="groove")
        self.lbl_gesture_type.pack(side=tk.LEFT, padx=(4, 15))

        tk.Label(row0, text="Hand Mode:", font=("Segoe UI", 9, "bold"), bg="#1a2332", fg="#fbbf24").pack(side=tk.LEFT, padx=(10, 6))
        tk.Radiobutton(row0, text="🖐 Right Hand (14F)", variable=self.dataset_hand_mode_var, value="right", bg="#1a2332", fg="#f8fafc", selectcolor="#0f172a", font=("Segoe UI", 9)).pack(side=tk.LEFT, padx=4)
        tk.Radiobutton(row0, text="🖐 Left Hand (14F)", variable=self.dataset_hand_mode_var, value="left", bg="#1a2332", fg="#f8fafc", selectcolor="#0f172a", font=("Segoe UI", 9)).pack(side=tk.LEFT, padx=4)
        tk.Radiobutton(row0, text="👐 Dual Gloves (28F)", variable=self.dataset_hand_mode_var, value="both", bg="#1a2332", fg="#f8fafc", selectcolor="#0f172a", font=("Segoe UI", 9)).pack(side=tk.LEFT, padx=4)

        # Row 1: Dual Recording Controls (Static 50+ Burst vs Dynamic Motion Stream)
        row1 = tk.Frame(top_controls, bg="#1a2332")
        row1.pack(fill=tk.X, pady=(4, 6))

        # Static Pose 50+ Burst Controls
        static_box = tk.LabelFrame(row1, text=" Static Pose Capture (Spatial Invariance) ", font=("Segoe UI", 8, "bold"), fg="#38bdf8", bg="#0f172a", padx=8, pady=6)
        static_box.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 6))

        self.btn_burst_snapshot = tk.Button(
            static_box,
            text="📸 Burst Capture (50+ Snapshots)",
            bg="#0284c7",
            fg="white",
            font=("Segoe UI", 9, "bold"),
            padx=10,
            pady=4,
            command=self._start_static_burst_recording
        )
        self.btn_burst_snapshot.pack(side=tk.LEFT, padx=3)

        tk.Label(static_box, text="Count:", font=("Segoe UI", 9), bg="#0f172a", fg="#94a3b8").pack(side=tk.LEFT, padx=(6, 2))
        self.spn_burst_count = ttk.Spinbox(static_box, from_=10, to=200, increment=10, width=5)
        self.spn_burst_count.set("50")
        self.spn_burst_count.pack(side=tk.LEFT, padx=3)

        self.btn_snapshot = tk.Button(
            static_box,
            text="+ 1 Frame",
            bg="#334155",
            fg="white",
            font=("Segoe UI", 8),
            padx=6,
            pady=3,
            command=self._record_single_snapshot
        )
        self.btn_snapshot.pack(side=tk.LEFT, padx=(6, 2))

        # Dynamic Motion Stream Controls
        dynamic_box = tk.LabelFrame(row1, text=" Dynamic Gesture Capture (Trajectory) ", font=("Segoe UI", 8, "bold"), fg="#fbbf24", bg="#0f172a", padx=8, pady=6)
        dynamic_box.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(6, 0))

        self.btn_record = tk.Button(
            dynamic_box,
            text="⏺ Record Stream",
            bg="#e11d48",
            fg="white",
            font=("Segoe UI", 9, "bold"),
            padx=10,
            pady=4,
            command=self._start_recording_session
        )
        self.btn_record.pack(side=tk.LEFT, padx=3)

        tk.Label(dynamic_box, text="Duration (s):", font=("Segoe UI", 9), bg="#0f172a", fg="#94a3b8").pack(side=tk.LEFT, padx=(6, 2))
        self.spn_duration = ttk.Spinbox(dynamic_box, from_=1.0, to=10.0, increment=0.5, width=5)
        self.spn_duration.set("3.0")
        self.spn_duration.pack(side=tk.LEFT, padx=3)

        # Row 2: Live Spatial Guidance Banner
        self.lbl_capture_guidance = tk.Label(
            top_controls,
            text="💡 Static Pose Tip: Hold 'A' handshape and click '📸 Burst Capture (50+)'. Slowly move hand in 3D space during capture for position invariance!",
            font=("Segoe UI", 9, "italic"),
            fg="#38bdf8",
            bg="#0f172a",
            padx=10,
            pady=5,
            relief="groove",
            wraplength=850,
            justify=tk.LEFT
        )
        self.lbl_capture_guidance.pack(fill=tk.X, pady=(4, 6))

        # Progress bar
        self.rec_prog_bar = ttk.Progressbar(top_controls, orient=tk.HORIZONTAL, mode="determinate")
        self.rec_prog_bar.pack(fill=tk.X, pady=(2, 4))

        self.lbl_rec_status = tk.Label(top_controls, text="Status: Ready to capture", font=("Segoe UI", 9), bg="#1a2332", fg="#94a3b8")
        self.lbl_rec_status.pack(anchor=tk.W)

        # Dataset Table & Stats
        bot_frame = tk.Frame(container, bg="#121820")
        bot_frame.pack(fill=tk.BOTH, expand=True)

        list_frame = tk.LabelFrame(bot_frame, text=" Dataset Summary (Class Distribution) ", font=("Segoe UI", 10, "bold"), fg="#38bdf8", bg="#1a2332", padx=10, pady=10)
        list_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))

        self.tree_dataset = ttk.Treeview(list_frame, columns=("Gesture", "Samples"), show="headings", height=12)
        self.tree_dataset.heading("Gesture", text="Gesture Class")
        self.tree_dataset.heading("Samples", text="Sample Count")
        self.tree_dataset.column("Gesture", width=180)
        self.tree_dataset.column("Samples", width=100)
        self.tree_dataset.tag_configure("black_text", foreground="#000000", background="#ffffff")
        self.tree_dataset.pack(fill=tk.BOTH, expand=True)

        manage_col = tk.Frame(bot_frame, bg="#121820", width=220)
        manage_col.pack(side=tk.RIGHT, fill=tk.Y, padx=(5, 0))

        tk.Button(manage_col, text="🔄 Refresh Table", bg="#1e293b", fg="white", font=("Segoe UI", 9), width=22, command=self._refresh_dataset_table).pack(pady=4)
        tk.Button(manage_col, text="⚡ Generate Bootstrap Data", bg="#0284c7", fg="white", font=("Segoe UI", 9, "bold"), width=22, command=self._generate_bootstrap).pack(pady=4)
        tk.Button(manage_col, text="🗑 Delete Selected Gesture", bg="#b91c1c", fg="white", font=("Segoe UI", 9), width=22, command=self._delete_selected_gesture).pack(pady=4)
        tk.Button(manage_col, text="⚠ Wipe Entire Dataset", bg="#7f1d1d", fg="white", font=("Segoe UI", 9), width=22, command=self._wipe_dataset).pack(pady=4)

        # Dataset Metadata Info Badge
        self.lbl_dataset_mode_info = tk.Label(
            manage_col,
            text="Dataset: Loading...",
            font=("Segoe UI", 8),
            fg="#38bdf8",
            bg="#121820",
            wraplength=200,
            justify=tk.LEFT
        )
        self.lbl_dataset_mode_info.pack(pady=(10, 4))

        self._refresh_dataset_table()

    # =========================================================================
    # TAB 4: Model Training
    # =========================================================================
    def _build_train_tab(self, parent):
        container = tk.Frame(parent, bg="#121820")
        container.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        card = tk.Frame(container, bg="#1a2332", padx=20, pady=16, bd=1, relief="ridge")
        card.pack(fill=tk.X, pady=(0, 10))

        tk.Label(card, text="CLASSIFIER CONFIGURATION", font=("Segoe UI", 11, "bold"), fg="#38bdf8", bg="#1a2332").pack(anchor=tk.W, pady=(0, 10))

        opt_row = tk.Frame(card, bg="#1a2332")
        opt_row.pack(fill=tk.X, pady=4)

        tk.Label(opt_row, text="Algorithm:", font=("Segoe UI", 10), bg="#1a2332", fg="#f8fafc").pack(side=tk.LEFT)
        self.model_type_var = tk.StringVar(value="rf")
        tk.Radiobutton(opt_row, text="Random Forest", variable=self.model_type_var, value="rf", bg="#1a2332", fg="white", selectcolor="#0f172a").pack(side=tk.LEFT, padx=10)
        tk.Radiobutton(opt_row, text="MLP Neural Net", variable=self.model_type_var, value="mlp", bg="#1a2332", fg="white", selectcolor="#0f172a").pack(side=tk.LEFT, padx=10)

        # Hand Mode Training Selector
        train_mode_row = tk.Frame(card, bg="#1a2332")
        train_mode_row.pack(fill=tk.X, pady=6)

        tk.Label(train_mode_row, text="Hand Mode:", font=("Segoe UI", 10, "bold"), bg="#1a2332", fg="#38bdf8").pack(side=tk.LEFT)
        tk.Radiobutton(train_mode_row, text="Auto-Detect from Data", variable=self.train_hand_mode_var, value="auto", bg="#1a2332", fg="white", selectcolor="#0f172a").pack(side=tk.LEFT, padx=6)
        tk.Radiobutton(train_mode_row, text="Right Hand Only (14 Feat)", variable=self.train_hand_mode_var, value="right", bg="#1a2332", fg="white", selectcolor="#0f172a").pack(side=tk.LEFT, padx=6)
        tk.Radiobutton(train_mode_row, text="Left Hand Only (14 Feat)", variable=self.train_hand_mode_var, value="left", bg="#1a2332", fg="white", selectcolor="#0f172a").pack(side=tk.LEFT, padx=6)
        tk.Radiobutton(train_mode_row, text="Dual Gloves (28 Feat)", variable=self.train_hand_mode_var, value="dual", bg="#1a2332", fg="white", selectcolor="#0f172a").pack(side=tk.LEFT, padx=6)

        # Spatial Invariance Checkbox Row
        spatial_row = tk.Frame(card, bg="#1a2332")
        spatial_row.pack(fill=tk.X, pady=(6, 4))

        self.spatial_invariance_var = tk.BooleanVar(value=True)
        self.chk_spatial = tk.Checkbutton(
            spatial_row,
            text=" 🌐 Spatial Translation & Position Invariance (Augment 3D Position, Motion & Tilt)",
            variable=self.spatial_invariance_var,
            bg="#1a2332",
            fg="#38bdf8",
            selectcolor="#0f172a",
            font=("Segoe UI", 9, "bold")
        )
        self.chk_spatial.pack(side=tk.LEFT)

        tk.Label(
            card,
            text="ℹ Augments training dataset with simulated 3D spatial translations, gravity tilts (±15°), and magnetic field variations so hand poses are detected anywhere in space.",
            font=("Segoe UI", 8, "italic"),
            fg="#94a3b8",
            bg="#1a2332",
            wraplength=850,
            justify=tk.LEFT
        ).pack(anchor=tk.W, pady=(0, 8))

        self.btn_train = tk.Button(
            card,
            text="🚀 Train ASL Recognition Model",
            bg="#2563eb",
            fg="white",
            font=("Segoe UI", 11, "bold"),
            padx=16,
            pady=8,
            command=self._start_training
        )
        self.btn_train.pack(anchor=tk.W, pady=(4, 8))

        # Metrics Display Box
        metrics_box = tk.LabelFrame(container, text=" Training Evaluation Results ", font=("Segoe UI", 10, "bold"), fg="#10b981", bg="#1a2332", padx=15, pady=12)
        metrics_box.pack(fill=tk.BOTH, expand=True)

        self.lbl_train_acc = tk.Label(metrics_box, text="Test Accuracy: Not Trained Yet", font=("Segoe UI", 14, "bold"), fg="#10b981", bg="#1a2332")
        self.lbl_train_acc.pack(anchor=tk.W, pady=4)

        self.txt_train_report = tk.Text(metrics_box, bg="#0f172a", fg="#f8fafc", font=("Consolas", 10), relief="flat")
        self.txt_train_report.pack(fill=tk.BOTH, expand=True, pady=6)


    # =========================================================================
    # Background Refresh & Inference Loop
    # =========================================================================
    def _telemetry_refresh_loop(self):
        try:
            l_state, r_state = self.receiver.get_latest_states()

            # Update Header Badges & Connection Bar Inbuilt LEDs
            if l_state["connected"]:
                self.left_indicator.config(text=f"● LEFT GLOVE: {self.receiver.left_fps:.0f} Hz", fg="#10b981")
                self.led_left.config(text="● INBUILT LED: ON", fg="#38bdf8", bg="#032b43")
                self.lbl_left_conn_status.config(text=f"Active ({self.receiver.left_fps:.0f} Hz)", fg="#10b981")
                if hasattr(self, "btn_left_connect"):
                    self.btn_left_connect.config(text="✕ Disconnect", bg="#b91c1c")
            else:
                self.left_indicator.config(text="● LEFT GLOVE: OFF", fg="#ef4444")
                self.led_left.config(text="● INBUILT LED: OFF", fg="#64748b", bg="#0f172a")
                if hasattr(self, "btn_left_connect") and str(self.btn_left_connect["state"]) != "disabled":
                    self.btn_left_connect.config(text="🔗 Connect", bg="#0284c7")
                curr_l = self.lbl_left_conn_status.cget("text")
                if not any(k in curr_l for k in ["Pinging", "Connecting", "Failed", "Standby"]):
                    self.lbl_left_conn_status.config(text="Standby (Click Connect)", fg="#94a3b8")

            if r_state["connected"]:
                self.right_indicator.config(text=f"● RIGHT GLOVE: {self.receiver.right_fps:.0f} Hz", fg="#10b981")
                self.led_right.config(text="● INBUILT LED: ON", fg="#10b981", bg="#064e3b")
                self.lbl_right_conn_status.config(text=f"Active ({self.receiver.right_fps:.0f} Hz)", fg="#10b981")
                if hasattr(self, "btn_right_connect"):
                    self.btn_right_connect.config(text="✕ Disconnect", bg="#b91c1c")
            else:
                self.right_indicator.config(text="● RIGHT GLOVE: OFF", fg="#ef4444")
                self.led_right.config(text="● INBUILT LED: OFF", fg="#64748b", bg="#0f172a")
                if hasattr(self, "btn_right_connect") and str(self.btn_right_connect["state"]) != "disabled":
                    self.btn_right_connect.config(text="🔗 Connect", bg="#059669")
                curr_r = self.lbl_right_conn_status.cget("text")
                if not any(k in curr_r for k in ["Pinging", "Connecting", "Failed", "Standby"]):
                    self.lbl_right_conn_status.config(text="Standby (Click Connect)", fg="#94a3b8")

            # Update Telemetry Bars
            finger_abbr = ["Thumb", "Index", "Middle", "Ring", "Pinky"]
            for i in range(5):
                l_val = int(l_state["flex_norm"][i] * 100)
                l_raw = l_state["flex_raw"][i]
                self.l_bars[i]["value"] = l_val
                self.l_bar_labels[i].config(text=f"{finger_abbr[i]}: {l_val}% ({l_raw})")

                r_val = int(r_state["flex_norm"][i] * 100)
                r_raw = r_state["flex_raw"][i]
                self.r_bars[i]["value"] = r_val
                self.r_bar_labels[i].config(text=f"{finger_abbr[i]}: {r_val}% ({r_raw})")

            lax, lay, laz = l_state["accel"]
            lgx, lgy, lgz = l_state["gyro"]
            self.l_imu_label.config(text=f"Ax:{lax} Ay:{lay} Az:{laz} | Gx:{lgx} Gy:{lgy} Gz:{lgz}")

            rax, ray, raz = r_state["accel"]
            rgx, rgy, rgz = r_state["gyro"]
            self.r_imu_label.config(text=f"Ax:{rax} Ay:{ray} Az:{raz} | Gx:{rgx} Gy:{rgy} Gz:{rgz}")

            # Update live orientation text & semantic palm direction labels
            lp = l_state.get("pitch_deg", 0.0)
            lr = l_state.get("roll_deg", 0.0)
            ly = l_state.get("yaw_deg", 0.0)
            l_palm = l_state.get("palm_orientation", "UNKNOWN")
            self.l_orient_label.config(text=f"Orientation: Pitch:{lp:+.1f}° | Roll:{lr:+.1f}° | Yaw:{ly:+.1f}°")
            self.l_palm_badge.config(text=f"PALM: {l_palm}")

            rp = r_state.get("pitch_deg", 0.0)
            rr = r_state.get("roll_deg", 0.0)
            ry = r_state.get("yaw_deg", 0.0)
            r_palm = r_state.get("palm_orientation", "UNKNOWN")
            self.r_orient_label.config(text=f"Orientation: Pitch:{rp:+.1f}° | Roll:{rr:+.1f}° | Yaw:{ry:+.1f}°")
            self.r_palm_badge.config(text=f"PALM: {r_palm}")

            # Update Model Badge in Header & Tab 1
            if self.recognizer.is_loaded:
                m_mode_str = self.recognizer.hand_mode.upper()
                n_f = self.recognizer.expected_features
                n_c = len(self.recognizer.label_encoder.classes_) if self.recognizer.label_encoder else 0
                self.lbl_model_indicator.config(text=f"● MODEL: {m_mode_str} ({n_f}F)", fg="#10b981")
                if hasattr(self, "lbl_model_status_badge"):
                    self.lbl_model_status_badge.config(
                        text=f"Active Model: {m_mode_str} ({n_f} Feat) | {n_c} Classes Trained",
                        fg="#38bdf8"
                    )
            else:
                self.lbl_model_indicator.config(text="● MODEL: UNTRAINED", fg="#ef4444")
                if hasattr(self, "lbl_model_status_badge"):
                    self.lbl_model_status_badge.config(text="Active Model: Not Loaded (Train model in Tab 4)", fg="#ef4444")

            # Update 3D Hand Skeleton Visualizer (MPU-9250 orientation + flex kinematics)
            if hasattr(self, "hand_visualizer"):
                self.hand_visualizer.update_frame(l_state, r_state)

            # Real-Time Gesture Inference (Gated: checks glove connectivity according to active model hand)
            model_hand = self.recognizer.hand_mode if self.recognizer.is_loaded else "right"
            if model_hand == "right":
                is_glove_active = r_state["connected"] or self.receiver.simulation_mode
                wait_text = "WAITING FOR RIGHT GLOVE"
            elif model_hand == "left":
                is_glove_active = l_state["connected"] or self.receiver.simulation_mode
                wait_text = "WAITING FOR LEFT GLOVE"
            else:
                is_glove_active = (l_state["connected"] or r_state["connected"]) or self.receiver.simulation_mode
                wait_text = "WAITING FOR GLOVES (DISCONNECTED)"

            if self.live_recognition_active.get() and self.recognizer.is_loaded and is_glove_active:
                vec = self.receiver.get_synchronized_feature_vector(hand_mode=model_hand)
                motion_meta = self.receiver.get_motion_metrics(hand_mode=model_hand)
                label, conf, is_new_event, sign_meta = self.recognizer.process_live_stream(vec, motion_meta)

                # Update live kinematics & classification badges
                if hasattr(self, "lbl_gesture_type"):
                    g_type = sign_meta.get("gesture_type", "NONE")
                    if g_type != "NONE":
                        self.lbl_gesture_type.config(
                            text=f"TYPE: {g_type}",
                            fg="#c084fc" if sign_meta.get("is_dynamic") else "#38bdf8"
                        )
                    else:
                        self.lbl_gesture_type.config(text="TYPE: WAITING ✋", fg="#64748b")

                if hasattr(self, "lbl_motion_state"):
                    vel = sign_meta.get("velocity_dps", 0.0)
                    m_state = sign_meta.get("motion_state", "STEADY")
                    is_mov = "MOTION" in m_state
                    self.lbl_motion_state.config(
                        text=f"KINEMATICS: {m_state} ({vel:.1f}°/s)",
                        fg="#f59e0b" if is_mov else "#10b981"
                    )

                if hasattr(self, "lbl_latch_status"):
                    if sign_meta.get("is_latched"):
                        self.lbl_latch_status.config(text="LATCH: COMMITTED (NO REPEAT)", fg="#fbbf24")
                    else:
                        self.lbl_latch_status.config(text="LATCH: READY FOR NEW SIGN", fg="#10b981")

                if label and label not in ["IDLE", "REST"]:
                    self.lbl_current_sign.config(text=f"SIGN: {label}")
                    self.lbl_confidence.config(text=f"Confidence: {conf*100:.1f}%")
                    self.prob_bar["value"] = int(conf * 100)
                elif label in ["IDLE", "REST"]:
                    self.lbl_current_sign.config(text="RESTING (IDLE)")
                    self.lbl_confidence.config(text=f"Confidence: {conf*100:.1f}%")
                    self.prob_bar["value"] = int(conf * 100)
                else:
                    self.lbl_current_sign.config(text="LISTENING...")
                    self.lbl_confidence.config(text="Confidence: 0.0%")
                    self.prob_bar["value"] = 0

                if is_new_event and label and label not in ["IDLE", "REST"]:
                    self._on_gesture_event(label)
            else:
                # Gloves are not streaming or recognition paused
                if not is_glove_active:
                    self.lbl_current_sign.config(text=wait_text)
                else:
                    self.lbl_current_sign.config(text="PAUSED")
                self.lbl_confidence.config(text="Confidence: 0.0%")
                self.prob_bar["value"] = 0
                if hasattr(self, "lbl_latch_status"):
                    self.lbl_latch_status.config(text="LATCH: IDLE", fg="#64748b")
                if hasattr(self, "lbl_motion_state"):
                    self.lbl_motion_state.config(text="KINEMATICS: IDLE", fg="#64748b")
                if hasattr(self, "lbl_gesture_type"):
                    self.lbl_gesture_type.config(text="TYPE: IDLE", fg="#64748b")
                self.recognizer.reset_state()


        except Exception as e:
            logger.debug(f"Refresh loop exception: {e}")

        self.after(50, self._telemetry_refresh_loop) # ~20Hz UI refresh

    def _on_gesture_event(self, sign: str):
        """Called when a stable gesture is confirmed."""
        sentence = self.builder.add_token(sign)
        self.txt_english_sentence.delete("1.0", tk.END)
        self.txt_english_sentence.insert("1.0", sentence)
        self._trigger_translation()

    # =========================================================================
    # Translation & TTS Handlers
    # =========================================================================
    def _trigger_translation(self):
        eng_text = self.txt_english_sentence.get("1.0", tk.END).strip()
        if not eng_text:
            return

        target_lang = self.target_lang_var.get()
        result = self.translator.translate(eng_text, target_lang)

        trans_text = result["translation"]
        phonetic = result["phonetic"]
        engine = result["engine"]

        self.lbl_translation_output.config(text=trans_text)
        self.lbl_phonetics.config(text=f"Pronunciation: {phonetic}")
        self.lbl_engine_info.config(text=f"Engine: {engine} | Target: {target_lang}")

        if self.auto_speak_var.get():
            self._speak_nigerian()

    def _toggle_neural_model(self):
        """Toggle between N-Atlas Authentic Lexicon and Deep Neural Transformer."""
        if self.neural_mode_var.get():
            if not self.translator.neural_ready:
                self.lbl_engine_info.config(text="Engine: Loading N-Atlas Neural Model in background...", fg="#f59e0b")
                self.translator.load_neural_model_async()
                def _check_ready():
                    if self.translator.neural_ready:
                        self.lbl_engine_info.config(text="Engine: N-Atlas Neural Transformer (Active)", fg="#10b981")
                        self._trigger_translation()
                    elif self.translator.neural_loading:
                        self.after(1000, _check_ready)
                    else:
                        self.lbl_engine_info.config(text="Engine: N-Atlas Lexicon (Neural load failed/offline)", fg="#94a3b8")
                self.after(1000, _check_ready)
            else:
                self.lbl_engine_info.config(text="Engine: N-Atlas Neural Transformer (Active)", fg="#10b981")
                self._trigger_translation()
        else:
            self.lbl_engine_info.config(text="Engine: N-Atlas Authentic Lexicon (Active)", fg="#94a3b8")
            self._trigger_translation()

    def _show_natlas_model_info(self):
        """Displays modal explaining how N-Atlas is included and its architecture."""
        info_win = tk.Toplevel(self)
        info_win.title("N-Atlas Multilingual Model Details & Architecture")
        info_win.geometry("640x520")
        info_win.configure(bg="#0f172a")
        info_win.resizable(False, False)
        info_win.transient(self)
        info_win.grab_set()

        card = tk.Frame(info_win, bg="#1a2332", padx=20, pady=16, bd=2, relief="groove")
        card.pack(fill=tk.BOTH, expand=True, padx=14, pady=14)

        tk.Label(
            card,
            text="🇳🇬 N-ATLAS TRANSLATION MODEL INTEGRATION",
            font=("Segoe UI", 13, "bold"),
            fg="#fbbf24",
            bg="#1a2332"
        ).pack(pady=(0, 6))

        details = self.translator.get_model_details()
        status_line = f"Active Engine: {details['active_engine']} | Neural Checkpoint: {details['neural_checkpoint']}"
        tk.Label(card, text=status_line, font=("Segoe UI", 9, "bold"), fg="#10b981", bg="#1a2332").pack(pady=(0, 8))

        doc_text = (
            "1. WHAT IS N-ATLAS?\n"
            "   N-Atlas is an Afro-centric Multilingual NLP initiative developed to solve the\n"
            "   low-resource language gap for major African languages:\n"
            "   • Yorùbá (yor_Latn / yo) — 45+ Million speakers (Niger-Congo)\n"
            "   • Igbo (ibo_Latn / ig)   — 30+ Million speakers (Niger-Congo)\n"
            "   • Hausa (hau_Latn / ha)  — 70+ Million speakers (Afroasiatic)\n\n"
            "2. HOW IT IS INCLUDED IN THIS PROJECT (software/translator.py):\n"
            "   The project uses a resilient Dual-Tier translation architecture:\n"
            "   • TIER 1 - Fast Offline Tonal Lexicon:\n"
            "     Curated high-accuracy bilingual repository with authentic tonal diacritics.\n"
            "     Runs with 0ms network latency — perfect for offline edge deployment.\n"
            "   • TIER 2 - Deep Neural Transformer (Hugging Face Transformers):\n"
            "     Integrates Seq2Seq transformer models (facebook/nllb-200-distilled-600M\n"
            "     and castorini/afri-n-atlas) for open-vocabulary generation via beam search.\n\n"
            "3. TONAL DIACRITIC PRESERVATION:\n"
            "   Yorùbá and Igbo are tonal languages where accents change word meaning:\n"
            "   (e.g., in Yorùbá: 'ọwọ́' = hand, 'owó' = money, 'ọ̀wọ̀' = respect).\n"
            "   N-Atlas preserves authentic high (´), low (`), and subdots (ẹ, ọ, ṣ, ụ, ị)!\n\n"
            "4. SPEECH SYNTHESIS (TTS):\n"
            "   The phonetic pronunciation guide passes these diacritics to the multilingual\n"
            "   TTS engine to pronounce authentic indigenous audio for the listener."
        )

        txt_box = tk.Text(card, bg="#0f172a", fg="#f8fafc", font=("Consolas", 9), relief="sunken", padx=10, pady=10, wrap=tk.WORD)
        txt_box.insert("1.0", doc_text)
        txt_box.config(state=tk.DISABLED)
        txt_box.pack(fill=tk.BOTH, expand=True, pady=4)

        tk.Button(
            card,
            text="Close",
            font=("Segoe UI", 10, "bold"),
            bg="#0284c7",
            fg="white",
            padx=16,
            pady=4,
            command=info_win.destroy
        ).pack(pady=(8, 0))

    def _speak_english(self):
        text = self.txt_english_sentence.get("1.0", tk.END).strip()
        if text:
            self.tts.speak(text, "English")

    def _speak_nigerian(self):
        text = self.lbl_translation_output.cget("text")
        if text and text != "[Translation will appear here]":
            self.tts.speak(text, self.target_lang_var.get())

    def _action_backspace(self):
        new_text = self.builder.backspace()
        self.txt_english_sentence.delete("1.0", tk.END)
        self.txt_english_sentence.insert("1.0", new_text)
        self._trigger_translation()

    def _action_clear_sentence(self):
        self.builder.clear()
        self.txt_english_sentence.delete("1.0", tk.END)
        self.lbl_translation_output.config(text="[Translation will appear here]")
        self.lbl_phonetics.config(text="Pronunciation: -")
        self.recognizer.reset_state()
        self.lbl_translation_output.config(text="[Translation will appear here]")
        self.lbl_phonetics.config(text="Pronunciation: -")

    # =========================================================================
    # Calibration Handlers
    # =========================================================================
    def _cal_set_flat(self, hand=None):
        l_s, r_s = self.receiver.get_latest_states()
        cal = self.receiver.calibration
        if hand == "LEFT":
            cal["LEFT"]["flex_flat"] = list(l_s["flex_raw"])
            msg = "Left Glove Flat (0°) Calibrated!"
        elif hand == "RIGHT":
            cal["RIGHT"]["flex_flat"] = list(r_s["flex_raw"])
            msg = "Right Glove Flat (0°) Calibrated!"
        else:
            cal["LEFT"]["flex_flat"] = list(l_s["flex_raw"])
            cal["RIGHT"]["flex_flat"] = list(r_s["flex_raw"])
            msg = "Both Gloves Flat (0°) Calibrated!"

        self.receiver.save_calibration(cal)
        self.lbl_cal_status.config(text=f"Status: {msg}", fg="#10b981")
        if hasattr(self, "hand_visualizer"):
            self.hand_visualizer.lbl_cal_status.config(text=f"Status: {msg}", fg="#10b981")
        return msg

    def _cal_set_bent(self, hand=None):
        l_s, r_s = self.receiver.get_latest_states()
        cal = self.receiver.calibration
        if hand == "LEFT":
            cal["LEFT"]["flex_bent"] = list(l_s["flex_raw"])
            msg = "Left Glove Closed Fist (90°) Calibrated!"
        elif hand == "RIGHT":
            cal["RIGHT"]["flex_bent"] = list(r_s["flex_raw"])
            msg = "Right Glove Closed Fist (90°) Calibrated!"
        else:
            cal["LEFT"]["flex_bent"] = list(l_s["flex_raw"])
            cal["RIGHT"]["flex_bent"] = list(r_s["flex_raw"])
            msg = "Both Gloves Closed Fist (90°) Calibrated!"

        self.receiver.save_calibration(cal)
        self.lbl_cal_status.config(text=f"Status: {msg}", fg="#10b981")
        if hasattr(self, "hand_visualizer"):
            self.hand_visualizer.lbl_cal_status.config(text=f"Status: {msg}", fg="#10b981")
        return msg

    def _cal_reset(self, hand=None):
        cal = self.receiver.load_default_calibration()
        self.receiver.save_calibration(cal)
        msg = "Calibration Defaults Restored"
        self.lbl_cal_status.config(text=f"Status: {msg}", fg="#94a3b8")
        if hasattr(self, "hand_visualizer"):
            self.hand_visualizer.lbl_cal_status.config(text=f"Status: {msg}", fg="#94a3b8")
        return msg

    # =========================================================================
    # Dataset & Training Handlers
    # =========================================================================
    def _toggle_simulation(self):
        if self.sim_mode_var.get():
            self.receiver.start_simulation()
        else:
            self.receiver.stop_simulation()

    def _on_gesture_combo_change(self, event=None):
        gest = self.cmb_gestures.get().strip().upper()
        if gest in getattr(config, "STATIC_GESTURES", []):
            self.lbl_gesture_type.config(text="[STATIC POSE]", fg="#38bdf8", bg="#032b43")
            if hasattr(self, "lbl_capture_guidance"):
                self.lbl_capture_guidance.config(
                    text=f"💡 Static Pose Guidance: Hold '{gest}' shape and click '📸 Burst Capture (50+)'. Slowly move hand in 3D space (up/down/left/right) during capture for position invariance!",
                    fg="#38bdf8"
                )
        elif gest in getattr(config, "DYNAMIC_GESTURES", []):
            self.lbl_gesture_type.config(text="[DYNAMIC MOTION]", fg="#fbbf24", bg="#2a1f05")
            if hasattr(self, "lbl_capture_guidance"):
                self.lbl_capture_guidance.config(
                    text=f"💡 Dynamic Motion Guidance: Click '⏺ Record Stream' and execute the full '{gest}' motion trajectory smoothly over 3 seconds.",
                    fg="#fbbf24"
                )
        else:
            self.lbl_gesture_type.config(text="[CUSTOM SIGN]", fg="#94a3b8", bg="#1e293b")
            if hasattr(self, "lbl_capture_guidance"):
                self.lbl_capture_guidance.config(
                    text=f"💡 Custom Sign: Choose '📸 Burst Capture (50+)' for static hand poses or '⏺ Record Stream' for gestures with hand movement.",
                    fg="#94a3b8"
                )

    def _start_static_burst_recording(self):
        gesture = self.cmb_gestures.get().strip().upper()
        if not gesture:
            messagebox.showwarning("Warning", "Select or type a gesture label first.")
            return

        try:
            count = int(self.spn_burst_count.get())
        except ValueError:
            count = 50
        count = max(count, 10)

        hand_mode = self.dataset_hand_mode_var.get()
        l_s, r_s = self.receiver.get_latest_states()
        if hand_mode == "right" and not (r_s["connected"] or self.receiver.simulation_mode):
            messagebox.showwarning("Glove Disconnected", "Right glove is not connected. Connect the glove or toggle Simulation Mode in Tab 2.")
            return
        elif hand_mode == "left" and not (l_s["connected"] or self.receiver.simulation_mode):
            messagebox.showwarning("Glove Disconnected", "Left glove is not connected. Connect the glove or toggle Simulation Mode in Tab 2.")
            return

        dur = max(2.5, count * 0.05)

        self.btn_burst_snapshot.config(state=tk.DISABLED)
        self.btn_record.config(state=tk.DISABLED)
        self.btn_snapshot.config(state=tk.DISABLED)
        self.lbl_rec_status.config(text=f"📸 Hold '{gesture}' pose! Move hand slowly in space... (0/{count})", fg="#38bdf8")
        self.rec_prog_bar["value"] = 0

        def _prog(progress, current_count, total_count):
            def _update():
                self.rec_prog_bar["value"] = int(progress * 100)
                self.lbl_rec_status.config(
                    text=f"📸 Recording '{gesture}' spatial variation: {current_count}/{total_count} ({progress*100:.0f}%)",
                    fg="#38bdf8"
                )
            self.after(0, _update)

        def _done(total):
            def _update():
                self.btn_burst_snapshot.config(state=tk.NORMAL)
                self.btn_record.config(state=tk.NORMAL)
                self.btn_snapshot.config(state=tk.NORMAL)
                self.lbl_rec_status.config(
                    text=f"✅ Done! Saved {total} spatial snapshots for '{gesture}' ({hand_mode.upper()} mode).",
                    fg="#10b981"
                )
                self._refresh_dataset_table()
            self.after(0, _update)

        self.recorder.record_static_burst(
            label=gesture,
            count=count,
            duration_sec=dur,
            hand_mode=hand_mode,
            progress_cb=_prog,
            done_cb=_done
        )

    def _start_recording_session(self):
        gesture = self.cmb_gestures.get().strip().upper()
        if not gesture:
            messagebox.showwarning("Warning", "Select or type a gesture label first.")
            return

        try:
            dur = float(self.spn_duration.get())
        except ValueError:
            dur = 3.0

        hand_mode = self.dataset_hand_mode_var.get()
        self.btn_record.config(state=tk.DISABLED)
        self.btn_burst_snapshot.config(state=tk.DISABLED)
        self.btn_snapshot.config(state=tk.DISABLED)
        self.lbl_rec_status.config(text=f"Recording '{gesture}' ({hand_mode.upper()} mode) in progress...", fg="#f59e0b")

        def _prog(progress, count):
            self.rec_prog_bar["value"] = int(progress * 100)

        def _done(total):
            self.btn_record.config(state=tk.NORMAL)
            self.btn_burst_snapshot.config(state=tk.NORMAL)
            self.btn_snapshot.config(state=tk.NORMAL)
            self.lbl_rec_status.config(text=f"Finished! Saved {total} samples for '{gesture}' ({hand_mode.upper()}).", fg="#10b981")
            self._refresh_dataset_table()

        self.recorder.record_gesture_session(gesture, duration_sec=dur, progress_cb=_prog, done_cb=_done, hand_mode=hand_mode)

    def _record_single_snapshot(self):
        gesture = self.cmb_gestures.get().strip().upper()
        if not gesture:
            return
        hand_mode = self.dataset_hand_mode_var.get()
        vec = self.receiver.get_synchronized_feature_vector(hand_mode=hand_mode)
        self.recorder.append_single_frame(gesture, vec, hand_mode=hand_mode)
        self._refresh_dataset_table()
        self.lbl_rec_status.config(text=f"Snapshot saved for '{gesture}' ({hand_mode.upper()} mode)", fg="#10b981")

    def _refresh_dataset_table(self):
        for item in self.tree_dataset.get_children():
            self.tree_dataset.delete(item)
        summary = self.recorder.get_dataset_summary()
        self.tree_dataset.tag_configure("black_text", foreground="#000000", background="#ffffff")
        for gest, count in sorted(summary.items()):
            self.tree_dataset.insert("", tk.END, values=(gest, count), tags=("black_text",))

        # Update dataset info badge
        if hasattr(self, "lbl_dataset_mode_info"):
            info = self.recorder.get_dataset_info()
            if info["exists"] and info["samples"] > 0:
                self.lbl_dataset_mode_info.config(
                    text=f"Dataset: {info['mode']}\nSamples: {info['samples']} | Classes: {len(info['classes'])}",
                    fg="#10b981"
                )
            else:
                self.lbl_dataset_mode_info.config(text="Dataset: Empty (Record or Bootstrap)", fg="#94a3b8")

    def _generate_bootstrap(self):
        hand_mode = self.dataset_hand_mode_var.get()
        self.recorder.generate_synthetic_bootstrap_dataset(hand_mode=hand_mode)
        self._refresh_dataset_table()
        messagebox.showinfo("Success", f"Synthetic dataset generated for {hand_mode.upper()} mode across all common ASL signs!")

    def _delete_selected_gesture(self):
        sel = self.tree_dataset.selection()
        if not sel:
            return
        item = self.tree_dataset.item(sel[0])
        gest = item["values"][0]
        if messagebox.askyesno("Confirm", f"Delete all samples for gesture '{gest}'?"):
            self.recorder.delete_gesture_samples(gest)
            self._refresh_dataset_table()

    def _wipe_dataset(self):
        if messagebox.askyesno("Confirm", "Are you sure you want to delete the ENTIRE dataset?"):
            self.recorder.clear_dataset()
            self._refresh_dataset_table()

    def _start_training(self):
        self.btn_train.config(state=tk.DISABLED, text="Training in progress...")
        chosen_mode = self.train_hand_mode_var.get()
        use_spatial = self.spatial_invariance_var.get()

        def _worker():
            success, metrics = train_classifier(
                model_type=self.model_type_var.get(),
                hand_mode=chosen_mode,
                spatial_augmentation=use_spatial
            )

            def _update_ui():
                self.btn_train.config(state=tk.NORMAL, text="🚀 Train ASL Recognition Model")
                if success:
                    acc = metrics["accuracy"] * 100
                    h_mode = metrics.get("hand_mode", "dual").upper()
                    n_feats = metrics.get("num_features", 28)
                    self.lbl_train_acc.config(text=f"Test Accuracy: {acc:.2f}% | Mode: {h_mode} ({n_feats} Feat)", fg="#10b981")
                    self.txt_train_report.delete("1.0", tk.END)
                    report_str = f"Model Algorithm: {metrics['model_type'].upper()}\n"
                    report_str += f"Hand Mode: {h_mode} ({n_feats} Features)\n"
                    report_str += f"Spatial Invariance: {'ENABLED (Augmented across 3D space)' if metrics.get('spatial_augmentation') else 'DISABLED'}\n"
                    orig_cnt = metrics.get('original_train_samples', metrics['train_samples'])
                    report_str += f"Training Samples: {metrics['train_samples']} (expanded from {orig_cnt} raw snapshots) | Test Samples: {metrics['test_samples']}\n\n"
                    report_str += "Classes (" + str(metrics['num_classes']) + "): " + ", ".join(metrics["classes"]) + "\n"
                    self.txt_train_report.insert("1.0", report_str)

                    # Reload recognizer model
                    self.recognizer.load_model()
                    messagebox.showinfo("Trained!", f"Model successfully trained in {h_mode} mode with {acc:.1f}% accuracy and spatial invariance!")
                else:
                    self.lbl_train_acc.config(text="Training Failed", fg="#ef4444")
                    messagebox.showerror("Error", metrics.get("error", "Unknown error"))

            self.after(0, _update_ui)

        threading.Thread(target=_worker, daemon=True).start()

    def on_close(self):
        self.receiver.stop()
        self.destroy()

if __name__ == "__main__":
    app = ASLTranslatorApp()
    app.mainloop()
