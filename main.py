import datetime
import secrets
import string
import os
from typing import List, Dict, Optional
from fastapi import FastAPI, Request, Depends, HTTPException, status, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from pydantic import BaseModel
from database import SessionLocal, EmployeeLog, Employee, Company, Supervisor, AppLog, Screenshot, Base, engine
from auth import (
    hash_password, verify_password, create_token, verify_token, 
    invalidate_token, get_token_from_cookies, get_current_supervisor, require_auth
)

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

templates = Jinja2Templates(directory="templates")

# Health Check for UptimeRobot
@app.get("/health")
def health_check():
    return {"status": "ok"}

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
    status: str

class SupervisorCreate(BaseModel):
    email: str
    password: str
    name: str
    company_id: int

class CompanyCreate(BaseModel):
    name: str

class LoginRequest(BaseModel):
    email: str
    password: str

class SettingsUpdate(BaseModel):
    screenshot_frequency: int
    dlp_enabled: int

class EmployeeInvite(BaseModel):
    name: str
    email: Optional[str] = None
    department: str = "General"

class EmployeeRegister(BaseModel):
    token: str
    password: str
    email: str

class AppLogin(BaseModel):
    email: str
    password: str

class SupervisorInvite(BaseModel):
    name: str
    email: str
    password: str
    role: str = "admin" # admin, viewer

# ===============================
# HEALTH CHECK
# ===============================
@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "employee-tracker"}

# ===============================
# AUTHENTICATION ROUTES
# ===============================
@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    """Render login page"""
    # Check if already logged in
    token = get_token_from_cookies(request)
    if token and verify_token(token):
        return RedirectResponse(url="/", status_code=302)
    return templates.TemplateResponse("login.html", {"request": request, "error": None})

@app.post("/login")
async def login(request: Request, email: str = Form(...), password: str = Form(...), db: Session = Depends(get_db)):
    """Handle login form submission"""
    supervisor = db.query(Supervisor).filter(Supervisor.email == email).first()
    
    if not supervisor or not verify_password(password, supervisor.password_hash):
        return templates.TemplateResponse("login.html", {
            "request": request, 
            "error": "Invalid email or password"
        })
    
    # Create token
    token = create_token(
        supervisor_id=supervisor.id,
        company_id=supervisor.company_id,
        is_super_admin=supervisor.is_super_admin == 1
    )
    
    # Set cookie and redirect
    response = RedirectResponse(url="/", status_code=302)
    response.set_cookie(key="auth_token", value=token, httponly=True, max_age=86400)
    return response

@app.get("/logout")
async def logout(request: Request):
    """Logout and clear session"""
    token = get_token_from_cookies(request)
    if token:
        invalidate_token(token)
    
    response = RedirectResponse(url="/login", status_code=302)
    response.delete_cookie("auth_token")
    return response

@app.get("/auth/me")
async def get_me(request: Request, db: Session = Depends(get_db)):
    """Get current logged-in supervisor info"""
    try:
        token_data = get_current_supervisor(request)
        supervisor = db.query(Supervisor).filter(Supervisor.id == token_data["supervisor_id"]).first()
        company = db.query(Company).filter(Company.id == token_data["company_id"]).first()
        
        return {
            "id": supervisor.id,
            "name": supervisor.name,
            "email": supervisor.email,
            "company_id": token_data["company_id"],
            "company_name": company.name if company else "Unknown",
            "is_super_admin": token_data["is_super_admin"]
        }
    except:
        raise HTTPException(status_code=401, detail="Not authenticated")

# ===============================
# DASHBOARD (Protected)
# ===============================
@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    """Protected dashboard - requires login"""
    token = get_token_from_cookies(request)
    if not token or not verify_token(token):
        return RedirectResponse(url="/login", status_code=302)
    
    return templates.TemplateResponse("dashboard_new.html", {"request": request})

@app.get("/dashboard-new", response_class=HTMLResponse)
async def dashboard_new(request: Request, db: Session = Depends(get_db)):
    """New Tailwind dashboard - requires login"""
    token = get_token_from_cookies(request)
    if not token or not verify_token(token):
        return RedirectResponse(url="/login", status_code=302)
    
    token_data = verify_token(token)
    supervisor = db.query(Supervisor).filter(Supervisor.id == token_data["supervisor_id"]).first()
    company = db.query(Company).filter(Company.id == token_data["company_id"]).first()
    
    return templates.TemplateResponse("dashboard_new.html", {
        "request": request,
        "supervisor_name": supervisor.name if supervisor else "Admin",
        "company_name": company.name if company else "Company"
    })

@app.get("/dashboard/stats")
async def get_dashboard_stats(request: Request, db: Session = Depends(get_db)):
    """Get dashboard stats - filtered by company"""
    # Check auth
    token = get_token_from_cookies(request)
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    token_data = verify_token(token)
    if not token_data:
        raise HTTPException(status_code=401, detail="Invalid token")
    
    company_id = token_data["company_id"]
    is_super_admin = token_data.get("is_super_admin", False)
    
    # Get employees (filtered by company unless super admin)
    if is_super_admin:
        employees = db.query(Employee).all()
    else:
        employees = db.query(Employee).filter(Employee.company_id == company_id).all()
    
    logs_data = []
    today_start = datetime.datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    
    # 1. Fetch ALL recent logs for valid activity feed (last 15 events)
    company_emp_names = [e.name for e in employees]
    recent_logs_db = db.query(EmployeeLog).filter(
        EmployeeLog.employee_name.in_(company_emp_names)
    ).order_by(EmployeeLog.timestamp.desc()).limit(15).all()

    recent_activity = [{
        "employee_name": log.employee_name,
        "status": log.status,
        "timestamp": log.timestamp
    } for log in recent_logs_db]

    count_present = 0
    count_break = 0
    count_away = 0
    count_offline = 0

    for emp in employees:
        user_logs = db.query(EmployeeLog).filter(
            EmployeeLog.employee_name == emp.name, 
            EmployeeLog.timestamp >= today_start
        ).order_by(EmployeeLog.timestamp).all()

        last_log = user_logs[-1] if user_logs else None
        status = last_log.status if last_log else "Offline"
        
        # Check heartbeat timeout (2 minutes = 120 seconds)
        heartbeat_timeout = datetime.datetime.utcnow() - datetime.timedelta(seconds=120)
        if emp.last_heartbeat is None or emp.last_heartbeat < heartbeat_timeout:
            # No heartbeat for 2+ minutes = Offline
            status = "Offline"
        
        if status in ["Present", "WORK_START", "BREAK_END"]:
            count_present += 1
        elif status == "BREAK_START":
            count_break += 1
        elif status == "Away":
            count_away += 1
        else:
            count_offline += 1
        
        # Calculate user present time
        user_present = 0
        last_time = None
        current_state = "Offline"
        for log in user_logs:
            if last_time:
                delta = (log.timestamp - last_time).total_seconds()
                if current_state in ["Present", "WORK_START", "BREAK_END"]:
                    user_present += delta
            last_time = log.timestamp
            current_state = log.status
        
        if last_time and current_state in ["Present", "WORK_START", "BREAK_END"]:
             user_present += (datetime.datetime.utcnow() - last_time).total_seconds()

        logs_data.append({
            "employee_name": emp.name,
            "department": emp.department or "-",
            "status": status,
            "timestamp": last_log.timestamp if last_log else datetime.datetime.utcnow(),
            "present_time": f"{int(user_present//3600)}h {int((user_present%3600)//60)}m"
        })

    return {
        "count_present": count_present,
        "count_break": count_break,
        "count_away": count_away,
        "count_offline": count_offline,
        "logs": logs_data,
        "recent_activity": recent_activity  # New field for feed
    }

# ===============================
# SUPERVISOR MANAGEMENT
# ===============================
@app.post("/api/supervisors")
async def create_supervisor(request: Request, data: SupervisorInvite, db: Session = Depends(get_db)):
    """Create a new supervisor (dashboard user)"""
    token = get_token_from_cookies(request)
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    token_data = verify_token(token)
    if not token_data:
        raise HTTPException(status_code=401, detail="Invalid token")

    # Only existing supervisors (admins) can add new ones
    current_sup = db.query(Supervisor).filter(Supervisor.id == token_data["supervisor_id"]).first()
    if not current_sup:
        raise HTTPException(status_code=403, detail="Permission denied")
    
    # RBAC Check
    if current_sup.role != 'admin':
        raise HTTPException(status_code=403, detail="Viewer accounts cannot create supervisors")

    # Check email uniqueness
    if db.query(Supervisor).filter(Supervisor.email == data.email).first():
        raise HTTPException(status_code=400, detail="Email already registered")

    # Create new supervisor
    hashed_pw = hash_password(data.password)
    new_sup = Supervisor(
        name=data.name,
        email=data.email,
        password_hash=hashed_pw,
        company_id=current_sup.company_id, # Link to same company
        role=data.role 
    )
    
    db.add(new_sup)
    db.commit()
    return {"status": "ok", "message": "Supervisor created"}

@app.get("/api/supervisors")
async def list_supervisors(request: Request, db: Session = Depends(get_db)):
    """List supervisors for the current company"""
    token = get_token_from_cookies(request)
    if not token: raise HTTPException(status_code=401)
    token_data = verify_token(token)
    
    supervisors = db.query(Supervisor).filter(Supervisor.company_id == token_data["company_id"]).all()
    return [{
        "id": s.id,
        "name": s.name,
        "email": s.email,
        "role": s.role,
        "created_at": s.created_at.isoformat()
    } for s in supervisors]

# ===============================
# EMPLOYEE MANAGEMENT (Protected)
# ===============================
@app.post("/admin/create-employee")
async def create_employee(request: Request, employee: EmployeeCreate, db: Session = Depends(get_db)):
    """Create employee - assigns to supervisor's company"""
    token = get_token_from_cookies(request)
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    if not token_data:
        raise HTTPException(status_code=401, detail="Invalid token")
    
    # RBAC Check
    current_sup = db.query(Supervisor).filter(Supervisor.id == token_data["supervisor_id"]).first()
    if not current_sup or current_sup.role != 'admin':
        raise HTTPException(status_code=403, detail="Viewer accounts cannot create employees")
    
    # Generate unique key
    while True:
        suffix = ''.join(secrets.choice(string.digits) for _ in range(4))
        key = f"KEY-{suffix}"
        if not db.query(Employee).filter(Employee.activation_key == key).first():
            break
    
    new_employee = Employee(
        name=employee.name,
        department=employee.department,
        activation_key=key,
        is_active=0,
        company_id=token_data["company_id"]  # Assign to supervisor's company
    )
    db.add(new_employee)
    db.commit()
    db.refresh(new_employee)
    
    print(f"ADMIN: Created employee {employee.name} with key {key} for company {token_data['company_id']}")
    return {"activation_key": key, "name": employee.name}

# ===============================
# DEVICE ACTIVATION (Public)
# ===============================
@app.post("/activate-device")
async def activate_device(data: DeviceActivation, db: Session = Depends(get_db)):
    employee = db.query(Employee).filter(Employee.activation_key == data.activation_key).first()
    
    if not employee:
        raise HTTPException(status_code=404, detail="Invalid activation key")
    
    if employee.hardware_id and employee.hardware_id != data.hardware_id:
        raise HTTPException(status_code=403, detail="Key already bound to another device")
        
    employee.hardware_id = data.hardware_id
    employee.is_active = 1
    db.commit()
    
    print(f"ACTIVATION: Device activated for {employee.name} on HWID {data.hardware_id}")
    return {"status": "success", "employee_name": employee.name, "token": data.activation_key}

# ===============================
# ACTIVITY LOGGING (Public - from detector)
# ===============================
@app.post("/log-activity")
async def log_activity(log: ActivityLog, db: Session = Depends(get_db)):
    employee = db.query(Employee).filter(Employee.activation_key == log.activation_key).first()
    if not employee:
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    new_log = EmployeeLog(
        employee_name=employee.name,
        status=log.status
    )
    db.add(new_log)
    db.commit()
    
    print(f"LOG: {employee.name} -> {log.status}")

    # Slack notification
    IMPORTANT_STATUSES = ["WORK_START", "BREAK_START", "BREAK_END", "Away"]
    SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL")

    if log.status in IMPORTANT_STATUSES and SLACK_WEBHOOK_URL:
        try:
            import requests
            slack_msg = {"text": f"📢 *{employee.name}* status update: *{log.status}*"}
            if log.status == "Away":
                slack_msg["text"] = f"⚠️ *{employee.name}* is marked as **Away/Missing**!"
            elif log.status == "BREAK_START":
                slack_msg["text"] = f"☕ *{employee.name}* is taking a break."
            elif log.status == "WORK_START":
                slack_msg["text"] = f"🟢 *{employee.name}* has started work."
            requests.post(SLACK_WEBHOOK_URL, json=slack_msg, timeout=2)
        except Exception as e:
            print(f"Slack Error: {e}")

    return {"status": "ACTIVE"}

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
    
    # Set initial heartbeat
    employee.last_heartbeat = datetime.datetime.utcnow()
    db.commit()
        
    return {"status": "ACTIVE", "employee_name": employee.name}

@app.post("/heartbeat")
async def heartbeat(data: dict, db: Session = Depends(get_db)):
    """Receive heartbeat from detector app every 30 seconds"""
    activation_key = data.get("activation_key")
    if not activation_key:
        raise HTTPException(status_code=400, detail="Missing activation_key")
    
    employee = db.query(Employee).filter(Employee.activation_key == activation_key).first()
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")
    
    # Update last heartbeat
    employee.last_heartbeat = datetime.datetime.utcnow()
    
    # Check for pending commands
    response_data = {
        "status": "OK", 
        "timestamp": employee.last_heartbeat.isoformat(),
        "settings": {
            "screenshot_frequency": employee.company.screenshot_frequency if employee.company else 600,
            "dlp_enabled": employee.company.dlp_enabled if employee.company else 0
        }
    }
    
    if employee.pending_screenshot == 1:
        response_data["command"] = "screenshot"
        # Reset flag
        employee.pending_screenshot = 0
        
    db.commit()
    
    return response_data

@app.post("/api/app-log")
async def log_app_usage(data: dict, db: Session = Depends(get_db)):
    """Log application usage from detector app"""
    activation_key = data.get("activation_key")
    app_name = data.get("app_name")
    window_title = data.get("window_title", "")
    duration = data.get("duration_seconds", 1)
    
    if not activation_key or not app_name:
        raise HTTPException(status_code=400, detail="Missing required fields")
    
    employee = db.query(Employee).filter(Employee.activation_key == activation_key).first()
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")
    
    new_log = AppLog(
        employee_name=employee.name,
        app_name=app_name,
        window_title=window_title,
        duration_seconds=duration
    )
    db.add(new_log)
    db.commit()
    
    return {"status": "OK"}

@app.get("/api/app-usage-stats")
async def get_app_usage_stats(request: Request, db: Session = Depends(get_db)):
    """Get aggregated app usage stats for dashboard"""
    try:
        token_data = get_current_supervisor(request)
    except:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    company_id = token_data["company_id"]
    is_super_admin = token_data["is_super_admin"]
    
    # Get employees for this company
    if is_super_admin:
        employees = db.query(Employee).all()
    else:
        employees = db.query(Employee).filter(Employee.company_id == company_id).all()
    
    emp_names = [e.name for e in employees]
    
    # Get today's app logs
    today_start = datetime.datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    
    logs = db.query(AppLog).filter(
        AppLog.employee_name.in_(emp_names),
        AppLog.timestamp >= today_start
    ).all()
    
    # Aggregate by app_name
    app_stats = {}
    for log in logs:
        if log.app_name not in app_stats:
            app_stats[log.app_name] = 0
        app_stats[log.app_name] += log.duration_seconds
    
    # Sort by duration, top 10
    sorted_apps = sorted(app_stats.items(), key=lambda x: x[1], reverse=True)[:10]
    
    return {
        "top_apps": [{"app": app, "duration": dur} for app, dur in sorted_apps],
        "total_logs": len(logs)
    }

@app.get("/api/employee-time/{activation_key}")
async def get_employee_time(activation_key: str, db: Session = Depends(get_db)):
    """Get today's time stats for an employee - used by detector.py on startup"""
    employee = db.query(Employee).filter(Employee.activation_key == activation_key).first()
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")
    
    today_start = datetime.datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    
    logs = db.query(EmployeeLog).filter(
        EmployeeLog.employee_name == employee.name,
        EmployeeLog.timestamp >= today_start
    ).order_by(EmployeeLog.timestamp).all()
    
    present_seconds = 0
    away_seconds = 0
    break_seconds = 0
    
    last_time = None
    state = "Offline"
    
    for log in logs:
        if last_time:
            delta = (log.timestamp - last_time).total_seconds()
            if state in ["Present", "WORK_START", "BREAK_END"]:
                present_seconds += delta
            elif state == "BREAK_START":
                break_seconds += delta
            elif state == "Away":
                away_seconds += delta
        last_time = log.timestamp
        state = log.status
    
    # Add time since last log until now
    if last_time:
        now_delta = (datetime.datetime.utcnow() - last_time).total_seconds()
        if state in ["Present", "WORK_START", "BREAK_END"]:
            present_seconds += now_delta
        elif state == "BREAK_START":
            break_seconds += now_delta
        elif state == "Away":
            away_seconds += now_delta
    
    return {
        "employee_name": employee.name,
        "present_seconds": int(present_seconds),
        "away_seconds": int(away_seconds),
        "break_seconds": int(break_seconds),
        "current_status": state
    }

# ===============================
# COMPANY MANAGEMENT (Super Admin)
# ===============================
@app.post("/admin/companies")
async def create_company(company: CompanyCreate, db: Session = Depends(get_db)):
    """Create a new company"""
    existing = db.query(Company).filter(Company.name == company.name).first()
    if existing:
        raise HTTPException(status_code=400, detail="Company already exists")
    
    new_company = Company(name=company.name)
    db.add(new_company)
    db.commit()
    db.refresh(new_company)
    
    return {"id": new_company.id, "name": new_company.name}

@app.get("/admin/companies")
async def list_companies(db: Session = Depends(get_db)):
    """List all companies"""
    companies = db.query(Company).all()
    return [{"id": c.id, "name": c.name} for c in companies]

@app.post("/admin/supervisors")
async def create_supervisor(supervisor: SupervisorCreate, db: Session = Depends(get_db)):
    """Create a new supervisor"""
    existing = db.query(Supervisor).filter(Supervisor.email == supervisor.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    company = db.query(Company).filter(Company.id == supervisor.company_id).first()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    
    new_supervisor = Supervisor(
        email=supervisor.email,
        password_hash=hash_password(supervisor.password),
        name=supervisor.name,
        company_id=supervisor.company_id,
        is_super_admin=0
    )
    db.add(new_supervisor)
    db.commit()
    db.refresh(new_supervisor)
    
    return {"id": new_supervisor.id, "email": new_supervisor.email, "company": company.name}

# ===============================
# EMPLOYEE DETAIL PAGE
# ===============================
@app.get("/employee/{name}", response_class=HTMLResponse)
async def read_item(name: str, request: Request):
    token = get_token_from_cookies(request)
    if not token or not verify_token(token):
        return RedirectResponse(url="/login", status_code=302)
    return templates.TemplateResponse("employee_detail_new.html", {"request": request, "name": name})

@app.get("/api/employee/{name}/stats")
async def get_employee_stats(name: str, request: Request, db: Session = Depends(get_db)):
    token = get_token_from_cookies(request)
    if not token or not verify_token(token):
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    all_logs = db.query(EmployeeLog).filter(EmployeeLog.employee_name == name).order_by(EmployeeLog.timestamp.desc()).all()
    today_start = datetime.datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    today_logs = [log for log in all_logs if log.timestamp >= today_start]
    
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

    full_history_asc = sorted(all_logs, key=lambda x: x.timestamp)
    filtered_history = []
    last_status = None
    
    for log in full_history_asc:
        if log.status != last_status:
            filtered_history.append(log)
            last_status = log.status
    filtered_history.reverse()

    # Determine current status with Heartbeat logic
    employee = db.query(Employee).filter(Employee.name == name).first()
    current_status = "Offline"
    
    if filtered_history and filtered_history[0].status:
        current_status = filtered_history[0].status
        
    # Check 2-minute heartbeat timeout
    if employee:
        heartbeat_timeout = datetime.datetime.utcnow() - datetime.timedelta(seconds=120)
        if employee.last_heartbeat is None or employee.last_heartbeat < heartbeat_timeout:
            current_status = "Offline"

    return {
        "name": name,
        "department": employee.department if employee else "-",
        "current_status": current_status,  # New explicit status
        "present_today": f"{int(present_seconds//3600)}h {int((present_seconds%3600)//60)}m",
        "break_today": f"{int(break_seconds//3600)}h {int((break_seconds%3600)//60)}m",
        "away_today": f"{int(away_seconds//3600)}h {int((away_seconds%3600)//60)}m",
        "logs": [{"timestamp": l.timestamp, "status": l.status} for l in filtered_history]
    }

# ===============================
# PERFORMANCE SCORING SYSTEM
# ===============================

def calculate_employee_score(employee_name: str, db: Session, days: int = 7) -> dict:
    """
    Calculate employee performance score (0-100)
    
    Scoring weights:
    - Present Time %: 40%
    - Low Away Time: 25%
    - Break Discipline: 15%
    - Consistency: 20%
    """
    start_date = datetime.datetime.utcnow() - datetime.timedelta(days=days)
    
    logs = db.query(EmployeeLog).filter(
        EmployeeLog.employee_name == employee_name,
        EmployeeLog.timestamp >= start_date
    ).order_by(EmployeeLog.timestamp).all()
    
    if not logs:
        return {
            "score": 0,
            "grade": "N/A",
            "present_hours": 0,
            "away_hours": 0,
            "break_hours": 0,
            "days_active": 0,
            "details": {"present_score": 0, "away_score": 0, "break_score": 0, "consistency_score": 0}
        }
    
def calculate_stats_from_logs(logs, period_days):
    if not logs:
        return {
            "score": 0,
            "grade": "N/A",
            "present_hours": 0,
            "away_hours": 0,
            "break_hours": 0,
            "days_active": 0,
            "details": {"present_score": 0, "away_score": 0, "break_score": 0, "consistency_score": 0}
        }
    
    # Calculate time in each state
    present_seconds = 0
    away_seconds = 0
    break_seconds = 0
    active_days = set()
    
    last_time = None
    state = "Offline"
    
    for log in logs:
        active_days.add(log.timestamp.date())
        if last_time:
            delta = (log.timestamp - last_time).total_seconds()
            # Cap individual deltas at 2 hours to handle gaps
            delta = min(delta, 7200)
            if state in ["Present", "WORK_START", "BREAK_END"]:
                present_seconds += delta
            elif state == "BREAK_START":
                break_seconds += delta
            elif state == "Away":
                away_seconds += delta
        last_time = log.timestamp
        state = log.status
    
    # Total tracked time
    total_seconds = present_seconds + away_seconds + break_seconds
    if total_seconds == 0:
        total_seconds = 1
    
    # Expected hours
    expected_hours = len(active_days) * 8
    expected_seconds = expected_hours * 3600
    
    # 1. Present Time Score (40%)
    present_ratio = min(present_seconds / max(expected_seconds, 1), 1.0)
    present_score = present_ratio * 100
    
    # 2. Away Time Score (25%)
    away_ratio = away_seconds / max(total_seconds, 1)
    away_score = max(0, 100 - (away_ratio * 200))
    
    # 3. Break Discipline (15%)
    breaks_per_day = break_seconds / max(len(active_days), 1)
    ideal_break = 45 * 60
    break_deviation = abs(breaks_per_day - ideal_break) / ideal_break
    break_score = max(0, 100 - (break_deviation * 50))
    
    # 4. Consistency (20%)
    consistency_ratio = len(active_days) / max(period_days, 1)
    consistency_score = min(consistency_ratio * 100, 100)
    
    # Final Score
    final_score = (present_score * 0.40 + away_score * 0.25 + break_score * 0.15 + consistency_score * 0.20)
    final_score = min(max(round(final_score), 0), 100)
    
    grade = "Poor"
    if final_score >= 90: grade = "Excellent"
    elif final_score >= 75: grade = "Good"
    elif final_score >= 60: grade = "Average"
    elif final_score >= 40: grade = "Needs Improvement"
    
    return {
        "score": final_score,
        "grade": grade,
        "present_hours": round(present_seconds / 3600, 1),
        "away_hours": round(away_seconds / 3600, 1),
        "break_hours": round(break_seconds / 3600, 1),
        "days_active": len(active_days),
        "details": {
            "present_score": round(present_score),
            "away_score": round(away_score),
            "break_score": round(break_score),
            "consistency_score": round(consistency_score)
        }
    }

def calculate_employee_score(employee_name: str, db: Session, days: int = 7) -> dict:
    start_date = datetime.datetime.utcnow() - datetime.timedelta(days=days)
    logs = db.query(EmployeeLog).filter(
        EmployeeLog.employee_name == employee_name,
        EmployeeLog.timestamp >= start_date
    ).order_by(EmployeeLog.timestamp).all()
    
    return calculate_stats_from_logs(logs, days)

@app.get("/api/scores")
async def get_all_scores(request: Request, days: int = 7, db: Session = Depends(get_db)):
    """Get performance scores for all employees"""
    token = get_token_from_cookies(request)
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    token_data = verify_token(token)
    if not token_data:
        raise HTTPException(status_code=401, detail="Invalid token")
    
    company_id = token_data["company_id"]
    is_super_admin = token_data.get("is_super_admin", False)
    
    if is_super_admin:
        employees = db.query(Employee).all()
    else:
        employees = db.query(Employee).filter(Employee.company_id == company_id).all()
    
    scores = []
    for emp in employees:
        score_data = calculate_employee_score(emp.name, db, days)
        scores.append({
            "employee_name": emp.name,
            "department": emp.department or "-",
            **score_data
        })
    
    # Sort by score descending
    scores.sort(key=lambda x: x["score"], reverse=True)
    
    return {
        "period_days": days,
        "total_employees": len(scores),
        "average_score": round(sum(s["score"] for s in scores) / max(len(scores), 1)),
        "scores": scores
    }

@app.get("/api/analytics/trends")
async def get_analytics_trends(request: Request, days: int = 7, db: Session = Depends(get_db)):
    """Get daily trends for charts"""
    token = get_token_from_cookies(request)
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    token_data = verify_token(token)
    if not token_data:
        raise HTTPException(status_code=401, detail="Invalid token")
    
    company_id = token_data["company_id"]
    is_super_admin = token_data.get("is_super_admin", False)
    
    if is_super_admin:
        employees = db.query(Employee).all()
    else:
        employees = db.query(Employee).filter(Employee.company_id == company_id).all()
    
    employee_names = [e.name for e in employees]
    
    # Get daily data for the past N days
    daily_data = []
    for i in range(days - 1, -1, -1):
        day = datetime.datetime.utcnow().date() - datetime.timedelta(days=i)
        day_start = datetime.datetime.combine(day, datetime.time.min)
        day_end = datetime.datetime.combine(day, datetime.time.max)
        
        # Count employees with activity on this day
        logs = db.query(EmployeeLog).filter(
            EmployeeLog.employee_name.in_(employee_names),
            EmployeeLog.timestamp >= day_start,
            EmployeeLog.timestamp <= day_end
        ).all()
        
        present_count = 0
        away_count = 0
        break_count = 0
        
        # Get last status per employee for this day
        emp_statuses = {}
        for log in logs:
            emp_statuses[log.employee_name] = log.status
        
        for status in emp_statuses.values():
            if status in ["Present", "WORK_START", "BREAK_END"]:
                present_count += 1
            elif status == "BREAK_START":
                break_count += 1
            elif status == "Away":
                away_count += 1
        
        daily_data.append({
            "date": day.strftime("%Y-%m-%d"),
            "day_name": day.strftime("%a"),
            "present": present_count,
            "away": away_count,
            "break": break_count,
            "total_active": len(emp_statuses)
        })
    
    return {
        "period_days": days,
        "daily_data": daily_data,
        "total_employees": len(employees)
    }

@app.get("/api/analytics/top-performers")
async def get_top_performers(request: Request, limit: int = 5, db: Session = Depends(get_db)):
    """Get top and bottom performers"""
    scores_response = await get_all_scores(request, days=7, db=db)
    scores = scores_response["scores"]
    
    return {
        "top_performers": scores[:limit],
        "needs_attention": list(reversed(scores[-limit:])) if len(scores) >= limit else list(reversed(scores))
    }

# ===============================
# SCREENSHOT ENDPOINTS
# ===============================

class ScreenshotUpload(BaseModel):
    activation_key: str
    screenshot_data: str  # Base64 encoded
    manual_request: bool = False

@app.post("/api/screenshot")
async def upload_screenshot(data: ScreenshotUpload, db: Session = Depends(get_db)):
    """Receive screenshot from detector app"""
    # Verify activation key
    employee = db.query(Employee).filter(Employee.activation_key == data.activation_key).first()
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")
    
    # Save screenshot (store only last 50 per employee to save space)
    old_screenshots = db.query(Screenshot).filter(
        Screenshot.employee_name == employee.name
    ).order_by(Screenshot.timestamp.asc()).all()
    
    # Delete oldest if more than 50
    if len(old_screenshots) >= 50:
        for old in old_screenshots[:-49]:
            db.delete(old)
    
    # Create new screenshot
    new_screenshot = Screenshot(
        employee_name=employee.name,
        company_id=employee.company_id,
        image_data=data.screenshot_data,
        manual_request=1 if data.manual_request else 0
    )
    db.add(new_screenshot)
    db.commit()
    
    return {"status": "ok", "message": "Screenshot saved"}

@app.get("/api/screenshots/{employee_name}")
async def get_employee_screenshots(employee_name: str, request: Request, limit: int = 20, db: Session = Depends(get_db)):
    """Get recent screenshots for an employee"""
    # Auth check
    token = get_token_from_cookies(request)
    if not token or not verify_token(token):
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    screenshots = db.query(Screenshot).filter(
        Screenshot.employee_name == employee_name
    ).order_by(Screenshot.timestamp.desc()).limit(limit).all()
    
    return [{
        "id": s.id,
        "timestamp": s.timestamp.isoformat() if s.timestamp else None,
        "image_data": s.image_data,
        "manual_request": bool(s.manual_request)
    } for s in screenshots]

@app.post("/api/request-screenshot/{employee_name}")
async def request_screenshot(employee_name: str, request: Request, db: Session = Depends(get_db)):
    """Supervisor requests an immediate screenshot from employee"""
    # Auth check
    token = get_token_from_cookies(request)
    if not token or not verify_token(token):
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    employee = db.query(Employee).filter(Employee.name == employee_name).first()
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")
    
    # Set pending flag
    employee.pending_screenshot = 1
    db.commit()
    
    return {"status": "ok", "message": f"Screenshot request sent to {employee_name}"}

@app.get("/api/settings")
async def get_settings(request: Request, db: Session = Depends(get_db)):
    """Get company settings"""
    token = get_token_from_cookies(request)
    if not token or not verify_token(token):
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    token_data = verify_token(token)
    company = db.query(Company).filter(Company.id == token_data["company_id"]).first()
    
    return {
        "screenshot_frequency": company.screenshot_frequency if company else 600,
        "dlp_enabled": company.dlp_enabled if company else 0
    }

@app.post("/api/settings")
async def update_settings(settings: SettingsUpdate, request: Request, db: Session = Depends(get_db)):
    """Update company settings"""
    token = get_token_from_cookies(request)
    if not token or not verify_token(token):
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    token_data = verify_token(token)
    
    # RBAC Check
    current_sup = db.query(Supervisor).filter(Supervisor.id == token_data["supervisor_id"]).first()
    if not current_sup or current_sup.role != 'admin':
        raise HTTPException(status_code=403, detail="Viewer accounts cannot change settings")

    company = db.query(Company).filter(Company.id == token_data["company_id"]).first()
    
    if company:
        company.screenshot_frequency = settings.screenshot_frequency
        company.dlp_enabled = settings.dlp_enabled
        db.commit()
        return {"status": "ok"}
    
    raise HTTPException(status_code=404, detail="Company not found")

# ===============================
# INVITATION & APP AUTH SYSTEM
# ===============================

@app.post("/api/employees/invite")
async def invite_employee(invite: EmployeeInvite, request: Request, db: Session = Depends(get_db)):
    """Invite an employee via email"""
    try:
        token = get_token_from_cookies(request)
        if not token or not verify_token(token):
            raise HTTPException(status_code=401, detail="Not authenticated")
        
        token_data = verify_token(token)

        # RBAC Check
        current_sup = db.query(Supervisor).filter(Supervisor.id == token_data["supervisor_id"]).first()
        if not current_sup or current_sup.role != 'admin':
            raise HTTPException(status_code=403, detail="Viewer accounts cannot invite employees")
        
        # Check if email exists (only if provided)
        if invite.email and db.query(Employee).filter(Employee.email == invite.email).first():
            raise HTTPException(status_code=400, detail="Email already registered")
        
        # Generate tokens
        activation_key = f"KEY-{secrets.token_hex(4).upper()}"
        invite_token = secrets.token_urlsafe(32)
        expires = datetime.datetime.utcnow() + datetime.timedelta(hours=48)
        
        new_employee = Employee(
            name=invite.name,
            email=invite.email, # Can be None
            department=invite.department,
            activation_key=activation_key,
            invite_token=invite_token,
            invite_expires=expires,
            company_id=token_data["company_id"],
            is_active=0,
            is_registered=0
        )
        db.add(new_employee)
        db.commit()
        
        # In a real app, send email here. For now, return the link.
        invite_link = f"{request.base_url}register?token={invite_token}"
        return {"status": "ok", "invite_link": invite_link}
    except HTTPException as he:
        raise he
    except Exception as e:
        print(f"❌ Invite Error: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/register", response_class=HTMLResponse)
async def register_page(request: Request, token: str):
    """Render registration page"""
    return templates.TemplateResponse("register.html", {"request": request, "token": token})

@app.post("/api/register")
async def register_employee(data: EmployeeRegister, db: Session = Depends(get_db)):
    """Set password and email for employee account"""
    employee = db.query(Employee).filter(Employee.invite_token == data.token).first()
    
    if not employee:
        raise HTTPException(status_code=400, detail="Invalid token")
        
    if employee.invite_expires and datetime.datetime.utcnow() > employee.invite_expires:
        raise HTTPException(status_code=400, detail="Token expired")
    
    # Check if email is already taken by ANOTHER employee
    existing = db.query(Employee).filter(Employee.email == data.email).first()
    if existing and existing.id != employee.id:
        raise HTTPException(status_code=400, detail="Email already registered")

    employee.password_hash = hash_password(data.password)
    employee.email = data.email
    employee.is_registered = 1
    employee.invite_token = None # Invalidate token
    db.commit()
    
    return {"status": "ok"}

@app.post("/api/app-login")
async def app_login(data: AppLogin, db: Session = Depends(get_db)):
    """Authenticate desktop app"""
    employee = db.query(Employee).filter(Employee.email == data.email).first()
    
    if not employee or not employee.password_hash:
        raise HTTPException(status_code=401, detail="Invalid credentials")
        
    if not verify_password(data.password, employee.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")
        
    # Return activation key for internal use
    return {
        "status": "ok", 
        "activation_key": employee.activation_key, 
        "name": employee.name,
        "company_id": employee.company_id
    }

@app.get("/api/app-usage-stats")
async def get_app_usage_stats(request: Request, employee_name: Optional[str] = None, db: Session = Depends(get_db)):
    """Get top apps usage stats - can be filtered by employee"""
    token = get_token_from_cookies(request)
    if not token or not verify_token(token):
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    token_data = verify_token(token)
    today_start = datetime.datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    
    query = db.query(AppLog).filter(AppLog.timestamp >= today_start)
    
    # Filter by company employees
    company_id = token_data["company_id"]
    is_super_admin = token_data.get("is_super_admin", False)
    
    if not is_super_admin:
        # Get company employees first
        employees = db.query(Employee).filter(Employee.company_id == company_id).all()
        emp_names = [e.name for e in employees]
        query = query.filter(AppLog.employee_name.in_(emp_names))
    
    # Filter by specific employee if requested
    if employee_name:
        query = query.filter(AppLog.employee_name == employee_name)
        
    logs = query.all()
    
    # Aggregate duration by app
    app_durations = {}
    
    for log in logs:
        app_name = log.app_name
        duration = log.duration_seconds
        app_durations[app_name] = app_durations.get(app_name, 0) + duration
        
    # Sort by duration
    sorted_apps = sorted(app_durations.items(), key=lambda x: x[1], reverse=True)
    
    # Format for chart (Top 10)
    top_apps = [{"app": name, "duration": dur} for name, dur in sorted_apps[:10]]
    
    return {"top_apps": top_apps}

class ReportRequest(BaseModel):
    start_date: str
    end_date: str
    filter_type: str  # 'all', 'department', 'employee', 'company'
    filter_values: List[str] = []

@app.post("/api/reports/generate")
async def generate_report(request: Request, report: ReportRequest, db: Session = Depends(get_db)):
    """Generate detailed reports based on filters"""
    token = get_token_from_cookies(request)
    if not token or not verify_token(token):
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    token_data = verify_token(token)
    company_id = token_data["company_id"]
    is_super_admin = token_data.get("is_super_admin", False)
    
    # Parse dates
    try:
        start_dt = datetime.datetime.strptime(report.start_date, "%Y-%m-%d")
        end_dt = datetime.datetime.strptime(report.end_date, "%Y-%m-%d").replace(hour=23, minute=59, second=59)
        period_days = (end_dt.date() - start_dt.date()).days + 1
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")
        
    query = db.query(Employee)
    
    if not is_super_admin:
        query = query.filter(Employee.company_id == company_id)
        
    # Apply filters
    if report.filter_type == 'employee':
        query = query.filter(Employee.name.in_(report.filter_values))
    elif report.filter_type == 'department':
        query = query.filter(Employee.department.in_(report.filter_values))
    # 'all' or 'company' just takes company filter already applied
    
    employees = query.all()
    results = []
    
    for emp in employees:
        logs = db.query(EmployeeLog).filter(
            EmployeeLog.employee_name == emp.name,
            EmployeeLog.timestamp >= start_dt,
            EmployeeLog.timestamp <= end_dt
        ).order_by(EmployeeLog.timestamp).all()
        
        stats = calculate_stats_from_logs(logs, period_days)
        results.append({
            "employee_id": emp.id,
            "name": emp.name,
            "department": emp.department,
            "stats": stats
        })
        
    return {
        "period": {"start": report.start_date, "end": report.end_date, "days": period_days},
        "data": results
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)