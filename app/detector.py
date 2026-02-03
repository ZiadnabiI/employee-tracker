"""
Employee Presence Monitor - Premium Edition
===========================================
Modern, dark-themed attendance tracking application.
Features:
- Custom UI (Borderless Window, Custom Titlebar)
- Separate Login Flow
- Advanced Monitoring (YOLO, DLP, App Tracking)
"""

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
from PIL import ImageGrab, ImageFilter, ImageDraw, ImageFont, ImageTk
import io
import base64
import ctypes

# Enable High DPI Support
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(1)
except:
    pass

# =============================================================================
# CONFIGURATION
# =============================================================================

SERVER_URL = os.getenv("SERVER_URL", "https://employee-tracker-up30.onrender.com")
CONFIDENCE_THRESHOLD = 0.6 
AWAY_LIMIT = 10
PRESENT_LIMIT = 3
REGISTRY_PATH = r"SOFTWARE\EmployeeTracker"

# =============================================================================
# THEME & STYLES
# =============================================================================

# =============================================================================
# THEME & STYLES (Light Mode)
# =============================================================================

class Theme:
    # Colors (Light Mode Palette - Clean & Corporate)
    BG_MAIN = "#ffffff"      # White
    BG_SIDEBAR = "#f1f5f9"   # Slate-100
    BG_CARD = "#f8fafc"      # Slate-50
    BG_INPUT = "#e2e8f0"     # Slate-200
    
    PRIMARY = "#000000"      # Black (High Contrast)
    PRIMARY_HOVER = "#333333"
    
    DANGER = "#ef4444"       # Red-500
    DANGER_HOVER = "#dc2626"
    
    SUCCESS = "#22c55e"      # Green-500
    WARNING = "#eab308"      # Yellow-500
    
    TEXT_MAIN = "#0f172a"    # Slate-900
    TEXT_MUTED = "#64748b"   # Slate-500
    
    TITLE_BAR = "#ffffff"    # White

    # Fonts
    FONT_TITLE = ("Segoe UI", 12, "bold")
    FONT_HEADER = ("Segoe UI", 24, "bold")
    FONT_BODY = ("Segoe UI", 10)
    FONT_BODY_BOLD = ("Segoe UI", 10, "bold")
    FONT_SMALL = ("Segoe UI", 9)
    FONT_MONO = ("Consolas", 12)

LOGO_PATH = r"C:/Users/ziadn/.gemini/antigravity/brain/6c4d7325-991d-4d51-b241-7470af94e1b0/uploaded_media_1770146996132.jpg"


# =============================================================================
# REGISTRY HELPERS
# =============================================================================

def get_registry_value(key_name, default=None):
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, REGISTRY_PATH) as reg:
            value, _ = winreg.QueryValueEx(reg, key_name)
            return value
    except:
        return default

def set_registry_value(key_name, value):
    try:
        import winreg
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, REGISTRY_PATH) as reg:
            winreg.SetValueEx(reg, key_name, 0, winreg.REG_SZ, str(value))
        return True
    except Exception as e:
        print(f"Registry error: {e}")
        return False

def get_hardware_id():
    hw_id = get_registry_value("hardware_id")
    if not hw_id:
        hw_id = f"HW-{uuid.uuid4().hex[:8].upper()}"
        set_registry_value("hardware_id", hw_id)
    return hw_id

# =============================================================================
# CUSTOM UI COMPONENTS
# =============================================================================

class ModernButton(tk.Button):
    def __init__(self, parent, text, command, bg=Theme.PRIMARY, hover_bg=Theme.PRIMARY_HOVER, fg="#ffffff", **kwargs):
        super().__init__(
            parent, text=text, command=command, bg=bg, fg=fg, 
            activebackground=hover_bg, activeforeground=fg,
            relief="flat", borderwidth=0, cursor="hand2", **kwargs
        )
        self.bg = bg
        self.hover_bg = hover_bg
        self.bind("<Enter>", self.on_enter)
        self.bind("<Leave>", self.on_leave)

    def on_enter(self, e):
        self['background'] = self.hover_bg

    def on_leave(self, e):
        self['background'] = self.bg

class DraggableWindow(tk.Tk):
    def __init__(self):
        super().__init__()
        self.overrideredirect(True) # Remove standard window chrome
        self.geometry("400x650")
        self.configure(bg=Theme.BG_MAIN)
        self.title_bar = None
        
    def add_custom_title_bar(self, title_text="Employee App"):
        # Title Bar Frame
        self.title_bar = tk.Frame(self, bg=Theme.TITLE_BAR, height=35)
        self.title_bar.pack(fill="x", side="top")
        self.title_bar.pack_propagate(False)
        
        # Dragging Logic
        self.title_bar.bind("<Button-1>", self.start_move)
        self.title_bar.bind("<B1-Motion>", self.do_move)
        
        # Icon/Title
        title = tk.Label(self.title_bar, text=title_text, bg=Theme.TITLE_BAR, fg=Theme.TEXT_MUTED, font=("Segoe UI", 10))
        title.pack(side="left", padx=10)
        
        # Window Controls
        close_btn = tk.Button(
            self.title_bar, text="✕", bg=Theme.TITLE_BAR, fg=Theme.TEXT_MUTED, 
            activebackground="#ef4444", activeforeground="white",
            relief="flat", bd=0, width=4, command=self.on_close
        )
        close_btn.pack(side="right", fill="y")
        
        min_btn = tk.Button(
            self.title_bar, text="─", bg=Theme.TITLE_BAR, fg=Theme.TEXT_MUTED, 
            activebackground=Theme.BG_CARD, activeforeground="white",
            relief="flat", bd=0, width=4, command=self.iconify
        )
        min_btn.pack(side="right", fill="y")

    def start_move(self, event):
        self.x = event.x
        self.y = event.y

    def do_move(self, event):
        deltax = event.x - self.x
        deltay = event.y - self.y
        x = self.winfo_x() + deltax
        y = self.winfo_y() + deltay
        self.geometry(f"+{x}+{y}")
        
    def on_close(self):
        self.destroy()

# =============================================================================
# MAIN LOGIC
# =============================================================================

class App(DraggableWindow):
    def __init__(self):
        super().__init__()
        self.add_custom_title_bar("InFrame | Employee Monitor")
        
        # App State
        self.activation_key = None
        self.hardware_id = get_hardware_id()
        self.is_running = True
        self.monitoring_active = False
        self.in_break_mode = False
        self.employee_name = "Employee"
        
        # Stats
        self.present_seconds = 0
        self.away_seconds = 0
        self.break_seconds = 0
        self.current_status = "Offline"
        
        # Settings
        self.screenshot_frequency = 600
        self.dlp_enabled = False
        
        # Initialize UI Container
        self.container = tk.Frame(self, bg=Theme.BG_MAIN)
        self.container.pack(fill="both", expand=True)
        
        # Check Session
        self.check_existing_session()

    def check_existing_session(self):
        key = get_registry_value("activation_key")
        name = get_registry_value("employee_name")
        
        if key:
            self.activation_key = key
            if name: self.employee_name = name
            # Verify session in background, but show main UI immediately for UX
            self.verify_session_async() 
            self.show_main_ui()
        else:
            self.show_login_ui()

    def verify_session_async(self):
        def verify():
            try:
                resp = requests.post(f"{SERVER_URL}/verify-checkin", json={"activation_key": self.activation_key}, timeout=5)
                if resp.status_code != 200:
                    # Invalid session
                    set_registry_value("activation_key", "")
                    self.show_login_ui()
            except:
                pass # Offline mode?
        Thread(target=verify, daemon=True).start()

    # -------------------------------------------------------------------------
    # UI: LOGIN SCREEN
    # -------------------------------------------------------------------------
    def show_login_ui(self):
        for widget in self.container.winfo_children():
            widget.destroy()
            
        # Center Content
        frame = tk.Frame(self.container, bg=Theme.BG_MAIN)
        frame.place(relx=0.5, rely=0.5, anchor="center", relwidth=0.85)
        
        # Logo/Icon
        icon_label = tk.Label(frame, text="🔒", font=("Segoe UI", 48), bg=Theme.BG_MAIN, fg=Theme.PRIMARY)
        icon_label.pack(pady=(0, 10))
        
        title = tk.Label(frame, text="Welcome Back", font=Theme.FONT_HEADER, bg=Theme.BG_MAIN, fg="white")
        title.pack(pady=(0, 5))
        
        subtitle = tk.Label(frame, text="Sign in to start your shift", font=Theme.FONT_BODY, bg=Theme.BG_MAIN, fg=Theme.TEXT_MUTED)
        subtitle.pack(pady=(0, 30))
        
        # Form
        tk.Label(frame, text="Email Address", bg=Theme.BG_MAIN, fg=Theme.TEXT_MUTED, font=Theme.FONT_SMALL).pack(anchor="w")
        self.entry_email = tk.Entry(frame, font=Theme.FONT_BODY, bg=Theme.BG_INPUT, fg="white", relief="flat", insertbackground="white")
        self.entry_email.pack(fill="x", pady=(5, 15), ipady=8)
        
        tk.Label(frame, text="Password", bg=Theme.BG_MAIN, fg=Theme.TEXT_MUTED, font=Theme.FONT_SMALL).pack(anchor="w")
        self.entry_pass = tk.Entry(frame, font=Theme.FONT_BODY, bg=Theme.BG_INPUT, fg="white", relief="flat", show="•", insertbackground="white")
        self.entry_pass.pack(fill="x", pady=(5, 25), ipady=8)
        
        # Login Button
        self.btn_login = ModernButton(frame, text="Sign In", command=self.perform_login, font=Theme.FONT_BODY_BOLD, height=2)
        self.btn_login.pack(fill="x")
        
        # Status Msg
        self.lbl_login_status = tk.Label(frame, text="", bg=Theme.BG_MAIN, fg=Theme.DANGER, font=Theme.FONT_SMALL)
        self.lbl_login_status.pack(pady=10)

    def perform_login(self):
        email = self.entry_email.get().strip()
        pwd = self.entry_pass.get().strip()
        
        if not email or not pwd:
            self.lbl_login_status.config(text="Please enter email and password")
            return
            
        self.lbl_login_status.config(text="Authenticating...", fg=Theme.WARNING)
        self.btn_login.config(state="disabled")
        
        def login_thread():
            try:
                resp = requests.post(f"{SERVER_URL}/api/app-login", json={"email": email, "password": pwd}, timeout=10)
                if resp.status_code == 200:
                    data = resp.json()
                    self.activation_key = data['activation_key']
                    self.employee_name = data['name']
                    
                    set_registry_value("activation_key", self.activation_key)
                    set_registry_value("employee_name", self.employee_name)
                    
                    self.container.after(0, self.show_main_ui)
                else:
                    msg = resp.json().get("detail", "Login failed")
                    self.container.after(0, lambda: self.login_failed(msg))
            except Exception as e:
                self.container.after(0, lambda: self.login_failed("Connection failed"))
                
        Thread(target=login_thread, daemon=True).start()

    def login_failed(self, msg):
        self.lbl_login_status.config(text=msg, fg=Theme.DANGER)
        self.btn_login.config(state="normal")

    # -------------------------------------------------------------------------
    # UI: MAIN DASHBOARD
    # -------------------------------------------------------------------------
    def show_main_ui(self):
        for widget in self.container.winfo_children():
            widget.destroy()
            
        # Top Info Bar
        top_bar = tk.Frame(self.container, bg=Theme.BG_SIDEBAR, height=80)
        top_bar.pack(fill="x")
        
        # Avatar placeholder
        avatar = tk.Label(top_bar, text=self.employee_name[0], font=("Segoe UI", 16, "bold"), 
                         bg=Theme.PRIMARY, fg="white", width=3, height=1)
        avatar.pack(side="left", padx=20)
        
        # Name & Status
        info_col = tk.Frame(top_bar, bg=Theme.BG_SIDEBAR)
        info_col.pack(side="left", fill="y", pady=15)
        
        tk.Label(info_col, text=self.employee_name, font=Theme.FONT_TITLE, bg=Theme.BG_SIDEBAR, fg="white").pack(anchor="w")
        self.lbl_status = tk.Label(info_col, text="● Initializing...", font=Theme.FONT_SMALL, bg=Theme.BG_SIDEBAR, fg=Theme.TEXT_MUTED)
        self.lbl_status.pack(anchor="w")
        
        # Main Content Area
        content = tk.Frame(self.container, bg=Theme.BG_MAIN, padx=20, pady=20)
        content.pack(fill="both", expand=True)
        
        # Stats Card
        stats_frame = tk.Frame(content, bg=Theme.BG_CARD, padx=15, pady=15)
        stats_frame.pack(fill="x", pady=(0, 20))
        
        tk.Label(stats_frame, text="SESSION STATS", font=("Segoe UI", 8, "bold"), bg=Theme.BG_CARD, fg=Theme.TEXT_MUTED).pack(anchor="w", pady=(0, 10))
        
        # Grid for stats
        grid = tk.Frame(stats_frame, bg=Theme.BG_CARD)
        grid.pack(fill="x")
        
        self.create_stat_item(grid, 0, "Online", "00:00:00", Theme.SUCCESS, "lbl_present")
        self.create_stat_item(grid, 1, "Away", "00:00:00", Theme.DANGER, "lbl_away")
        self.create_stat_item(grid, 2, "Break", "00:00:00", Theme.WARNING, "lbl_break")
        
        # Actions
        tk.Label(content, text="QUICK ACTIONS", font=("Segoe UI", 8, "bold"), bg=Theme.BG_MAIN, fg=Theme.TEXT_MUTED).pack(anchor="w", pady=(0, 10))
        
        self.btn_break = ModernButton(content, text="☕ Take a Break", bg=Theme.WARNING, hover_bg="#ca8a04", command=self.toggle_break, height=2, font=Theme.FONT_BODY_BOLD)
        self.btn_break.pack(fill="x", pady=(0, 10))
        
        ModernButton(content, text="📸 Capture Now", bg=Theme.BG_CARD, hover_bg=Theme.BG_INPUT, fg="white", command=lambda: self.capture_and_send_screenshot(True), height=2).pack(fill="x", pady=(0, 10))
        
        ModernButton(content, text="🛑 End Shift", bg=Theme.DANGER, hover_bg=Theme.DANGER_HOVER, command=self.on_close, height=2).pack(fill="x")
        
        # Device Info Footer
        tk.Label(self.container, text=f"ID: {self.hardware_id}", bg=Theme.BG_MAIN, fg=Theme.BG_INPUT, font=("Segoe UI", 7)).pack(side="bottom", pady=5)
        
        # Start Threads
        self.start_monitoring()

    def create_stat_item(self, parent, col, title, value, color, attr_name):
        f = tk.Frame(parent, bg=Theme.BG_CARD)
        f.grid(row=0, column=col, sticky="ew", padx=5)
        parent.grid_columnconfigure(col, weight=1)
        
        tk.Label(f, text=title, bg=Theme.BG_CARD, fg="#94a3b8", font=("Segoe UI", 9)).pack(anchor="w")
        l = tk.Label(f, text=value, bg=Theme.BG_CARD, fg=color, font=("Consolas", 16, "bold"))
        l.pack(anchor="w")
        setattr(self, attr_name, l)

    # -------------------------------------------------------------------------
    # FUNCTIONALITY
    # -------------------------------------------------------------------------
    def format_time(self, seconds):
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        s = int(seconds % 60)
        return f"{h:02d}:{m:02d}:{s:02d}"

    def update_status(self, text, color):
        self.lbl_status.config(text=f"● {text}", fg=color)

    def start_monitoring(self):
        if self.monitoring_active: return
        self.monitoring_active = True
        
        # Threads
        Thread(target=self.loop_camera, daemon=True).start()
        Thread(target=self.loop_ticks, daemon=True).start()
        Thread(target=self.loop_heartbeat, daemon=True).start()
        Thread(target=self.loop_apps, daemon=True).start()
        Thread(target=self.loop_screenshots, daemon=True).start()
        
        # Wait a sec then fetch time
        self.after(1000, self.fetch_server_time)

    def fetch_server_time(self):
        try:
            resp = requests.get(f"{SERVER_URL}/api/employee-time/{self.activation_key}", timeout=5)
            if resp.status_code == 200:
                d = resp.json()
                self.present_seconds = d.get('present_seconds', 0)
                self.away_seconds = d.get('away_seconds', 0)
                self.break_seconds = d.get('break_seconds', 0)
        except: pass

    # --- Loops ---

    def loop_ticks(self):
        while self.is_running:
            if self.monitoring_active:
                if self.in_break_mode:
                    self.break_seconds += 1
                elif self.current_status == "Present":
                    self.present_seconds += 1
                elif self.current_status == "Away":
                    self.away_seconds += 1
                
                # Update UI
                self.after(0, self.update_timers)
            time.sleep(1)

    def update_timers(self):
        if hasattr(self, 'lbl_present') and self.lbl_present.winfo_exists():
            self.lbl_present.config(text=self.format_time(self.present_seconds))
            self.lbl_away.config(text=self.format_time(self.away_seconds))
            self.lbl_break.config(text=self.format_time(self.break_seconds))

    def toggle_break(self):
        self.in_break_mode = not self.in_break_mode
        if self.in_break_mode:
            self.btn_break.config(text="▶ Resume Work", bg=Theme.PRIMARY, hover_bg=Theme.PRIMARY_HOVER)
            self.update_status("On Break", Theme.WARNING)
            self.send_log("BREAK_START")
        else:
            self.btn_break.config(text="☕ Take a Break", bg=Theme.WARNING, hover_bg="#ca8a04")
            self.update_status("Active", Theme.SUCCESS)
            self.send_log("BREAK_END")

    def loop_camera(self):
        model = YOLO("yolo11n.pt")
        cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
        
        consecutive_away = 0
        consecutive_present = 0
        
        while self.is_running:
            if self.in_break_mode:
                time.sleep(1)
                continue
                
            ret, frame = cap.read()
            if not ret:
                time.sleep(1)
                continue
                
            results = model(frame, verbose=False)
            person = False
            for r in results:
                for box in r.boxes:
                    if int(box.cls) == 0 and float(box.conf) > CONFIDENCE_THRESHOLD:
                        person = True; break
                if person: break
            
            if person:
                consecutive_present += 1
                consecutive_away = 0
                if consecutive_present >= PRESENT_LIMIT and self.current_status != "Present":
                    self.current_status = "Present"
                    self.send_log("Present")
                    self.after(0, lambda: self.update_status("Active", Theme.SUCCESS))
                    self.after(0, self.hide_warning)
            else:
                consecutive_present = 0
                consecutive_away += 1
                if consecutive_away >= AWAY_LIMIT and self.current_status != "Away":
                    self.current_status = "Away"
                    self.send_log("Away")
                    self.after(0, lambda: self.update_status("Away Detected", Theme.DANGER))
                    self.after(0, self.show_warning)
            
            time.sleep(1)
        cap.release()

    def loop_heartbeat(self):
        while self.is_running:
            try:
                resp = requests.post(f"{SERVER_URL}/heartbeat", json={"activation_key": self.activation_key}, timeout=5)
                if resp.status_code == 200:
                    data = resp.json()
                    if data.get("command") == "screenshot":
                        self.capture_and_send_screenshot(True)
                    if "settings" in data:
                        self.screenshot_frequency = data["settings"].get("screenshot_frequency", 600)
                        self.dlp_enabled = bool(data["settings"].get("dlp_enabled", 0))
            except: pass
            time.sleep(10)

    def loop_apps(self):
        last_app = None
        start_t = time.time()
        while self.is_running:
            try:
                hwnd = win32gui.GetForegroundWindow()
                title = win32gui.GetWindowText(hwnd)
                _, pid = win32process.GetWindowThreadProcessId(hwnd)
                try: app = psutil.Process(pid).name()
                except: app = "unknown"
                
                if app != last_app and last_app:
                    dur = int(time.time() - start_t)
                    if dur > 2:
                        requests.post(f"{SERVER_URL}/api/app-log", json={
                            "activation_key": self.activation_key,
                            "app_name": last_app, "window_title": title[:200], "duration_seconds": dur
                        })
                    start_t = time.time()
                last_app = app
            except: pass
            time.sleep(5)

    def loop_screenshots(self):
        while self.is_running:
            if not self.in_break_mode:
                self.capture_and_send_screenshot()
            
            # Smart sleep
            target = time.time() + self.screenshot_frequency
            while time.time() < target:
                if not self.is_running: break
                time.sleep(5)

    def capture_and_send_screenshot(self, manual=False):
        try:
            screen = ImageGrab.grab()
            # DLP
            if self.dlp_enabled:
                self.apply_dlp(screen)
            
            buf = io.BytesIO()
            screen.save(buf, format='JPEG', quality=60)
            b64 = base64.b64encode(buf.getvalue()).decode()
            
            requests.post(f"{SERVER_URL}/api/screenshot", json={
                "activation_key": self.activation_key, "screenshot_data": b64, "manual_request": manual
            })
            print("Screenshot sent")
        except Exception as e: print(e)

    def apply_dlp(self, img):
        # Simply logic from before
        keywords = ["password", "bank", "credit", "inbox"]
        windows = []
        def handler(hwnd, _):
            if win32gui.IsWindowVisible(hwnd):
                t = win32gui.GetWindowText(hwnd).lower()
                if any(k in t for k in keywords):
                    try:
                        rect = win32gui.GetWindowRect(hwnd)
                        # Basic blur
                        draw = ImageDraw.Draw(img)
                        draw.rectangle(rect, fill="black") # Blackout is safer/easier than blur for now
                    except: pass
        win32gui.EnumWindows(handler, None)

    def send_log(self, status):
        try: requests.post(f"{SERVER_URL}/log-activity", json={"activation_key": self.activation_key, "status": status})
        except: pass

    # --- Windows ---
    def show_warning(self):
        if hasattr(self, 'win_warn') and self.win_warn.winfo_exists(): return
        self.win_warn = tk.Toplevel(self)
        self.win_warn.overrideredirect(True)
        self.win_warn.attributes('-topmost', True)
        self.win_warn.configure(bg=Theme.DANGER)
        w, h = 600, 300
        x = (self.winfo_screenwidth()-w)//2
        y = (self.winfo_screenheight()-h)//2
        self.win_warn.geometry(f"{w}x{h}+{x}+{y}")
        tk.Label(self.win_warn, text="⚠️ YOU ARE AWAY", font=("Segoe UI", 30, "bold"), bg=Theme.DANGER, fg="white").pack(expand=True)
    
    def hide_warning(self):
        if hasattr(self, 'win_warn') and self.win_warn: self.win_warn.destroy()

    def on_close(self):
        if messagebox.askokcancel("Quit", "End Shift and Close?"):
            self.send_log("WORK_END")
            self.is_running = False
            self.destroy()

if __name__ == "__main__":
    app = App()
    app.mainloop()