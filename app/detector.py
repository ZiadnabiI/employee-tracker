"""
Employee Presence Monitor — Premium Edition
=============================================
Built with CustomTkinter for a truly modern, professional look.
Design matches the InFrame web dashboard (dark slate theme).
"""

import customtkinter as ctk
import cv2
import time
import requests
import tkinter as tk
from tkinter import messagebox
from threading import Thread
from ultralytics import YOLO
import os
import uuid
import win32gui
import win32process
import psutil
from PIL import Image, ImageGrab, ImageFilter, ImageDraw, ImageFont, ImageTk
import io
import base64
import ctypes

# High DPI
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(1)
except:
    pass

# ── CustomTkinter global config ──
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

# =============================================================================
# CONFIGURATION
# =============================================================================

SERVER_URL = os.getenv("SERVER_URL", "https://inframe-dab3gthvbkgpe2dp.italynorth-01.azurewebsites.net")
CONFIDENCE_THRESHOLD = 0.6
AWAY_LIMIT = 10
PRESENT_LIMIT = 3
REGISTRY_PATH = r"SOFTWARE\EmployeeTracker"

# =============================================================================
# DESIGN TOKENS (matching web dashboard)
# =============================================================================

COLORS = {
    "bg_deep":    "#020617",  # slate-950
    "bg_main":    "#0f172a",  # slate-900
    "bg_card":    "#1e293b",  # slate-800
    "bg_input":   "#334155",  # slate-700
    "border":     "#334155",  # slate-700
    "text_white": "#f8fafc",  # slate-50
    "text":       "#e2e8f0",  # slate-200
    "text_muted": "#94a3b8",  # slate-400
    "text_dim":   "#64748b",  # slate-500
    "accent":     "#3b82f6",  # blue-500
    "accent_h":   "#2563eb",  # blue-600
    "green":      "#22c55e",
    "yellow":     "#eab308",
    "red":        "#ef4444",
}

LOGO_PATH = r"C:/Users/ziadn/.gemini/antigravity/brain/6c4d7325-991d-4d51-b241-7470af94e1b0/uploaded_media_1770146996132.jpg"

# =============================================================================
# REGISTRY HELPERS
# =============================================================================

def get_reg(key, default=None):
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, REGISTRY_PATH) as r:
            v, _ = winreg.QueryValueEx(r, key)
            return v
    except:
        return default

def set_reg(key, value):
    try:
        import winreg
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, REGISTRY_PATH) as r:
            winreg.SetValueEx(r, key, 0, winreg.REG_SZ, str(value))
    except:
        pass

def get_hw_id():
    hw = get_reg("hardware_id")
    if not hw:
        hw = f"HW-{uuid.uuid4().hex[:8].upper()}"
        set_reg("hardware_id", hw)
    return hw


# =============================================================================
# MAIN APPLICATION
# =============================================================================

class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("INFRAME | Employee Monitor")
        self.geometry("440x600")
        self.resizable(False, False)
        self.configure(fg_color=COLORS["bg_deep"])

        # Center on screen
        self.update_idletasks()
        x = (self.winfo_screenwidth() - 440) // 2
        y = (self.winfo_screenheight() - 600) // 2
        self.geometry(f"440x600+{x}+{y}")

        # ── State ──
        self.activation_key = None
        self.hardware_id = get_hw_id()
        self.is_running = True
        self.monitoring_active = False
        self.in_break_mode = False
        self.employee_name = "Employee"
        self.warning_snoozed_until = 0
        self.consecutive_away = 0
        self.consecutive_present = 0
        self._latest_frame = None

        self.present_seconds = 0
        self.away_seconds = 0
        self.break_seconds = 0
        self.current_status = "Offline"

        self.screenshot_frequency = 600
        self.dlp_enabled = False

        # ── Container ──
        self.container = ctk.CTkFrame(self, fg_color=COLORS["bg_deep"])
        self.container.pack(fill="both", expand=True)

        self._check_session()

    # ─────────────────────────────────────────────────────────────────────
    #  SESSION
    # ─────────────────────────────────────────────────────────────────────

    def _check_session(self):
        key = get_reg("activation_key")
        name = get_reg("employee_name")
        if key:
            self.activation_key = key
            if name:
                self.employee_name = name
            self._show_login(verifying=True)
            self._verify()
        else:
            self._show_login()

    def _verify(self):
        def work():
            try:
                r = requests.post(f"{SERVER_URL}/verify-checkin",
                                  json={"activation_key": self.activation_key}, timeout=5)
                if r.status_code == 200:
                    self.after(0, self._show_dashboard)
                else:
                    set_reg("activation_key", "")
                    self.activation_key = None
                    self.after(0, self._show_login)
            except:
                if self.activation_key:
                    self.after(0, self._show_dashboard)
        Thread(target=work, daemon=True).start()

    # ─────────────────────────────────────────────────────────────────────
    #  LOGIN SCREEN
    # ─────────────────────────────────────────────────────────────────────

    def _show_login(self, verifying=False):
        self._clear()

        # ── Logo banner ──
        banner = ctk.CTkFrame(self.container, fg_color=COLORS["bg_main"], height=120,
                              corner_radius=0)
        banner.pack(fill="x")
        banner.pack_propagate(False)

        try:
            if os.path.exists(LOGO_PATH):
                img = Image.open(LOGO_PATH)
                img.thumbnail((180, 70))
                self._logo_img = ctk.CTkImage(light_image=img, dark_image=img,
                                               size=img.size)
                ctk.CTkLabel(banner, image=self._logo_img, text="").place(
                    relx=0.5, rely=0.5, anchor="center")
            else:
                raise FileNotFoundError
        except:
            ctk.CTkLabel(banner, text="INFRAME",
                         font=ctk.CTkFont("Segoe UI", 28, "bold"),
                         text_color=COLORS["text_white"]).place(
                relx=0.5, rely=0.5, anchor="center")

        # ── Form ──
        form = ctk.CTkFrame(self.container, fg_color=COLORS["bg_deep"], corner_radius=0)
        form.pack(fill="both", expand=True, padx=36, pady=(28, 20))

        ctk.CTkLabel(form, text="Sign In",
                     font=ctk.CTkFont("Segoe UI", 24, "bold"),
                     text_color=COLORS["text_white"]).pack(anchor="w")
        ctk.CTkLabel(form, text="Enter your credentials to continue",
                     font=ctk.CTkFont("Segoe UI", 12),
                     text_color=COLORS["text_muted"]).pack(anchor="w", pady=(2, 24))

        # Email
        ctk.CTkLabel(form, text="EMAIL",
                     font=ctk.CTkFont("Segoe UI", 10, "bold"),
                     text_color=COLORS["text_dim"]).pack(anchor="w")
        self.entry_email = ctk.CTkEntry(
            form, height=44, corner_radius=8,
            fg_color=COLORS["bg_card"], border_color=COLORS["border"],
            text_color=COLORS["text"], placeholder_text="you@company.com",
            placeholder_text_color=COLORS["text_dim"],
            font=ctk.CTkFont("Segoe UI", 12))
        self.entry_email.pack(fill="x", pady=(4, 16))

        # Password
        ctk.CTkLabel(form, text="PASSWORD",
                     font=ctk.CTkFont("Segoe UI", 10, "bold"),
                     text_color=COLORS["text_dim"]).pack(anchor="w")
        self.entry_pass = ctk.CTkEntry(
            form, height=44, corner_radius=8, show="\u2022",
            fg_color=COLORS["bg_card"], border_color=COLORS["border"],
            text_color=COLORS["text"], placeholder_text="Enter password",
            placeholder_text_color=COLORS["text_dim"],
            font=ctk.CTkFont("Segoe UI", 12))
        self.entry_pass.pack(fill="x", pady=(4, 6))

        # Options row
        opts = ctk.CTkFrame(form, fg_color="transparent")
        opts.pack(fill="x", pady=(0, 20))

        self._show_pw_var = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(opts, text="Show password", variable=self._show_pw_var,
                        command=self._toggle_pw, font=ctk.CTkFont("Segoe UI", 11),
                        text_color=COLORS["text_muted"], fg_color=COLORS["accent"],
                        hover_color=COLORS["accent_h"], border_color=COLORS["border"],
                        checkbox_height=18, checkbox_width=18, corner_radius=4
                        ).pack(side="left")

        self._remember_var = ctk.BooleanVar(
            value=True if get_reg("remember_me") == "1" else False)
        ctk.CTkCheckBox(opts, text="Remember me", variable=self._remember_var,
                        font=ctk.CTkFont("Segoe UI", 11),
                        text_color=COLORS["text_muted"], fg_color=COLORS["accent"],
                        hover_color=COLORS["accent_h"], border_color=COLORS["border"],
                        checkbox_height=18, checkbox_width=18, corner_radius=4
                        ).pack(side="right")

        # Sign In button
        ctk.CTkButton(form, text="Sign In", height=46, corner_radius=10,
                      font=ctk.CTkFont("Segoe UI", 14, "bold"),
                      fg_color=COLORS["accent"], hover_color=COLORS["accent_h"],
                      command=self._do_login).pack(fill="x")

        # Status
        txt = "Verifying session..." if verifying else ""
        clr = COLORS["yellow"] if verifying else COLORS["red"]
        self.lbl_status_login = ctk.CTkLabel(form, text=txt,
                                              font=ctk.CTkFont("Segoe UI", 11),
                                              text_color=clr)
        self.lbl_status_login.pack(pady=(12, 0))

    def _toggle_pw(self):
        self.entry_pass.configure(show="" if self._show_pw_var.get() else "\u2022")

    def _do_login(self):
        email = self.entry_email.get().strip()
        pwd = self.entry_pass.get().strip()
        if not email or not pwd:
            self.lbl_status_login.configure(text="Enter email and password",
                                             text_color=COLORS["red"])
            return
        self.lbl_status_login.configure(text="Authenticating...",
                                         text_color=COLORS["yellow"])

        def work():
            try:
                r = requests.post(f"{SERVER_URL}/api/app-login",
                                  json={"email": email, "password": pwd}, timeout=10)
                if r.status_code == 200:
                    d = r.json()
                    self.activation_key = d["activation_key"]
                    self.employee_name = d["name"]
                    if self._remember_var.get():
                        set_reg("activation_key", self.activation_key)
                        set_reg("employee_name", self.employee_name)
                        set_reg("remember_me", "1")
                    else:
                        set_reg("activation_key", "")
                        set_reg("remember_me", "0")
                    self.after(0, self._show_dashboard)
                else:
                    msg = r.json().get("detail", "Login failed")
                    self.after(0, lambda: self.lbl_status_login.configure(
                        text=msg, text_color=COLORS["red"]))
            except:
                self.after(0, lambda: self.lbl_status_login.configure(
                    text="Connection failed", text_color=COLORS["red"]))
        Thread(target=work, daemon=True).start()

    # ─────────────────────────────────────────────────────────────────────
    #  DASHBOARD
    # ─────────────────────────────────────────────────────────────────────

    def _show_dashboard(self):
        self._clear()

        # ── Header ──
        header = ctk.CTkFrame(self.container, fg_color=COLORS["bg_main"],
                              height=60, corner_radius=0)
        header.pack(fill="x")
        header.pack_propagate(False)

        # Logo left
        try:
            if os.path.exists(LOGO_PATH):
                img = Image.open(LOGO_PATH)
                img.thumbnail((140, 50))
                self._dash_logo = ctk.CTkImage(light_image=img, dark_image=img,
                                                size=img.size)
                ctk.CTkLabel(header, image=self._dash_logo, text="").pack(
                    side="left", padx=18)
            else:
                raise FileNotFoundError
        except:
            ctk.CTkLabel(header, text="INFRAME",
                         font=ctk.CTkFont("Segoe UI", 16, "bold"),
                         text_color=COLORS["text_white"]).pack(side="left", padx=18)

        # Right side: gear | name column
        ctk.CTkButton(header, text="\u2699", width=34, height=34,
                      corner_radius=8, fg_color=COLORS["bg_card"],
                      hover_color=COLORS["bg_input"],
                      text_color=COLORS["text_muted"],
                      font=ctk.CTkFont(size=15),
                      command=self._profile_menu).pack(side="right", padx=(0, 14))

        info = ctk.CTkFrame(header, fg_color="transparent")
        info.pack(side="right", padx=(0, 10))
        ctk.CTkLabel(info, text=self.employee_name,
                     font=ctk.CTkFont("Segoe UI", 12, "bold"),
                     text_color=COLORS["text_white"]).pack(anchor="e")
        self.lbl_dash_status = ctk.CTkLabel(info, text="\u25cf Monitoring...",
                                             font=ctk.CTkFont("Segoe UI", 10),
                                             text_color=COLORS["text_muted"])
        self.lbl_dash_status.pack(anchor="e")

        # ── Content ──
        content = ctk.CTkFrame(self.container, fg_color=COLORS["bg_deep"],
                               corner_radius=0)
        content.pack(fill="both", expand=True, padx=18, pady=(14, 10))

        # ── Stats Card ──
        card = ctk.CTkFrame(content, fg_color=COLORS["bg_card"], corner_radius=14,
                            border_width=1, border_color=COLORS["border"])
        card.pack(fill="x", pady=(0, 14))

        ctk.CTkLabel(card, text="TODAY'S ACTIVITY",
                     font=ctk.CTkFont("Segoe UI", 10, "bold"),
                     text_color=COLORS["text_dim"]).pack(anchor="w", padx=20, pady=(16, 14))

        stats = ctk.CTkFrame(card, fg_color="transparent")
        stats.pack(fill="x", padx=20, pady=(0, 18))
        stats.columnconfigure((0, 1, 2), weight=1)

        self._stat_labels = {}
        for i, (label, color, key) in enumerate([
            ("Active", COLORS["green"], "present"),
            ("Away",   COLORS["red"],   "away"),
            ("Break",  COLORS["yellow"],"break_"),
        ]):
            f = ctk.CTkFrame(stats, fg_color="transparent")
            f.grid(row=0, column=i, sticky="nsew")
            ctk.CTkLabel(f, text=label, font=ctk.CTkFont("Segoe UI", 11),
                         text_color=COLORS["text_muted"]).pack()
            lbl = ctk.CTkLabel(f, text="0h 0m",
                               font=ctk.CTkFont("Consolas", 20, "bold"),
                               text_color=color)
            lbl.pack(pady=(4, 0))
            self._stat_labels[key] = lbl

        # ── Controls Card ──
        ctrl = ctk.CTkFrame(content, fg_color=COLORS["bg_card"], corner_radius=14,
                            border_width=1, border_color=COLORS["border"])
        ctrl.pack(fill="x", pady=(0, 14))

        ctk.CTkLabel(ctrl, text="CONTROLS",
                     font=ctk.CTkFont("Segoe UI", 10, "bold"),
                     text_color=COLORS["text_dim"]).pack(anchor="w", padx=20, pady=(16, 14))

        btns = ctk.CTkFrame(ctrl, fg_color="transparent")
        btns.pack(fill="x", padx=20, pady=(0, 18))

        self.btn_break = ctk.CTkButton(
            btns, text="\u2615  Take a Break", height=44, corner_radius=10,
            font=ctk.CTkFont("Segoe UI", 13, "bold"),
            fg_color=COLORS["yellow"], hover_color="#ca8a04",
            text_color=COLORS["bg_deep"],
            command=self._toggle_break)
        self.btn_break.pack(fill="x", pady=(0, 8))

        ctk.CTkButton(
            btns, text="\u26d4  End Shift", height=44, corner_radius=10,
            font=ctk.CTkFont("Segoe UI", 13, "bold"),
            fg_color=COLORS["red"], hover_color="#dc2626",
            text_color="white",
            command=self.on_close).pack(fill="x")

        # ── Footer ──
        ctk.CTkLabel(content, text=f"Device: {self.hardware_id}",
                     font=ctk.CTkFont("Segoe UI", 9),
                     text_color=COLORS["text_dim"]).pack(side="bottom", pady=(6, 0))

        self._start_monitoring()

    # ─────────────────────────────────────────────────────────────────────
    #  PROFILE MENU / LOGOUT / CHANGE PASSWORD
    # ─────────────────────────────────────────────────────────────────────

    def _profile_menu(self):
        menu = tk.Menu(self, tearoff=0, bg=COLORS["bg_card"], fg=COLORS["text"],
                       font=("Segoe UI", 10), activebackground=COLORS["accent"],
                       activeforeground="white", bd=0, relief="flat")
        menu.add_command(label="  \U0001F513  Change Password", command=self._change_pw_dialog)
        menu.add_separator()
        menu.add_command(label="  \U0001F6AA  Logout", command=self._logout)
        try:
            menu.tk_popup(self.winfo_x() + 360, self.winfo_y() + 80)
        finally:
            menu.grab_release()

    def _logout(self):
        self.is_running = False
        self.monitoring_active = False
        self.activation_key = None
        set_reg("activation_key", "")
        set_reg("remember_me", "0")
        self._close_popup("_warn_win")
        self._close_popup("_cam_err_win")
        self.is_running = True
        self._show_login()

    def _change_pw_dialog(self):
        dialog = ctk.CTkToplevel(self)
        dialog.title("Change Password")
        dialog.geometry("380x340")
        dialog.resizable(False, False)
        dialog.configure(fg_color=COLORS["bg_card"])
        dialog.attributes("-topmost", True)
        dialog.grab_set()

        # Center
        dialog.update_idletasks()
        x = (self.winfo_screenwidth() - 380) // 2
        y = (self.winfo_screenheight() - 340) // 2
        dialog.geometry(f"380x340+{x}+{y}")

        pad = ctk.CTkFrame(dialog, fg_color="transparent")
        pad.pack(fill="both", expand=True, padx=28, pady=24)

        ctk.CTkLabel(pad, text="Change Password",
                     font=ctk.CTkFont("Segoe UI", 18, "bold"),
                     text_color=COLORS["text_white"]).pack(anchor="w")
        ctk.CTkLabel(pad, text="Verify your identity to change password",
                     font=ctk.CTkFont("Segoe UI", 11),
                     text_color=COLORS["text_muted"]).pack(anchor="w", pady=(2, 16))

        # Old password
        ctk.CTkLabel(pad, text="CURRENT PASSWORD",
                     font=ctk.CTkFont("Segoe UI", 9, "bold"),
                     text_color=COLORS["text_dim"]).pack(anchor="w")
        entry_old = ctk.CTkEntry(pad, height=40, corner_radius=8, show="\u2022",
                             fg_color=COLORS["bg_input"],
                             border_color=COLORS["border"],
                             text_color=COLORS["text"],
                             font=ctk.CTkFont("Segoe UI", 12))
        entry_old.pack(fill="x", pady=(4, 12))

        # New password
        ctk.CTkLabel(pad, text="NEW PASSWORD",
                     font=ctk.CTkFont("Segoe UI", 9, "bold"),
                     text_color=COLORS["text_dim"]).pack(anchor="w")
        entry_new = ctk.CTkEntry(pad, height=40, corner_radius=8, show="\u2022",
                             fg_color=COLORS["bg_input"],
                             border_color=COLORS["border"],
                             text_color=COLORS["text"],
                             placeholder_text="Min 8 characters",
                             font=ctk.CTkFont("Segoe UI", 12))
        entry_new.pack(fill="x", pady=(4, 10))

        result = ctk.CTkLabel(pad, text="", font=ctk.CTkFont("Segoe UI", 11))
        result.pack(pady=(0, 8))

        def do_it():
            old = entry_old.get().strip()
            new = entry_new.get().strip()
            if not old:
                result.configure(text="Enter current password", text_color=COLORS["red"])
                return
            if len(new) < 8:
                result.configure(text="New password: min 8 characters", text_color=COLORS["red"])
                return
            try:
                r = requests.post(f"{SERVER_URL}/api/app-change-password",
                                  json={"activation_key": self.activation_key,
                                        "old_password": old,
                                        "new_password": new}, timeout=10)
                if r.status_code == 200:
                    result.configure(text="\u2705 Password changed!", text_color=COLORS["green"])
                    dialog.after(1500, dialog.destroy)
                else:
                    result.configure(text=r.json().get("detail", "Error"),
                                     text_color=COLORS["red"])
            except:
                result.configure(text="Connection error", text_color=COLORS["red"])

        row = ctk.CTkFrame(pad, fg_color="transparent")
        row.pack(fill="x")
        ctk.CTkButton(row, text="Update", height=40, corner_radius=8,
                      fg_color=COLORS["accent"], hover_color=COLORS["accent_h"],
                      font=ctk.CTkFont("Segoe UI", 12, "bold"),
                      command=do_it).pack(side="left", expand=True, fill="x", padx=(0, 6))
        ctk.CTkButton(row, text="Cancel", height=40, corner_radius=8,
                      fg_color=COLORS["bg_input"], hover_color=COLORS["border"],
                      font=ctk.CTkFont("Segoe UI", 12, "bold"),
                      command=dialog.destroy).pack(side="right", expand=True,
                                                    fill="x", padx=(6, 0))

    # ─────────────────────────────────────────────────────────────────────
    #  FUNCTIONALITY
    # ─────────────────────────────────────────────────────────────────────

    def _fmt(self, s):
        return f"{int(s//3600)}h {int((s%3600)//60)}m"

    def _set_status(self, text, color):
        if hasattr(self, "lbl_dash_status") and self.lbl_dash_status.winfo_exists():
            self.lbl_dash_status.configure(text=f"\u25cf {text}", text_color=color)

    def _start_monitoring(self):
        if self.monitoring_active:
            return
        self.monitoring_active = True
        for fn in [self._loop_cam, self._loop_tick, self._loop_hb,
                   self._loop_apps, self._loop_ss]:
            Thread(target=fn, daemon=True).start()
        self.after(500, lambda: self._set_status("Monitoring...", COLORS["text_muted"]))
        self.after(1000, self._fetch_time)

    def _fetch_time(self):
        try:
            r = requests.get(f"{SERVER_URL}/api/employee-time/{self.activation_key}",
                             timeout=5)
            if r.status_code == 200:
                d = r.json()
                self.present_seconds = d.get("present_seconds", 0)
                self.away_seconds = d.get("away_seconds", 0)
                self.break_seconds = d.get("break_seconds", 0)
        except:
            pass

    def _toggle_break(self):
        self.in_break_mode = not self.in_break_mode
        if self.in_break_mode:
            if hasattr(self, "btn_break") and self.btn_break.winfo_exists():
                self.btn_break.configure(text="\u25b6  Resume Work",
                                          fg_color=COLORS["accent"],
                                          hover_color=COLORS["accent_h"],
                                          text_color="white")
            self._set_status("On Break", COLORS["yellow"])
            self._log("BREAK_START")
        else:
            if hasattr(self, "btn_break") and self.btn_break.winfo_exists():
                self.btn_break.configure(text="\u2615  Take a Break",
                                          fg_color=COLORS["yellow"],
                                          hover_color="#ca8a04",
                                          text_color=COLORS["bg_deep"])
            self._set_status("Active", COLORS["green"])
            self._log("BREAK_END")

    # ── Loops ──

    def _loop_tick(self):
        while self.is_running:
            if self.monitoring_active:
                if self.in_break_mode:
                    self.break_seconds += 1
                elif self.current_status == "Present":
                    self.present_seconds += 1
                elif self.current_status == "Away":
                    self.away_seconds += 1
                self.after(0, self._update_timers)
            time.sleep(1)

    def _update_timers(self):
        if not hasattr(self, "_stat_labels"):
            return
        try:
            self._stat_labels["present"].configure(text=self._fmt(self.present_seconds))
            self._stat_labels["away"].configure(text=self._fmt(self.away_seconds))
            self._stat_labels["break_"].configure(text=self._fmt(self.break_seconds))
        except:
            pass

    def _loop_cam(self):
        model = YOLO("yolo11n.pt")
        cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
        cam_err = 0
        self.consecutive_away = 0
        self.consecutive_present = 0

        while self.is_running:
            try:
                if self.in_break_mode:
                    time.sleep(1)
                    continue
                ret, frame = cap.read()
                person = False
                if ret:
                    cam_err = 0
                    self._latest_frame = frame.copy()
                    for r in model(frame, verbose=False):
                        for box in r.boxes:
                            if int(box.cls) == 0 and float(box.conf) > CONFIDENCE_THRESHOLD:
                                person = True
                                break
                        if person:
                            break
                else:
                    cam_err += 1
                    if cap:
                        cap.release()
                    cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
                    if cam_err >= 5:
                        self.after(0, self._show_cam_err)
                        time.sleep(5)
                        continue

                if person:
                    self.consecutive_present += 1
                    self.consecutive_away = 0
                    if self.consecutive_present >= PRESENT_LIMIT and self.current_status != "Present":
                        self.current_status = "Present"
                        self._log("Present")
                        self.after(0, lambda: self._set_status("Active", COLORS["green"]))
                        self.after(0, self._hide_warn)
                else:
                    self.consecutive_present = 0
                    self.consecutive_away += 1
                    if self.consecutive_away >= AWAY_LIMIT:
                        if self.current_status != "Away":
                            self.current_status = "Away"
                            self._log("Away")
                            self.after(0, lambda: self._set_status("Away", COLORS["red"]))
                        if time.time() > self.warning_snoozed_until:
                            self.after(0, self._show_warn)
            except:
                pass
            time.sleep(1)
        if cap:
            cap.release()

    def _loop_hb(self):
        while self.is_running:
            try:
                r = requests.post(f"{SERVER_URL}/heartbeat",
                                  json={"activation_key": self.activation_key}, timeout=5)
                if r.status_code == 200:
                    d = r.json()
                    if d.get("command") == "screenshot":
                        self._take_ss(True)
                    if "settings" in d:
                        self.screenshot_frequency = d["settings"].get("screenshot_frequency", 600)
                        self.dlp_enabled = bool(d["settings"].get("dlp_enabled", 0))
            except:
                pass
            time.sleep(10)

    def _loop_apps(self):
        last_app = None
        start_t = time.time()
        while self.is_running:
            try:
                hwnd = win32gui.GetForegroundWindow()
                title = win32gui.GetWindowText(hwnd)
                _, pid = win32process.GetWindowThreadProcessId(hwnd)
                try:
                    app = psutil.Process(pid).name()
                except:
                    app = "unknown"
                if app != last_app and last_app:
                    dur = int(time.time() - start_t)
                    if dur > 2:
                        requests.post(f"{SERVER_URL}/api/app-log", json={
                            "activation_key": self.activation_key,
                            "app_name": last_app, "window_title": title[:200],
                            "duration_seconds": dur})
                    start_t = time.time()
                last_app = app
            except:
                pass
            time.sleep(5)

    def _loop_ss(self):
        while self.is_running:
            if not self.in_break_mode:
                self._take_ss()
            t = time.time() + self.screenshot_frequency
            while time.time() < t:
                if not self.is_running:
                    break
                time.sleep(5)

    def _take_ss(self, manual=False):
        try:
            screen = ImageGrab.grab()
            if self.dlp_enabled:
                self._dlp(screen)
            buf = io.BytesIO()
            screen.save(buf, format="JPEG", quality=60)
            b64 = base64.b64encode(buf.getvalue()).decode()
            requests.post(f"{SERVER_URL}/api/screenshot", json={
                "activation_key": self.activation_key,
                "screenshot_data": b64, "manual_request": manual})
            print("Screenshot sent")
        except Exception as e:
            print(e)

    def _dlp(self, img):
        kw = ["password","bank","credit","inbox","login","sign in","facebook",
              "twitter","instagram","gmail","stripe","paypal","confidential",
              "finance","accounting","hr","payroll","messages","whatsapp"]
        try:
            hdc = ctypes.windll.user32.GetDC(0)
            dpi = ctypes.windll.gdi32.GetDeviceCaps(hdc, 88)
            ctypes.windll.user32.ReleaseDC(0, hdc)
            sf = dpi / 96.0
        except:
            sf = 1.0

        def handler(hwnd, _):
            if win32gui.IsWindowVisible(hwnd):
                t = win32gui.GetWindowText(hwnd).lower()
                if any(k in t for k in kw):
                    try:
                        rect = win32gui.GetWindowRect(hwnd)
                        x1, y1 = max(0, int(rect[0]*sf)), max(0, int(rect[1]*sf))
                        x2, y2 = min(img.size[0], int(rect[2]*sf)), min(img.size[1], int(rect[3]*sf))
                        if x2 > x1 and y2 > y1:
                            box = (x1, y1, x2, y2)
                            region = img.crop(box).filter(ImageFilter.GaussianBlur(30))
                            overlay = Image.new("RGBA", region.size, (0,0,0,128))
                            blurred = Image.alpha_composite(region.convert("RGBA"), overlay).convert("RGB")
                            img.paste(blurred, box)
                            draw = ImageDraw.Draw(img)
                            txt = "\U0001F512 SENSITIVE DATA BLURRED"
                            try: fnt = ImageFont.truetype("arial.ttf", 24)
                            except: fnt = ImageFont.load_default()
                            bb = draw.textbbox((0,0), txt, font=fnt)
                            tw, th = bb[2]-bb[0], bb[3]-bb[1]
                            cx, cy = x1+(x2-x1)//2, y1+(y2-y1)//2
                            draw.rectangle([cx-tw//2-10, cy-th//2-10, cx+tw//2+10, cy+th//2+10],
                                           fill=(220,38,38))
                            draw.text((cx-tw//2, cy-th//2), txt, fill="white", font=fnt)
                    except:
                        pass
        win32gui.EnumWindows(handler, None)

    def _log(self, status):
        try:
            requests.post(f"{SERVER_URL}/log-activity",
                          json={"activation_key": self.activation_key, "status": status})
        except:
            pass

    # ─────────────────────────────────────────────────────────────────────
    #  POPUPS (Professional CTkToplevel dialogs)
    # ─────────────────────────────────────────────────────────────────────

    def _show_warn(self):
        if not self.monitoring_active:
            return
        if hasattr(self, "_warn_win"):
            try:
                if self._warn_win.winfo_exists():
                    return
            except:
                pass

        win = ctk.CTkToplevel(self)
        win.overrideredirect(True)
        win.attributes("-topmost", True)
        w, h = 400, 220
        x = (self.winfo_screenwidth() - w) // 2
        y = (self.winfo_screenheight() - h) // 2
        win.geometry(f"{w}x{h}+{x}+{y}")
        win.configure(fg_color=COLORS["bg_card"])
        self._warn_win = win

        # Red accent bar
        ctk.CTkFrame(win, fg_color=COLORS["red"], height=4,
                     corner_radius=0).pack(fill="x")

        pad = ctk.CTkFrame(win, fg_color=COLORS["bg_card"])
        pad.pack(fill="both", expand=True, padx=24, pady=(16, 20))

        ctk.CTkLabel(pad, text="Away Detected",
                     font=ctk.CTkFont("Segoe UI", 18, "bold"),
                     text_color=COLORS["text_white"]).pack(anchor="w")
        ctk.CTkLabel(pad, text="Your presence was not detected by the camera.",
                     font=ctk.CTkFont("Segoe UI", 11),
                     text_color=COLORS["text_muted"]).pack(anchor="w", pady=(2, 16))

        row = ctk.CTkFrame(pad, fg_color="transparent")
        row.pack(fill="x")
        ctk.CTkButton(row, text="\U0001F504  Retry", height=40, corner_radius=8,
                      fg_color=COLORS["accent"], hover_color=COLORS["accent_h"],
                      font=ctk.CTkFont("Segoe UI", 12, "bold"),
                      command=self._retry_cam).pack(side="left", expand=True,
                                                      fill="x", padx=(0, 6))
        ctk.CTkButton(row, text="\u2615  Go on Break", height=40, corner_radius=8,
                      fg_color=COLORS["yellow"], hover_color="#ca8a04",
                      text_color=COLORS["bg_deep"],
                      font=ctk.CTkFont("Segoe UI", 12, "bold"),
                      command=self._warn_break).pack(side="right", expand=True,
                                                       fill="x", padx=(6, 0))

        self._warn_result = ctk.CTkLabel(pad, text="",
                                          font=ctk.CTkFont("Segoe UI", 11))
        self._warn_result.pack(pady=(10, 0))

    def _show_cam_err(self):
        if not self.activation_key:
            return
        if hasattr(self, "_cam_err_win"):
            try:
                if self._cam_err_win.winfo_exists():
                    return
            except:
                pass

        win = ctk.CTkToplevel(self)
        win.overrideredirect(True)
        win.attributes("-topmost", True)
        w, h = 400, 220
        x = (self.winfo_screenwidth() - w) // 2
        y = (self.winfo_screenheight() - h) // 2
        win.geometry(f"{w}x{h}+{x}+{y}")
        win.configure(fg_color=COLORS["bg_card"])
        self._cam_err_win = win

        ctk.CTkFrame(win, fg_color=COLORS["yellow"], height=4,
                     corner_radius=0).pack(fill="x")

        pad = ctk.CTkFrame(win, fg_color=COLORS["bg_card"])
        pad.pack(fill="both", expand=True, padx=24, pady=(16, 20))

        ctk.CTkLabel(pad, text="Camera Error",
                     font=ctk.CTkFont("Segoe UI", 18, "bold"),
                     text_color=COLORS["text_white"]).pack(anchor="w")
        ctk.CTkLabel(pad, text="Unable to access camera. Check that no other\n"
                     "app is using it and permissions are enabled.",
                     font=ctk.CTkFont("Segoe UI", 11),
                     text_color=COLORS["text_muted"], justify="left").pack(
            anchor="w", pady=(2, 16))

        row = ctk.CTkFrame(pad, fg_color="transparent")
        row.pack(fill="x")
        ctk.CTkButton(row, text="Retry", height=40, corner_radius=8,
                      fg_color=COLORS["accent"], hover_color=COLORS["accent_h"],
                      font=ctk.CTkFont("Segoe UI", 12, "bold"),
                      command=self._hide_cam_err).pack(side="left", expand=True,
                                                         fill="x", padx=(0, 6))
        ctk.CTkButton(row, text="\u2615  Go on Break", height=40, corner_radius=8,
                      fg_color=COLORS["bg_input"], hover_color=COLORS["border"],
                      font=ctk.CTkFont("Segoe UI", 12, "bold"),
                      command=self._cam_break).pack(side="right", expand=True,
                                                      fill="x", padx=(6, 0))

    def _retry_cam(self):
        if hasattr(self, "_warn_result") and self._warn_result.winfo_exists():
            self._warn_result.configure(text="Testing...", text_color=COLORS["yellow"])
        if self._latest_frame is not None:
            if hasattr(self, "_warn_result") and self._warn_result.winfo_exists():
                self._warn_result.configure(text="\u2705  Camera OK! Resuming...",
                                             text_color=COLORS["green"])
            self.consecutive_away = 0
            self.current_status = "Present"
            self._log("Present")
            self._set_status("Active", COLORS["green"])
            self.after(1200, self._hide_warn)
        else:
            if hasattr(self, "_warn_result") and self._warn_result.winfo_exists():
                self._warn_result.configure(text="\u274c  Camera not working",
                                             text_color=COLORS["red"])

    def _warn_break(self):
        self._hide_warn()
        if not self.in_break_mode:
            self._toggle_break()

    def _cam_break(self):
        self._hide_cam_err()
        if not self.in_break_mode:
            self._toggle_break()

    def _hide_warn(self):
        self._close_popup("_warn_win")

    def _hide_cam_err(self):
        self._close_popup("_cam_err_win")

    def _close_popup(self, attr):
        if hasattr(self, attr):
            try:
                getattr(self, attr).destroy()
            except:
                pass

    # ─────────────────────────────────────────────────────────────────────
    #  HELPERS
    # ─────────────────────────────────────────────────────────────────────

    def _clear(self):
        for w in self.container.winfo_children():
            w.destroy()

    def on_close(self):
        if messagebox.askokcancel("Quit", "End shift and close?"):
            self._log("WORK_END")
            self.is_running = False
            self.destroy()
            os._exit(0)


# =============================================================================
if __name__ == "__main__":
    app = App()
    app.mainloop()