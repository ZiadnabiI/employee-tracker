import datetime
import secrets
import string
import os
from typing import List, Dict, Optional
from fastapi import FastAPI, Request, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from pydantic import BaseModel
from database import SessionLocal, EmployeeLog, Employee, Base, engine

# Ensure tables are created
Base.metadata.create_all(bind=engine)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Health check endpoint for uptime monitoring (e.g., UptimeRobot)
@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "employee-tracker"}

# Dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# --- Pydantic Models ---
class EmployeeCreate(BaseModel):
    name: str
    department: str = None

class DeviceActivation(BaseModel):
    activation_key: str
    hardware_id: str

class ActivityLog(BaseModel):
    activation_key: str
    status: str # WORK_START, BREAK_START, BREAK_END, SHUTDOWN, HEARTBEAT

# --- 1. Admin Endpoint: Create Employee & Generate Key ---
@app.post("/admin/create-employee")
async def create_employee(employee: EmployeeCreate, db: Session = Depends(get_db)):
    # Generate unique key (e.g., KEY-5599)
    # Simple 4-digit suffix for readability as per diagram, but unique
    while True:
        suffix = ''.join(secrets.choice(string.digits) for _ in range(4))
        key = f"KEY-{suffix}"
        if not db.query(Employee).filter(Employee.activation_key == key).first():
            break
    
    new_employee = Employee(
        name=employee.name,
        department=employee.department,
        activation_key=key,
        is_active=0
    )
    db.add(new_employee)
    db.commit()
    db.refresh(new_employee)
    
    print(f"ADMIN: Created employee {employee.name} with key {key}")
    return {"activation_key": key, "name": employee.name}

# --- 2. Device Activation (First Run) ---
@app.post("/activate-device")
async def activate_device(data: DeviceActivation, db: Session = Depends(get_db)):
    employee = db.query(Employee).filter(Employee.activation_key == data.activation_key).first()
    
    if not employee:
        raise HTTPException(status_code=404, detail="Invalid activation key")
    
    # Check if already active on another hardware (optional strictness)
    # If hardware_id is set and different, reject. If null, bind it.
    if employee.hardware_id and employee.hardware_id != data.hardware_id:
        # For this implementation, maybe we allow re-binding or reject?
        # Let's reject to prevent sharing, unless admin resets.
        # But for simplicity, we might just warn. Let's stick to strict binding.
        raise HTTPException(status_code=403, detail="Key already bound to another device")
        
    employee.hardware_id = data.hardware_id
    employee.is_active = 1
    db.commit()
    
    print(f"ACTIVATION: Device activated for {employee.name} on HWID {data.hardware_id}")
    return {"status": "success", "employee_name": employee.name, "token": data.activation_key} # returning key as token for simplicity

# --- 3. Activity Logging & Heartbeat ---
@app.post("/log-activity")
async def log_activity(log: ActivityLog, db: Session = Depends(get_db)):
    employee = db.query(Employee).filter(Employee.activation_key == log.activation_key).first()
    if not employee:
        raise HTTPException(status_code=401, detail="Unauthorized")

    # If status is just heartbeat, maybe we don't save to DB every time to save space?
    # Or we save it to track online presence. 
    # Diagram says "Heartbeat (Status: Present)".
    # Let's save it.
    
    new_log = EmployeeLog(
        employee_name=employee.name,
        status=log.status
    )
    db.add(new_log)
    db.commit()
    
    print(f"LOG: {employee.name} -> {log.status}")

    # --- Slack Notification Logic ---
    # Only notify for important status changes to reduce noise
    IMPORTANT_STATUSES = ["WORK_START", "BREAK_START", "BREAK_END", "Away"]
    
    # Get Slack webhook from environment variable (set in Render dashboard)
    SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL")

    if log.status in IMPORTANT_STATUSES and SLACK_WEBHOOK_URL:
        try:
            import requests
            slack_msg = {
                "text": f"📢 *{employee.name}* status update: *{log.status}*"
            }
            # Custom messages
            if log.status == "Away":
                slack_msg["text"] = f"⚠️ *{employee.name}* is marked as **Away/Missing**!"
            elif log.status == "BREAK_START":
                 slack_msg["text"] = f"☕ *{employee.name}* is taking a break."
            elif log.status == "WORK_START":
                 slack_msg["text"] = f"🟢 *{employee.name}* has started work."

            requests.post(SLACK_WEBHOOK_URL, json=slack_msg, timeout=2)
        except Exception as e:
            print(f"Slack Error: {e}")

    # Return active status so client knows to keep running
    return {"status": "ACTIVE"}

# --- 7. Serve Dashboard ---
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

templates = Jinja2Templates(directory="templates")

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

# --- 4. Verify Check-in (Start of Shift) ---
@app.post("/verify-checkin")
async def verify_checkin(data: dict, db: Session = Depends(get_db)):
    activation_key = data.get("activation_key")
    if not activation_key:
        raise HTTPException(status_code=400, detail="Missing activation_key")
        
    employee = db.query(Employee).filter(Employee.activation_key == activation_key).first()
    if not employee:
        raise HTTPException(status_code=401, detail="Invalid key")
        
    if employee.is_active == 0:
        raise HTTPException(status_code=403, detail="Device not active")
        
    # Optional: Update last seen or similar?
    return {"status": "ACTIVE", "employee_name": employee.name}

# --- 5. Get Current Status (Optional, for polling if needed) ---
@app.get("/check-status/{activation_key}")
async def check_status(activation_key: str, db: Session = Depends(get_db)):
    employee = db.query(Employee).filter(Employee.activation_key == activation_key).first()
    if not employee:
        return {"status": "INVALID"}
    
    # This could be used by admin to force shutdown remotely by modifying DB
    if employee.is_active == 0:
        return {"status": "INACTIVE"}
        
    return {"status": "ACTIVE"}

# --- 6. Dashboard Stats ---
@app.get("/dashboard/stats")
async def get_dashboard_stats(db: Session = Depends(get_db)):
    employees = db.query(Employee).all()
    logs_data = []
    
    total_present_seconds = 0
    total_away_seconds = 0
    
    # Helper to calculate seconds between time strings
    # Assumption: Everything is UTC or consistent timezone
    
    # Only calculate for "today" (simple approximation)
    today_start = datetime.datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)

    # Global time calc (across all employees)
    all_logs = db.query(EmployeeLog).filter(EmployeeLog.timestamp >= today_start).order_by(EmployeeLog.timestamp).all()
    
    count_present = 0
    count_break = 0
    count_away = 0

    for emp in employees:
        user_logs = db.query(EmployeeLog).filter(
            EmployeeLog.employee_name == emp.name, 
            EmployeeLog.timestamp >= today_start
        ).order_by(EmployeeLog.timestamp).all()

        # ... (Time calc logic remains for detail view, but we focus on HEADCOUNT for main dashboard) ...
        # Actually, we can keep the time calc logic if we want, but user asked to CHANGE the display.
        # Let's just calculate the current status for the headcount.
        
        last_log = user_logs[-1] if user_logs else None
        status = last_log.status if last_log else "Offline"
        
        if status in ["Present", "WORK_START", "BREAK_END"]:
            count_present += 1
        elif status == "BREAK_START":
            count_break += 1
        elif status == "Away":
            count_away += 1
        
        # Keep per-user time calc for the table if needed, or remove to simplify?
        # User only said "instead of displaying total time in the main display".
        # I will keep the detailed time calc for the /employee/ detail page, but here we can just return what's needed.
        # For the table, we might still want the "present_time" column?
        # Let's keep the existing loop logic but just ignore the global totals.
        
        user_present = 0
        # (re-pasting the time calc logic briefly to ensure 'present_time' in logs_data is preserved)
        
        last_time = None
        current_state = "Offline"
        for log in user_logs:
            if last_time:
                delta = (log.timestamp - last_time).total_seconds()
                if current_state in ["Present", "WORK_START", "BREAK_END"]:
                    user_present += delta
                # ... others
            last_time = log.timestamp
            current_state = log.status
        
        if last_time and current_state in ["Present", "WORK_START", "BREAK_END"]:
             user_present += (datetime.datetime.utcnow() - last_time).total_seconds()

        logs_data.append({
            "employee_name": emp.name,
            "status": status,
            "timestamp": last_log.timestamp if last_log else datetime.datetime.utcnow(),
            "present_time": f"{int(user_present//3600)}h {int((user_present%3600)//60)}m"
        })

    return {
        "count_present": count_present,
        "count_break": count_break,
        "count_away": count_away,
        "logs": logs_data
    }

# --- 7. Serve Detail Page ---
@app.get("/employee/{name}", response_class=HTMLResponse)
async def read_item(name: str, request: Request):
    return templates.TemplateResponse("employee_detail.html", {"request": request, "name": name})

# --- 8. Specific Employee Stats API ---
@app.get("/api/employee/{name}/stats")
async def get_employee_stats(name: str, db: Session = Depends(get_db)):
    # Get all logs for user
    all_logs = db.query(EmployeeLog).filter(EmployeeLog.employee_name == name).order_by(EmployeeLog.timestamp.desc()).all()
    
    # Separate today vs history
    today_start = datetime.datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    today_logs = [log for log in all_logs if log.timestamp >= today_start]
    
    # Calculate Today's Stats
    present_seconds = 0
    break_seconds = 0
    away_seconds = 0
    
    sorted_today = sorted(today_logs, key=lambda x: x.timestamp)
    last_t = None
    state = "Offline"
    
    for log in sorted_today:
        if last_t:
            delta = (log.timestamp - last_t).total_seconds()
            if state in ["Present", "WORK_START", "BREAK_END"]:
                present_seconds += delta
            elif state == "BREAK_START":
                break_seconds += delta
            elif state == "Away":
                away_seconds += delta
                
        last_t = log.timestamp
        state = log.status
        
    if last_t:
        now_delta = (datetime.datetime.utcnow() - last_t).total_seconds()
        if state in ["Present", "WORK_START", "BREAK_END"]:
            present_seconds += now_delta
        elif state == "BREAK_START":
            break_seconds += now_delta
        elif state == "Away":
            away_seconds += now_delta

    # Filter logs for history table: Only show changes
    # Sort ASC first to find transitions
    full_history_asc = sorted(all_logs, key=lambda x: x.timestamp)
    filtered_history = []
    last_status = None
    
    for log in full_history_asc:
        if log.status != last_status:
            filtered_history.append(log)
            last_status = log.status
            
    # Return DESC for UI
    filtered_history.reverse()

    return {
        "name": name,
        "present_today": f"{int(present_seconds//3600)}h {int((present_seconds%3600)//60)}m",
        "break_today": f"{int(break_seconds//3600)}h {int((break_seconds%3600)//60)}m",
        "away_today": f"{int(away_seconds//3600)}h {int((away_seconds%3600)//60)}m",
        "logs": filtered_history 
    }

# --- 7. Serve Dashboard ---
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

templates = Jinja2Templates(directory="templates")

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)