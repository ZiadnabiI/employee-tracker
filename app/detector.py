"""
Employee Presence Monitor - Redesigned
=======================================
A modern desktop application for employee attendance tracking.
Uses Windows Registry for storage (no external files).
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

# =============================================================================
# CONFIGURATION
# =============================================================================

SERVER_URL = os.getenv("SERVER_URL", "https://employee-tracker-up30.onrender.com")
CONFIDENCE_THRESHOLD = 0.6 # Increased to reduce false positives
AWAY_LIMIT = 10
PRESENT_LIMIT = 3 # Seconds of continuous presence required

REGISTRY_PATH = r"SOFTWARE\EmployeeTracker"

# =============================================================================
# REGISTRY HELPERS (No File Storage)
# =============================================================================

def get_registry_value(key_name, default=None):
    """Get a value from Windows Registry"""
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, REGISTRY_PATH) as reg:
            value, _ = winreg.QueryValueEx(reg, key_name)
            return value
    except:
        return default

def set_registry_value(key_name, value):
    """Set a value in Windows Registry"""
    try:
        import winreg
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, REGISTRY_PATH) as reg:
            winreg.SetValueEx(reg, key_name, 0, winreg.REG_SZ, str(value))
        return True
    except Exception as e:
        print(f"Registry error: {e}")
        return False

def delete_registry_key():
    """Delete all stored data from Registry"""
    try:
        import winreg
        winreg.DeleteKey(winreg.HKEY_CURRENT_USER, REGISTRY_PATH)
    except:
        pass

# =============================================================================
# STYLES - Dark Theme
# =============================================================================

class Colors:
    # Background colors (Clean Light Mode)
    BG_DARK = "#f5f6fa"      # Main background (Soft Grey)
    BG_DARKER = "#ffffff"    # Header/Footer (Pure White)
    BG_CARD = "#ffffff"      # Card surface (White)
    BG_CARD_HOVER = "#f1f2f6"
    
    # Accent colors
    PRIMARY = "#00cec9"      # Teal
    SECONDARY = "#00b894"    # Green
    WARNING = "#fdcb6e"      # Yellow/Orange
    DANGER = "#ff7675"       # Soft Red
    INFO = "#74b9ff"         # Soft Blue
    
    # Text colors
    TEXT_PRIMARY = "#2d3436" # Dark Grey (almost black)
    TEXT_SECONDARY = "#636e72" # Grey
    TEXT_MUTED = "#b2bec3"   # Light Grey
    
    # Status colors
    ONLINE = "#00b894"
    AWAY = "#ff7675"
    BREAK = "#fdcb6e"
    OFFLINE = "#b2bec3"

class Fonts:
    TITLE = ("Segoe UI", 16, "bold")
    HEADING = ("Segoe UI", 14, "bold")
    BODY = ("Segoe UI", 12)
    BODY_BOLD = ("Segoe UI", 12, "bold")
    SMALL = ("Segoe UI", 10)
    TIMER = ("Consolas", 14, "bold")

# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def format_time(seconds):
    """Format seconds into HH:MM:SS"""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"

def get_hardware_id():
    """Get or create a unique hardware ID (stored in Registry)"""
    hw_id = get_registry_value("hardware_id")
    if not hw_id:
        hw_id = f"HW-{uuid.uuid4().hex[:8].upper()}"
        set_registry_value("hardware_id", hw_id)
    return hw_id

# =============================================================================
# MAIN APPLICATION
# =============================================================================

class EmployeeApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Employee Presence Monitor")
        self.root.geometry("420x720") # Increased height for better spacing
        self.root.configure(bg=Colors.BG_DARK)
        self.root.resizable(False, False)
        
        # State
        self.activation_key = None
        self.hardware_id = get_hardware_id()
        self.is_running = True
        self.monitoring_active = False
        self.in_break_mode = False
        self.employee_name = "Employee"
        
        # Time tracking
        self.session_start_time = None
        self.present_seconds = 0
        self.away_seconds = 0
        self.break_seconds = 0
        self.current_status = "Present"

        self.build_ui()
        self.check_existing_login()
        
        # Handle window close
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

    # =========================================================================
    # UI BUILDING
    # =========================================================================

    def build_ui(self):
        """Build the main user interface"""
        
        # Header
        self.header_frame = tk.Frame(self.root, bg=Colors.BG_DARKER, height=70)
        self.header_frame.pack(fill="x")
        self.header_frame.pack_propagate(False)
        
        self.label_title = tk.Label(
            self.header_frame, 
            text="👤 Employee Tracker", 
            fg=Colors.TEXT_PRIMARY, 
            bg=Colors.BG_DARKER, 
            font=Fonts.TITLE
        )
        self.label_title.pack(pady=20)

        # Status Indicator
        self.status_frame = tk.Frame(self.root, bg=Colors.BG_DARK)
        self.status_frame.pack(pady=15, fill="x", padx=20)
        
        self.status_indicator = tk.Frame(self.status_frame, bg=Colors.OFFLINE, width=12, height=12)
        self.status_indicator.pack(side="left", padx=(0, 10))
        
        self.label_status = tk.Label(
            self.status_frame, 
            text="Initializing...", 
            fg=Colors.TEXT_SECONDARY, 
            bg=Colors.BG_DARK, 
            font=Fonts.BODY
        )
        self.label_status.pack(side="left")

        # Stats Card
        self.stats_card = tk.Frame(self.root, bg=Colors.BG_CARD, padx=30, pady=25)
        
        # Online time row
        self._create_stat_row(self.stats_card, "🟢 Online Time", "label_present_time", Colors.ONLINE)
        
        # Away time row  
        self._create_stat_row(self.stats_card, "🔴 Away Time", "label_away_time", Colors.AWAY)
        
        # Break time row
        self._create_stat_row(self.stats_card, "☕ Break Time", "label_break_time", Colors.BREAK)
        
        # Separator
        tk.Frame(self.stats_card, bg=Colors.BG_DARK, height=1, bd=0).pack(fill="x", pady=20)
        
        # Session time row
        self._create_stat_row(self.stats_card, "⏱ Session", "label_session_time", Colors.INFO)

        # Action Area
        self.action_frame = tk.Frame(self.root, bg=Colors.BG_DARK, padx=30, pady=15)
        self.action_frame.pack(pady=10, fill="both", expand=True)

        # Break Button
        self.btn_break = tk.Button(
            self.action_frame, 
            text="☕ Take a Break", 
            command=self.toggle_break, 
            bg=Colors.WARNING, 
            fg="#333",
            activebackground=Colors.BG_CARD_HOVER,
            font=Fonts.BODY_BOLD, 
            height=2,
            relief="flat",
            bd=0,
            cursor="hand2",
            padx=20,
            pady=5
        )
        
        # End Shift Button
        self.btn_end_shift = tk.Button(
            self.action_frame,
            text="🏁 End Shift",
            command=self.show_end_shift_modal,
            bg=Colors.DANGER,
            fg="white",
            activebackground="#c0392b",
            font=Fonts.BODY_BOLD,
            height=2,
            relief="flat",
            bd=0,
            cursor="hand2",
            padx=20,
            pady=5
        )

        # Login Widgets
        self.login_frame = tk.Frame(self.action_frame, bg=Colors.BG_DARK)
        
        tk.Label(
            self.login_frame,
            text="Enter Activation Key",
            fg=Colors.TEXT_SECONDARY,
            bg=Colors.BG_DARK,
            font=Fonts.SMALL
        ).pack(pady=(0, 8))
        
        self.entry_key = tk.Entry(
            self.login_frame, 
            font=Fonts.BODY, 
            justify='center',
            bg=Colors.BG_CARD,
            fg=Colors.TEXT_PRIMARY,
            insertbackground=Colors.TEXT_PRIMARY,
            relief="flat",
            width=25
        )
        self.entry_key.pack(pady=5, ipady=10)
        
        self.btn_activate = tk.Button(
            self.login_frame, 
            text="🔓 Activate Device", 
            command=self.activate_device, 
            bg=Colors.PRIMARY, 
            fg="white",
            activebackground=Colors.SECONDARY,
            font=Fonts.BODY_BOLD, 
            height=2,
            relief="flat",
            cursor="hand2"
        )
        self.btn_activate.pack(pady=15, fill="x")

        # Footer
        self.footer_frame = tk.Frame(self.root, bg=Colors.BG_DARKER, height=40)
        self.footer_frame.pack(fill="x", side="bottom")
        self.footer_frame.pack_propagate(False)
        
        tk.Label(
            self.footer_frame,
            text=f"Device: {self.hardware_id}",
            fg=Colors.TEXT_MUTED,
            bg=Colors.BG_DARKER,
            font=Fonts.SMALL
        ).pack(pady=10)

    def _create_stat_row(self, parent, label_text, attr_name, color):
        """Create a stat row with label and value"""
        row = tk.Frame(parent, bg=Colors.BG_CARD, bd=0)
        row.pack(fill="x", pady=12)
        
        tk.Label(
            row, 
            text=label_text, 
            bg=Colors.BG_CARD, 
            fg=Colors.TEXT_SECONDARY, 
            font=Fonts.BODY
        ).pack(side="left")
        
        label = tk.Label(
            row, 
            text="00:00:00", 
            bg=Colors.BG_CARD, 
            fg=color, 
            font=Fonts.TIMER
        )
        label.pack(side="right")
        setattr(self, attr_name, label)

    # =========================================================================
    # AUTHENTICATION
    # =========================================================================

    def check_existing_login(self):
        """Check if user is already logged in (from Registry)"""
        self.activation_key = get_registry_value("activation_key")
        self.employee_name = get_registry_value("employee_name", "Employee")
        
        if self.activation_key:
            self.verify_checkin()
        else:
            self.show_login_ui()

    def show_login_ui(self):
        """Show the login interface"""
        self.label_status.config(text="Please enter your Activation Key")
        self.status_indicator.config(bg=Colors.OFFLINE)
        self.login_frame.pack(pady=20, fill="x")

    def show_main_ui(self):
        """Show the main monitoring interface"""
        self.login_frame.pack_forget()
        
        self.label_title.config(text=f"👤 {self.employee_name}")
        self.label_status.config(text="Monitoring Active", fg=Colors.ONLINE)
        self.status_indicator.config(bg=Colors.ONLINE)
        
        self.stats_card.pack(pady=10, padx=20, fill="x")
        
        self.btn_break.pack(pady=10, fill="x")
        self.btn_end_shift.pack(pady=5, fill="x")
        
        # Fetch today's time from server
        self.fetch_initial_time()
        
        # Start monitoring
        if not self.monitoring_active:
            self.monitoring_active = True
            self.session_start_time = time.time()
            Thread(target=self.monitoring_loop, daemon=True).start()
            Thread(target=self.heartbeat_loop, daemon=True).start()
            Thread(target=self.app_tracking_loop, daemon=True).start()
            self.root.after(1000, self.tick_time)

    def activate_device(self):
        """Activate device with the entered key"""
        key = self.entry_key.get().strip()
        if not key:
            messagebox.showwarning("Missing Key", "Please enter an activation key")
            return
        
        self.label_status.config(text="Activating...", fg=Colors.WARNING)
        
        try:
            payload = {"activation_key": key, "hardware_id": self.hardware_id}
            resp = requests.post(f"{SERVER_URL}/activate-device", json=payload, timeout=10)
            
            if resp.status_code == 200:
                data = resp.json()
                self.activation_key = key
                self.employee_name = data.get("employee_name", "Employee")
                
                # Save to Registry (no files!)
                set_registry_value("activation_key", key)
                set_registry_value("employee_name", self.employee_name)
                
                self.show_main_ui()
            else:
                error_msg = resp.json().get("detail", "Activation failed")
                messagebox.showerror("Activation Failed", error_msg)
                self.label_status.config(text="Activation failed", fg=Colors.DANGER)
        except Exception as e:
            messagebox.showerror("Connection Error", f"Could not reach server: {e}")
            self.label_status.config(text="Connection error", fg=Colors.DANGER)

    def verify_checkin(self):
        """Verify existing login with server"""
        self.label_status.config(text="Verifying...", fg=Colors.WARNING)
        
        try:
            payload = {"activation_key": self.activation_key}
            resp = requests.post(f"{SERVER_URL}/verify-checkin", json=payload, timeout=5)
            
            if resp.status_code == 200:
                data = resp.json()
                self.employee_name = data.get("employee_name", "Employee")
                set_registry_value("employee_name", self.employee_name)
                self.show_main_ui()
            else:
                # Session expired, show login
                self.label_status.config(text="Session expired. Please login again.", fg=Colors.WARNING)
                self.show_login_ui()
        except:
            self.label_status.config(text="Server offline. Retrying...", fg=Colors.WARNING)
            self.root.after(3000, self.verify_checkin)

    # =========================================================================
    # TIME TRACKING
    # =========================================================================

    def fetch_initial_time(self):
        """Fetch today's accumulated time from server"""
        try:
            resp = requests.get(f"{SERVER_URL}/api/employee-time/{self.activation_key}", timeout=5)
            if resp.status_code == 200:
                data = resp.json()
                self.present_seconds = data.get("present_seconds", 0)
                self.away_seconds = data.get("away_seconds", 0)
                self.break_seconds = data.get("break_seconds", 0)
                
                # Update display
                self.label_present_time.config(text=format_time(self.present_seconds))
                self.label_away_time.config(text=format_time(self.away_seconds))
                self.label_break_time.config(text=format_time(self.break_seconds))
                
                print(f"✓ Synced time - Present: {self.present_seconds}s, Away: {self.away_seconds}s")
        except Exception as e:
            print(f"Could not sync time: {e}")

    def tick_time(self):
        """Called every second to update counters"""
        if not self.monitoring_active or not self.is_running:
            return
        
        # Add 1 second to the appropriate counter
        if self.in_break_mode:
            self.break_seconds += 1
        elif self.current_status == "Present":
            self.present_seconds += 1
        elif self.current_status == "Away":
            self.away_seconds += 1
        
        # Update display
        self.label_present_time.config(text=format_time(self.present_seconds))
        self.label_away_time.config(text=format_time(self.away_seconds))
        self.label_break_time.config(text=format_time(self.break_seconds))
        
        if self.session_start_time:
            session_elapsed = time.time() - self.session_start_time
            self.label_session_time.config(text=format_time(session_elapsed))
        
        # Schedule next tick
        if self.is_running:
            self.root.after(1000, self.tick_time)

    # =========================================================================
    # BREAK & SHIFT MANAGEMENT
    # =========================================================================

    def toggle_break(self):
        """Toggle break mode"""
        if self.in_break_mode:
            # Resume Work
            self.in_break_mode = False
            self.current_status = "Present"
            self.send_log("BREAK_END")
            self.btn_break.config(text="☕ Take a Break", bg=Colors.WARNING, fg="#333")
            self.label_status.config(text="Monitoring Active", fg=Colors.ONLINE)
            self.status_indicator.config(bg=Colors.ONLINE)
        else:
            # Start Break
            self.in_break_mode = True
            self.send_log("BREAK_START")
            self.btn_break.config(text="▶ Resume Work", bg=Colors.PRIMARY, fg="white")
            self.label_status.config(text="On Break", fg=Colors.BREAK)
            self.status_indicator.config(bg=Colors.BREAK)

    def show_end_shift_modal(self):
        """Show confirmation modal for ending shift"""
        modal = tk.Toplevel(self.root)
        modal.title("End Shift")
        modal.geometry("380x280")
        modal.configure(bg=Colors.BG_CARD)
        modal.resizable(False, False)
        modal.transient(self.root)
        modal.grab_set()
        
        # Center the modal
        modal.update_idletasks()
        x = self.root.winfo_x() + (self.root.winfo_width() - 380) // 2
        y = self.root.winfo_y() + (self.root.winfo_height() - 280) // 2
        modal.geometry(f"380x280+{x}+{y}")
        
        # Content
        tk.Label(modal, text="⚠️", font=("Segoe UI", 48), bg=Colors.BG_CARD, fg=Colors.WARNING).pack(pady=15)
        tk.Label(modal, text="End Shift?", font=Fonts.HEADING, bg=Colors.BG_CARD, fg=Colors.TEXT_PRIMARY).pack()
        tk.Label(modal, text="This will close the monitoring app.", font=Fonts.SMALL, bg=Colors.BG_CARD, fg=Colors.TEXT_MUTED).pack(pady=5)
        
        if self.session_start_time:
            session_duration = time.time() - self.session_start_time
            tk.Label(modal, text=f"Session: {format_time(session_duration)}", font=Fonts.BODY_BOLD, bg=Colors.BG_CARD, fg=Colors.INFO).pack(pady=5)
        
        # Buttons
        btn_frame = tk.Frame(modal, bg=Colors.BG_CARD)
        btn_frame.pack(pady=20, fill="x", padx=30)
        
        tk.Button(
            btn_frame, text="Cancel", command=modal.destroy,
            bg=Colors.BG_DARK, fg=Colors.TEXT_PRIMARY,
            font=Fonts.BODY, relief="flat", width=12, cursor="hand2"
        ).pack(side="left", padx=5)
        
        tk.Button(
            btn_frame, text="End Shift", command=lambda: self.end_shift(modal),
            bg=Colors.DANGER, fg="white",
            font=Fonts.BODY_BOLD, relief="flat", width=12, cursor="hand2"
        ).pack(side="right", padx=5)

    def end_shift(self, modal=None):
        """End the shift and close the app"""
        self.send_log("WORK_END")
        self.is_running = False
        self.monitoring_active = False
        if modal:
            modal.destroy()
        self.root.quit()

    # =========================================================================
    # MONITORING & SERVER COMMUNICATION
    # =========================================================================

    def monitoring_loop(self):
        """Main camera monitoring loop"""
        model = YOLO("yolo11n.pt")
        
        # Try to find a working camera index
        cap = None
        for index in range(2):
            print(f"Testing camera index {index}...")
            temp_cap = cv2.VideoCapture(index, cv2.CAP_DSHOW)
            if temp_cap.isOpened():
                ret, _ = temp_cap.read()
                if ret:
                    print(f"✅ Found working camera at index {index}")
                    cap = temp_cap
                    break
                else:
                    temp_cap.release()
            
        if cap is None or not cap.isOpened():
            print("❌ No working camera found! Trying default backend...")
            cap = cv2.VideoCapture(0)
            if not cap.isOpened():
                print("❌ CRITICAL: Could not open any camera.")
                self.root.after(0, lambda: messagebox.showerror("Camera Error", "No camera detected. Please check your connection."))
                return

        consecutive_away = 0
        consecutive_present = 0
        
        while self.is_running:
            try:
                if self.in_break_mode:
                    time.sleep(1)
                    continue
                
                ret, frame = cap.read()
                if not ret:
                    print("⚠️ Failed to grab frame")
                    time.sleep(1)
                    continue
                
                results = model(frame, verbose=False)
                person_detected = False
                
                for result in results:
                    for box in result.boxes:
                        if int(box.cls) == 0 and float(box.conf) > CONFIDENCE_THRESHOLD:
                            person_detected = True
                            break
                
                if person_detected:
                    print("👤 Person Detected", end='\r')
                    consecutive_present += 1
                    consecutive_away = 0
                    
                    if consecutive_present >= PRESENT_LIMIT and self.current_status != "Present":
                        self.current_status = "Present"
                        self.send_log("Present")
                        self.root.after(0, lambda: self.label_status.config(text="Monitoring Active", fg=Colors.ONLINE))
                        self.root.after(0, lambda: self.status_indicator.config(bg=Colors.ONLINE))
                        self.root.after(0, self.hide_warning_modal)

                else:
                    print("👻 No Person     ", end='\r')
                    consecutive_present = 0 # Reset present counter
                    consecutive_away += 1
                    
                    if consecutive_away >= AWAY_LIMIT and self.current_status != "Away":
                        self.current_status = "Away"
                        self.send_log("Away")
                        self.root.after(0, lambda: self.label_status.config(text="Away Detected", fg=Colors.AWAY))
                        self.root.after(0, lambda: self.status_indicator.config(bg=Colors.AWAY))
                        self.root.after(0, self.alert_user)
                        self.root.after(0, self.show_warning_modal)
                        
            except Exception as e:
                print(f"❌ Error in monitoring loop: {e}")
                time.sleep(1)

            
            time.sleep(1)
        
        cap.release()

    def show_warning_modal(self):
        """Show a large warning modal when away"""
        if hasattr(self, 'warning_modal') and self.warning_modal and self.warning_modal.winfo_exists():
            return
            
        self.warning_modal = tk.Toplevel(self.root)
        self.warning_modal.title("⚠️ Alert")
        self.warning_modal.configure(bg=Colors.DANGER)
        self.warning_modal.attributes('-topmost', True)
        self.warning_modal.overrideredirect(True) # Remove title bar
        
        # Center on screen
        w, h = 600, 300
        x = (self.root.winfo_screenwidth() - w) // 2
        y = (self.root.winfo_screenheight() - h) // 2
        self.warning_modal.geometry(f"{w}x{h}+{x}+{y}")
        
        tk.Label(
            self.warning_modal, 
            text="⚠️", 
            font=("Segoe UI", 80), 
            bg=Colors.DANGER, 
            fg="white"
        ).pack(pady=10)
        
        tk.Label(
            self.warning_modal, 
            text="YOU ARE AWAY!", 
            font=("Segoe UI", 32, "bold"), 
            bg=Colors.DANGER, 
            fg="white"
        ).pack()
        
        tk.Label(
            self.warning_modal, 
            text="Please return to your station.", 
            font=("Segoe UI", 16), 
            bg=Colors.DANGER, 
            fg="white"
        ).pack(pady=10)

    def hide_warning_modal(self):
        """Hide the warning modal"""
        if hasattr(self, 'warning_modal') and self.warning_modal and self.warning_modal.winfo_exists():
            self.warning_modal.destroy()
            self.warning_modal = None

    def alert_user(self):
        """Alert user when away detected"""
        try:
            # Visual alert (Restore window)
            self.root.deiconify()
            self.root.state('normal')
            self.root.lift()
            self.root.focus_force()
            
        except Exception as e:
            print(f"Alert error: {e}")

    def heartbeat_loop(self):
        """Send heartbeat to server every 30 seconds"""
        while self.is_running:
            try:
                payload = {"activation_key": self.activation_key}
                resp = requests.post(f"{SERVER_URL}/heartbeat", json=payload, timeout=5)
                if resp.status_code == 200:
                    print("💓 Heartbeat OK")
            except Exception as e:
                print(f"❌ Heartbeat failed: {e}")
            
            time.sleep(30)

    def app_tracking_loop(self):
        """Track which app is currently active and send to server"""
        last_app = None
        last_title = None
        app_start_time = time.time()
        
        while self.is_running:
            try:
                # Get active window info
                hwnd = win32gui.GetForegroundWindow()
                window_title = win32gui.GetWindowText(hwnd)
                
                # Get process name
                _, pid = win32process.GetWindowThreadProcessId(hwnd)
                try:
                    process = psutil.Process(pid)
                    app_name = process.name()
                except:
                    app_name = "unknown.exe"
                
                # If app changed, send previous app's usage
                if app_name != last_app and last_app is not None:
                    duration = int(time.time() - app_start_time)
                    if duration > 2:  # Only log if used for >2 seconds
                        self.send_app_log(last_app, last_title, duration)
                    app_start_time = time.time()
                
                last_app = app_name
                last_title = window_title
                
            except Exception as e:
                print(f"App tracking error: {e}")
            
            time.sleep(5)  # Check every 5 seconds
    
    def send_app_log(self, app_name, window_title, duration):
        """Send app usage log to server"""
        try:
            payload = {
                "activation_key": self.activation_key,
                "app_name": app_name,
                "window_title": window_title[:200] if window_title else "",  # Truncate long titles
                "duration_seconds": duration
            }
            resp = requests.post(f"{SERVER_URL}/api/app-log", json=payload, timeout=3)
            if resp.status_code == 200:
                print(f"📱 App log: {app_name} ({duration}s)")
        except:
            pass  # Silent fail for app logs


    def send_log(self, status):
        """Send activity log to server"""
        if self.in_break_mode and status == "Present":
            return
        try:
            print(f"📤 Sending status: {status}...", end='')
            resp = requests.post(
                f"{SERVER_URL}/log-activity", 
                json={"activation_key": self.activation_key, "status": status}, 
                timeout=2
            )
            if resp.status_code == 200:
                print(" ✅ OK")
            else:
                print(f" ❌ Failed ({resp.status_code})")
        except Exception as e:
            print(f" ❌ Error: {e}")

    def on_closing(self):
        """Handle window close"""
        self.show_end_shift_modal()

# =============================================================================
# MAIN ENTRY POINT
# =============================================================================

if __name__ == "__main__":
    root = tk.Tk()
    app = EmployeeApp(root)
    root.mainloop()