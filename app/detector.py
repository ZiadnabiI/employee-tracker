import cv2
import time
import requests
import tkinter as tk
from tkinter import messagebox
from threading import Thread
from ultralytics import YOLO
import os
import json
import uuid
import subprocess

# --- Configuration ---
SERVER_URL = os.getenv("SERVER_URL", "https://employee-tracker-up30.onrender.com")
CONFIDENCE_THRESHOLD = 0.5
AWAY_LIMIT = 10 
SECRETS_FILE = "secrets.json"
DEVICE_ID_FILE = "device_id.txt"

def hide_file(filepath):
    """Hide a file in Windows"""
    if os.path.exists(filepath) and os.name == 'nt':
        try:
            subprocess.run(['attrib', '+H', filepath], check=True, capture_output=True)
        except:
            pass

def format_time(seconds):
    """Format seconds into HH:MM:SS"""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"

class EmployeeApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Employee Presence Monitor")
        self.root.geometry("400x600")
        self.root.configure(bg="#f0f2f5")
        
        self.activation_key = None
        self.hardware_id = self.get_hardware_id()
        self.is_running = True
        self.monitoring_active = False
        self.in_break_mode = False
        self.employee_name = "Unknown"
        
        # Time tracking - simple counters
        self.session_start_time = None
        self.present_seconds = 0
        self.away_seconds = 0
        self.break_seconds = 0
        self.last_tick = None
        self.current_status = "Present"

        self.build_ui()
        self.check_existing_login()

    def get_hardware_id(self):
        if os.path.exists(DEVICE_ID_FILE):
            with open(DEVICE_ID_FILE, "r") as f:
                return f.read().strip()
        else:
            hw_id = f"HW-{uuid.uuid4().hex[:8].upper()}"
            with open(DEVICE_ID_FILE, "w") as f:
                f.write(hw_id)
            hide_file(DEVICE_ID_FILE)
            return hw_id

    def build_ui(self):
        # Header
        self.header_frame = tk.Frame(self.root, bg="#1877f2", height=60)
        self.header_frame.pack(fill="x")
        self.label_title = tk.Label(self.header_frame, text="Employee Tracker", 
                                    fg="white", bg="#1877f2", font=("Segoe UI", 14, "bold"))
        self.label_title.pack(pady=15)

        # Status Area
        self.status_frame = tk.Frame(self.root, bg="#f0f2f5")
        self.status_frame.pack(pady=10, fill="x")
        
        self.label_status = tk.Label(self.status_frame, text="Initializing...", 
                                     fg="#65676b", bg="#f0f2f5", font=("Segoe UI", 11))
        self.label_status.pack()

        # Time Stats Frame
        self.stats_frame = tk.Frame(self.root, bg="white", padx=20, pady=15)
        
        # Online time
        row1 = tk.Frame(self.stats_frame, bg="white")
        row1.pack(fill="x", pady=8)
        tk.Label(row1, text="🟢 Online Time:", bg="white", fg="#333", 
                 font=("Segoe UI", 12)).pack(side="left")
        self.label_present_time = tk.Label(row1, text="00:00:00", bg="white", 
                                           fg="#28a745", font=("Segoe UI", 12, "bold"))
        self.label_present_time.pack(side="right")
        
        # Away time
        row2 = tk.Frame(self.stats_frame, bg="white")
        row2.pack(fill="x", pady=8)
        tk.Label(row2, text="🔴 Away Time:", bg="white", fg="#333", 
                 font=("Segoe UI", 12)).pack(side="left")
        self.label_away_time = tk.Label(row2, text="00:00:00", bg="white", 
                                        fg="#dc3545", font=("Segoe UI", 12, "bold"))
        self.label_away_time.pack(side="right")
        
        # Break time
        row3 = tk.Frame(self.stats_frame, bg="white")
        row3.pack(fill="x", pady=8)
        tk.Label(row3, text="☕ Break Time:", bg="white", fg="#333", 
                 font=("Segoe UI", 12)).pack(side="left")
        self.label_break_time = tk.Label(row3, text="00:00:00", bg="white", 
                                         fg="#ff8c00", font=("Segoe UI", 12, "bold"))
        self.label_break_time.pack(side="right")
        
        # Session time
        row4 = tk.Frame(self.stats_frame, bg="white")
        row4.pack(fill="x", pady=8)
        tk.Label(row4, text="⏱ Session:", bg="white", fg="#333", 
                 font=("Segoe UI", 12)).pack(side="left")
        self.label_session_time = tk.Label(row4, text="00:00:00", bg="white", 
                                           fg="#17a2b8", font=("Segoe UI", 12, "bold"))
        self.label_session_time.pack(side="right")

        # Action Area
        self.action_frame = tk.Frame(self.root, bg="white", padx=20, pady=20)
        self.action_frame.pack(pady=10, padx=20, fill="both", expand=True)

        # Break Button
        self.btn_break = tk.Button(self.action_frame, text="☕ Take a Break", 
                                   command=self.toggle_break, bg="#ffc107", fg="black", 
                                   font=("Segoe UI", 12, "bold"), height=2, state="disabled")
        
        # Login Widgets
        self.entry_key = tk.Entry(self.action_frame, font=("Segoe UI", 14), justify='center')
        self.btn_activate = tk.Button(self.action_frame, text="Activate Device", 
                                      command=self.activate_device, bg="#42b72a", fg="white", 
                                      font=("Segoe UI", 12, "bold"), height=2)

    def show_end_shift_modal(self):
        """Show confirmation modal for ending shift"""
        modal = tk.Toplevel(self.root)
        modal.title("End Shift")
        modal.geometry("400x300")
        modal.configure(bg="white")
        modal.resizable(False, False)
        modal.transient(self.root)
        modal.grab_set()
        
        # Center the modal
        modal.update_idletasks()
        x = self.root.winfo_x() + (self.root.winfo_width() - 400) // 2
        y = self.root.winfo_y() + (self.root.winfo_height() - 300) // 2
        modal.geometry(f"400x300+{x}+{y}")
        
        # Content
        tk.Label(modal, text="⚠️", font=("Segoe UI", 48), bg="white").pack(pady=15)
        tk.Label(modal, text="End Shift?", font=("Segoe UI", 16, "bold"), bg="white").pack()
        tk.Label(modal, text="This will close the monitoring app.", 
                 font=("Segoe UI", 11), bg="white", fg="#666").pack(pady=10)
        
        if self.session_start_time:
            session_duration = time.time() - self.session_start_time
            tk.Label(modal, text=f"Session: {format_time(session_duration)}", 
                     font=("Segoe UI", 12, "bold"), bg="white", fg="#17a2b8").pack(pady=5)
        
        # Buttons frame with more space
        btn_frame = tk.Frame(modal, bg="white")
        btn_frame.pack(pady=25, fill="x", padx=40)
        
        def confirm_end_shift():
            modal.destroy()
            self.end_shift()
        
        def cancel():
            modal.destroy()
        
        # BIGGER BUTTONS with proper styling
        cancel_btn = tk.Button(btn_frame, text="Cancel", command=cancel, 
                               bg="#cccccc", fg="black", font=("Segoe UI", 14, "bold"),
                               width=10, height=2, relief="raised", cursor="hand2")
        cancel_btn.pack(side="left", padx=10)
        
        end_btn = tk.Button(btn_frame, text="End Shift", command=confirm_end_shift, 
                            bg="#e74c3c", fg="white", font=("Segoe UI", 14, "bold"),
                            width=10, height=2, relief="raised", cursor="hand2")
        end_btn.pack(side="right", padx=10)

    def end_shift(self):
        """Properly close the app without hanging"""
        # Stop all loops first
        self.is_running = False
        self.monitoring_active = False
        
        # Send log in background
        try:
            self.send_log("SHUTDOWN")
        except:
            pass
        
        # Give monitoring thread time to stop
        time.sleep(0.5)
        
        # Force close OpenCV windows
        try:
            cv2.destroyAllWindows()
        except:
            pass
        
        # Force exit the application
        try:
            self.root.quit()
        except:
            pass
        
        # Force terminate if still running
        import os
        os._exit(0)

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

    def check_existing_login(self):
        if os.path.exists(SECRETS_FILE):
            try:
                with open(SECRETS_FILE, "r") as f:
                    data = json.load(f)
                    self.activation_key = data.get("activation_key")
                    self.employee_name = data.get("employee_name", "Employee")
                    if self.activation_key:
                        self.verify_checkin()
                        return
            except:
                pass
        self.show_login_ui()

    def show_login_ui(self):
        self.label_status.config(text="Please enter your Activation Key")
        self.entry_key.pack(pady=10, fill="x")
        self.btn_activate.pack(pady=10, fill="x")

    def show_main_ui(self):
        self.entry_key.pack_forget()
        self.btn_activate.pack_forget()
        
        self.label_title.config(text=f"Welcome, {self.employee_name}")
        self.label_status.config(text="● Monitoring Active", fg="green")
        
        self.stats_frame.pack(pady=10, padx=20, fill="x")
        
        self.btn_break.config(state="normal", text="☕ Take a Break", bg="#ffc107")
        self.btn_break.pack(pady=15, fill="x")
        
        # Fetch today's accumulated time from server
        self.fetch_initial_time()
        
        # Initialize session timing
        self.session_start_time = time.time()
        self.current_status = "Present"
        
        # Start monitoring
        if not self.monitoring_active:
            self.monitoring_active = True
            Thread(target=self.monitoring_loop, daemon=True).start()
            # Start the timer tick
            self.root.after(1000, self.tick_time)
    
    def fetch_initial_time(self):
        """Fetch today's accumulated time from server to continue where we left off"""
        try:
            resp = requests.get(f"{SERVER_URL}/api/employee-time/{self.activation_key}", timeout=5)
            if resp.status_code == 200:
                data = resp.json()
                self.present_seconds = data.get("present_seconds", 0)
                self.away_seconds = data.get("away_seconds", 0)
                self.break_seconds = data.get("break_seconds", 0)
                print(f"Synced time from server: Present={self.present_seconds}s, Away={self.away_seconds}s, Break={self.break_seconds}s")
                # Update labels immediately
                self.label_present_time.config(text=format_time(self.present_seconds))
                self.label_away_time.config(text=format_time(self.away_seconds))
                self.label_break_time.config(text=format_time(self.break_seconds))
            else:
                # If server fails, start from zero
                self.present_seconds = 0
                self.away_seconds = 0
                self.break_seconds = 0
        except Exception as e:
            print(f"Failed to fetch initial time: {e}")
            # Start from zero if server unavailable
            self.present_seconds = 0
            self.away_seconds = 0
            self.break_seconds = 0

    def activate_device(self):
        key = self.entry_key.get().strip()
        if not key:
            messagebox.showwarning("Input Error", "Please enter an activation key")
            return

        try:
            payload = {"activation_key": key, "hardware_id": self.hardware_id}
            resp = requests.post(f"{SERVER_URL}/activate-device", json=payload, timeout=5)
            
            if resp.status_code == 200:
                data = resp.json()
                self.activation_key = key
                self.employee_name = data.get("employee_name", "Employee")
                
                with open(SECRETS_FILE, "w") as f:
                    json.dump({"activation_key": key, "employee_name": self.employee_name}, f)
                hide_file(SECRETS_FILE)
                
                self.show_main_ui()
            else:
                messagebox.showerror("Activation Failed", resp.json().get("detail", "Unknown Error"))
        except Exception as e:
            messagebox.showerror("Connection Error", f"Could not reach server: {e}")

    def verify_checkin(self):
        self.label_status.config(text="Verifying...")
        try:
            payload = {"activation_key": self.activation_key}
            resp = requests.post(f"{SERVER_URL}/verify-checkin", json=payload, timeout=5)
            
            if resp.status_code == 200:
                data = resp.json()
                self.employee_name = data.get("employee_name", "Employee")
                self.show_main_ui()
            else:
                self.label_status.config(text="Session Expired. Please login again.")
                self.show_login_ui()
        except:
             self.label_status.config(text="Server Offline. Retrying...")
             self.root.after(3000, self.verify_checkin)

    def toggle_break(self):
        if self.in_break_mode:
            # Resume Work
            self.in_break_mode = False
            self.current_status = "Present"
            self.send_log("BREAK_END")
            self.btn_break.config(text="☕ Take a Break", bg="#ffc107")
            self.label_status.config(text="● Monitoring Active", fg="green")
        else:
            # Start Break
            self.in_break_mode = True
            self.send_log("BREAK_START")
            self.btn_break.config(text="▶ Resume Work", bg="#42b72a")
            self.label_status.config(text="⏸ On Break", fg="orange")

    def send_log(self, status):
        if self.in_break_mode and status == "Present":
            return
        try:
            requests.post(f"{SERVER_URL}/log-activity", 
                          json={"activation_key": self.activation_key, "status": status}, timeout=2)
        except:
            pass

    def monitoring_loop(self):
        model = YOLO('yolov8n.pt')
        cap = None 
        last_heartbeat = 0
        last_seen_time = time.time()
        camera_retries = 0
        max_retries = 5
        
        while self.is_running:
            if self.in_break_mode:
                if cap is not None:
                    cap.release()
                    cv2.destroyAllWindows()
                    cap = None
                time.sleep(0.5)
                continue
            
            # Try to open camera with different backends
            if cap is None:
                # Try DirectShow first (more reliable on Windows)
                cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
                if not cap.isOpened():
                    # Fallback to default MSMF
                    cap = cv2.VideoCapture(0)
                if not cap.isOpened():
                    camera_retries += 1
                    if camera_retries <= max_retries:
                        time.sleep(2)
                        continue
                    else:
                        # Camera not available, keep trying
                        time.sleep(5)
                        camera_retries = 0
                        continue
                else:
                    camera_retries = 0
            
            ret, frame = cap.read()
            if not ret:
                # Release and retry
                cap.release()
                cap = None
                time.sleep(1)
                continue

            results = model(frame, classes=[0], conf=CONFIDENCE_THRESHOLD, verbose=False)
            person_detected = len(results[0].boxes) > 0
            now = time.time()
            
            if person_detected:
                last_seen_time = now
                if self.current_status == "Away":
                    self.current_status = "Present"
                    self.send_log("Present")
            else:
                if (now - last_seen_time) > AWAY_LIMIT and self.current_status == "Present":
                    self.current_status = "Away"
                    self.send_log("Away")

            # Visual feedback
            display_frame = frame.copy()
            color = (0, 255, 0) if self.current_status == "Present" else (0, 0, 255)
            cv2.putText(display_frame, f"Status: {self.current_status}", (10, 30), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)
            
            if self.current_status == "Away":
                overlay = display_frame.copy()
                cv2.rectangle(overlay, (0, 0), (display_frame.shape[1], display_frame.shape[0]), (0, 0, 255), -1)
                cv2.addWeighted(overlay, 0.3, display_frame, 0.7, 0, display_frame)
            
            # Heartbeat
            if self.current_status == "Present" and (now - last_heartbeat > 5):
                Thread(target=self.send_log, args=("Present",)).start()
                last_heartbeat = now

            small_frame = cv2.resize(display_frame, (320, 240))
            cv2.imshow('Live Monitor', small_frame)
            cv2.waitKey(1)
                
        if cap:
            cap.release()
        cv2.destroyAllWindows()

if __name__ == "__main__":
    root = tk.Tk()
    app = EmployeeApp(root)
    root.protocol("WM_DELETE_WINDOW", app.show_end_shift_modal)
    root.mainloop()