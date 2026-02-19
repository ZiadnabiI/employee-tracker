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

SERVER_URL = os.getenv("SERVER_URL", "https://inframe-dab3gthvbkgpe2dp.italynorth-01.azurewebsites.net")
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
    
    def config(self, cnf=None, **kw):
        # Accept custom 'hover_bg' and ensure underlying tk options are kept in sync
        hover = None
        if cnf and isinstance(cnf, dict):
            hover = cnf.pop('hover_bg', None)
        hover = kw.pop('hover_bg', hover)
        if hover is not None:
            self.hover_bg = hover
            kw['activebackground'] = hover

        # Handle bg/background provided either via dict or kwargs
        bg_val = None
        if cnf and isinstance(cnf, dict):
            bg_val = cnf.pop('bg', None) or cnf.pop('background', None)
        bg_val = kw.get('bg') or kw.get('background') or bg_val
        if bg_val is not None:
            self.bg = bg_val
            kw['background'] = bg_val

        return super().config(cnf or {}, **kw)

    configure = config

class DraggableWindow(tk.Tk):
    def __init__(self):
        super().__init__()
        self.overrideredirect(True) # Remove standard window chrome
        self.geometry("400x650")
        self.configure(bg=Theme.BG_MAIN)
        self.title_bar = None
        self.after(10, self.set_app_window)
        
    def set_app_window(self):
        GWL_EXSTYLE = -20
        WS_EX_APPWINDOW = 0x00040000
        WS_EX_TOOLWINDOW = 0x00000080
        
        try:
            hwnd = ctypes.windll.user32.GetParent(self.winfo_id())
            style = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
            style = style & ~WS_EX_TOOLWINDOW
            style = style | WS_EX_APPWINDOW
            ctypes.windll.user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style)
            # Toggle visibility to apply changes
            self.withdraw()
            self.after(10, self.deiconify)
        except Exception as e:
            print(e)
        
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
            relief="flat", bd=0, width=4, command=self.minimize_window
        )
        min_btn.pack(side="right", fill="y")

    def minimize_window(self):
        try:
            hwnd = ctypes.windll.user32.GetParent(self.winfo_id())
            ctypes.windll.user32.ShowWindow(hwnd, 6) # SW_MINIMIZE = 6
        except:
            self.iconify()

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
        self.add_custom_title_bar("INFRAME | Employee Monitor")
        self.center_on_screen()
        
        # App State
        self.activation_key = None
        self.hardware_id = get_hardware_id()
        self.is_running = True
        self.monitoring_active = False
        self.in_break_mode = False
        self.employee_name = "Employee"
        self.warning_snoozed_until = 0
        self.consecutive_away = 0
        self.consecutive_present = 0
        
        # Stats
        self.present_seconds = 0
        self.away_seconds = 0
        self.break_seconds = 0
        self.current_status = "Offline"
        
        # Settings
        self.screenshot_frequency = 600
        self.dlp_enabled = False
        self.logo_img = None # Keep reference
        
        # Initialize UI Container
        self.container = tk.Frame(self, bg=Theme.BG_MAIN)
        self.container.pack(fill="both", expand=True)
        
        # Check Session
        self.check_existing_session()

    def center_on_screen(self):
        self.update_idletasks()
        width = 450  # Wider to let counters breathe
        height = 680
        x = (self.winfo_screenwidth() // 2) - (width // 2)
        y = (self.winfo_screenheight() // 2) - (height // 2)
        self.geometry(f"{width}x{height}+{x}+{y}")

    def load_logo(self, size=(100, 100)):
        try:
            if os.path.exists(LOGO_PATH):
                img = Image.open(LOGO_PATH)
                img = img.resize(size, Image.Resampling.LANCZOS)
                return ImageTk.PhotoImage(img)
        except Exception as e:
            print(f"Logo error: {e}")
        return None

    def check_existing_session(self):
        key = get_registry_value("activation_key")
        name = get_registry_value("employee_name")
        
        if key:
            self.activation_key = key
            if name: self.employee_name = name
            self.verify_session_async() 
            self.show_main_ui()
        else:
            self.show_login_ui()

    def verify_session_async(self):
        def verify():
            try:
                resp = requests.post(f"{SERVER_URL}/verify-checkin", json={"activation_key": self.activation_key}, timeout=5)
                if resp.status_code != 200:
                    set_registry_value("activation_key", "")
                    self.show_login_ui()
            except:
                pass
        Thread(target=verify, daemon=True).start()

    # -------------------------------------------------------------------------
    # UI: LOGIN SCREEN
    # -------------------------------------------------------------------------
    def show_login_ui(self):
        for widget in self.container.winfo_children():
            widget.destroy()
            
        # Black Banner for Logo
        banner = tk.Frame(self.container, bg="black", height=140)
        banner.pack(fill="x", side="top")
        banner.pack_propagate(False) # Force height
        
        # Center Content Wrapper for Logo
        center_frame = tk.Frame(banner, bg="black")
        center_frame.place(relx=0.5, rely=0.5, anchor="center")

        try:
            from PIL import Image, ImageTk
            if os.path.exists(LOGO_PATH):
                img = Image.open(LOGO_PATH)
                img.thumbnail((200, 90))
                self.login_logo = ImageTk.PhotoImage(img)
                tk.Label(center_frame, image=self.login_logo, bg="black", bd=0).pack()
            else:
                tk.Label(center_frame, text="INFRAME", font=("Segoe UI", 32, "bold"), bg="black", fg="white").pack()
        except:
             tk.Label(center_frame, text="INFRAME", font=("Segoe UI", 32, "bold"), bg="black", fg="white").pack()
        
        # Form Container
        form_frame = tk.Frame(self.container, bg=Theme.BG_MAIN)
        form_frame.pack(fill="both", expand=True, padx=40, pady=20)
        
        tk.Label(form_frame, text="Sign In", font=Theme.FONT_HEADER, bg=Theme.BG_MAIN, fg=Theme.TEXT_MAIN).pack(pady=(10, 5))
        tk.Label(form_frame, text="Enter your credentials to continue", font=Theme.FONT_BODY, bg=Theme.BG_MAIN, fg=Theme.TEXT_MUTED).pack(pady=(0, 30))
        
        # Form Elements
        tk.Label(form_frame, text="Email Address", bg=Theme.BG_MAIN, fg=Theme.TEXT_MUTED, font=Theme.FONT_SMALL).pack(anchor="w")
        self.entry_email = tk.Entry(form_frame, font=Theme.FONT_BODY, bg=Theme.BG_INPUT, fg=Theme.TEXT_MAIN, relief="flat", insertbackground=Theme.PRIMARY)
        self.entry_email.pack(fill="x", pady=(5, 15), ipady=8)
        
        tk.Label(form_frame, text="Password", bg=Theme.BG_MAIN, fg=Theme.TEXT_MUTED, font=Theme.FONT_SMALL).pack(anchor="w")
        self.entry_pass = tk.Entry(form_frame, font=Theme.FONT_BODY, bg=Theme.BG_INPUT, fg=Theme.TEXT_MAIN, relief="flat", show="•", insertbackground=Theme.PRIMARY)
        self.entry_pass.pack(fill="x", pady=(5, 25), ipady=8)
        
        # Login Button
        self.btn_login = ModernButton(form_frame, text="Sign In", command=self.perform_login, font=Theme.FONT_BODY_BOLD, height=2)
        self.btn_login.pack(fill="x")
        
        # Status
        self.lbl_login_status = tk.Label(form_frame, text="", bg=Theme.BG_MAIN, fg=Theme.DANGER, font=Theme.FONT_SMALL)
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
            except:
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
            
        # Top Info Bar (Black Header)
        top_bar = tk.Frame(self.container, bg="black", height=110)
        top_bar.pack(fill="x")
        top_bar.pack_propagate(False)
        
        # Logo in Header
        try:
            from PIL import Image, ImageTk
            if os.path.exists(LOGO_PATH):
                img = Image.open(LOGO_PATH)
                img.thumbnail((120, 50))
                self.dash_logo = ImageTk.PhotoImage(img) # Keep ref
                tk.Label(top_bar, image=self.dash_logo, bg="black", bd=0).pack(side="left", padx=25)
            else:
                tk.Label(top_bar, text="INFRAME", font=("Segoe UI", 18, "bold"), bg="black", fg="white").pack(side="left", padx=25)
        except:
             tk.Label(top_bar, text="INFRAME", font=("Segoe UI", 18, "bold"), bg="black", fg="white").pack(side="left", padx=25)
        
        # User Info (Right aligned)
        info_col = tk.Frame(top_bar, bg="black")
        info_col.pack(side="right", fill="y", pady=25, padx=20)
        
        tk.Label(info_col, text=self.employee_name, font=("Segoe UI", 11, "bold"), bg="black", fg="white").pack(anchor="e")
        self.lbl_status = tk.Label(info_col, text="● Initializing...", font=Theme.FONT_SMALL, bg="black", fg="#9ca3af")
        self.lbl_status.pack(anchor="e")
        
        # Main Content (Gray background for contrast)
        content = tk.Frame(self.container, bg=Theme.BG_SIDEBAR, padx=25, pady=25)
        content.pack(fill="both", expand=True)
        
        # Stats Card (White card on gray bg)
        stats_frame = tk.Frame(content, bg=Theme.BG_MAIN, padx=15, pady=15)
        stats_frame.pack(fill="x", pady=(0, 25))
        
        tk.Label(stats_frame, text="TODAY'S ACTIVITY", font=("Segoe UI", 9, "bold"), bg=Theme.BG_MAIN, fg=Theme.TEXT_MUTED).pack(anchor="w", pady=(0, 15))
        
        # Stats Layout
        stats_row = tk.Frame(stats_frame, bg=Theme.BG_MAIN)
        stats_row.pack(fill="x")
        
        self.create_stat_item(stats_row, "Active", "00:00:00", Theme.SUCCESS, "lbl_present")
        self.create_stat_item(stats_row, "Away", "00:00:00", Theme.DANGER, "lbl_away")
        self.create_stat_item(stats_row, "Break", "00:00:00", Theme.WARNING, "lbl_break")
        
        # Actions
        tk.Label(content, text="CONTROLS", font=("Segoe UI", 9, "bold"), bg=Theme.BG_SIDEBAR, fg=Theme.TEXT_MUTED).pack(anchor="w", pady=(0, 10))
        
        self.btn_break = ModernButton(content, text="☕ Take a Break", bg=Theme.WARNING, hover_bg="#ca8a04", command=self.toggle_break, height=2, font=Theme.FONT_BODY_BOLD)
        self.btn_break.pack(fill="x", pady=(0, 15))
        
        ModernButton(content, text="🛑 End Shift", bg=Theme.DANGER, hover_bg=Theme.DANGER_HOVER, command=self.on_close, height=2).pack(fill="x")
        
        tk.Label(self.container, text=f"Device ID: {self.hardware_id}", bg=Theme.BG_SIDEBAR, fg=Theme.BG_INPUT, font=("Segoe UI", 8)).pack(side="bottom", pady=10)
        
        # Separator Line for Header
        tk.Frame(self.container, bg=Theme.BG_INPUT, height=1).place(x=0, y=99, relwidth=1.0)
        
        self.start_monitoring()

    def create_stat_item(self, parent, title, value, color, attr_name):
        f = tk.Frame(parent, bg=Theme.BG_MAIN)
        f.pack(side="left", expand=True, fill="both", padx=2)
        
        tk.Label(f, text=title, bg=Theme.BG_MAIN, fg="#94a3b8", font=("Segoe UI", 10)).pack(anchor="center")
        l = tk.Label(f, text=value, bg=Theme.BG_MAIN, fg=color, font=("Consolas", 14, "bold"))
        l.pack(anchor="center", pady=(5, 0))
        setattr(self, attr_name, l)

    # -------------------------------------------------------------------------
    # FUNCTIONALITY
    # -------------------------------------------------------------------------
    def format_time(self, seconds):
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        # s = int(seconds % 60) # Seconds removed for cleaner look
        return f"{h}h {m}m"

    def update_status(self, text, color):
        if hasattr(self, 'lbl_status') and self.lbl_status.winfo_exists():
            self.lbl_status.config(text=f"● {text}", fg=color)

    def start_monitoring(self):
        if self.monitoring_active: return
        self.monitoring_active = True
        
        Thread(target=self.loop_camera, daemon=True).start()
        Thread(target=self.loop_ticks, daemon=True).start()
        Thread(target=self.loop_heartbeat, daemon=True).start()
        Thread(target=self.loop_apps, daemon=True).start()
        Thread(target=self.loop_screenshots, daemon=True).start()
        
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
        
        self.consecutive_away = 0
        self.consecutive_present = 0
        consecutive_cam_errors = 0
        
        while self.is_running:
            try:
                if self.in_break_mode:
                    time.sleep(1)
                    continue
                    
                ret, frame = cap.read()
                person = False
                
                if ret:
                    consecutive_cam_errors = 0
                    results = model(frame, verbose=False)
                    for r in results:
                        for box in r.boxes:
                            if int(box.cls) == 0 and float(box.conf) > CONFIDENCE_THRESHOLD:
                                person = True; break
                        if person: break
                else:
                    consecutive_cam_errors += 1
                    # Try to restart the camera if it fails
                    if cap:
                        cap.release()
                    cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
                    
                    if consecutive_cam_errors >= 5:
                        self.after(0, self.show_cam_error)
                        time.sleep(5)  # Pause longer before retrying to prevent spamming
                        continue
                
                if person:
                    self.consecutive_present += 1
                    self.consecutive_away = 0
                    if self.consecutive_present >= PRESENT_LIMIT and self.current_status != "Present":
                        self.current_status = "Present"
                        self.send_log("Present")
                        self.after(0, lambda: self.update_status("Active", Theme.SUCCESS))
                        self.after(0, self.hide_warning)
                else:
                    self.consecutive_present = 0
                    self.consecutive_away += 1
                    
                    if self.consecutive_away >= AWAY_LIMIT:
                        if self.current_status != "Away":
                            self.current_status = "Away"
                            self.send_log("Away")
                            self.after(0, lambda: self.update_status("Away Detected", Theme.DANGER))
                        
                        if time.time() > self.warning_snoozed_until:
                            self.after(0, self.show_warning)
            except: pass
            time.sleep(1)
        if cap: cap.release()

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
            
            target = time.time() + self.screenshot_frequency
            while time.time() < target:
                if not self.is_running: break
                time.sleep(5)

    def capture_and_send_screenshot(self, manual=False):
        try:
            screen = ImageGrab.grab()
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
        # Keywords to trigger DLP
        keywords = ["password", "bank", "credit", "inbox", "login", "sign in", "facebook", "twitter", "instagram", "gmail"]
        
        def handler(hwnd, _):
            if win32gui.IsWindowVisible(hwnd):
                title = win32gui.GetWindowText(hwnd).lower()
                if any(k in title for k in keywords):
                    try:
                        # Get Window Coordinates
                        msg = win32gui.GetWindowRect(hwnd)
                        x1, y1, x2, y2 = msg
                        
                        # Ensure coordinates are improved for High DPI if needed, 
                        # but for now rely on PIL's coordinate system matching screen.
                        # Crop the sensitive area
                        box = (x1, y1, x2, y2)
                        
                        # Validate box is within image
                        if x1 >= 0 and y1 >= 0 and x2 > x1 and y2 > y1:
                            # 1. Pixelate/Blur Effect
                            region = img.crop(box)
                            # Apply heavy blur
                            blurred = region.filter(ImageFilter.GaussianBlur(radius=15))
                            img.paste(blurred, box)
                            
                            # 2. Add "Sensitive Data" Watermark
                            draw = ImageDraw.Draw(img)
                            # Draw a semi-transparent overlay or text
                            # Since standard PIL doesn't support alpha on RGB direct draw easily without converting,
                            # we'll just draw text
                            
                            # Calculate center
                            cx, cy = x1 + (x2-x1)//2, y1 + (y2-y1)//2
                            text = "🔒 SENSITIVE DATA HIDDEN"
                            
                            # Use default font if custom not loaded
                            font = ImageFont.load_default()
                            
                            # Draw text with shadow for visibility
                            draw.text((cx-2, cy-2), text, fill="black", font=font)
                            draw.text((cx, cy), text, fill="white", font=font)
                            
                    except Exception as e:
                        pass
        
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
        self.win_warn.attributes('-alpha', 0.95)
        self.win_warn.configure(bg=Theme.DANGER)
        w, h = 500, 260
        x = (self.winfo_screenwidth()-w)//2
        y = (self.winfo_screenheight()-h)//2
        self.win_warn.geometry(f"{w}x{h}+{x}+{y}")
        
        # Inner Frame with Border
        frame = tk.Frame(self.win_warn, bg=Theme.DANGER, highlightbackground="white", highlightthickness=2)
        frame.pack(fill="both", expand=True, padx=4, pady=4)
        
        tk.Label(frame, text="⚠️", font=("Segoe UI", 48), bg=Theme.DANGER, fg="white").pack(pady=(15, 0))
        tk.Label(frame, text="YOU ARE AWAY", font=("Segoe UI", 24, "bold"), bg=Theme.DANGER, fg="white").pack()
        tk.Label(frame, text="Presence not detected. Activity logging paused.", font=("Segoe UI", 11), bg=Theme.DANGER, fg="white").pack(pady=(5, 15))
        
        # Manual Bypass Button
        ModernButton(frame, text="I'm Here (Dismiss)", font=("Segoe UI", 11, "bold"), bg="#ffffff", fg=Theme.DANGER, hover_bg="#f8fafc", command=self.manual_presence, height=2, width=20).pack(pady=(0, 20))
        
    def show_cam_error(self):
        if hasattr(self, 'win_cam_error') and self.win_cam_error.winfo_exists(): return
        if hasattr(self, 'win_warn') and self.win_warn.winfo_exists(): self.hide_warning()
        
        self.win_cam_error = tk.Toplevel(self)
        self.win_cam_error.overrideredirect(True)
        self.win_cam_error.attributes('-topmost', True)
        self.win_cam_error.attributes('-alpha', 0.95)
        self.win_cam_error.configure(bg=Theme.WARNING)
        w, h = 500, 280
        x = (self.winfo_screenwidth()-w)//2
        y = (self.winfo_screenheight()-h)//2
        self.win_cam_error.geometry(f"{w}x{h}+{x}+{y}")
        
        frame = tk.Frame(self.win_cam_error, bg=Theme.WARNING, highlightbackground="black", highlightthickness=2)
        frame.pack(fill="both", expand=True, padx=4, pady=4)
        
        tk.Label(frame, text="📷", font=("Segoe UI", 40), bg=Theme.WARNING, fg="black").pack(pady=(10, 0))
        tk.Label(frame, text="CAMERA ERROR", font=("Segoe UI", 20, "bold"), bg=Theme.WARNING, fg="black").pack()
        
        msg = "Unable to access the camera.\n\n1. Ensure another app is NOT using the camera.\n" \
              "2. Check Privacy Settings:\n   Settings > Privacy & security > Camera\n" \
              "   Turn on 'Let desktop apps access your camera'."
        
        tk.Label(frame, text=msg, font=("Segoe UI", 10), bg=Theme.WARNING, fg="black", justify="left").pack(pady=10)
        
        ModernButton(frame, text="I Fixed It (Retry)", font=("Segoe UI", 11, "bold"), bg="black", fg="white", hover_bg="#333", command=self.hide_cam_error, height=2, width=20).pack(pady=(0, 15))
        
    def manual_presence(self):
        self.warning_snoozed_until = time.time() + 300 # Snooze for 5 minutes
        self.consecutive_away = 0
        if self.current_status != "Present":
            self.current_status = "Present"
            self.send_log("Present")
            self.update_status("Active (Manual)", Theme.SUCCESS)
        self.hide_warning()
    
    def hide_warning(self):
        if hasattr(self, 'win_warn') and self.win_warn: self.win_warn.destroy()

    def hide_cam_error(self):
        if hasattr(self, 'win_cam_error') and self.win_cam_error: self.win_cam_error.destroy()

    def on_close(self):
        if messagebox.askokcancel("Quit", "End Shift and Close?"):
            self.send_log("WORK_END")
            self.is_running = False
            self.destroy()
            import os
            os._exit(0)

if __name__ == "__main__":
    app = App()
    app.mainloop()