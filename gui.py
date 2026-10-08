"""
ATTEND-X: GUI Module
Dark terminal-style campus attendance interface built with Tkinter.

Layout:
  ┌───────────────────────────────────────────────────────────────┐
  │  HEADER  (title + clock)                                      │
  ├────────────────────────┬──────────────────────────────────────┤
  │  LEFT PANEL            │  RIGHT PANEL                         │
  │  - Camera preview      │  - Status indicator                  │
  │  - Status bar          │  - Student confirmation card         │
  │  - Counter             │  - Recent attendance timeline        │
  ├────────────────────────┴──────────────────────────────────────┤
  │  NAV TABS  [TERMINAL] [STUDENTS] [ATTENDANCE] [REPORTS]       │
  └───────────────────────────────────────────────────────────────┘
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import threading
import time
import logging
import cv2
import numpy as np
from datetime import datetime, date
from pathlib import Path
from PIL import Image, ImageTk, ImageDraw

import database as db
import students as stu_mod
import attendance as att_mod
import subjects as sub_mod
import receipt as receipt_mod
import face_recognition_module as frm
import barcode_scanner
from camera import CameraManager, DetectionEvent, capture_student_photo
import id_card as idcard_mod
import reports as rep_mod

logger = logging.getLogger(__name__)

# ─── Palette ─────────────────────────────────────────────────────────────────
C = {
    "bg":          "#0a0c10",
    "surface":     "#121620",
    "surface2":    "#181f2c",
    "border":      "#242d3d",
    "border_lit":  "#334155",
    "accent":      "#00d296",       # Campus Terminal Green
    "accent_dim":  "#003828",
    "accent2":     "#38bdf8",       # Sky cyan
    "danger":      "#f43f5e",       # Rose red
    "warn":        "#f59e0b",       # Warm amber
    "text":        "#f8fafc",       # Slate 50
    "text_sec":    "#cbd5e1",       # Slate 300
    "muted":       "#94a3b8",       # Slate 400
    "dimmed":      "#475569",       # Slate 600
    "white":       "#ffffff",
}

FONTS = {
    "brand":       ("Segoe UI", 17, "bold"),
    "title":       ("Segoe UI", 17, "bold"),
    "subtitle":    ("Consolas", 8, "bold"),
    "clock":       ("Consolas", 20, "bold"),
    "sys_badge":   ("Consolas", 10, "bold"),
    "tab":         ("Segoe UI", 10, "bold"),
    "status":      ("Consolas", 13, "bold"),
    "status_s":    ("Segoe UI", 9),
    "label":       ("Segoe UI", 9),
    "label_b":     ("Segoe UI", 9, "bold"),
    "value":       ("Consolas", 15, "bold"),
    "name":        ("Segoe UI", 16, "bold"),
    "id_tag":      ("Consolas", 11, "bold"),
    "stat_val":    ("Consolas", 17, "bold"),
    "stat_lbl":    ("Consolas", 8, "bold"),
    "small":       ("Segoe UI", 9),
    "small_mono":  ("Consolas", 9),
    "btn":         ("Segoe UI", 9, "bold"),
    "mono":        ("Consolas", 10),
    "mono_s":      ("Consolas", 9),
    "head":        ("Segoe UI", 13, "bold"),
}

STATUS_COLORS = {
    "INITIALIZING": C["muted"],
    "READY":        C["accent"],
    "FACE DETECTED":C["accent"],
    "CARD DETECTED":C["accent2"],
    "IDENTIFYING":  C["warn"],
    "RECORDED":     C["accent"],
    "DUPLICATE":    C["warn"],
    "NOT ENROLLED": C["danger"],
    "NO SESSION":   C["warn"],
    "UNKNOWN":      C["danger"],
    "CAMERA ERROR": C["danger"],
    "DEMO MODE":    C["accent2"],
}

STATUS_DOT = {
    "INITIALIZING": C["muted"],
    "READY":        C["accent"],
    "FACE DETECTED":C["accent"],
    "CARD DETECTED":C["accent2"],
    "IDENTIFYING":  C["warn"],
    "RECORDED":     C["accent"],
    "DUPLICATE":    C["warn"],
    "NOT ENROLLED": C["danger"],
    "NO SESSION":   C["warn"],
    "UNKNOWN":      C["danger"],
    "CAMERA ERROR": C["danger"],
    "DEMO MODE":    C["accent2"],
}


# ─── Helper: thin separator ───────────────────────────────────────────────────
def separator(parent, color=None, pady=4):
    color = color or C["border"]
    frm = tk.Frame(parent, bg=color, height=1)
    frm.pack(fill="x", pady=pady)
    return frm


def _hex_to_rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))


def _make_dot_image(color: str, size: int = 10) -> ImageTk.PhotoImage:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.ellipse([1, 1, size - 2, size - 2], fill=color)
    return ImageTk.PhotoImage(img)


def bind_canvas_mousewheel(canvas: tk.Canvas, window: tk.Misc = None):
    """
    Enables smooth mouse wheel and touchpad scrolling for a Tkinter Canvas
    across Windows, macOS, and Linux, even when hovering over child widgets (cards, labels, buttons).
    """
    def _is_descendant(ancestor, widget):
        curr = widget
        while curr:
            if curr == ancestor:
                return True
            try:
                curr = curr.master
            except Exception:
                break
        return False

    def _on_mousewheel(event):
        try:
            target = getattr(event, "widget", None)
            if isinstance(target, str):
                try:
                    target = canvas.nametowidget(target)
                except Exception:
                    target = None

            is_inside = False
            if target and _is_descendant(canvas, target):
                is_inside = True
            else:
                try:
                    px, py = canvas.winfo_pointerxy()
                    ptr_widget = canvas.winfo_containing(px, py)
                    if ptr_widget and _is_descendant(canvas, ptr_widget):
                        is_inside = True
                except Exception:
                    pass

            if is_inside:
                if event.num == 4:
                    canvas.yview_scroll(-2, "units")
                elif event.num == 5:
                    canvas.yview_scroll(2, "units")
                elif getattr(event, "delta", 0):
                    delta = int(-1 * (event.delta / 120))
                    if delta == 0:
                        delta = -1 if event.delta > 0 else 1
                    canvas.yview_scroll(delta * 2, "units")
                return "break"
        except Exception:
            pass

    top = window or canvas.winfo_toplevel()
    top.bind("<MouseWheel>", _on_mousewheel, add="+")
    top.bind("<Button-4>", _on_mousewheel, add="+")
    top.bind("<Button-5>", _on_mousewheel, add="+")
    canvas.bind("<MouseWheel>", _on_mousewheel, add="+")
    canvas.bind("<Button-4>", _on_mousewheel, add="+")
    canvas.bind("<Button-5>", _on_mousewheel, add="+")


# ─── Main Application ─────────────────────────────────────────────────────────
class AttendXApp(tk.Tk):

    CONFIRM_DISPLAY_SECONDS = 3    # How long to show confirmation overlay
    POLL_INTERVAL_MS        = 60   # Camera event poll interval

    def __init__(self):
        super().__init__()

        # ── Window setup ──
        self.title("ATTEND-X  ·  Campus Attendance Terminal")
        self.configure(bg=C["bg"])
        self.minsize(1100, 680)
        self.geometry("1200x730")
        self.resizable(True, True)
        try:
            self.iconbitmap(default="")
        except Exception:
            pass

        # ── State ──
        self._current_status = "INITIALIZING"
        self._known_encodings: list = []
        self._confirm_after_id = None
        self._camera_photo     = None  # keep PhotoImage reference
        self._demo_mode        = False
        self._dot_imgs         = {}    # cache dot PhotoImages
        self._active_receipt_data = None  # for receipt download

        # ── Camera ──
        self.camera = CameraManager(camera_index=0)
        self.camera.on_frame     = self._on_camera_frame
        self.camera.on_detection = None   # handled by polling

        # ── Build UI ──
        self._build_ui()
        self._start_clock()

        # ── Init DB + start camera ──
        self.after(100, self._initialize)

    # ═══════════════════════════════════════════════════════════════════════════
    # UI CONSTRUCTION
    # ═══════════════════════════════════════════════════════════════════════════

    def _build_ui(self):
        # Header
        self._build_header()
        separator(self, pady=0)

        # Navigation tabs bar (at top under header - always visible)
        self._build_tabs_nav()
        separator(self, pady=0)

        # Main container that swaps views
        self._tab_container = tk.Frame(self, bg=C["bg"])
        self._tab_container.pack(fill="both", expand=True, padx=0, pady=0)

        # Terminal view
        self._terminal_frame = tk.Frame(self._tab_container, bg=C["bg"])
        self._terminal_frame.pack(fill="both", expand=True, padx=0, pady=0)
        self._terminal_frame.columnconfigure(0, weight=3)
        self._terminal_frame.columnconfigure(1, weight=2)
        self._terminal_frame.rowconfigure(0, weight=1)
        self._terminal_frame.rowconfigure(1, weight=0)

        self._build_left_panel(self._terminal_frame)
        self._build_right_panel(self._terminal_frame)
        self._build_bottom_stats(self._terminal_frame)

        # Tab panels
        self._tab_panels = {}
        self._build_tab_students()
        self._build_tab_subjects()
        self._build_tab_attendance()
        self._build_tab_reports()

        self._current_panel = None

        # Global Technical Footer
        separator(self, pady=0)
        self._build_footer()

    # ── Header ──────────────────────────────────────────────────────────────

    def _build_header(self):
        hdr = tk.Frame(self, bg=C["surface"], height=64)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)

        # Left: brand title & terminal subtitle
        left = tk.Frame(hdr, bg=C["surface"])
        left.pack(side="left", padx=20, pady=8)

        brand_row = tk.Frame(left, bg=C["surface"])
        brand_row.pack(anchor="w")
        tk.Label(brand_row, text="ATTEND-X", font=FONTS["brand"],
                 bg=C["surface"], fg=C["text"]).pack(side="left")
        tk.Label(brand_row, text=" TERMINAL", font=FONTS["subtitle"],
                 bg=C["surface"], fg=C["accent"]).pack(side="left", padx=(4, 0), pady=(4, 0))

        tk.Label(left, text="CAMPUS ATTENDANCE TERMINAL",
                 font=FONTS["subtitle"], bg=C["surface"], fg=C["muted"]).pack(anchor="w")

        # Right: system status indicator + live clock
        right = tk.Frame(hdr, bg=C["surface"])
        right.pack(side="right", padx=20)

        status_box = tk.Frame(right, bg=C["surface2"], bd=0,
                              highlightthickness=1, highlightbackground=C["border"])
        status_box.pack(side="right", pady=10)

        self._sys_badge_label = tk.Label(
            status_box,
            text="● INITIALIZING",
            font=FONTS["sys_badge"],
            bg=C["surface2"],
            fg=C["muted"],
            padx=12,
            pady=4
        )
        self._sys_badge_label.pack(side="left")

        tk.Frame(status_box, bg=C["border"], width=1).pack(side="left", fill="y", pady=4)

        self._clock_label = tk.Label(
            status_box,
            text="--:--:--",
            font=FONTS["clock"],
            bg=C["surface2"],
            fg=C["text"],
            padx=14,
            pady=2
        )
        self._clock_label.pack(side="left")

    # ── Left panel: camera + status ──────────────────────────────────────────

    def _build_left_panel(self, parent):
        panel = tk.Frame(parent, bg=C["bg"])
        panel.grid(row=0, column=0, sticky="nsew", padx=(16, 8), pady=(12, 6))
        panel.columnconfigure(0, weight=1)
        panel.rowconfigure(0, weight=1)

        # Camera frame container
        cam_outer = tk.Frame(panel, bg=C["surface2"], bd=0,
                             highlightthickness=1, highlightbackground=C["border"])
        cam_outer.grid(row=0, column=0, sticky="nsew")

        self._cam_label = tk.Label(cam_outer, bg=C["surface2"],
                                   text="CAMERA INITIALIZING…",
                                   fg=C["muted"], font=FONTS["mono"])
        self._cam_label.pack(fill="both", expand=True)

        # Camera offline frame (shown if camera is unavailable or disconnected)
        self._cam_offline_frame = tk.Frame(cam_outer, bg=C["surface2"])

        tk.Label(self._cam_offline_frame, text="!",
                 font=("Consolas", 38, "bold"),
                 bg=C["surface2"], fg=C["danger"]).pack(pady=(45, 4))

        tk.Label(self._cam_offline_frame, text="CAMERA OFFLINE",
                 font=FONTS["head"],
                 bg=C["surface2"], fg=C["danger"]).pack(pady=(0, 6))

        tk.Label(self._cam_offline_frame, text="Camera could not be opened.",
                 font=FONTS["label_b"],
                 bg=C["surface2"], fg=C["text"]).pack(pady=(0, 2))

        tk.Label(self._cam_offline_frame, text="Check your webcam connection.",
                 font=FONTS["small"],
                 bg=C["surface2"], fg=C["muted"]).pack(pady=(0, 16))

        self._retry_cam_btn = tk.Button(
            self._cam_offline_frame,
            text="[ ⟳ RETRY CAMERA ]",
            font=FONTS["btn"],
            bg=C["surface"],
            fg=C["accent"],
            activebackground=C["border"],
            activeforeground=C["accent"],
            relief="flat",
            bd=0,
            padx=18,
            pady=8,
            cursor="hand2",
            command=self._retry_camera
        )
        self._retry_cam_btn.pack(pady=(0, 20))

        # Status indicator bar below camera
        status_bar = tk.Frame(panel, bg=C["surface"], height=40,
                              highlightthickness=1, highlightbackground=C["border"])
        status_bar.grid(row=1, column=0, sticky="ew", pady=(8, 0))
        status_bar.pack_propagate(False)

        left_pill = tk.Frame(status_bar, bg=C["surface"])
        left_pill.pack(side="left", padx=12, fill="y")

        self._dot_canvas = tk.Canvas(left_pill, width=12, height=12,
                                     bg=C["surface"], highlightthickness=0)
        self._dot_canvas.pack(side="left", pady=14)
        self._dot_oval = self._dot_canvas.create_oval(1, 1, 11, 11,
                                                       fill=C["muted"], outline="")

        self._status_label = tk.Label(left_pill, text="INITIALIZING…",
                                      font=FONTS["status"], bg=C["surface"],
                                      fg=C["muted"])
        self._status_label.pack(side="left", padx=(6, 0))

        self._hint_label = tk.Label(status_bar,
                                    text="LOOK AT CAMERA OR PRESENT ID CARD",
                                    font=FONTS["small_mono"],
                                    bg=C["surface"], fg=C["muted"])
        self._hint_label.pack(side="right", padx=14)

    # ── Right panel: confirmation + timeline ─────────────────────────────────

    def _build_right_panel(self, parent):
        panel = tk.Frame(parent, bg=C["bg"])
        panel.grid(row=0, column=1, sticky="nsew", padx=(8, 16), pady=(12, 6))
        panel.columnconfigure(0, weight=1)
        panel.rowconfigure(0, weight=0)
        panel.rowconfigure(1, weight=0)
        panel.rowconfigure(2, weight=1)

        # ── Current Class Session Widget (Header of Right Panel) ──
        self._cur_class_box = tk.Frame(panel, bg=C["surface"],
                                       bd=0, highlightthickness=1,
                                       highlightbackground=C["border"])
        self._cur_class_box.grid(row=0, column=0, sticky="ew", pady=(0, 8))

        cur_top = tk.Frame(self._cur_class_box, bg=C["surface"])
        cur_top.pack(fill="x", padx=14, pady=(10, 2))

        tk.Label(cur_top, text="CURRENT CLASS", font=FONTS["subtitle"],
                 bg=C["surface"], fg=C["muted"]).pack(side="left")

        self._cur_class_badge = tk.Label(cur_top, text="● NO ACTIVE CLASS",
                                         font=FONTS["sys_badge"], bg=C["surface2"],
                                         fg=C["warn"], padx=8, pady=2)
        self._cur_class_badge.pack(side="right")

        cur_body = tk.Frame(self._cur_class_box, bg=C["surface"])
        cur_body.pack(fill="x", padx=14, pady=(2, 6))

        self._cur_class_name = tk.Label(cur_body, text="NO ACTIVE CLASS",
                                        font=FONTS["head"], bg=C["surface"],
                                        fg=C["text"], anchor="w")
        self._cur_class_name.pack(anchor="w")

        code_row = tk.Frame(cur_body, bg=C["surface"])
        code_row.pack(anchor="w", pady=(1, 2))

        self._cur_class_code = tk.Label(code_row, text="",
                                        font=FONTS["mono"], bg=C["surface"],
                                        fg=C["accent2"])
        self._cur_class_code.pack(side="left")

        self._cur_class_detail = tk.Label(cur_body,
                                          text="Select a subject to start attendance.",
                                          font=FONTS["small"], bg=C["surface"],
                                          fg=C["dimmed"], anchor="w")
        self._cur_class_detail.pack(anchor="w")

        cur_btn_row = tk.Frame(self._cur_class_box, bg=C["surface"])
        cur_btn_row.pack(fill="x", padx=14, pady=(2, 10))

        self._cur_class_btn = tk.Button(
            cur_btn_row,
            text="[ + SELECT SUBJECT ]",
            font=FONTS["btn"],
            bg=C["surface2"],
            fg=C["accent"],
            activebackground=C["border"],
            activeforeground=C["accent"],
            relief="flat", bd=0, padx=12, pady=4, cursor="hand2",
            command=self._show_subjects
        )
        self._cur_class_btn.pack(side="right")

        # ── Confirmation Card (Dual-State: Idle Guide vs Active Verification) ──
        self._conf_card = tk.Frame(panel, bg=C["surface"],
                                   bd=0, highlightthickness=1,
                                   highlightbackground=C["border"])
        self._conf_card.grid(row=1, column=0, sticky="ew", pady=(0, 8))

        # State 1: IDLE / HOW IT WORKS STATE
        self._conf_idle_frame = tk.Frame(self._conf_card, bg=C["surface"])
        self._conf_idle_frame.pack(fill="both", expand=True, padx=16, pady=12)

        idle_top = tk.Frame(self._conf_idle_frame, bg=C["surface"])
        idle_top.pack(fill="x")

        self._conf_idle_ready_lbl = tk.Label(idle_top, text="● READY", font=FONTS["status"],
                                             bg=C["surface"], fg=C["accent"])
        self._conf_idle_ready_lbl.pack(anchor="w")

        self._conf_idle_sub_title = tk.Label(idle_top, text="AUTOMATIC DETECTION ACTIVE",
                                             font=FONTS["sys_badge"], bg=C["surface"], fg=C["text"])
        self._conf_idle_sub_title.pack(anchor="w", pady=(3, 0))

        self._conf_idle_methods = tk.Label(idle_top, text="FACE + ID CARD",
                                           font=FONTS["subtitle"], bg=C["surface"], fg=C["accent2"])
        self._conf_idle_methods.pack(anchor="w", pady=(2, 0))

        self._conf_idle_hint = tk.Label(idle_top, text="Waiting for student...",
                                        font=FONTS["small"], bg=C["surface"], fg=C["dimmed"])
        self._conf_idle_hint.pack(anchor="w", pady=(2, 4))

        separator(self._conf_idle_frame, color=C["border"], pady=4)

        # 3-step technical guidance
        steps_box = tk.Frame(self._conf_idle_frame, bg=C["surface"])
        steps_box.pack(fill="x", pady=2)

        steps = [
            ("1", "Look directly at camera for face recognition"),
            ("2", "Or present student ID card barcode / QR"),
            ("3", "Attendance is verified & recorded instantly"),
        ]
        for num, text in steps:
            srow = tk.Frame(steps_box, bg=C["surface"])
            srow.pack(fill="x", pady=2)
            tk.Label(srow, text=f" {num} ", font=FONTS["sys_badge"],
                     bg=C["surface2"], fg=C["accent"], width=3).pack(side="left", padx=(0, 8))
            tk.Label(srow, text=text, font=FONTS["label"],
                     bg=C["surface"], fg=C["text_sec"], anchor="w").pack(side="left")

        # State 2: ACTIVE RECOGNITION / VERIFICATION STATE (Hidden by default)
        self._conf_active_frame = tk.Frame(self._conf_card, bg=C["surface"])

        self._conf_status_badge = tk.Label(self._conf_active_frame,
                                           text="✓ ATTENDANCE RECORDED",
                                           font=FONTS["status"],
                                           bg=C["surface"], fg=C["accent"])
        self._conf_status_badge.pack(pady=(10, 2))

        self._conf_name = tk.Label(self._conf_active_frame, text="",
                                   font=FONTS["name"],
                                   bg=C["surface"], fg=C["text"])
        self._conf_name.pack()

        self._conf_id = tk.Label(self._conf_active_frame, text="",
                                 font=FONTS["id_tag"],
                                 bg=C["surface"], fg=C["accent"])
        self._conf_id.pack(pady=(2, 0))

        self._conf_subject = tk.Label(self._conf_active_frame, text="",
                                      font=FONTS["label_b"],
                                      bg=C["surface"], fg=C["accent2"])
        self._conf_subject.pack(pady=(2, 0))

        self._conf_detail = tk.Label(self._conf_active_frame, text="",
                                     font=FONTS["label"],
                                     bg=C["surface"], fg=C["muted"])
        self._conf_detail.pack(pady=(2, 0))

        self._conf_time = tk.Label(self._conf_active_frame, text="",
                                   font=FONTS["value"],
                                   bg=C["surface"], fg=C["text"])
        self._conf_time.pack(pady=(2, 0))

        self._conf_method = tk.Label(self._conf_active_frame, text="",
                                     font=FONTS["sys_badge"],
                                     bg=C["surface2"], fg=C["accent"],
                                     padx=10, pady=2)
        self._conf_method.pack(pady=(2, 2))

        self._conf_att_id = tk.Label(self._conf_active_frame, text="",
                                     font=FONTS["small_mono"],
                                     bg=C["surface"], fg=C["muted"])
        self._conf_att_id.pack(pady=(1, 2))

        self._conf_receipt_btn = tk.Button(
            self._conf_active_frame,
            text="[ 💾 SAVE RECEIPT ]",
            font=FONTS["btn"],
            bg=C["surface2"],
            fg=C["accent"],
            activebackground=C["border"],
            activeforeground=C["accent"],
            relief="flat", bd=0, padx=12, pady=4, cursor="hand2",
            command=self._save_active_receipt
        )
        self._conf_receipt_btn.pack(pady=(2, 4))

        self._conf_note = tk.Label(self._conf_active_frame, text="",
                                   font=FONTS["small_mono"],
                                   bg=C["surface"], fg=C["dimmed"])
        self._conf_note.pack(pady=(0, 8))

        # ── Live Attendance Timeline (Scrollable) ──
        tl_container = tk.Frame(panel, bg=C["bg"])
        tl_container.grid(row=2, column=0, sticky="nsew")
        tl_container.columnconfigure(0, weight=1)
        tl_container.rowconfigure(2, weight=1)

        hdr_row = tk.Frame(tl_container, bg=C["bg"])
        hdr_row.grid(row=0, column=0, sticky="ew", pady=(0, 4))

        tk.Label(hdr_row, text="LIVE ATTENDANCE", font=FONTS["label_b"],
                 bg=C["bg"], fg=C["text"]).pack(side="left")

        today_str = datetime.now().strftime("%d %b %Y").upper()
        self._timeline_date_lbl = tk.Label(hdr_row, text=today_str,
                                           font=FONTS["small_mono"],
                                           bg=C["bg"], fg=C["accent"])
        self._timeline_date_lbl.pack(side="right")

        sep = tk.Frame(tl_container, bg=C["border"], height=1)
        sep.grid(row=1, column=0, sticky="ew", pady=2)

        # Scrollable Timeline Area
        tl_frame = tk.Frame(tl_container, bg=C["bg"])
        tl_frame.grid(row=2, column=0, sticky="nsew")

        self._timeline_canvas = tk.Canvas(tl_frame, bg=C["bg"], highlightthickness=0)
        tl_scroll = ttk.Scrollbar(tl_frame, orient="vertical", command=self._timeline_canvas.yview)
        self._timeline_canvas.configure(yscrollcommand=tl_scroll.set)
        self._timeline_canvas.pack(side="left", fill="both", expand=True)
        tl_scroll.pack(side="right", fill="y")

        self._timeline_inner = tk.Frame(self._timeline_canvas, bg=C["bg"])
        self._tl_window = self._timeline_canvas.create_window(
            (0, 0), window=self._timeline_inner, anchor="nw"
        )
        self._timeline_inner.bind("<Configure>", self._on_timeline_resize)
        self._timeline_canvas.bind("<Configure>", self._on_timeline_canvas_resize)
        bind_canvas_mousewheel(self._timeline_canvas, self)

    # ── Bottom stats bar ─────────────────────────────────────────────────────

    def _build_bottom_stats(self, parent):
        stats_outer = tk.Frame(parent, bg=C["surface"], height=58,
                               highlightthickness=1, highlightbackground=C["border"])
        stats_outer.grid(row=1, column=0, columnspan=2, sticky="ew", padx=16, pady=(4, 8))
        stats_outer.pack_propagate(False)

        # 4 Metric tiles
        tiles_frame = tk.Frame(stats_outer, bg=C["surface"])
        tiles_frame.pack(side="left", padx=16, fill="y")

        self._stat_boxes = {}
        for key, label, color in [
            ("present", "PRESENT", C["accent"]),
            ("absent",  "ABSENT",  C["danger"]),
            ("total",   "TOTAL",   C["text"]),
            ("rate",    "RATE",    C["accent2"]),
        ]:
            tile = tk.Frame(tiles_frame, bg=C["surface"])
            tile.pack(side="left", padx=(0, 20), pady=6)
            lbl = tk.Label(tile, text=label, font=FONTS["stat_lbl"], bg=C["surface"], fg=C["muted"])
            lbl.pack(anchor="w")
            val = tk.Label(tile, text="0", font=FONTS["stat_val"], bg=C["surface"], fg=color)
            val.pack(anchor="w")
            self._stat_boxes[key] = val

        # Progress bar on the right
        prog_frame = tk.Frame(stats_outer, bg=C["surface"])
        prog_frame.pack(side="right", padx=20, fill="y")

        self._progress_text = tk.Label(
            prog_frame,
            text="0 / 0 PRESENT  •  0.0%",
            font=FONTS["label_b"],
            bg=C["surface"],
            fg=C["muted"]
        )
        self._progress_text.pack(anchor="e", pady=(8, 4))

        self._prog_canvas = tk.Canvas(
            prog_frame,
            width=240,
            height=6,
            bg=C["surface2"],
            highlightthickness=0
        )
        self._prog_canvas.pack(anchor="e")
        self._prog_fill = self._prog_canvas.create_rectangle(0, 0, 0, 6, fill=C["accent"], width=0)

    # ── Global footer ────────────────────────────────────────────────────────

    def _build_footer(self):
        footer = tk.Frame(self, bg=C["bg"], height=28)
        footer.pack(side="bottom", fill="x")
        footer.pack_propagate(False)

        tk.Label(
            footer,
            text="ATTEND-X v1.0  ·  LOCAL PROCESSING",
            font=FONTS["small_mono"],
            bg=C["bg"],
            fg=C["dimmed"]
        ).pack(side="left", padx=16)

        tk.Label(
            footer,
            text="LOCAL PROCESSING • NO CAMERA FOOTAGE PERMANENTLY RECORDED",
            font=FONTS["small_mono"],
            bg=C["bg"],
            fg=C["dimmed"]
        ).pack(side="left", expand=True)

        self._footer_status = tk.Label(
            footer,
            text="CAMERA: ONLINE  ·  DATABASE: CONNECTED  ·  MODE: AUTOMATIC",
            font=FONTS["small_mono"],
            bg=C["bg"],
            fg=C["muted"]
        )
        self._footer_status.pack(side="right", padx=16)

    # ── Tabs Navigation ──────────────────────────────────────────────────────

    def _build_tabs_nav(self):
        nav = tk.Frame(self, bg=C["surface"], height=42)
        nav.pack(fill="x")
        nav.pack_propagate(False)

        self._tab_buttons = {}
        tabs = [
            ("TERMINAL",   self._show_terminal),
            ("STUDENTS",   self._show_students),
            ("SUBJECTS",   self._show_subjects),
            ("ATTENDANCE", self._show_attendance),
            ("REPORTS",    self._show_reports),
        ]
        self._active_tab = "TERMINAL"

        for name, cmd in tabs:
            btn = tk.Button(nav, text=f"  {name}  ", font=FONTS["tab"],
                            bg=C["surface"], fg=C["muted"],
                            activebackground=C["surface2"],
                            activeforeground=C["accent"],
                            relief="flat", bd=0, padx=16, pady=10,
                            cursor="hand2",
                            command=lambda n=name, c=cmd: self._on_tab(n, c))
            btn.pack(side="left")
            self._tab_buttons[name] = btn

        # Right side: demo & debug mode buttons
        tk.Button(nav, text="✦ DEMO MODE", font=FONTS["tab"],
                  bg=C["surface2"], fg=C["accent2"],
                  activebackground=C["border"],
                  activeforeground=C["accent2"],
                  relief="flat", bd=0, padx=14, pady=6,
                  cursor="hand2",
                  command=self._open_demo).pack(side="right", padx=(4, 16), pady=4)

        tk.Button(nav, text="⚙ ID DEBUG", font=FONTS["tab"],
                  bg=C["surface2"], fg=C["warn"],
                  activebackground=C["border"],
                  activeforeground=C["warn"],
                  relief="flat", bd=0, padx=12, pady=6,
                  cursor="hand2",
                  command=self._open_debug).pack(side="right", padx=(0, 4), pady=4)

        self._set_active_tab("TERMINAL")

    def _on_tab(self, name: str, cmd):
        self._set_active_tab(name)
        if name == "TERMINAL":
            self._show_terminal()
        else:
            cmd()

    def _set_active_tab(self, name: str):
        self._active_tab = name
        for n, btn in self._tab_buttons.items():
            if n == name:
                btn.configure(fg=C["accent"], bg=C["surface2"])
            else:
                btn.configure(fg=C["muted"], bg=C["surface"])

    def _show_terminal(self):
        self._hide_tab_panel()
        self._terminal_frame.pack(fill="both", expand=True)

    def _hide_tab_panel(self):
        if self._current_panel:
            self._current_panel.pack_forget()
            self._current_panel = None

    def _show_panel(self, name: str):
        self._terminal_frame.pack_forget()
        self._hide_tab_panel()
        panel = self._tab_panels.get(name)
        if panel:
            panel.pack(fill="both", expand=True)
            self._current_panel = panel

    # ═══════════════════════════════════════════════════════════════════════════
    # TAB PANELS
    # ═══════════════════════════════════════════════════════════════════════════

    # ── Students panel ────────────────────────────────────────────────────────

    def _build_tab_students(self):
        panel = tk.Frame(self._tab_container, bg=C["bg"])
        self._tab_panels["STUDENTS"] = panel

        # Top toolbar
        toolbar = tk.Frame(panel, bg=C["surface"])
        toolbar.pack(fill="x", padx=0, pady=0)

        tk.Label(toolbar, text="STUDENT MANAGEMENT",
                 font=FONTS["head"], bg=C["surface"], fg=C["text"]).pack(
            side="left", padx=16, pady=8)

        btn_style = dict(font=FONTS["btn"], bg=C["accent"], fg=C["bg"],
                         relief="flat", bd=0, padx=12, pady=5, cursor="hand2")
        tk.Button(toolbar, text="+ ADD STUDENT", **btn_style,
                  command=self._open_add_student).pack(side="right", padx=8, pady=6)
        tk.Button(toolbar, text="LOAD DEMO DATA",
                  font=FONTS["btn"], bg=C["surface2"], fg=C["accent2"],
                  relief="flat", bd=0, padx=12, pady=5, cursor="hand2",
                  command=self._load_demo_data).pack(side="right", padx=4, pady=6)

        separator(panel, pady=0)

        # Search bar
        search_row = tk.Frame(panel, bg=C["bg"])
        search_row.pack(fill="x", padx=16, pady=8)
        tk.Label(search_row, text="SEARCH:", font=FONTS["label"],
                 bg=C["bg"], fg=C["muted"]).pack(side="left", padx=(0, 8))
        self._stu_search_var = tk.StringVar()
        self._stu_search_var.trace_add("write", lambda *a: self._refresh_students())
        entry = tk.Entry(search_row, textvariable=self._stu_search_var,
                         font=FONTS["mono"], bg=C["surface2"], fg=C["text"],
                         insertbackground=C["accent"], relief="flat", bd=0,
                         width=30)
        entry.pack(side="left", ipady=4, padx=4)

        # Student table
        cols = ("student_id", "name", "branch", "semester", "face", "actions")
        tbl_frame = tk.Frame(panel, bg=C["bg"])
        tbl_frame.pack(fill="both", expand=True, padx=16, pady=(0, 8))

        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Dark.Treeview",
                         background=C["surface"],
                         foreground=C["text"],
                         fieldbackground=C["surface"],
                         rowheight=28,
                         font=FONTS["mono"])
        style.configure("Dark.Treeview.Heading",
                         background=C["surface2"],
                         foreground=C["muted"],
                         font=FONTS["label_b"],
                         relief="flat")
        style.map("Dark.Treeview",
                  background=[("selected", C["surface2"])],
                  foreground=[("selected", C["accent"])])

        self._stu_tree = ttk.Treeview(tbl_frame,
                                       columns=("ID", "Name", "Branch", "Sem", "Face"),
                                       show="headings",
                                       style="Dark.Treeview",
                                       selectmode="browse")
        for col, w in [("ID", 100), ("Name", 200), ("Branch", 160),
                        ("Sem", 70), ("Face", 70)]:
            self._stu_tree.heading(col, text=col.upper())
            self._stu_tree.column(col, width=w, anchor="w")

        vsb = ttk.Scrollbar(tbl_frame, orient="vertical",
                             command=self._stu_tree.yview)
        self._stu_tree.configure(yscrollcommand=vsb.set)
        self._stu_tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

        self._stu_tree.bind("<Double-1>", self._on_student_double_click)

        # Action row below table
        act_row = tk.Frame(panel, bg=C["bg"])
        act_row.pack(fill="x", padx=16, pady=(0, 8))
        for txt, cmd, color in [
            ("CAPTURE FACE",       self._capture_selected_face,       C["accent"]),
            ("GENERATE ID CARD",   self._gen_selected_card,           C["accent2"]),
            ("ATTENDANCE PROFILE", self._show_selected_student_profile, C["surface2"]),
            ("EDIT",               self._edit_selected_student,       C["surface2"]),
            ("DELETE",             self._delete_selected_student,     C["danger"]),
        ]:
            tk.Button(act_row, text=txt,
                      font=FONTS["btn"], bg=color,
                      fg=C["bg"] if color in (C["accent"], C["danger"]) else C["text"],
                      relief="flat", bd=0, padx=12, pady=5, cursor="hand2",
                      command=cmd).pack(side="left", padx=(0, 8))

    def _show_students(self):
        self._show_panel("STUDENTS")
        self._refresh_students()

    def _refresh_students(self):
        q = self._stu_search_var.get().strip()
        rows = stu_mod.search_students(q)
        self._stu_tree.delete(*self._stu_tree.get_children())
        if not rows:
            msg = "NO STUDENTS REGISTERED — Click + ADD STUDENT to begin." if not q else f"No students matching '{q}'"
            self._stu_tree.insert("", "end", values=("—", msg, "—", "—", "—"))
            return
        for s in rows:
            has_face = "✓" if s.get("face_encoding") else "—"
            self._stu_tree.insert("", "end",
                                   iid=s["student_id"],
                                   values=(s["student_id"], s["name"],
                                           s["branch"], s["semester"], has_face))

    def _open_add_student(self):
        dlg = StudentDialog(self, title="ADD STUDENT")
        self.wait_window(dlg)
        if dlg.result:
            sid, name, branch, sem = dlg.result
            ok, msg = stu_mod.add_student(sid, name, branch, sem)
            if ok:
                self._reload_encodings()
                messagebox.showinfo("ATTEND-X", msg, parent=self)
                self._refresh_students()
            else:
                messagebox.showerror("Error", msg, parent=self)

    def _edit_selected_student(self):
        sel = self._stu_tree.selection()
        if not sel:
            messagebox.showinfo("Select Student", "Please select a student to edit.", parent=self)
            return
        student_id = sel[0]
        s = stu_mod.get_student(student_id)
        if s:
            self._open_edit_student(s)

    def _show_selected_student_profile(self):
        sel = self._stu_tree.selection()
        if not sel:
            messagebox.showinfo("Select Student", "Please select a student to view attendance profile.", parent=self)
            return
        student_id = sel[0]
        profile_data = sub_mod.get_student_attendance_profile(student_id)
        if profile_data:
            StudentProfileDialog(self, profile_data)
        else:
            messagebox.showerror("Error", "Could not load student attendance profile.", parent=self)

    def _on_student_double_click(self, event):
        self._show_selected_student_profile()

    def _open_edit_student(self, student: dict):
        dlg = StudentDialog(self, title="EDIT STUDENT", student=student)
        self.wait_window(dlg)
        if dlg.result:
            _, name, branch, sem = dlg.result
            ok, msg = stu_mod.edit_student(student["student_id"],
                                           name=name, branch=branch, semester=sem)
            if ok:
                messagebox.showinfo("ATTEND-X", msg, parent=self)
                self._refresh_students()
            else:
                messagebox.showerror("Error", msg, parent=self)

    def _delete_selected_student(self):
        sel = self._stu_tree.selection()
        if not sel:
            messagebox.showwarning("No Selection", "Select a student first.", parent=self)
            return
        student_id = sel[0]
        if messagebox.askyesno("Confirm Delete",
                                f"Delete student {student_id}? This also removes their attendance records.",
                                parent=self):
            ok, msg = stu_mod.remove_student(student_id)
            messagebox.showinfo("ATTEND-X", msg, parent=self)
            self._refresh_students()
            self._reload_encodings()

    def _capture_selected_face(self):
        sel = self._stu_tree.selection()
        if not sel:
            messagebox.showwarning("No Selection", "Select a student first.", parent=self)
            return
        student_id = sel[0]
        FaceCaptureDialog(self, student_id=student_id,
                          camera=self.camera,
                          on_done=self._on_face_captured)

    def _on_face_captured(self, student_id: str, encoding, photo_path: str):
        if encoding is not None:
            ok, msg = stu_mod.save_face_encoding(student_id, encoding, photo_path)
            messagebox.showinfo("ATTEND-X", f"Face registered for {student_id}." if ok else msg,
                                parent=self)
            self._reload_encodings()
            self._refresh_students()
        elif photo_path:
            ok = db.update_student(student_id, photo_path=photo_path)
            if ok:
                messagebox.showinfo("ATTEND-X", f"Photo registered for {student_id} (used for ID cards).", parent=self)
            else:
                messagebox.showerror("ATTEND-X", "Failed to update student photo.", parent=self)
            self._refresh_students()
        else:
            messagebox.showwarning("Face Capture", "No face or photo captured. Try again.", parent=self)

    def _gen_selected_card(self):
        sel = self._stu_tree.selection()
        if not sel:
            messagebox.showwarning("No Selection", "Select a student first.", parent=self)
            return
        student_id = sel[0]
        s = stu_mod.get_student(student_id)
        if not s:
            return
        path = idcard_mod.generate_id_card(s)
        if path:
            messagebox.showinfo("ID Card Generated",
                                f"Saved to:\n{path}\n\nOpen the file to print.",
                                parent=self)
            try:
                import os
                os.startfile(path)
            except Exception:
                pass
        else:
            messagebox.showerror("Error", "Failed to generate ID card.", parent=self)

    def _load_demo_data(self):
        if not messagebox.askyesno("Load Demo Data",
                                    "Load demo students (23CS001–23CS006 etc.)?\n"
                                    "Already-existing students will be skipped.",
                                    parent=self):
            return
        results = stu_mod.load_demo_students()
        self._refresh_students()
        self._reload_encodings()
        self._refresh_timeline()
        self._refresh_counter()
        messagebox.showinfo("Demo Data Loaded",
                            "\n".join(results), parent=self)

    # ── Subjects panel ────────────────────────────────────────────────────────

    def _build_tab_subjects(self):
        panel = tk.Frame(self._tab_container, bg=C["bg"])
        self._tab_panels["SUBJECTS"] = panel

        # Top toolbar
        toolbar = tk.Frame(panel, bg=C["surface"])
        toolbar.pack(fill="x", padx=0, pady=0)

        tk.Label(toolbar, text="SUBJECT MANAGEMENT",
                 font=FONTS["head"], bg=C["surface"], fg=C["text"]).pack(
            side="left", padx=16, pady=8)

        btn_style = dict(font=FONTS["btn"], bg=C["accent"], fg=C["bg"],
                         relief="flat", bd=0, padx=12, pady=5, cursor="hand2")
        tk.Button(toolbar, text="+ ADD SUBJECT", **btn_style,
                  command=self._open_add_subject).pack(side="right", padx=12, pady=6)

        separator(panel, pady=0)

        # Search bar
        search_row = tk.Frame(panel, bg=C["bg"])
        search_row.pack(fill="x", padx=16, pady=8)
        tk.Label(search_row, text="SEARCH:", font=FONTS["label"],
                 bg=C["bg"], fg=C["muted"]).pack(side="left", padx=(0, 8))
        self._sub_search_var = tk.StringVar()
        self._sub_search_var.trace_add("write", lambda *a: self._refresh_subjects())
        entry = tk.Entry(search_row, textvariable=self._sub_search_var,
                         font=FONTS["mono"], bg=C["surface2"], fg=C["text"],
                         insertbackground=C["accent"], relief="flat", bd=0,
                         width=30)
        entry.pack(side="left", ipady=4, padx=4)

        # Scrollable Cards Area
        cards_container = tk.Frame(panel, bg=C["bg"])
        cards_container.pack(fill="both", expand=True, padx=16, pady=(0, 8))

        self._sub_canvas = tk.Canvas(cards_container, bg=C["bg"], highlightthickness=0)
        sub_scroll = ttk.Scrollbar(cards_container, orient="vertical", command=self._sub_canvas.yview)
        self._sub_inner = tk.Frame(self._sub_canvas, bg=C["bg"])

        self._sub_window = self._sub_canvas.create_window((0, 0), window=self._sub_inner, anchor="nw")
        self._sub_canvas.configure(yscrollcommand=sub_scroll.set)

        self._sub_inner.bind("<Configure>", lambda e: self._sub_canvas.configure(scrollregion=self._sub_canvas.bbox("all")))
        self._sub_canvas.bind("<Configure>", lambda e: self._sub_canvas.itemconfigure(self._sub_window, width=e.width))

        self._sub_canvas.pack(side="left", fill="both", expand=True)
        sub_scroll.pack(side="right", fill="y")
        bind_canvas_mousewheel(self._sub_canvas, self)

    def _show_subjects(self):
        self._show_panel("SUBJECTS")
        self._refresh_subjects()

    def _refresh_subjects(self):
        for w in self._sub_inner.winfo_children():
            w.destroy()

        q = getattr(self, "_sub_search_var", None)
        query = q.get().strip() if q else ""
        subjects = sub_mod.search_subjects(query)

        active = sub_mod.get_active_session()
        active_sub_id = active["subject_id"] if active else None

        if not subjects:
            box = tk.Frame(self._sub_inner, bg=C["surface"], highlightthickness=1, highlightbackground=C["border"])
            box.pack(fill="x", pady=20, padx=4)
            tk.Label(box, text="NO SUBJECTS FOUND", font=FONTS["head"], bg=C["surface"], fg=C["muted"]).pack(pady=(20, 4))
            tk.Label(box, text="Click + ADD SUBJECT to register a new course.", font=FONTS["small"], bg=C["surface"], fg=C["dimmed"]).pack(pady=(0, 20))
            self._sub_inner.update_idletasks()
            self._sub_canvas.configure(scrollregion=self._sub_canvas.bbox("all"))
            return

        for s in subjects:
            is_active = (s["id"] == active_sub_id)
            card = tk.Frame(self._sub_inner, bg=C["surface"],
                            bd=0, highlightthickness=1,
                            highlightbackground=C["accent"] if is_active else C["border"])
            card.pack(fill="x", pady=6, padx=2)

            top_row = tk.Frame(card, bg=C["surface"])
            top_row.pack(fill="x", padx=16, pady=(12, 4))

            # Code
            tk.Label(top_row, text=s["subject_code"], font=FONTS["id_tag"],
                     bg=C["surface2"], fg=C["accent2"], padx=8, pady=2).pack(side="left")

            if is_active:
                tk.Label(top_row, text="● ATTENDANCE ACTIVE", font=FONTS["sys_badge"],
                         bg=C["surface2"], fg=C["accent"], padx=10, pady=2).pack(side="right")

            # Title
            tk.Label(card, text=s["subject_name"], font=FONTS["head"],
                     bg=C["surface"], fg=C["text"], anchor="w").pack(fill="x", padx=16, pady=(4, 2))

            # Meta row
            meta_txt = f"{s.get('branch', '—')} • Semester {s.get('semester', '—')}   ·   Faculty: {s.get('faculty', '—')}   ·   Room: {s.get('room', '—')}"
            tk.Label(card, text=meta_txt, font=FONTS["small"],
                     bg=C["surface"], fg=C["muted"], anchor="w").pack(fill="x", padx=16, pady=(0, 4))

            # Metrics row
            metrics_txt = f"Enrolled Students: {s['enrolled_count']}   ·   Sessions Held: {s['total_sessions']}   ·   Avg Attendance: {s['avg_percent']:.1f}%"
            tk.Label(card, text=metrics_txt, font=FONTS["small_mono"],
                     bg=C["surface"], fg=C["text_sec"], anchor="w").pack(fill="x", padx=16, pady=(0, 10))

            separator(card, pady=0)

            # Actions row
            act = tk.Frame(card, bg=C["surface"])
            act.pack(fill="x", padx=16, pady=8)

            if is_active:
                tk.Button(act, text="[ ⏹ END SESSION ]", font=FONTS["btn"],
                          bg=C["surface2"], fg=C["danger"], relief="flat", bd=0,
                          padx=14, pady=5, cursor="hand2",
                          command=self._confirm_end_session).pack(side="left", padx=(0, 8))
            else:
                tk.Button(act, text="[ ▶ START ATTENDANCE ]", font=FONTS["btn"],
                          bg=C["accent"], fg=C["bg"], relief="flat", bd=0,
                          padx=14, pady=5, cursor="hand2",
                          command=lambda sid=s["id"]: self._start_subject_attendance(sid)).pack(side="left", padx=(0, 8))

            tk.Button(act, text="MANAGE STUDENTS", font=FONTS["btn"],
                      bg=C["surface2"], fg=C["accent2"], relief="flat", bd=0,
                      padx=12, pady=5, cursor="hand2",
                      command=lambda sid=s["id"]: self._open_manage_enrollment(sid)).pack(side="left", padx=(0, 8))

            tk.Button(act, text="EDIT", font=FONTS["btn"],
                      bg=C["surface2"], fg=C["muted"], relief="flat", bd=0,
                      padx=12, pady=5, cursor="hand2",
                      command=lambda subj=s: self._open_edit_subject(subj)).pack(side="left", padx=(0, 8))

            tk.Button(act, text="DELETE", font=FONTS["btn"],
                      bg=C["surface2"], fg=C["danger"], relief="flat", bd=0,
                      padx=12, pady=5, cursor="hand2",
                      command=lambda sid=s["id"]: self._delete_subject(sid)).pack(side="right")

        self._sub_inner.update_idletasks()
        self._sub_canvas.configure(scrollregion=self._sub_canvas.bbox("all"))

    def _open_add_subject(self):
        dlg = SubjectDialog(self, title="ADD SUBJECT")
        self.wait_window(dlg)
        if dlg.result:
            code, name, branch, sem, fac, rm = dlg.result
            ok, msg = sub_mod.add_subject(code, name, branch, sem, fac, rm)
            if ok:
                messagebox.showinfo("ATTEND-X", msg, parent=self)
                self._refresh_subjects()
            else:
                messagebox.showerror("Error", msg, parent=self)

    def _open_edit_subject(self, subject: dict):
        dlg = SubjectDialog(self, title="EDIT SUBJECT", subject=subject)
        self.wait_window(dlg)
        if dlg.result:
            code, name, branch, sem, fac, rm = dlg.result
            ok, msg = sub_mod.edit_subject(subject["id"], code, name, branch, sem, fac, rm)
            if ok:
                messagebox.showinfo("ATTEND-X", msg, parent=self)
                self._refresh_subjects()
                self._refresh_current_class_widget()
            else:
                messagebox.showerror("Error", msg, parent=self)

    def _delete_subject(self, subject_id: int):
        s = sub_mod.get_subject(subject_id)
        if not s:
            return
        if not messagebox.askyesno("Delete Subject",
                                   f"Delete subject '{s['subject_name']}' ({s['subject_code']})?\n"
                                   "All enrollment and session records for this subject will be removed.",
                                   parent=self):
            return
        ok, msg = sub_mod.delete_subject(subject_id)
        if ok:
            messagebox.showinfo("ATTEND-X", msg, parent=self)
            self._refresh_subjects()
            self._refresh_current_class_widget()
        else:
            messagebox.showerror("Error", msg, parent=self)

    def _open_manage_enrollment(self, subject_id: int):
        dlg = ManageEnrollmentDialog(self, subject_id=subject_id)
        self.wait_window(dlg)
        self._refresh_subjects()

    def _start_subject_attendance(self, subject_id: int):
        ok, sess = sub_mod.start_attendance_session(subject_id)
        if not ok:
            messagebox.showerror("Error", f"Failed to start session: {sess}", parent=self)
            return

        self._set_active_tab("TERMINAL")
        self._show_terminal()
        self._refresh_current_class_widget()
        self._refresh_timeline()
        self._refresh_counter()
        self._set_status("READY")
        messagebox.showinfo(
            "Session Started",
            f"Attendance session started for:\n{sess['subject_name']} ({sess['subject_code']})\n\nCamera terminal is now active.",
            parent=self
        )

    def _confirm_end_session(self):
        active = sub_mod.get_active_session()
        if not active:
            messagebox.showwarning("No Active Session", "There is no active session to end.", parent=self)
            return

        enrolled = len(db.get_enrolled_students(active["subject_id"]))
        present = len(db.get_session_attendance(active["id"]))

        msg = (
            f"END ATTENDANCE SESSION?\n\n"
            f"Subject: {active['subject_name']} ({active['subject_code']})\n"
            f"Present: {present} / {enrolled}\n\n"
            f"After ending, no more attendance can be marked for this session."
        )
        if not messagebox.askyesno("End Session", msg, parent=self):
            return

        ok, summary = sub_mod.end_current_session()
        if ok:
            self._refresh_current_class_widget()
            self._refresh_timeline()
            self._refresh_counter()
            self._return_to_ready()
            SessionSummaryDialog(self, summary)
        else:
            messagebox.showerror("Error", f"Failed to end session: {summary}", parent=self)

    def _refresh_current_class_widget(self):
        active = sub_mod.get_active_session()
        if hasattr(self, "_cur_class_box"):
            if active:
                self._cur_class_badge.configure(text="● ATTENDANCE ACTIVE", fg=C["accent"])
                self._cur_class_name.configure(text=active["subject_name"].upper(), fg=C["text"])
                self._cur_class_code.configure(text=f"CODE: {active['subject_code']}")
                self._cur_class_detail.configure(
                    text=f"{active.get('branch','')} • SEM {active.get('semester','')}  ·  FACULTY: {active.get('faculty','')}  ·  ROOM: {active.get('room','')}",
                    fg=C["muted"]
                )
                self._cur_class_btn.configure(
                    text="[ ⏹ END SESSION ]",
                    fg=C["danger"],
                    command=self._confirm_end_session
                )
                if hasattr(self, "_conf_idle_sub_title"):
                    self._conf_idle_sub_title.configure(text=f"ACTIVE CLASS: {active['subject_name'].upper()}")
                if hasattr(self, "_hint_label") and self._current_status == "READY":
                    self._hint_label.configure(text="LOOK AT CAMERA OR PRESENT ID CARD", fg=C["muted"])
            else:
                self._cur_class_badge.configure(text="● NO ACTIVE CLASS", fg=C["warn"])
                self._cur_class_name.configure(text="NO ACTIVE CLASS", fg=C["muted"])
                self._cur_class_code.configure(text="")
                self._cur_class_detail.configure(text="Select a subject in the SUBJECTS tab to start attendance.", fg=C["dimmed"])
                self._cur_class_btn.configure(
                    text="[ + SELECT SUBJECT ]",
                    fg=C["accent"],
                    command=self._show_subjects
                )
                if hasattr(self, "_conf_idle_sub_title"):
                    self._conf_idle_sub_title.configure(text="NO ACTIVE CLASS — Select a subject")
                if hasattr(self, "_hint_label") and self._current_status == "READY":
                    self._hint_label.configure(text="SELECT A SUBJECT IN THE SUBJECTS TAB TO START ATTENDANCE", fg=C["warn"])

    def _save_active_receipt(self):
        if not getattr(self, "_active_receipt_data", None):
            messagebox.showinfo("Receipt", "No receipt available to save.", parent=self)
            return

        r_path = receipt_mod.generate_receipt_image(self._active_receipt_data)
        if r_path:
            messagebox.showinfo("Receipt Saved", f"Attendance verification receipt saved successfully:\n{r_path}", parent=self)
            try:
                import os
                os.startfile(r_path)
            except Exception:
                pass
        else:
            messagebox.showerror("Error", "Failed to generate receipt image.", parent=self)

    # ── Attendance panel ──────────────────────────────────────────────────────

    def _build_tab_attendance(self):
        panel = tk.Frame(self._tab_container, bg=C["bg"])
        self._tab_panels["ATTENDANCE"] = panel

        # Header
        hdr = tk.Frame(panel, bg=C["surface"])
        hdr.pack(fill="x")
        tk.Label(hdr, text="ATTENDANCE DASHBOARD",
                 font=FONTS["head"], bg=C["surface"], fg=C["text"]).pack(
            side="left", padx=16, pady=8)

        # Filter row
        filt = tk.Frame(panel, bg=C["bg"])
        filt.pack(fill="x", padx=16, pady=8)

        tk.Label(filt, text="DATE:", font=FONTS["label"],
                 bg=C["bg"], fg=C["muted"]).pack(side="left")
        self._att_date_var = tk.StringVar(value=date.today().isoformat())
        date_entry = tk.Entry(filt, textvariable=self._att_date_var,
                              font=FONTS["mono"], bg=C["surface2"], fg=C["text"],
                              insertbackground=C["accent"], relief="flat", bd=0, width=14)
        date_entry.pack(side="left", ipady=4, padx=8)

        tk.Label(filt, text="STUDENT:", font=FONTS["label"],
                 bg=C["bg"], fg=C["muted"]).pack(side="left", padx=(16, 0))
        self._att_stu_var = tk.StringVar()
        stu_entry = tk.Entry(filt, textvariable=self._att_stu_var,
                             font=FONTS["mono"], bg=C["surface2"], fg=C["text"],
                             insertbackground=C["accent"], relief="flat", bd=0, width=20)
        stu_entry.pack(side="left", ipady=4, padx=8)

        tk.Button(filt, text="REFRESH", font=FONTS["btn"],
                  bg=C["accent"], fg=C["bg"],
                  relief="flat", bd=0, padx=10, pady=4, cursor="hand2",
                  command=self._refresh_attendance).pack(side="left", padx=8)

        # Stats row
        self._att_stats_frame = tk.Frame(panel, bg=C["bg"])
        self._att_stats_frame.pack(fill="x", padx=16, pady=(0, 8))

        # Table
        tbl_frame = tk.Frame(panel, bg=C["bg"])
        tbl_frame.pack(fill="both", expand=True, padx=16, pady=(0, 8))

        self._att_tree = ttk.Treeview(tbl_frame,
                                       columns=("ID", "Name", "Time", "Method"),
                                       show="headings",
                                       style="Dark.Treeview",
                                       selectmode="browse")
        for col, w in [("ID", 110), ("Name", 200), ("Time", 90), ("Method", 100)]:
            self._att_tree.heading(col, text=col.upper())
            self._att_tree.column(col, width=w, anchor="w")

        vsb = ttk.Scrollbar(tbl_frame, orient="vertical",
                             command=self._att_tree.yview)
        self._att_tree.configure(yscrollcommand=vsb.set)
        self._att_tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

    def _show_attendance(self):
        self._show_panel("ATTENDANCE")
        self._refresh_attendance()

    def _refresh_attendance(self):
        d = self._att_date_var.get().strip() or date.today().isoformat()
        q = self._att_stu_var.get().strip().lower()
        records = db.get_attendance_by_date(d)
        if q:
            records = [r for r in records
                       if q in r["student_id"].lower() or q in r["name"].lower()]

        total = len(db.get_all_students())
        present = len(records)
        absent  = max(0, total - present)
        pct     = round(present / total * 100, 1) if total else 0

        # Rebuild stats row
        for w in self._att_stats_frame.winfo_children():
            w.destroy()
        for label, val, color in [
            ("PRESENT", present, C["accent"]),
            ("ABSENT",  absent,  C["danger"]),
            ("TOTAL",   total,   C["text"]),
            ("RATE",    f"{pct}%", C["accent2"]),
        ]:
            box = tk.Frame(self._att_stats_frame, bg=C["surface"],
                           bd=0, highlightthickness=1,
                           highlightbackground=C["border"])
            box.pack(side="left", padx=(0, 10))
            tk.Label(box, text=str(val), font=FONTS["value"],
                     bg=C["surface"], fg=color).pack(padx=20, pady=(8, 0))
            tk.Label(box, text=label, font=FONTS["small"],
                     bg=C["surface"], fg=C["muted"]).pack(padx=20, pady=(0, 8))

        self._att_tree.delete(*self._att_tree.get_children())
        if not records:
            msg = f"No attendance recorded for {d}" if not q else f"No attendance matching '{q}'"
            self._att_tree.insert("", "end", values=("—", msg, "—", "—"))
            return
        for r in records:
            self._att_tree.insert("", "end",
                                   values=(r["student_id"], r["name"],
                                           r["time"][:5], r["method"]))

    # ── Reports panel ─────────────────────────────────────────────────────────

    def _build_tab_reports(self):
        panel = tk.Frame(self._tab_container, bg=C["bg"])
        self._tab_panels["REPORTS"] = panel

        # Header
        hdr = tk.Frame(panel, bg=C["surface"])
        hdr.pack(fill="x")
        tk.Label(hdr, text="ATTENDANCE REPORTS",
                 font=FONTS["head"], bg=C["surface"], fg=C["text"]).pack(
            side="left", padx=16, pady=8)

        # Controls
        ctrl = tk.Frame(panel, bg=C["bg"])
        ctrl.pack(fill="x", padx=16, pady=8)

        tk.Label(ctrl, text="FROM:", font=FONTS["label"],
                 bg=C["bg"], fg=C["muted"]).pack(side="left")
        self._rep_from_var = tk.StringVar(value=date.today().isoformat())
        tk.Entry(ctrl, textvariable=self._rep_from_var, width=14,
                 font=FONTS["mono"], bg=C["surface2"], fg=C["text"],
                 insertbackground=C["accent"], relief="flat", bd=0).pack(
            side="left", ipady=4, padx=6)

        tk.Label(ctrl, text="TO:", font=FONTS["label"],
                 bg=C["bg"], fg=C["muted"]).pack(side="left", padx=(10, 0))
        self._rep_to_var = tk.StringVar(value=date.today().isoformat())
        tk.Entry(ctrl, textvariable=self._rep_to_var, width=14,
                 font=FONTS["mono"], bg=C["surface2"], fg=C["text"],
                 insertbackground=C["accent"], relief="flat", bd=0).pack(
            side="left", ipady=4, padx=6)

        tk.Label(ctrl, text="STUDENT:", font=FONTS["label"],
                 bg=C["bg"], fg=C["muted"]).pack(side="left", padx=(14, 0))
        self._rep_stu_var = tk.StringVar()
        tk.Entry(ctrl, textvariable=self._rep_stu_var, width=16,
                 font=FONTS["mono"], bg=C["surface2"], fg=C["text"],
                 insertbackground=C["accent"], relief="flat", bd=0).pack(
            side="left", ipady=4, padx=6)

        tk.Label(ctrl, text="SUBJECT:", font=FONTS["label"],
                 bg=C["bg"], fg=C["muted"]).pack(side="left", padx=(12, 0))
        self._rep_sub_var = tk.StringVar(value="ALL SUBJECTS")
        self._rep_sub_menu = ttk.OptionMenu(ctrl, self._rep_sub_var, "ALL SUBJECTS", "ALL SUBJECTS")
        self._rep_sub_menu.pack(side="left", padx=6)

        tk.Button(ctrl, text="GENERATE", font=FONTS["btn"],
                  bg=C["accent"], fg=C["bg"], relief="flat", bd=0,
                  padx=10, pady=4, cursor="hand2",
                  command=self._generate_report).pack(side="left", padx=8)

        tk.Button(ctrl, text="EXPORT CSV", font=FONTS["btn"],
                  bg=C["surface2"], fg=C["accent2"], relief="flat", bd=0,
                  padx=10, pady=4, cursor="hand2",
                  command=self._export_csv).pack(side="left")

        separator(panel, pady=2)

        # Report output area
        rep_frame = tk.Frame(panel, bg=C["bg"])
        rep_frame.pack(fill="both", expand=True, padx=16, pady=(0, 8))
        rep_frame.columnconfigure(0, weight=1)
        rep_frame.rowconfigure(0, weight=1)

        self._rep_text = tk.Text(rep_frame, bg=C["surface"], fg=C["text"],
                                  font=FONTS["mono"], relief="flat", bd=0,
                                  wrap="none", state="disabled",
                                  insertbackground=C["accent"])
        rep_vsb = ttk.Scrollbar(rep_frame, orient="vertical",
                                 command=self._rep_text.yview)
        rep_hsb = ttk.Scrollbar(rep_frame, orient="horizontal",
                                 command=self._rep_text.xview)
        self._rep_text.configure(yscrollcommand=rep_vsb.set,
                                  xscrollcommand=rep_hsb.set)
        self._rep_text.grid(row=0, column=0, sticky="nsew")
        rep_vsb.grid(row=0, column=1, sticky="ns")
        rep_hsb.grid(row=1, column=0, sticky="ew")

        self._last_report_data = None  # for CSV export

    def _show_reports(self):
        self._show_panel("REPORTS")
        # Populate subjects dropdown
        subs = sub_mod.search_subjects()
        sub_options = ["ALL SUBJECTS"] + [f"{s['subject_code']} - {s['subject_name']}" for s in subs]
        menu = self._rep_sub_menu["menu"]
        menu.delete(0, "end")
        for opt in sub_options:
            menu.add_command(label=opt, command=lambda v=opt: self._rep_sub_var.set(v))
        if self._rep_sub_var.get() not in sub_options:
            self._rep_sub_var.set("ALL SUBJECTS")

    def _generate_report(self):
        from_d = self._rep_from_var.get().strip()
        to_d   = self._rep_to_var.get().strip()
        stu_q  = self._rep_stu_var.get().strip()
        sub_sel = self._rep_sub_var.get()

        subject_id = None
        if sub_sel and sub_sel != "ALL SUBJECTS":
            code = sub_sel.split(" - ")[0].strip()
            s = db.get_subject_by_code(code)
            if s:
                subject_id = s["id"]

        report_text, self._last_report_data = rep_mod.generate_report(from_d, to_d, stu_q, subject_id=subject_id)

        self._rep_text.configure(state="normal")
        self._rep_text.delete("1.0", "end")
        self._rep_text.insert("end", report_text)
        self._rep_text.configure(state="disabled")

    def _export_csv(self):
        if self._last_report_data is None:
            messagebox.showwarning("No Report", "Generate a report first.", parent=self)
            return
        path = filedialog.asksaveasfilename(
            title="Export Attendance CSV",
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
            initialdir="exports",
        )
        if not path:
            return
        ok, msg = rep_mod.export_to_csv(self._last_report_data, path)
        if ok:
            messagebox.showinfo("Exported", f"Saved to:\n{path}", parent=self)
        else:
            messagebox.showerror("Export Error", msg, parent=self)

    # ═══════════════════════════════════════════════════════════════════════════
    # CAMERA & DETECTION
    # ═══════════════════════════════════════════════════════════════════════════

    def _initialize(self):
        try:
            db.initialize_database()
        except Exception as e:
            messagebox.showerror("Database Error",
                                 f"Failed to initialize database:\n{e}", parent=self)

        self._reload_encodings()

        ok = self.camera.start()
        if not ok:
            self._show_camera_offline()
            self._set_status("CAMERA ERROR")
        else:
            self._show_camera_online()
            self._set_status("READY")

        self._refresh_current_class_widget()
        self._refresh_timeline()
        self._refresh_counter()
        self._poll_camera_events()

    def _retry_camera(self):
        self._set_status("INITIALIZING")
        if hasattr(self, "_cam_offline_frame"):
            self._cam_offline_frame.pack_forget()
        self._cam_label.configure(image="", text="CONNECTING TO CAMERA…", fg=C["accent"])
        self._cam_label.pack(fill="both", expand=True)

        def _worker():
            ok = self.camera.start()
            self.after(0, lambda: self._on_camera_retry_done(ok))

        threading.Thread(target=_worker, daemon=True).start()

    def _on_camera_retry_done(self, ok: bool):
        if ok:
            self._show_camera_online()
            self._set_status("READY")
        else:
            self._show_camera_offline()
            self._set_status("CAMERA ERROR")

    def _show_camera_online(self):
        if hasattr(self, "_cam_offline_frame"):
            self._cam_offline_frame.pack_forget()
        if hasattr(self, "_cam_label"):
            self._cam_label.pack(fill="both", expand=True)

    def _show_camera_offline(self):
        if hasattr(self, "_cam_label"):
            self._cam_label.pack_forget()
        if hasattr(self, "_cam_offline_frame"):
            self._cam_offline_frame.pack(fill="both", expand=True)

    def _poll_camera_events(self):
        """Poll the camera event queue and dispatch detections."""
        events = self.camera.drain_events()
        for evt in events:
            self._handle_detection(evt)
        self.after(self.POLL_INTERVAL_MS, self._poll_camera_events)

    def _handle_detection(self, evt: DetectionEvent):
        if self._current_status in ("IDENTIFYING", "CARD DETECTED", "RECORDED", "DUPLICATE", "UNKNOWN", "NOT ENROLLED", "NO SESSION"):
            return  # Still in confirmation display or processing – ignore

        if evt.kind == DetectionEvent.BARCODE:
            barcode_val = evt.data
            clean_id = barcode_scanner.extract_student_id(barcode_val)
            self._set_status("CARD DETECTED")
            self._show_reading_card(clean_id)
            self.after(200, lambda: self._show_identifying_student(clean_id))
            self.after(450, lambda: self._process_barcode(clean_id))

        elif evt.kind == DetectionEvent.CARD_UNREADABLE:
            self._set_status("CARD DETECTED")
            self._show_unreadable_card()
            if self._confirm_after_id:
                self.after_cancel(self._confirm_after_id)
            self._confirm_after_id = self.after(2500, self._return_to_ready)

        elif evt.kind == DetectionEvent.FACE:
            match = evt.data
            if isinstance(match, dict) and match.get("matched", False) and match.get("student_id"):
                student_id = match["student_id"]
                student_name = match.get("name", "")
                self._set_status("FACE DETECTED")
                self._show_detecting_face()
                self.after(200, lambda: self._show_identifying_face(student_id, student_name))
                self.after(450, lambda: self._process_face_attendance(student_id))
            else:
                # Face detected, but not registered in ATTEND-X database
                self._set_status("FACE DETECTED")
                self._show_detecting_face()
                self.after(250, self._process_unknown_face)

    def _process_barcode(self, barcode_val: str):
        result = att_mod.mark_by_barcode(barcode_val)
        self._show_result(result)

    def _process_face_attendance(self, student_id: str):
        result = att_mod.mark_attendance(student_id, "FACE")
        self._show_result(result)

    def _process_unknown_face(self):
        self._show_unknown_face()

    def _show_result(self, result: dict):
        status = result["status"]
        student = result.get("student")
        t = result.get("time", "")
        method = result.get("method", "FACE")
        subject = result.get("subject")
        att_id = result.get("attendance_id")

        if status == "ok":
            self._set_status("RECORDED")
            is_demo = getattr(self, "_demo_mode", False)
            self._update_conf_card_success(student, t, method, subject=subject, att_id=att_id, is_demo=is_demo)
            self._refresh_timeline()
            self._refresh_counter()
        elif status == "duplicate":
            self._set_status("DUPLICATE")
            self._update_conf_card_duplicate(student, t, method, subject=subject, att_id=att_id)
        elif status == "not_enrolled":
            self._set_status("NOT ENROLLED")
            self._update_conf_card_not_enrolled(student, subject, method=method)
        elif status == "no_session":
            self._set_status("NO SESSION")
            self._update_conf_card_no_session(student=student)
        elif status == "unknown_card":
            self._set_status("UNKNOWN")
            self._update_conf_card_unknown_card(result.get("student_id", ""))
        elif status == "unknown":
            self._set_status("UNKNOWN")
            self._update_conf_card_unknown_face()
        else:
            self._set_status("CAMERA ERROR")
            self._update_conf_card_error(result.get("message", ""))

        # Schedule return to READY
        if self._confirm_after_id:
            self.after_cancel(self._confirm_after_id)
        self._confirm_after_id = self.after(
            self.CONFIRM_DISPLAY_SECONDS * 1000, self._return_to_ready
        )
        self.camera.trigger_cooldown(self.CONFIRM_DISPLAY_SECONDS + 0.5)

    def _show_unknown_face(self):
        self._set_status("UNKNOWN")
        self._update_conf_card_unknown_face()
        if self._confirm_after_id:
            self.after_cancel(self._confirm_after_id)
        self._confirm_after_id = self.after(3000, self._return_to_ready)
        self.camera.trigger_cooldown(3.5)

    def _return_to_ready(self):
        self._demo_mode = False
        self._set_status("READY")
        self._clear_conf_card()
        self._refresh_current_class_widget()
        self._confirm_after_id = None

    # ─── Camera frame display ─────────────────────────────────────────────────

    def _on_camera_frame(self, frame):
        """Called from camera thread – schedule GUI update on main thread."""
        self._latest_frame = frame
        if not getattr(self, "_frame_pending", False):
            self._frame_pending = True
            try:
                self.after_idle(self._process_cam_frame)
            except Exception:
                pass

    def _process_cam_frame(self):
        self._frame_pending = False
        if hasattr(self, "_latest_frame") and self._latest_frame is not None:
            self._update_cam_preview(self._latest_frame)

    def _update_cam_preview(self, frame):
        try:
            w = self._cam_label.winfo_width()
            h = self._cam_label.winfo_height()
            if w < 20 or h < 20:
                return

            fh, fw = frame.shape[:2]
            scale = min(w / fw, h / fh)
            nw = max(1, int(fw * scale))
            nh = max(1, int(fh * scale))

            # Resize frame proportionally
            resized = cv2.resize(frame, (nw, nh), interpolation=cv2.INTER_LINEAR)

            # Draw subtle technical reticle corners on the frame
            box_w = int(nw * 0.55)
            box_h = int(nh * 0.65)
            bx1 = (nw - box_w) // 2
            by1 = (nh - box_h) // 2
            bx2 = bx1 + box_w
            by2 = by1 + box_h
            arm = min(24, box_w // 4)

            # Emerald accent in BGR: (150, 210, 0)
            ret_color = (150, 210, 0) if self._current_status in ("READY", "FACE DETECTED", "CARD DETECTED", "RECORDED") else (184, 163, 148)
            thick = 2

            # Reticle 4 corners
            cv2.line(resized, (bx1, by1), (bx1 + arm, by1), ret_color, thick)
            cv2.line(resized, (bx1, by1), (bx1, by1 + arm), ret_color, thick)
            cv2.line(resized, (bx2, by1), (bx2 - arm, by1), ret_color, thick)
            cv2.line(resized, (bx2, by1), (bx2, by1 + arm), ret_color, thick)
            cv2.line(resized, (bx1, by2), (bx1 + arm, by2), ret_color, thick)
            cv2.line(resized, (bx1, by2), (bx1, by2 - arm), ret_color, thick)
            cv2.line(resized, (bx2, by2), (bx2 - arm, by2), ret_color, thick)
            cv2.line(resized, (bx2, by2), (bx2, by2 - arm), ret_color, thick)

            # Create letterbox canvas with terminal surface color
            bg_bgr = _hex_to_rgb(C["surface2"])[::-1]
            canvas = np.full((h, w, 3), bg_bgr, dtype=np.uint8)
            y_off = (h - nh) // 2
            x_off = (w - nw) // 2
            canvas[y_off:y_off+nh, x_off:x_off+nw] = resized

            frame_rgb = cv2.cvtColor(canvas, cv2.COLOR_BGR2RGB)
            img = Image.fromarray(frame_rgb)
            photo = ImageTk.PhotoImage(img)
            self._cam_label.configure(image=photo, text="")
            self._camera_photo = photo  # prevent GC
        except Exception:
            pass

    # ═══════════════════════════════════════════════════════════════════════════
    # CONFIRMATION CARD
    # ═══════════════════════════════════════════════════════════════════════════

    def _show_detecting_face(self):
        if hasattr(self, "_conf_idle_frame") and hasattr(self, "_conf_active_frame"):
            self._conf_idle_frame.pack_forget()
            self._conf_active_frame.pack(fill="both", expand=True)

        self._conf_status_badge.configure(text="● FACE DETECTED", fg=C["accent"])
        self._conf_name.configure(text="IDENTIFYING STUDENT...", fg=C["text_sec"])
        self._conf_id.configure(text="BIOMETRIC SCAN", fg=C["accent"])
        self._conf_subject.configure(text="")
        self._conf_detail.configure(text="Matching facial features with database...", fg=C["muted"])
        self._conf_time.configure(text="")
        self._conf_method.configure(text="METHOD: FACE", fg=C["accent"])
        self._conf_att_id.configure(text="")
        if hasattr(self, "_conf_receipt_btn"):
            self._conf_receipt_btn.configure(state="disabled")
        self._conf_note.configure(text="Please look directly at camera...", fg=C["dimmed"])
        self._conf_card.configure(highlightbackground=C["accent"])

    def _show_identifying_face(self, student_id: str, student_name: str):
        if hasattr(self, "_conf_idle_frame") and hasattr(self, "_conf_active_frame"):
            self._conf_idle_frame.pack_forget()
            self._conf_active_frame.pack(fill="both", expand=True)

        self._set_status("IDENTIFYING")
        self._conf_status_badge.configure(text="✓ STUDENT FOUND", fg=C["accent"])
        self._conf_name.configure(text=student_name or "STUDENT FOUND", fg=C["text"])
        self._conf_id.configure(text=student_id, fg=C["accent"])
        self._conf_subject.configure(text="")
        self._conf_detail.configure(text="ENROLLMENT VERIFIED  ·  CHECKING STATUS...", fg=C["muted"])
        self._conf_time.configure(text="")
        self._conf_method.configure(text="METHOD: FACE", fg=C["accent"])
        self._conf_att_id.configure(text="")
        if hasattr(self, "_conf_receipt_btn"):
            self._conf_receipt_btn.configure(state="disabled")
        self._conf_note.configure(text="Verifying subject enrollment in database...", fg=C["dimmed"])
        self._conf_card.configure(highlightbackground=C["accent"])

    def _show_reading_card(self, barcode_val: str):
        if hasattr(self, "_conf_idle_frame") and hasattr(self, "_conf_active_frame"):
            self._conf_idle_frame.pack_forget()
            self._conf_active_frame.pack(fill="both", expand=True)

        self._conf_status_badge.configure(text="● CARD DETECTED", fg=C["accent2"])
        self._conf_name.configure(text="READING ID CARD...", fg=C["text_sec"])
        self._conf_id.configure(text=f"ID: {barcode_val}", fg=C["accent2"])
        self._conf_detail.configure(text="Decoding student ID from card...", fg=C["muted"])
        self._conf_time.configure(text="")
        self._conf_method.configure(text="METHOD: ID CARD", fg=C["accent2"])
        self._conf_note.configure(text="Reading card data...", fg=C["dimmed"])
        self._conf_card.configure(highlightbackground=C["accent2"])

    def _show_identifying_student(self, student_id: str):
        if self._current_status != "CARD DETECTED":
            return
        self._conf_status_badge.configure(text="● IDENTIFYING STUDENT...", fg=C["warn"])
        self._conf_name.configure(text="IDENTIFYING STUDENT...", fg=C["text_sec"])
        self._conf_id.configure(text=f"ID: {student_id}", fg=C["accent2"])
        self._conf_detail.configure(text="Verifying student in database...", fg=C["muted"])
        self._conf_note.configure(text="Validating enrollment status...", fg=C["dimmed"])

    def _show_unreadable_card(self):
        if hasattr(self, "_conf_idle_frame") and hasattr(self, "_conf_active_frame"):
            self._conf_idle_frame.pack_forget()
            self._conf_active_frame.pack(fill="both", expand=True)

        self._conf_status_badge.configure(text="● CARD DETECTED", fg=C["warn"])
        self._conf_name.configure(text="UNABLE TO READ CARD", fg=C["warn"])
        self._conf_id.configure(text="CARD DETECTED", fg=C["warn"])
        self._conf_detail.configure(text="Please hold the card inside the scanning area.\nEnsure good lighting and avoid glare.", fg=C["muted"])
        self._conf_time.configure(text="")
        self._conf_method.configure(text="METHOD: ID CARD", fg=C["dimmed"])
        self._conf_att_id.configure(text="")
        if hasattr(self, "_conf_receipt_btn"):
            self._conf_receipt_btn.configure(state="disabled")
        self._conf_note.configure(text="Please hold the card inside the scanning area.", fg=C["dimmed"])
        self._conf_card.configure(highlightbackground=C["warn"])

    def _update_conf_card_success(self, student: dict, time_str: str, method: str,
                                  subject: dict = None, att_id: str = None, is_demo: bool = False):
        if hasattr(self, "_conf_idle_frame") and hasattr(self, "_conf_active_frame"):
            self._conf_idle_frame.pack_forget()
            self._conf_active_frame.pack(fill="both", expand=True)

        name = student.get("name", "Unknown") if student else "Unknown"
        sid  = student.get("student_id", "") if student else ""
        sub_name = subject.get("subject_name", "General Class") if subject else "General Class"
        sub_code = subject.get("subject_code", "") if subject else ""
        t_str = time_str[:8] if time_str else datetime.now().strftime("%H:%M:%S")
        date_str = (subject.get("date") if subject else "") or datetime.now().strftime("%d %b %Y").upper()

        self._active_receipt_data = {
            "name": name,
            "student_id": sid,
            "subject_name": sub_name,
            "subject_code": sub_code,
            "date": date_str,
            "time": t_str,
            "method": method,
            "status": "PRESENT",
            "attendance_id": att_id or f"AX-{datetime.now().strftime('%y%m%d-%H%M%S')}"
        }

        self._conf_status_badge.configure(text="✓ ATTENDANCE RECORDED", fg=C["accent"])
        self._conf_name.configure(text=name, fg=C["text"])
        self._conf_id.configure(text=sid, fg=C["accent"])
        self._conf_subject.configure(text=f"SUBJECT: {sub_name} ({sub_code})" if sub_code else f"SUBJECT: {sub_name}")
        self._conf_detail.configure(text=f"DATE: {date_str}   ·   STATUS: PRESENT", fg=C["muted"])
        self._conf_time.configure(text=t_str, fg=C["text"])
        method_txt = f"METHOD: {method}"
        if is_demo:
            method_txt += " (DEMO)"
        self._conf_method.configure(text=method_txt, fg=C["accent"] if method == "FACE" else C["accent2"])
        if att_id:
            self._conf_att_id.configure(text=f"Verification ID: {att_id}", fg=C["muted"])
        else:
            self._conf_att_id.configure(text="")
        if hasattr(self, "_conf_receipt_btn"):
            self._conf_receipt_btn.configure(state="normal")
        if is_demo:
            self._conf_note.configure(text="✦ DEMO MODE ACTIVE  ·  DATA RECORDED", fg=C["accent2"])
        else:
            self._conf_note.configure(text="✓ ATTENDANCE RECORDED", fg=C["accent"])
        self._conf_card.configure(highlightbackground=C["accent"])

    def _update_conf_card_duplicate(self, student: dict, time_str: str, method: str, subject: dict = None, att_id: str = None):
        if hasattr(self, "_conf_idle_frame") and hasattr(self, "_conf_active_frame"):
            self._conf_idle_frame.pack_forget()
            self._conf_active_frame.pack(fill="both", expand=True)

        name = student.get("name", "Unknown") if student else "Unknown"
        sid  = student.get("student_id", "") if student else ""
        sub_name = subject.get("subject_name", "") if subject else ""
        rec_time = f"Recorded at {time_str[:5]}" if time_str else "Recorded earlier"

        self._active_receipt_data = None
        self._conf_status_badge.configure(text="! ALREADY MARKED", fg=C["warn"])
        self._conf_name.configure(text=name, fg=C["text"])
        self._conf_id.configure(text=sid, fg=C["warn"])
        if sub_name:
            self._conf_subject.configure(text=f"Subject: {sub_name}")
        else:
            self._conf_subject.configure(text="")
        self._conf_detail.configure(text="Attendance already recorded for this session.", fg=C["muted"])
        self._conf_time.configure(text=rec_time, fg=C["warn"])
        self._conf_method.configure(text=f"METHOD: {method}", fg=C["muted"])
        if att_id:
            self._conf_att_id.configure(text=f"Verification ID: {att_id}", fg=C["warn"])
        else:
            self._conf_att_id.configure(text="")
        if hasattr(self, "_conf_receipt_btn"):
            self._conf_receipt_btn.configure(state="disabled")
        self._conf_note.configure(text="Attendance already recorded for this session.", fg=C["dimmed"])
        self._conf_card.configure(highlightbackground=C["warn"])

    def _update_conf_card_not_enrolled(self, student: dict, subject: dict = None, method: str = "FACE"):
        if hasattr(self, "_conf_idle_frame") and hasattr(self, "_conf_active_frame"):
            self._conf_idle_frame.pack_forget()
            self._conf_active_frame.pack(fill="both", expand=True)

        name = student.get("name", "Unknown") if student else "Unknown"
        sid  = student.get("student_id", "") if student else ""
        sub_name = subject.get("subject_name", "the current subject") if subject else "the current subject"
        sub_code = subject.get("subject_code", "") if subject else ""

        self._active_receipt_data = None
        self._conf_status_badge.configure(text="! NOT ENROLLED", fg=C["danger"])
        self._conf_name.configure(text=name, fg=C["text"])
        self._conf_id.configure(text=sid, fg=C["danger"])
        self._conf_subject.configure(
            text=f"Not enrolled in: {sub_name} ({sub_code})" if sub_code else f"Not enrolled in: {sub_name}",
            fg=C["warn"]
        )
        self._conf_detail.configure(text=f"{name} is not enrolled in {sub_name}.", fg=C["muted"])
        self._conf_time.configure(text="")
        self._conf_method.configure(text=f"METHOD: {method}", fg=C["muted"])
        self._conf_att_id.configure(text="")
        if hasattr(self, "_conf_receipt_btn"):
            self._conf_receipt_btn.configure(state="disabled")
        self._conf_note.configure(text="No attendance record created.", fg=C["dimmed"])
        self._conf_card.configure(highlightbackground=C["danger"])

    def _update_conf_card_no_session(self, student: dict = None):
        if hasattr(self, "_conf_idle_frame") and hasattr(self, "_conf_active_frame"):
            self._conf_idle_frame.pack_forget()
            self._conf_active_frame.pack(fill="both", expand=True)

        self._active_receipt_data = None
        self._conf_status_badge.configure(text="! NO ACTIVE CLASS", fg=C["warn"])
        if student:
            self._conf_name.configure(text=student.get("name", "Student Identified"), fg=C["text"])
            self._conf_id.configure(text=student.get("student_id", ""), fg=C["warn"])
        else:
            self._conf_name.configure(text="No Class Session Active", fg=C["text"])
            self._conf_id.configure(text="TERMINAL STANDBY", fg=C["warn"])
        self._conf_subject.configure(text="")
        self._conf_detail.configure(text="Attendance requires an active subject session.\nPlease start a session in the SUBJECTS tab.", fg=C["muted"])
        self._conf_time.configure(text="")
        self._conf_method.configure(text="STANDBY", fg=C["muted"])
        self._conf_att_id.configure(text="")
        if hasattr(self, "_conf_receipt_btn"):
            self._conf_receipt_btn.configure(state="disabled")
        self._conf_note.configure(text="No attendance record created.", fg=C["dimmed"])
        self._conf_card.configure(highlightbackground=C["warn"])

    def _update_conf_card_unknown_face(self):
        if hasattr(self, "_conf_idle_frame") and hasattr(self, "_conf_active_frame"):
            self._conf_idle_frame.pack_forget()
            self._conf_active_frame.pack(fill="both", expand=True)

        self._active_receipt_data = None
        self._conf_status_badge.configure(text="! STUDENT NOT FOUND", fg=C["danger"])
        self._conf_name.configure(text="STUDENT NOT FOUND", fg=C["danger"])
        self._conf_id.configure(text="UNREGISTERED FACE", fg=C["danger"])
        self._conf_subject.configure(text="")
        self._conf_detail.configure(
            text="No registered student matches this face.\nThis face is not registered in ATTEND-X.",
            fg=C["muted"]
        )
        self._conf_time.configure(text="")
        self._conf_method.configure(text="METHOD: FACE", fg=C["dimmed"])
        self._conf_att_id.configure(text="")
        if hasattr(self, "_conf_receipt_btn"):
            self._conf_receipt_btn.configure(state="disabled")
        self._conf_note.configure(text="No attendance record created.", fg=C["dimmed"])
        self._conf_card.configure(highlightbackground=C["danger"])

    def _update_conf_card_unknown_card(self, barcode_val: str):
        if hasattr(self, "_conf_idle_frame") and hasattr(self, "_conf_active_frame"):
            self._conf_idle_frame.pack_forget()
            self._conf_active_frame.pack(fill="both", expand=True)

        self._conf_status_badge.configure(text="! STUDENT NOT FOUND", fg=C["danger"])
        self._conf_name.configure(text="STUDENT NOT FOUND", fg=C["text_sec"])
        self._conf_id.configure(text=f"ID: {barcode_val}", fg=C["danger"])
        self._conf_detail.configure(text="This student ID does not exist in the ATTEND-X database.", fg=C["muted"])
        self._conf_time.configure(text="")
        self._conf_method.configure(text="METHOD: ID CARD", fg=C["dimmed"])
        self._conf_note.configure(text="This student ID does not exist in the ATTEND-X database.", fg=C["dimmed"])
        self._conf_card.configure(highlightbackground=C["danger"])

    def _update_conf_card_error(self, message: str):
        if hasattr(self, "_conf_idle_frame") and hasattr(self, "_conf_active_frame"):
            self._conf_idle_frame.pack_forget()
            self._conf_active_frame.pack(fill="both", expand=True)

        self._conf_status_badge.configure(text="! SYSTEM ERROR", fg=C["danger"])
        self._conf_name.configure(text="Error", fg=C["danger"])
        self._conf_id.configure(text="", fg=C["dimmed"])
        self._conf_detail.configure(text=message, fg=C["muted"])
        self._conf_time.configure(text="")
        self._conf_method.configure(text="", fg=C["dimmed"])
        self._conf_note.configure(text="Check camera or database connection.", fg=C["dimmed"])
        self._conf_card.configure(highlightbackground=C["danger"])

    def _clear_conf_card(self):
        if hasattr(self, "_conf_idle_frame") and hasattr(self, "_conf_active_frame"):
            self._conf_active_frame.pack_forget()
            self._conf_idle_frame.pack(fill="both", expand=True)
        self._conf_card.configure(highlightbackground=C["border"])

    # ═══════════════════════════════════════════════════════════════════════════
    # STATUS & TIMELINE
    # ═══════════════════════════════════════════════════════════════════════════

    def _set_status(self, status: str):
        self._current_status = status
        color = STATUS_COLORS.get(status, C["muted"])
        dot_color = STATUS_DOT.get(status, C["muted"])

        if hasattr(self, "_status_label"):
            self._status_label.configure(text=status, fg=color)
        if hasattr(self, "_dot_canvas"):
            self._dot_canvas.itemconfigure(self._dot_oval, fill=dot_color)

        # Header status badge
        header_badge_map = {
            "INITIALIZING": ("● INITIALIZING",   C["muted"]),
            "READY":        ("● SYSTEM ONLINE",  C["accent"]),
            "CAMERA READY": ("● CAMERA READY",   C["accent"]),
            "FACE DETECTED":("● FACE DETECTED",  C["accent"]),
            "CARD DETECTED":("● CARD DETECTED",  C["accent2"]),
            "IDENTIFYING":  ("● IDENTIFYING...", C["warn"]),
            "RECORDED":     ("✓ ATTENDANCE RECORDED", C["accent"]),
            "DUPLICATE":    ("! ALREADY MARKED", C["warn"]),
            "NOT ENROLLED": ("! NOT ENROLLED",   C["danger"]),
            "NO SESSION":   ("! NO ACTIVE CLASS", C["warn"]),
            "UNKNOWN":      ("! STUDENT NOT FOUND", C["danger"]),
            "CAMERA ERROR": ("! CAMERA OFFLINE", C["danger"]),
            "DEMO MODE":    ("✦ DEMO MODE ACTIVE", C["accent2"]),
        }
        badge_txt, badge_col = header_badge_map.get(status, ("● SYSTEM ONLINE", C["accent"]))
        if hasattr(self, "_sys_badge_label"):
            self._sys_badge_label.configure(text=badge_txt, fg=badge_col)

        hint_map = {
            "READY":        "LOOK AT CAMERA OR PRESENT ID CARD",
            "FACE DETECTED":"FACE DETECTED  ·  IDENTIFYING STUDENT...",
            "CARD DETECTED":"CARD DETECTED  ·  READING ID...",
            "IDENTIFYING":  "IDENTIFYING STUDENT...",
            "RECORDED":     "✓ ATTENDANCE RECORDED",
            "DUPLICATE":    "! ALREADY MARKED TODAY",
            "NOT ENROLLED": "! STUDENT NOT ENROLLED IN THIS SUBJECT",
            "NO SESSION":   "! NO ACTIVE CLASS SESSION",
            "UNKNOWN":      "! STUDENT NOT FOUND  ·  NOT REGISTERED",
            "CAMERA ERROR": "! CAMERA OFFLINE",
            "DEMO MODE":    "✦ DEMO MODE ACTIVE",
        }
        hint = hint_map.get(status, "")
        if hasattr(self, "_hint_label"):
            self._hint_label.configure(text=hint, fg=color if status != "READY" else C["muted"])

        # Update footer hardware indicator
        if hasattr(self, "_footer_status"):
            cam_stat = "OFFLINE" if status == "CAMERA ERROR" or not getattr(self.camera, "available", True) else "ONLINE"
            self._footer_status.configure(
                text=f"CAMERA: {cam_stat}  ·  DATABASE: CONNECTED  ·  MODE: AUTOMATIC"
            )

    def _refresh_timeline(self):
        for w in self._timeline_inner.winfo_children():
            w.destroy()

        # Update date in timeline header
        if hasattr(self, "_timeline_date_lbl"):
            self._timeline_date_lbl.configure(text=datetime.now().strftime("%d %b %Y").upper())

        records = att_mod.get_recent_records(n=14)
        if not records:
            empty_box = tk.Frame(self._timeline_inner, bg=C["bg"])
            empty_box.pack(fill="both", expand=True, pady=32)
            tk.Label(empty_box, text="No attendance recorded yet.",
                     font=FONTS["label_b"], bg=C["bg"], fg=C["muted"]).pack()
            tk.Label(empty_box, text="The next student will appear here.",
                     font=FONTS["small"], bg=C["bg"], fg=C["dimmed"]).pack(pady=(4, 0))
            return

        for r in records:
            card = tk.Frame(self._timeline_inner, bg=C["surface"], bd=0,
                            highlightthickness=1, highlightbackground=C["border"])
            card.pack(fill="x", pady=2, padx=2)

            # Left: time
            time_lbl = tk.Label(card, text=r["time"][:5],
                                font=FONTS["small_mono"], bg=C["surface"],
                                fg=C["muted"], width=6, anchor="w")
            time_lbl.pack(side="left", padx=(10, 4), pady=5)

            # Center: student name and secondary student ID
            info_col = tk.Frame(card, bg=C["surface"])
            info_col.pack(side="left", fill="x", expand=True, padx=4, pady=3)

            tk.Label(info_col, text=r["name"], font=FONTS["label_b"],
                     bg=C["surface"], fg=C["text"], anchor="w").pack(anchor="w")
            tk.Label(info_col, text=r.get("student_id", ""),
                     font=FONTS["small_mono"], bg=C["surface"],
                     fg=C["dimmed"], anchor="w").pack(anchor="w")

            # Right: method badge
            method = r.get("method", "FACE")
            m_color = C["accent"] if method == "FACE" else C["accent2"]
            badge = tk.Label(card, text=f" {method} ", font=FONTS["subtitle"],
                             bg=C["surface2"], fg=m_color, padx=6, pady=2)
            badge.pack(side="right", padx=(4, 10), pady=5)

        self._timeline_inner.update_idletasks()
        self._timeline_canvas.configure(
            scrollregion=self._timeline_canvas.bbox("all")
        )

    def _on_timeline_resize(self, event):
        self._timeline_canvas.configure(
            scrollregion=self._timeline_canvas.bbox("all")
        )

    def _on_timeline_canvas_resize(self, event):
        self._timeline_canvas.itemconfigure(self._tl_window, width=event.width)

    def _refresh_counter(self):
        stats = att_mod.get_today_stats()
        present = stats["present"]
        total   = stats["total"]
        absent  = stats["absent"]
        pct     = stats["percent"]

        if hasattr(self, "_stat_boxes"):
            self._stat_boxes["present"].configure(text=str(present))
            self._stat_boxes["absent"].configure(text=str(absent))
            self._stat_boxes["total"].configure(text=str(total))
            self._stat_boxes["rate"].configure(text=f"{pct:.1f}%")

        if hasattr(self, "_progress_text"):
            self._progress_text.configure(text=f"{present} / {total} PRESENT  •  {pct:.1f}%")

        if hasattr(self, "_prog_canvas"):
            w = int(240 * (pct / 100.0)) if total > 0 else 0
            self._prog_canvas.coords(self._prog_fill, 0, 0, w, 6)

    # ═══════════════════════════════════════════════════════════════════════════
    # CLOCK
    # ═══════════════════════════════════════════════════════════════════════════

    def _start_clock(self):
        self._tick_clock()

    def _tick_clock(self):
        now = datetime.now().strftime("%H:%M:%S")
        self._clock_label.configure(text=now)
        self.after(1000, self._tick_clock)

    # ═══════════════════════════════════════════════════════════════════════════
    # FACE ENCODINGS
    # ═══════════════════════════════════════════════════════════════════════════

    def _reload_encodings(self):
        def _load():
            enc = stu_mod.load_all_face_encodings()
            self._known_encodings = enc
            self.camera.set_known_encodings(enc)
        threading.Thread(target=_load, daemon=True).start()

    # ═══════════════════════════════════════════════════════════════════════════
    # DEMO MODE
    # ═══════════════════════════════════════════════════════════════════════════

    def _open_demo(self):
        DemoDialog(self, camera=self.camera,
                   on_event=self._handle_detection_data)

    def _open_debug(self):
        IdCardDebugDialog(self, camera=self.camera)

    def _handle_detection_data(self, kind: str, data: str):
        """Called from DemoDialog with kind=FACE|BARCODE|UNKNOWN_FACE and data=student_id|barcode."""
        from camera import DetectionEvent
        if kind == "UNKNOWN_FACE":
            evt = DetectionEvent(DetectionEvent.FACE,
                                 data={"matched": False, "student_id": None, "name": None})
        elif kind == "FACE":
            # Simulate a registered student face match
            stu = db.get_student_by_id(data)
            stu_name = stu["name"] if stu else ""
            evt = DetectionEvent(DetectionEvent.FACE,
                                 data={"matched": True, "student_id": data, "name": stu_name})
        else:
            evt = DetectionEvent(DetectionEvent.BARCODE, data=data)
        self._handle_detection(evt)

    # ═══════════════════════════════════════════════════════════════════════════
    # CLEANUP
    # ═══════════════════════════════════════════════════════════════════════════

    def destroy(self):
        self.camera.stop()
        super().destroy()


# ═══════════════════════════════════════════════════════════════════════════════
# DIALOGS
# ═══════════════════════════════════════════════════════════════════════════════

class _BaseDialog(tk.Toplevel):
    def __init__(self, parent, title: str, width: int = 420, height: int = 380):
        super().__init__(parent)
        self.result = None
        self.configure(bg=C["bg"])
        self.title(title)
        self.geometry(f"{width}x{height}")
        self.resizable(False, False)
        self.grab_set()
        self.focus_set()
        # Center
        self.update_idletasks()
        px = parent.winfo_x() + (parent.winfo_width() - width) // 2
        py = parent.winfo_y() + (parent.winfo_height() - height) // 2
        self.geometry(f"{width}x{height}+{px}+{py}")


class StudentDialog(_BaseDialog):
    """Add or Edit student dialog."""

    def __init__(self, parent, title: str, student: dict = None):
        super().__init__(parent, title, width=440, height=380)

        tk.Label(self, text=title, font=FONTS["head"],
                 bg=C["bg"], fg=C["accent"]).pack(pady=(20, 10))
        separator(self)

        form = tk.Frame(self, bg=C["bg"])
        form.pack(fill="x", padx=32, pady=10)

        self._vars = {}
        fields = [
            ("STUDENT ID",  "student_id"),
            ("FULL NAME",   "name"),
            ("BRANCH",      "branch"),
            ("SEMESTER",    "semester"),
        ]

        for label, key in fields:
            row = tk.Frame(form, bg=C["bg"])
            row.pack(fill="x", pady=4)
            tk.Label(row, text=label, font=FONTS["label"],
                     bg=C["bg"], fg=C["muted"], width=14, anchor="w").pack(side="left")
            var = tk.StringVar(value=(student.get(key, "") if student else ""))
            entry = tk.Entry(row, textvariable=var, font=FONTS["mono"],
                             bg=C["surface2"], fg=C["text"],
                             insertbackground=C["accent"], relief="flat", bd=0)
            entry.pack(side="left", fill="x", expand=True, ipady=5, padx=(8, 0))
            self._vars[key] = var
            if student and key == "student_id":
                entry.configure(state="disabled")

        separator(self)

        btn_row = tk.Frame(self, bg=C["bg"])
        btn_row.pack(pady=14)
        tk.Button(btn_row, text="SAVE", font=FONTS["btn"],
                  bg=C["accent"], fg=C["bg"], relief="flat", bd=0,
                  padx=20, pady=6, cursor="hand2",
                  command=self._save).pack(side="left", padx=8)
        tk.Button(btn_row, text="CANCEL", font=FONTS["btn"],
                  bg=C["surface2"], fg=C["muted"], relief="flat", bd=0,
                  padx=20, pady=6, cursor="hand2",
                  command=self.destroy).pack(side="left")

    def _save(self):
        sid  = self._vars["student_id"].get().strip()
        name = self._vars["name"].get().strip()
        branch = self._vars["branch"].get().strip()
        sem    = self._vars["semester"].get().strip()
        if not sid or not name:
            messagebox.showwarning("Validation", "Student ID and Name are required.", parent=self)
            return
        self.result = (sid, name, branch, sem)
        self.destroy()


class FaceCaptureDialog(_BaseDialog):
    """Live camera face capture for a student."""

    PREVIEW_W = 360
    PREVIEW_H = 270

    def __init__(self, parent, student_id: str, camera: CameraManager, on_done):
        super().__init__(parent, f"CAPTURE FACE — {student_id}", width=420, height=420)
        self._student_id = student_id
        self._camera     = camera
        self._on_done    = on_done
        self._photo_ref  = None
        self._captured_frame = None
        self._captured_enc   = None
        self._captured_path  = None

        tk.Label(self, text=f"CAPTURE FACE — {student_id}",
                 font=FONTS["head"], bg=C["bg"], fg=C["accent"]).pack(pady=(16, 6))
        tk.Label(self,
                 text="Centre your face in the frame, then press CAPTURE.",
                 font=FONTS["small"], bg=C["bg"], fg=C["muted"]).pack()

        self._preview = tk.Label(self, bg=C["surface2"],
                                 width=self.PREVIEW_W, height=self.PREVIEW_H)
        self._preview.pack(pady=10, padx=24, fill="both", expand=True)

        btn_row = tk.Frame(self, bg=C["bg"])
        btn_row.pack(pady=8)

        self._cap_btn = tk.Button(btn_row, text="CAPTURE", font=FONTS["btn"],
                                   bg=C["accent"], fg=C["bg"], relief="flat", bd=0,
                                   padx=16, pady=6, cursor="hand2",
                                   command=self._capture)
        self._cap_btn.pack(side="left", padx=8)

        self._save_btn = tk.Button(btn_row, text="SAVE", font=FONTS["btn"],
                                    bg=C["surface2"], fg=C["muted"], relief="flat", bd=0,
                                    padx=16, pady=6, cursor="hand2", state="disabled",
                                    command=self._save)
        self._save_btn.pack(side="left", padx=8)

        tk.Button(btn_row, text="CANCEL", font=FONTS["btn"],
                  bg=C["surface2"], fg=C["muted"], relief="flat", bd=0,
                  padx=16, pady=6, cursor="hand2",
                  command=self.destroy).pack(side="left")

        self._camera.pause()
        self._orig_on_frame   = self._camera.on_frame
        self._camera.on_frame = self._on_frame
        self.protocol("WM_DELETE_WINDOW", self.destroy)

    def _on_frame(self, frame):
        self._live_frame = frame
        if self._captured_frame is None:
            self.after(0, lambda f=frame: self._update_preview(f))

    def _update_preview(self, frame):
        try:
            import cv2
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            img = Image.fromarray(rgb)
            img = img.resize((self.PREVIEW_W, self.PREVIEW_H), Image.BILINEAR)
            ph  = ImageTk.PhotoImage(img)
            self._preview.configure(image=ph, text="")
            self._photo_ref = ph
        except Exception:
            pass

    def _capture(self):
        frame = getattr(self, "_live_frame", None)
        if frame is None:
            frame = self._camera.capture_still()
        if frame is None:
            messagebox.showwarning("Capture", "No camera frame available.", parent=self)
            return

        enc, loc = frm.encode_face_from_frame(frame)
        if loc is None:
            locs = frm.detect_faces_in_frame(frame)
            if locs:
                loc = locs[0]

        import cv2
        Path("faces").mkdir(exist_ok=True)
        path = f"faces/{self._student_id}.jpg"
        cv2.imwrite(path, frame)
        self._captured_frame = frame
        self._captured_enc   = enc
        self._captured_path  = path

        if loc:
            annotated = frm.draw_face_boxes(frame.copy(), [loc], label="CAPTURED")
            self._update_preview(annotated)
        else:
            self._update_preview(frame)

        self._save_btn.configure(state="normal", bg=C["accent"], fg=C["bg"])

    def _save(self):
        self._on_done(self._student_id, self._captured_enc, self._captured_path)
        self.destroy()

    def destroy(self):
        if hasattr(self, "_orig_on_frame") and self._orig_on_frame is not None:
            self._camera.on_frame = self._orig_on_frame
            self._orig_on_frame = None
        self._camera.resume()
        super().destroy()


class SubjectDialog(_BaseDialog):
    """Add or Edit subject dialog."""

    def __init__(self, parent, title: str, subject: dict = None):
        super().__init__(parent, title, width=460, height=450)

        tk.Label(self, text=title, font=FONTS["head"],
                 bg=C["bg"], fg=C["accent"]).pack(pady=(18, 8))
        separator(self)

        form = tk.Frame(self, bg=C["bg"])
        form.pack(fill="x", padx=32, pady=10)

        self._vars = {}
        fields = [
            ("SUBJECT CODE", "subject_code"),
            ("SUBJECT NAME", "subject_name"),
            ("BRANCH",       "branch"),
            ("SEMESTER",     "semester"),
            ("FACULTY",      "faculty"),
            ("ROOM",         "room"),
        ]

        for label, key in fields:
            row = tk.Frame(form, bg=C["bg"])
            row.pack(fill="x", pady=4)
            tk.Label(row, text=label, font=FONTS["label"],
                     bg=C["bg"], fg=C["muted"], width=14, anchor="w").pack(side="left")
            val = str(subject.get(key, "")) if subject else ""
            var = tk.StringVar(value=val)
            entry = tk.Entry(row, textvariable=var, font=FONTS["mono"],
                             bg=C["surface2"], fg=C["text"],
                             insertbackground=C["accent"], relief="flat", bd=0)
            entry.pack(side="left", fill="x", expand=True, ipady=4, padx=(8, 0))
            self._vars[key] = var

        separator(self)

        btn_row = tk.Frame(self, bg=C["bg"])
        btn_row.pack(pady=12)
        tk.Button(btn_row, text="SAVE SUBJECT", font=FONTS["btn"],
                  bg=C["accent"], fg=C["bg"], relief="flat", bd=0,
                  padx=20, pady=6, cursor="hand2",
                  command=self._save).pack(side="left", padx=8)
        tk.Button(btn_row, text="CANCEL", font=FONTS["btn"],
                  bg=C["surface2"], fg=C["muted"], relief="flat", bd=0,
                  padx=20, pady=6, cursor="hand2",
                  command=self.destroy).pack(side="left")

    def _save(self):
        code   = self._vars["subject_code"].get().strip().upper()
        name   = self._vars["subject_name"].get().strip()
        branch = self._vars["branch"].get().strip().upper()
        sem    = self._vars["semester"].get().strip()
        fac    = self._vars["faculty"].get().strip()
        room   = self._vars["room"].get().strip().upper()

        if not code or not name:
            messagebox.showwarning("Validation", "Subject Code and Subject Name are required.", parent=self)
            return

        self.result = (code, name, branch, sem, fac, room)
        self.destroy()


class ManageEnrollmentDialog(_BaseDialog):
    """Manage enrolled students for a subject."""

    def __init__(self, parent, subject_id: int):
        super().__init__(parent, "MANAGE ENROLLED STUDENTS", width=520, height=560)
        self.subject_id = subject_id
        self.subject = sub_mod.get_subject(subject_id)
        if not self.subject:
            self.destroy()
            return

        # Header
        tk.Label(self, text="MANAGE ENROLLMENT", font=FONTS["head"],
                 bg=C["bg"], fg=C["accent2"]).pack(pady=(16, 2))
        sub_info = f"{self.subject['subject_name']} ({self.subject['subject_code']})"
        tk.Label(self, text=sub_info, font=FONTS["label_b"],
                 bg=C["bg"], fg=C["text"]).pack(pady=(0, 2))
        tk.Label(self, text="Select students eligible to take attendance for this subject.",
                 font=FONTS["small"], bg=C["bg"], fg=C["muted"]).pack(pady=(0, 8))

        separator(self)

        # Toolbar: Select All / Clear All & Counter
        tool_row = tk.Frame(self, bg=C["surface"], padx=14, pady=6)
        tool_row.pack(fill="x", padx=16, pady=(6, 4))

        tk.Button(tool_row, text="SELECT ALL", font=FONTS["small_mono"],
                  bg=C["surface2"], fg=C["accent"], relief="flat", bd=0,
                  padx=8, pady=3, cursor="hand2", command=self._select_all).pack(side="left", padx=(0, 6))
        tk.Button(tool_row, text="CLEAR ALL", font=FONTS["small_mono"],
                  bg=C["surface2"], fg=C["muted"], relief="flat", bd=0,
                  padx=8, pady=3, cursor="hand2", command=self._clear_all).pack(side="left")

        self._count_lbl = tk.Label(tool_row, text="", font=FONTS["small_mono"],
                                   bg=C["surface"], fg=C["accent2"])
        self._count_lbl.pack(side="right")

        # Scrollable checklist
        list_container = tk.Frame(self, bg=C["bg"])
        list_container.pack(fill="both", expand=True, padx=16, pady=4)

        canvas = tk.Canvas(list_container, bg=C["surface"], highlightthickness=1,
                           highlightbackground=C["border"])
        sb = ttk.Scrollbar(list_container, orient="vertical", command=canvas.yview)
        inner = tk.Frame(canvas, bg=C["surface"])

        win = canvas.create_window((0, 0), window=inner, anchor="nw")
        canvas.configure(yscrollcommand=sb.set)

        inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>", lambda e: canvas.itemconfigure(win, width=e.width))

        canvas.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        bind_canvas_mousewheel(canvas, self)

        all_students = db.get_all_students()
        enrolled_ids = set(db.get_enrolled_student_ids(subject_id))

        self._checks = {}
        if not all_students:
            empty_lbl = tk.Label(
                inner,
                text="No students registered yet.\nAdd students in the STUDENTS tab first.",
                font=FONTS["small"], bg=C["surface"], fg=C["muted"], pady=30
            )
            empty_lbl.pack(fill="x")
        else:
            for s in all_students:
                sid = s["student_id"]
                var = tk.BooleanVar(value=(sid in enrolled_ids))
                var.trace_add("write", lambda *a: self._update_count())
                self._checks[sid] = var

                row = tk.Frame(inner, bg=C["surface"], pady=4, padx=8)
                row.pack(fill="x", pady=1)

                cb = tk.Checkbutton(row, text=f"{sid}  —  {s['name']}",
                                    variable=var, font=FONTS["mono_s"],
                                    bg=C["surface"], fg=C["text"],
                                    selectcolor=C["surface2"], activebackground=C["surface"],
                                    activeforeground=C["accent"])
                cb.pack(side="left")

                meta = f"{s.get('branch','')} Sem {s.get('semester','')}"
                tk.Label(row, text=meta, font=FONTS["small"],
                         bg=C["surface"], fg=C["dimmed"]).pack(side="right", padx=6)

        inner.update_idletasks()
        canvas.configure(scrollregion=canvas.bbox("all"))

        self._update_count()

        separator(self)

        # Bottom buttons
        btn_row = tk.Frame(self, bg=C["bg"])
        btn_row.pack(pady=12)

        tk.Button(btn_row, text="SAVE ENROLLMENT", font=FONTS["btn"],
                  bg=C["accent"], fg=C["bg"], relief="flat", bd=0,
                  padx=18, pady=6, cursor="hand2",
                  command=self._save).pack(side="left", padx=8)
        tk.Button(btn_row, text="CANCEL", font=FONTS["btn"],
                  bg=C["surface2"], fg=C["muted"], relief="flat", bd=0,
                  padx=16, pady=6, cursor="hand2",
                  command=self.destroy).pack(side="left")

    def _select_all(self):
        for v in self._checks.values():
            v.set(True)

    def _clear_all(self):
        for v in self._checks.values():
            v.set(False)

    def _update_count(self):
        selected = sum(1 for v in self._checks.values() if v.get())
        total = len(self._checks)
        if hasattr(self, "_count_lbl"):
            self._count_lbl.configure(text=f"ENROLLED: {selected} / {total}")

    def _save(self):
        selected_ids = [sid for sid, v in self._checks.items() if v.get()]
        ok, msg = sub_mod.set_enrolled_students(self.subject_id, selected_ids)
        if ok:
            messagebox.showinfo("Enrollment Updated", msg, parent=self)
            self.destroy()
        else:
            messagebox.showerror("Error", msg, parent=self)


class SessionSummaryDialog(_BaseDialog):
    """Post-session completion report dialog."""

    def __init__(self, parent, summary: dict):
        super().__init__(parent, "SESSION COMPLETED", width=460, height=480)

        tk.Label(self, text="SESSION COMPLETED", font=FONTS["head"],
                 bg=C["bg"], fg=C["accent"]).pack(pady=(18, 4))
        tk.Label(self, text="● ATTENDANCE RECORDED AND FINALIZED",
                 font=FONTS["sys_badge"], bg=C["bg"], fg=C["muted"]).pack(pady=(0, 10))

        separator(self)

        card = tk.Frame(self, bg=C["surface"], highlightthickness=1, highlightbackground=C["border"])
        card.pack(fill="x", padx=24, pady=12)

        # Subject info
        tk.Label(card, text=summary.get("subject_name", "").upper(),
                 font=FONTS["head"], bg=C["surface"], fg=C["text"]).pack(pady=(12, 2), padx=16, anchor="w")
        tk.Label(card, text=f"CODE: {summary.get('subject_code', '')}   ·   DATE: {summary.get('date', '')}",
                 font=FONTS["id_tag"], bg=C["surface"], fg=C["accent2"]).pack(pady=(0, 6), padx=16, anchor="w")

        meta = f"Faculty: {summary.get('faculty', '—')}   ·   Room: {summary.get('room', '—')}\nDuration: {summary.get('start_time', '')[:5]} - {summary.get('end_time', '')[:5]}"
        tk.Label(card, text=meta, font=FONTS["small"],
                 bg=C["surface"], fg=C["muted"], justify="left").pack(pady=(0, 10), padx=16, anchor="w")

        separator(card, pady=0)

        # Stats grid
        grid = tk.Frame(card, bg=C["surface"], pady=12)
        grid.pack(fill="x", padx=16)

        stats = [
            ("PRESENT", str(summary.get("present_count", 0)), C["accent"]),
            ("ABSENT",  str(summary.get("absent_count", 0)),  C["danger"]),
            ("TOTAL",   str(summary.get("total_enrolled", 0)), C["text"]),
            ("RATE",    f"{summary.get('percent', 0.0):.1f}%", C["accent2"]),
        ]
        for label, val, color in stats:
            box = tk.Frame(grid, bg=C["surface2"], padx=10, pady=8, highlightthickness=1, highlightbackground=C["border"])
            box.pack(side="left", fill="both", expand=True, padx=3)
            tk.Label(box, text=val, font=FONTS["stat_val"], bg=C["surface2"], fg=color).pack()
            tk.Label(box, text=label, font=FONTS["stat_lbl"], bg=C["surface2"], fg=C["muted"]).pack()

        # Method breakdown
        breakdown = tk.Frame(card, bg=C["surface"], pady=6)
        breakdown.pack(fill="x", padx=16, pady=(0, 10))
        b_txt = f"Method Breakdown:  Face: {summary.get('face_count', 0)}   ·   ID Card: {summary.get('id_card_count', 0)}"
        tk.Label(breakdown, text=b_txt, font=FONTS["small_mono"],
                 bg=C["surface"], fg=C["text_sec"]).pack(anchor="w")

        separator(self)

        tk.Button(self, text="CLOSE", font=FONTS["btn"],
                  bg=C["surface2"], fg=C["text"], relief="flat", bd=0,
                  padx=24, pady=6, cursor="hand2",
                  command=self.destroy).pack(pady=12)


class StudentProfileDialog(_BaseDialog):
    """Subject-wise attendance profile for a student."""

    def __init__(self, parent, profile: dict):
        super().__init__(parent, f"PROFILE — {profile['student']['name']}", width=560, height=520)

        stu = profile["student"]
        tk.Label(self, text="STUDENT ATTENDANCE PROFILE", font=FONTS["head"],
                 bg=C["bg"], fg=C["accent"]).pack(pady=(16, 2))

        # Student banner
        banner = tk.Frame(self, bg=C["surface"], padx=16, pady=10,
                          highlightthickness=1, highlightbackground=C["border"])
        banner.pack(fill="x", padx=20, pady=6)

        top_b = tk.Frame(banner, bg=C["surface"])
        top_b.pack(fill="x")
        tk.Label(top_b, text=stu["name"].upper(), font=FONTS["name"],
                 bg=C["surface"], fg=C["text"]).pack(side="left")
        tk.Label(top_b, text=stu["student_id"], font=FONTS["id_tag"],
                 bg=C["surface2"], fg=C["accent2"], padx=8, pady=2).pack(side="right")

        meta = f"{stu.get('branch', '—')} • Semester {stu.get('semester', '—')}"
        tk.Label(banner, text=meta, font=FONTS["small"],
                 bg=C["surface"], fg=C["muted"]).pack(anchor="w", pady=(2, 0))

        separator(self)

        # Subject breakdown table
        sub_list_container = tk.Frame(self, bg=C["bg"])
        sub_list_container.pack(fill="both", expand=True, padx=20, pady=6)

        tk.Label(sub_list_container, text="SUBJECT ATTENDANCE SUMMARY", font=FONTS["subtitle"],
                 bg=C["bg"], fg=C["muted"]).pack(anchor="w", pady=(0, 4))

        canvas = tk.Canvas(sub_list_container, bg=C["surface"], highlightthickness=1,
                           highlightbackground=C["border"])
        sb = ttk.Scrollbar(sub_list_container, orient="vertical", command=canvas.yview)
        inner = tk.Frame(canvas, bg=C["surface"])

        win = canvas.create_window((0, 0), window=inner, anchor="nw")
        canvas.configure(yscrollcommand=sb.set)

        inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>", lambda e: canvas.itemconfigure(win, width=e.width))

        canvas.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        bind_canvas_mousewheel(canvas, self)

        subjects_data = profile.get("subjects", [])
        if not subjects_data:
            empty = tk.Label(inner, text="Student is not enrolled in any subjects.",
                             font=FONTS["small"], bg=C["surface"], fg=C["muted"], pady=20)
            empty.pack(fill="x")
        else:
            for s in subjects_data:
                row = tk.Frame(inner, bg=C["surface"], pady=6, padx=12)
                row.pack(fill="x", pady=1)

                left = tk.Frame(row, bg=C["surface"])
                left.pack(side="left", fill="x", expand=True)
                tk.Label(left, text=s["subject_name"], font=FONTS["label_b"],
                         bg=C["surface"], fg=C["text"], anchor="w").pack(anchor="w")
                tk.Label(left, text=f"{s['subject_code']}   ·   Faculty: {s.get('faculty','—')}",
                         font=FONTS["small_mono"], bg=C["surface"], fg=C["dimmed"], anchor="w").pack(anchor="w")

                right = tk.Frame(row, bg=C["surface"])
                right.pack(side="right")
                stat_txt = f"{s['attended']} / {s['total_sessions']} Sessions"
                tk.Label(right, text=stat_txt, font=FONTS["small_mono"],
                         bg=C["surface"], fg=C["text_sec"], anchor="e").pack(anchor="e")

                pct = s["percent"]
                p_color = C["accent"] if pct >= 75 else (C["warn"] if pct >= 60 else C["danger"])
                tk.Label(right, text=f"{pct:.1f}%", font=FONTS["label_b"],
                         bg=C["surface"], fg=p_color, anchor="e").pack(anchor="e")

                separator(inner, pady=0)

        # Overall footer
        tot_att = profile.get("total_attended", 0)
        tot_ses = profile.get("total_sessions", 0)
        overall_pct = profile.get("overall_percent", 0.0)

        ov_bar = tk.Frame(self, bg=C["surface2"], padx=16, pady=8, highlightthickness=1, highlightbackground=C["border"])
        ov_bar.pack(fill="x", padx=20, pady=(4, 8))
        tk.Label(ov_bar, text="OVERALL ATTENDANCE", font=FONTS["subtitle"],
                 bg=C["surface2"], fg=C["muted"]).pack(side="left")

        ov_stat = f"{tot_att} / {tot_ses} Sessions   ({overall_pct:.1f}%)"
        ov_color = C["accent"] if overall_pct >= 75 else (C["warn"] if overall_pct >= 60 else C["danger"])
        tk.Label(ov_bar, text=ov_stat, font=FONTS["head"],
                 bg=C["surface2"], fg=ov_color).pack(side="right")

        tk.Button(self, text="CLOSE", font=FONTS["btn"],
                  bg=C["surface2"], fg=C["text"], relief="flat", bd=0,
                  padx=20, pady=6, cursor="hand2",
                  command=self.destroy).pack(pady=(0, 10))


class DemoDialog(_BaseDialog):
    """Demo mode: simulate face or ID card detection against active class session."""

    def __init__(self, parent, camera: CameraManager, on_event):
        super().__init__(parent, "DEMO MODE", width=480, height=530)
        self._on_event = on_event

        tk.Label(self, text="DEMO MODE", font=FONTS["head"],
                 bg=C["bg"], fg=C["accent2"]).pack(pady=(16, 2))
        tk.Label(self,
                 text="Simulate attendance without physical camera.\nAll results use real database records.",
                 font=FONTS["small"], bg=C["bg"], fg=C["muted"],
                 justify="center").pack()

        separator(self)

        # Active Session Status
        active = sub_mod.get_active_session()
        sess_box = tk.Frame(self, bg=C["surface"], padx=14, pady=8,
                            highlightthickness=1, highlightbackground=C["border"])
        sess_box.pack(fill="x", padx=28, pady=6)

        if active:
            tk.Label(sess_box, text="● CURRENT ACTIVE CLASS", font=FONTS["subtitle"],
                     bg=C["surface"], fg=C["accent"]).pack(anchor="w")
            tk.Label(sess_box, text=f"{active['subject_name']} ({active['subject_code']})",
                     font=FONTS["label_b"], bg=C["surface"], fg=C["text"]).pack(anchor="w")
            tk.Label(sess_box, text=f"Faculty: {active.get('faculty','—')}  ·  Room: {active.get('room','—')}",
                     font=FONTS["small"], bg=C["surface"], fg=C["muted"]).pack(anchor="w")
        else:
            tk.Label(sess_box, text="⚠ NO ACTIVE CLASS SESSION", font=FONTS["subtitle"],
                     bg=C["surface"], fg=C["warn"]).pack(anchor="w")
            tk.Label(sess_box, text="Attendance requires an active session.\nGo to SUBJECTS tab to start one.",
                     font=FONTS["small"], bg=C["surface"], fg=C["danger"], justify="left").pack(anchor="w")

        # Load students
        all_students = db.get_all_students()
        if not all_students:
            tk.Label(self, text="No students registered.\nAdd students first.",
                     font=FONTS["mono"], bg=C["bg"], fg=C["danger"]).pack(pady=20)
            tk.Button(self, text="CLOSE", font=FONTS["btn"],
                      bg=C["surface2"], fg=C["muted"], relief="flat", bd=0,
                      padx=16, pady=6, cursor="hand2",
                      command=self.destroy).pack()
            return

        # Student picker
        pick_row = tk.Frame(self, bg=C["bg"])
        pick_row.pack(fill="x", padx=28, pady=8)
        tk.Label(pick_row, text="SELECT STUDENT:", font=FONTS["label"],
                 bg=C["bg"], fg=C["muted"]).pack(side="left")

        student_names = [f"{s['student_id']}  {s['name']}" for s in all_students]
        self._student_var = tk.StringVar(value=student_names[0])
        self._student_map = {f"{s['student_id']}  {s['name']}": s for s in all_students}

        opt = ttk.OptionMenu(pick_row, self._student_var, student_names[0], *student_names)
        opt.pack(side="left", padx=10, fill="x", expand=True)

        separator(self)

        btn_frame = tk.Frame(self, bg=C["bg"])
        btn_frame.pack(pady=8)

        tk.Button(btn_frame, text="SIMULATE FACE",
                  font=FONTS["btn"], bg=C["accent"], fg=C["bg"],
                  relief="flat", bd=0, padx=16, pady=7, cursor="hand2",
                  command=lambda: self._simulate("FACE")).pack(side="left", padx=8)

        tk.Button(btn_frame, text="SIMULATE ID CARD",
                  font=FONTS["btn"], bg=C["accent2"], fg=C["bg"],
                  relief="flat", bd=0, padx=16, pady=7, cursor="hand2",
                  command=lambda: self._simulate("BARCODE")).pack(side="left", padx=8)

        btn_unknown = tk.Frame(self, bg=C["bg"])
        btn_unknown.pack(pady=(0, 6))

        tk.Button(btn_unknown, text="SIMULATE UNKNOWN FACE",
                  font=FONTS["btn"], bg=C["surface2"], fg=C["danger"],
                  relief="flat", bd=0, padx=14, pady=5, cursor="hand2",
                  command=self._simulate_unknown_face).pack()

        separator(self)

        tk.Label(self, text="⚠  DEMO MODE  —  Results are real database records.",
                 font=FONTS["small"], bg=C["bg"], fg=C["warn"],
                 justify="center").pack(pady=4)

        tk.Button(self, text="CLOSE", font=FONTS["btn"],
                  bg=C["surface2"], fg=C["muted"], relief="flat", bd=0,
                  padx=16, pady=6, cursor="hand2",
                  command=self.destroy).pack(pady=4)

    def _simulate(self, kind: str):
        selected = self._student_var.get()
        student = self._student_map.get(selected)
        if not student:
            return
        if kind == "FACE":
            self._on_event("FACE", student["student_id"])
        else:
            self._on_event("BARCODE", student.get("barcode_value") or student["student_id"])
        self.after(500, self.destroy)

    def _simulate_unknown_face(self):
        self._on_event("UNKNOWN_FACE", "")
        self.after(500, self.destroy)


class IdCardDebugDialog(_BaseDialog):
    """Developer diagnostics dialog for ID card detection & barcode/QR/OCR scanning."""

    def __init__(self, parent, camera: CameraManager):
        super().__init__(parent, "ID CARD DEBUG", width=520, height=580)
        self._camera = camera

        tk.Label(self, text="ID CARD DEBUG", font=FONTS["head"],
                 bg=C["bg"], fg=C["warn"]).pack(pady=(16, 2))
        tk.Label(self,
                 text="Live diagnostics for camera feed, barcode, QR code,\nand OCR fallback mechanisms.",
                 font=FONTS["small"], bg=C["bg"], fg=C["muted"],
                 justify="center").pack()

        separator(self)

        # Hardware & Engine Status Cards
        info_frame = tk.Frame(self, bg=C["surface"], padx=16, pady=12,
                              highlightthickness=1, highlightbackground=C["border"])
        info_frame.pack(fill="x", padx=24, pady=6)

        cam_online = getattr(self._camera, "available", False)
        dbg = barcode_scanner.get_debug_info()

        self._labels = {}
        rows = [
            ("Camera:", "ONLINE" if cam_online else "OFFLINE", C["accent"] if cam_online else C["danger"]),
            ("Barcode Detector:", dbg.get("barcode_detector", "ACTIVE"), C["accent"] if dbg.get("barcode_detector") == "ACTIVE" else C["danger"]),
            ("QR Detector:", dbg.get("qr_detector", "ACTIVE"), C["accent"]),
            ("OCR Fallback:", dbg.get("ocr_fallback", "READY"), C["accent"] if dbg.get("ocr_fallback") == "READY" else C["muted"]),
        ]
        for label, val, col in rows:
            r = tk.Frame(info_frame, bg=C["surface"])
            r.pack(fill="x", pady=2)
            tk.Label(r, text=label, font=FONTS["label_b"], bg=C["surface"], fg=C["text"]).pack(side="left")
            lbl = tk.Label(r, text=val, font=FONTS["label_b"], bg=C["surface"], fg=col)
            lbl.pack(side="right")
            self._labels[label] = lbl

        separator(self)

        # Last Scan Diagnostic Card
        scan_box = tk.Frame(self, bg=C["surface2"], padx=16, pady=12,
                            highlightthickness=1, highlightbackground=C["border"])
        scan_box.pack(fill="x", padx=24, pady=6)

        tk.Label(scan_box, text="LAST SCAN DIAGNOSTICS", font=FONTS["subtitle"],
                 bg=C["surface2"], fg=C["muted"]).pack(anchor="w", pady=(0, 6))

        self._scan_rows = {}
        scan_fields = [
            ("Last Scan:", dbg.get("last_scan", "NONE")),
            ("Decode:", dbg.get("decode", "IDLE")),
            ("Method:", dbg.get("method", "NONE")),
            ("Reason:", dbg.get("reason", "Ready")),
        ]
        for label, val in scan_fields:
            r = tk.Frame(scan_box, bg=C["surface2"])
            r.pack(fill="x", pady=2)
            tk.Label(r, text=label, font=FONTS["label"], bg=C["surface2"], fg=C["muted"]).pack(side="left")
            lbl = tk.Label(r, text=val, font=FONTS["label_b"], bg=C["surface2"], fg=C["text"])
            lbl.pack(side="right")
            self._scan_rows[label] = lbl

        # Database Check row
        db_r = tk.Frame(scan_box, bg=C["surface2"])
        db_r.pack(fill="x", pady=2)
        tk.Label(db_r, text="Database:", font=FONTS["label"], bg=C["surface2"], fg=C["muted"]).pack(side="left")
        self._db_status_lbl = tk.Label(db_r, text="CHECKING...", font=FONTS["label_b"], bg=C["surface2"], fg=C["muted"])
        self._db_status_lbl.pack(side="right")

        self._update_db_status(dbg.get("last_scan", "NONE"))

        separator(self)

        # Diagnostic Actions
        btn_frame = tk.Frame(self, bg=C["bg"])
        btn_frame.pack(pady=8)

        tk.Button(btn_frame, text="TEST CAMERA FRAME NOW",
                  font=FONTS["btn"], bg=C["accent"], fg=C["bg"],
                  relief="flat", bd=0, padx=14, pady=7, cursor="hand2",
                  command=self._test_cam_frame).pack(side="left", padx=6)

        tk.Button(btn_frame, text="TEST CARD FILE",
                  font=FONTS["btn"], bg=C["accent2"], fg=C["bg"],
                  relief="flat", bd=0, padx=14, pady=7, cursor="hand2",
                  command=self._test_card_file).pack(side="left", padx=6)

        tk.Button(self, text="CLOSE", font=FONTS["btn"],
                  bg=C["surface2"], fg=C["muted"], relief="flat", bd=0,
                  padx=18, pady=6, cursor="hand2",
                  command=self.destroy).pack(pady=(6, 8))

    def _update_db_status(self, student_id: str):
        if not student_id or student_id == "NONE":
            self._db_status_lbl.configure(text="NO DATA", fg=C["muted"])
            return
        stu = db.get_student_by_id(student_id) or db.get_student_by_barcode(student_id)
        if stu:
            self._db_status_lbl.configure(text=f"STUDENT FOUND ({stu['name']})", fg=C["accent"])
        else:
            self._db_status_lbl.configure(text="STUDENT NOT FOUND", fg=C["danger"])

    def _refresh(self):
        cam_online = getattr(self._camera, "available", False)
        dbg = barcode_scanner.get_debug_info()
        if "Camera:" in self._labels:
            self._labels["Camera:"].configure(
                text="ONLINE" if cam_online else "OFFLINE",
                fg=C["accent"] if cam_online else C["danger"]
            )
        for k in ("Last Scan:", "Decode:", "Method:", "Reason:"):
            field_key = k.rstrip(":").lower().replace(" ", "_")
            val = dbg.get(field_key, "NONE")
            if k in self._scan_rows:
                col = C["accent"] if dbg.get("decode") == "SUCCESS" and k == "Decode:" else (
                    C["danger"] if dbg.get("decode") == "FAILED" and k == "Decode:" else C["text"]
                )
                self._scan_rows[k].configure(text=str(val), fg=col)
        self._update_db_status(dbg.get("last_scan", "NONE"))

    def _test_cam_frame(self):
        frame = self._camera.capture_still()
        if frame is None:
            messagebox.showwarning("Diagnostic", "No frame available from camera.")
            return
        barcode_scanner.scan_frame(frame, allow_ocr=True)
        self._refresh()

    def _test_card_file(self):
        from pathlib import Path
        path = Path("generated_cards/IU2441230311_card.png")
        if not path.exists():
            messagebox.showwarning("Diagnostic", f"Card file not found: {path}")
            return
        img = cv2.imread(str(path))
        barcode_scanner.scan_frame(img, allow_ocr=True)
        self._refresh()
