import cv2
import time
import requests
import tkinter as tk
from tkinter import messagebox, simpledialog
from threading import Thread
from ultralytics import YOLO
import os
import json
import uuid

# --- Configuration ---
# --- Configuration ---
# Use SERVER_URL from environment for production, fallback to localhost for testing
SERVER_URL = os.getenv("SERVER_URL", "http://localhost:8000")
CONFIDENCE_THRESHOLD = 0.5
AWAY_LIMIT = 10 
SECRETS_FILE = "secrets.json"

class EmployeeApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Employee Presence Monitor")
        self.root.geometry("400x550")
        self.root.configure(bg="#f0f2f5")
        
        self.activation_key = None
        self.hardware_id = self.get_hardware_id()
        self.is_running = True
        self.monitoring_active = False
        self.in_break_mode = False
        self.employee_name = "Unknown"

        # --- UI Build ---
        self.build_ui()

        # --- Check Login ---
        self.check_existing_login()

    def get_hardware_id(self):
        # Simple unique ID for this device
        if os.path.exists("device_id.txt"):
            with open("device_id.txt", "r") as f:
                return f.read().strip()
        else:
            hw_id = f"HW-{uuid.uuid4().hex[:8].upper()}"
            with open("device_id.txt", "w") as f:
                f.write(hw_id)
            return hw_id

    def build_ui(self):
        # Header
        self.header_frame = tk.Frame(self.root, bg="#1877f2", height=60)
        self.header_frame.pack(fill="x")
        self.label_title = tk.Label(self.header_frame, text="Employee Tracker", 
                                    fg="white", bg="#1877f2", font=("Segoe UI", 12, "bold"))
        self.label_title.pack(pady=15)

        # Status Area
        self.status_frame = tk.Frame(self.root, bg="#f0f2f5")
        self.status_frame.pack(pady=20, fill="x")
        
        self.label_status = tk.Label(self.status_frame, text="Initializing...", 
                                     fg="#65676b", bg="#f0f2f5", font=("Segoe UI", 10))
        self.label_status.pack()

        # Action Area (Login or Controls)
        self.action_frame = tk.Frame(self.root, bg="white", padx=20, pady=20)
        self.action_frame.pack(pady=10, padx=20, fill="both", expand=True)

        # Buttons (Hidden initially)
        self.btn_break = tk.Button(self.action_frame, text="☕ Take a Break", 
                                   command=self.toggle_break, bg="#ffc107", fg="black", 
                                   font=("Segoe UI", 11), state="disabled")
        
        # Login Widgets
        self.entry_key = tk.Entry(self.action_frame, font=("Segoe UI", 12), justify='center')
        self.btn_activate = tk.Button(self.action_frame, text="Activate Device", 
                                      command=self.activate_device, bg="#42b72a", fg="white", 
                                      font=("Segoe UI", 11, "bold"))

    def check_existing_login(self):
        if os.path.exists(SECRETS_FILE):
            try:
                with open(SECRETS_FILE, "r") as f:
                    data = json.load(f)
                    self.activation_key = data.get("activation_key")
                    if self.activation_key:
                        self.verify_checkin()
                        return
            except:
                pass # Corrupt file?
        
        # No valid login found
        self.show_login_ui()

    def show_login_ui(self):
        self.label_status.config(text="Please enter your Activation Key")
        self.entry_key.pack(pady=10, fill="x")
        self.btn_activate.pack(pady=10, fill="x")

    def show_main_ui(self):
        # Hide login
        self.entry_key.pack_forget()
        self.btn_activate.pack_forget()
        
        # Show Main Controls
        self.label_title.config(text=f"Welcome, {self.employee_name}")
        self.label_status.config(text="● Monitoring Active", fg="green")
        
        self.btn_break.config(state="normal", text="☕ Take a Break", bg="#ffc107")
        self.btn_break.pack(pady=20, fill="x")
        
        # Start Monitoring
        if not self.monitoring_active:
            self.monitoring_active = True
            Thread(target=self.monitoring_loop, daemon=True).start()

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
                
                # Save locally
                with open(SECRETS_FILE, "w") as f:
                    json.dump({"activation_key": key, "employee_name": self.employee_name}, f)
                
                self.show_main_ui()
            else:
                messagebox.showerror("Activation Failed", resp.json().get("detail", "Unknown Error"))
        except Exception as e:
            messagebox.showerror("Connection Error", f"Could not reach server: {e}")

    def verify_checkin(self):
        self.label_status.config(text="Verifying Check-in...")
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
            # We set flag to False AFTER sending the log, to ensure no "Present" slips in before "BREAK_END" (though less critical here)
            # Actually, to be safe, we want monitoring to resume after we signal Break End.
            self.send_log("BREAK_END")
            self.in_break_mode = False
            self.btn_break.config(text="☕ Take a Break", bg="#ffc107")
            self.label_status.config(text="● Monitoring Resumed", fg="green")
            # Logic for restarting camera is handled in the loop
        else:
            # Start Break
            # Set flag FIRST to stop the monitoring loop immediately
            self.in_break_mode = True
            self.send_log("BREAK_START")
            self.btn_break.config(text="▶ Resume Work", bg="#42b72a")
            self.label_status.config(text="⏸ On Break (Privacy Mode On)", fg="orange")
            # Logic for closing camera is handled in the loop

    def send_log(self, status):
        # Prevent "Present" logs if we are in break mode (handling race conditions)
        if self.in_break_mode and status == "Present":
            return

        try:
            requests.post(f"{SERVER_URL}/log-activity", 
                          json={"activation_key": self.activation_key, "status": status})
        except:
            pass

    def monitoring_loop(self):
        model = YOLO('yolov8n.pt')
        cap = None 
        
        last_heartbeat = 0
        last_seen_time = time.time()
        current_status = "Present" # Assume present initially or wait for detection
        
        while self.is_running:
            # --- Break Mode Handling ---
            if self.in_break_mode:
                if cap is not None:
                    cap.release()
                    cv2.destroyAllWindows()
                    cap = None
                time.sleep(1)
                continue
            
            # --- Active Monitoring ---
            if cap is None:
                cap = cv2.VideoCapture(0)
            
            ret, frame = cap.read()
            if not ret: 
                time.sleep(1)
                continue

            # Detect
            results = model(frame, classes=[0], conf=CONFIDENCE_THRESHOLD, verbose=False)
            person_detected = len(results[0].boxes) > 0
            
            # --- Status Logic (Presense / Away) ---
            if person_detected:
                last_seen_time = time.time()
                if current_status == "Away":
                    self.send_log("Present") # Back to work
                    current_status = "Present"
            else:
                elapsed_away = time.time() - last_seen_time
                if elapsed_away > AWAY_LIMIT and current_status == "Present":
                    self.send_log("Away") # Gone for too long
                    current_status = "Away"

            # --- Feedback UI ---
            display_frame = frame.copy()
            if current_status == "Away":
                # Red overlay
                overlay = display_frame.copy()
                cv2.rectangle(overlay, (0, 0), (display_frame.shape[1], display_frame.shape[0]), (0, 0, 255), -1)
                cv2.addWeighted(overlay, 0.3, display_frame, 0.7, 0, display_frame)
                cv2.putText(display_frame, "AWAY / MISSING", (50, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
            
            # --- Heartbeat (Only if present) ---
            # Send heartbeat every 5s if status is Present (regardless of ephemeral detection loss < 10s)
            if current_status == "Present" and (time.time() - last_heartbeat > 5):
                Thread(target=self.send_log, args=("Present",)).start()
                last_heartbeat = time.time()

            # Resize for smaller window
            small_frame = cv2.resize(display_frame, (320, 240))
            
            # Show Feed
            cv2.imshow('Live Monitor', small_frame)
            if cv2.waitKey(1) & 0xFF == ord('q'): break
                
        if cap:
            cap.release()
        cv2.destroyAllWindows()

if __name__ == "__main__":
    root = tk.Tk()
    app = EmployeeApp(root)
    root.mainloop()