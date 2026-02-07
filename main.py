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
import stripe
import os

# Stripe Configuration
STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY")
STRIPE_PRICE_ID_BASIC = os.getenv("STRIPE_PRICE_ID_BASIC")
STRIPE_PRICE_ID_PRO = os.getenv("STRIPE_PRICE_ID_PRO")

stripe.api_key = STRIPE_SECRET_KEY


from pydantic import BaseModel
from database import SessionLocal, engine, Company, Supervisor, Employee, EmployeeLog, AppLog, Screenshot, Department, Base, engine
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

# Static files (CSS, images, etc.)
from fastapi.staticfiles import StaticFiles
app.mount("/static", StaticFiles(directory="static"), name="static")

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

class DepartmentCreate(BaseModel):
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
# PUBLIC MARKETING PAGES
# ===============================
@app.get("/home", response_class=HTMLResponse)
async def landing_page(request: Request):
    """Public landing page"""
    return templates.TemplateResponse("landing.html", {"request": request})

@app.get("/pricing", response_class=HTMLResponse)
async def pricing_page(request: Request):
    """Public pricing page"""
    return templates.TemplateResponse("pricing.html", {"request": request})

@app.get("/privacy", response_class=HTMLResponse)
async def privacy_page(request: Request):
    """Public privacy policy page"""
    return templates.TemplateResponse("privacy.html", {"request": request})

# ===============================
# AUTHENTICATION ROUTES
# ===============================
@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    """Serve landing page by default"""
    return templates.TemplateResponse("landing.html", {"request": request})

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

# ===============================
# COMPANY SELF-REGISTRATION
# ===============================
@app.post("/register")
async def register_company(
    request: Request,
    company_name: str = Form(...),
    name: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    plan: str = Form("pro"),  # Default plan selection
    db: Session = Depends(get_db)
):
    """Register a new company with admin account - redirects to payment"""
    # Check if email already exists
    existing = db.query(Supervisor).filter(Supervisor.email == email).first()
    if existing:
        return templates.TemplateResponse("login.html", {
            "request": request, 
            "error": "Email already registered. Please login."
        })
    
    # Check if company name already exists
    existing_company = db.query(Company).filter(Company.name == company_name).first()
    if existing_company:
        return templates.TemplateResponse("login.html", {
            "request": request, 
            "error": "Company name already taken. Please choose another."
        })
    
    # Create new company with PENDING status (no access until payment)
    new_company = Company(
        name=company_name,
        subscription_plan="pending",  # Will be updated after payment
        subscription_status="pending",
        max_employees=0  # No employees allowed until payment
    )
    db.add(new_company)
    db.commit()
    db.refresh(new_company)
    
    # Create admin supervisor
    new_supervisor = Supervisor(
        email=email,
        password_hash=hash_password(password),
        name=name,
        company_id=new_company.id,
        role="admin",
        is_super_admin=0
    )
    db.add(new_supervisor)
    db.commit()
    db.refresh(new_supervisor)

    # Create token for immediate login
    token = create_token(
        supervisor_id=new_supervisor.id,
        company_id=new_company.id,
        is_super_admin=False
    )

    # Redirect to dashboard
    response = RedirectResponse(url="/?welcome=true", status_code=302)
    response.set_cookie(key="auth_token", value=token, httponly=True, max_age=86400)
    return response

# ===============================
# DEPARTMENT MANAGEMENT
# ===============================
@app.get("/api/departments")
async def list_departments(request: Request, db: Session = Depends(get_db)):
    """List departments for current company"""
    token = get_token_from_cookies(request)
    if not token or not verify_token(token):
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    token_data = verify_token(token)
    depts = db.query(Department).filter(Department.company_id == token_data["company_id"]).all()
    return [{"id": d.id, "name": d.name} for d in depts]

@app.post("/api/departments")
async def create_department(request: Request, dept: DepartmentCreate, db: Session = Depends(get_db)):
    """Create new department"""
    token = get_token_from_cookies(request)
    if not token or not verify_token(token):
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    token_data = verify_token(token)
    
    # Check duplicate
    existing = db.query(Department).filter(
        Department.name == dept.name, 
        Department.company_id == token_data["company_id"]
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Department already exists")
    
    new_dept = Department(name=dept.name, company_id=token_data["company_id"])
    db.add(new_dept)
    db.commit()
    return {"status": "ok", "id": new_dept.id}

@app.delete("/api/departments/{dept_id}")
async def delete_department(dept_id: int, request: Request, db: Session = Depends(get_db)):
    """Delete a department"""
    token = get_token_from_cookies(request)
    if not token or not verify_token(token):
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    token_data = verify_token(token)
    
    dept = db.query(Department).filter(
        Department.id == dept_id,
        Department.company_id == token_data["company_id"]
    ).first()
    
    if not dept:
        raise HTTPException(status_code=404, detail="Department not found")
        
    db.delete(dept)
    db.commit()
    return {"status": "ok"}

    
    # Create Stripe customer immediately
    if stripe.api_key:
        try:
            customer = stripe.Customer.create(
                email=email,
                name=company_name,
                metadata={"company_id": str(new_company.id)}
            )
            new_company.stripe_customer_id = customer.id
            db.commit()
            
            # Select price based on plan
            price_id = resolve_price_id(STRIPE_PRICE_ID_BASIC) if plan == "basic" else resolve_price_id(STRIPE_PRICE_ID_PRO)
            
            if price_id:
                # Create checkout session
                base_url = str(request.base_url).rstrip('/')
                session = stripe.checkout.Session.create(
                    customer=customer.id,
                    payment_method_types=["card"],
                    line_items=[{"price": price_id}],
                    mode="subscription",
                    success_url=f"{base_url}/payment-success?session_id={{CHECKOUT_SESSION_ID}}",
                    cancel_url=f"{base_url}/payment-cancelled",
                    metadata={"plan": plan, "company_id": str(new_company.id)}
                )
                
                # Set auth cookie and redirect to Stripe
                response = RedirectResponse(url=session.url, status_code=302)
                token = create_token(
                    supervisor_id=new_supervisor.id,
                    company_id=new_company.id,
                    is_super_admin=False
                )
                response.set_cookie(key="auth_token", value=token, httponly=True, max_age=86400)
                return response
        except Exception as e:
            print(f"Stripe error during registration: {e}")
    
    # Fallback: redirect to choose plan page if Stripe not configured
    token = create_token(
        supervisor_id=new_supervisor.id,
        company_id=new_company.id,
        is_super_admin=False
    )
    response = RedirectResponse(url="/choose-plan", status_code=302)
    response.set_cookie(key="auth_token", value=token, httponly=True, max_age=86400)
    return response

# ===============================
# PAYMENT FLOW PAGES
# ===============================
@app.get("/choose-plan", response_class=HTMLResponse)
async def choose_plan_page(request: Request, db: Session = Depends(get_db)):
    """Show plan selection page for pending users"""
    token = get_token_from_cookies(request)
    if not token or not verify_token(token):
        return RedirectResponse(url="/login", status_code=302)
    
    token_data = verify_token(token)
    company = db.query(Company).filter(Company.id == token_data["company_id"]).first()
    
    # If already subscribed, go to dashboard
    if company and company.subscription_status not in ["pending", None]:
        return RedirectResponse(url="/", status_code=302)
    
    return templates.TemplateResponse("pricing.html", {
        "request": request,
        "show_signup": False,  # Hide signup form, show plan buttons only
        "company_name": company.name if company else ""
    })

@app.get("/payment-success", response_class=HTMLResponse)
async def payment_success_page(request: Request, session_id: str = None, db: Session = Depends(get_db)):
    """Handle successful payment - activate subscription and redirect to dashboard"""
    token = get_token_from_cookies(request)
    
    if session_id and stripe.api_key:
        try:
            # Retrieve the checkout session to get plan info
            checkout_session = stripe.checkout.Session.retrieve(session_id)
            company_id = checkout_session.metadata.get("company_id")
            plan = checkout_session.metadata.get("plan", "pro")
            
            if company_id:
                company = db.query(Company).filter(Company.id == int(company_id)).first()
                if company:
                    company.subscription_plan = plan
                    company.subscription_status = "active"
                    company.max_employees = 1000 if plan == "pro" else 100
                    db.commit()
                    print(f"✅ Payment success: {company.name} upgraded to {plan}")
        except Exception as e:
            print(f"Error processing payment success: {e}")
    
    # Redirect to dashboard with success param
    plan_param = "pro"
    if session_id:
        try:
            checkout_session = stripe.checkout.Session.retrieve(session_id)
            plan_param = checkout_session.metadata.get("plan", "pro")
        except:
            pass
    
    return RedirectResponse(url=f"/?payment=success&plan={plan_param}", status_code=302)

@app.get("/payment-cancelled", response_class=HTMLResponse)
async def payment_cancelled_page(request: Request):
    """Handle cancelled payment - redirect back to plan selection"""
    return RedirectResponse(url="/choose-plan?cancelled=true", status_code=302)

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
async def read_root(request: Request, db: Session = Depends(get_db)):
    """Root route - redirect based on login and subscription status"""
    token = get_token_from_cookies(request)
    if not token or not verify_token(token):
        return RedirectResponse(url="/home", status_code=302)
    
    token_data = verify_token(token)
    supervisor = db.query(Supervisor).filter(Supervisor.id == token_data["supervisor_id"]).first()
    company = db.query(Company).filter(Company.id == token_data["company_id"]).first()
    
    # Check if subscription is pending (not paid yet)
    if company and company.subscription_status == "pending":
        return RedirectResponse(url="/choose-plan", status_code=302)
    
    return templates.TemplateResponse("dashboard_new.html", {
        "request": request,
        "supervisor_name": supervisor.name if supervisor else "Admin",
        "company_name": company.name if company else "Company",
        "role": supervisor.role if supervisor else "viewer"
    })

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
        "company_name": company.name if company else "Company",
        "role": supervisor.role if supervisor else "viewer"
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

        # Get latest screenshot
        latest_screenshot = db.query(Screenshot).filter(
            Screenshot.employee_name == emp.name
        ).order_by(Screenshot.timestamp.desc()).first()

        logs_data.append({
            "id": emp.id,
            "employee_name": emp.name,
            "department": emp.department or "-",
            "status": status,
            "timestamp": last_log.timestamp if last_log else datetime.datetime.utcnow(),
            "present_time": f"{int(user_present//3600)}h {int((user_present%3600)//60)}m",
            "last_screenshot": latest_screenshot.image_data if latest_screenshot else None
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

class EmployeeUpdate(BaseModel):
    name: Optional[str] = None
    department: Optional[str] = None

@app.put("/api/employees/{employee_id}")
async def update_employee(employee_id: int, data: EmployeeUpdate, request: Request, db: Session = Depends(get_db)):
    """Update employee details (Admin only)"""
    token = get_token_from_cookies(request)
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    token_data = verify_token(token)
    if not token_data:
        raise HTTPException(status_code=401, detail="Invalid token")

    # RBAC Check
    current_sup = db.query(Supervisor).filter(Supervisor.id == token_data["supervisor_id"]).first()
    if not current_sup or current_sup.role != 'admin':
        raise HTTPException(status_code=403, detail="Viewer accounts cannot edit employees")
    
    # Check employee belongs to company
    employee = db.query(Employee).filter(
        Employee.id == employee_id,
        Employee.company_id == token_data["company_id"]
    ).first()
    
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")

    if data.name:
        employee.name = data.name
    if data.department:
        employee.department = data.department
    
    db.commit()
    return {"status": "ok", "message": "Employee updated"}

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

def update_stripe_usage(company_id: int, db: Session):
    """
    Syncs the Stripe subscription quantity with the number of active employees.
    Handles both per-seat (licensed) and metered billing modes, including flexible billing.
    """
    try:
        company = db.query(Company).filter(Company.id == company_id).first()
        if not company or not company.stripe_customer_id:
            print(f"⚠️ Company {company_id} has no Stripe ID. Skipping sync.")
            return

        employee_count = db.query(Employee).filter(Employee.company_id == company_id).count()
        
        if not stripe.api_key:
            print("⚠️ Stripe API key missing. Skipping sync.")
            return

        # Find active subscription
        subscriptions = stripe.Subscription.list(customer=company.stripe_customer_id, status='active', limit=1)
        if not subscriptions.data:
            print(f"⚠️ No active subscription for company {company.name}")
            return
            
        subscription = subscriptions.data[0]
        subscription_item_id = subscription['items']['data'][0].id
        
        # Update usage
        try:
            # Try standard quantity update (for Per-Seat / Licensed plans)
            stripe.SubscriptionItem.modify(
                subscription_item_id,
                quantity=employee_count
            )
            print(f"✅ Updated Stripe usage (Licensed) for {company.name}: {employee_count} employees")
        except stripe.error.InvalidRequestError as e:
            error_message = str(e)
            # Check for flexible billing or metered plan errors
            if "metered plans" in error_message or "billing_mode.type=flexible" in error_message or "quantity" in error_message:
                # Fallback for Metered/Flexible plans: Send usage record via raw API
                import requests
                
                resp = requests.post(
                    f"https://api.stripe.com/v1/subscription_items/{subscription_item_id}/usage_records",
                    auth=(stripe.api_key, ""),
                    data={
                        "quantity": employee_count,
                        "timestamp": int(datetime.datetime.utcnow().timestamp()),
                        "action": "set"
                    }
                )
                
                if not resp.ok:
                    if "billing/meter_events" in resp.text:
                        print("❌ Stripe Configuration Error: Your Price is set to 'New Metered Billing' which requires Event Streams.")
                        print("👉 ACTION REQUIRED: Please create a new Price in Stripe with 'Standard Pricing' (Recurring / Per-Seat).")
                        print("   Then update STRIPE_PRICE_ID in your environment variables.")
                    else:
                        print(f"❌ Stripe Usage Log Failed: {resp.text}")
                else:
                    print(f"✅ Updated Stripe usage (Metered/Flexible) for {company.name}: {employee_count} employees")
            else:
                raise e
        
    except Exception as e:
        import traceback
        print(f"❌ Error updating Stripe usage: {e}")
        # print(traceback.format_exc()) # Uncomment for deep debugging


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
    
    # Sync Stripe Usage
    update_stripe_usage(token_data["company_id"], db)
    
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

class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str

@app.post("/api/change-password")
async def change_password(data: ChangePasswordRequest, request: Request, db: Session = Depends(get_db)):
    """Change the current user's password"""
    token = get_token_from_cookies(request)
    if not token or not verify_token(token):
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    token_data = verify_token(token)
    supervisor = db.query(Supervisor).filter(Supervisor.id == token_data["supervisor_id"]).first()
    
    if not supervisor:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Verify current password
    if not supervisor.password_hash:
        raise HTTPException(status_code=400, detail="No password set. Please contact admin.")
    
    if not verify_password(data.current_password, supervisor.password_hash):
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    
    # Validate new password
    if len(data.new_password) < 8:
        raise HTTPException(status_code=400, detail="New password must be at least 8 characters")
    
    # Hash and save new password
    supervisor.password_hash = hash_password(data.new_password)
    db.commit()
    
    return {"status": "ok", "message": "Password updated successfully"}

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
        
        # Sync Stripe Usage - Add 1 employee to invoice immediately
        try:
            # We use background task or immediate call. Immediate for simplicity now.
            sync_stripe_quantity(db, token_data["company_id"])
        except Exception as e:
            print(f"⚠️ Failed to sync Stripe usage: {e}")

        return {"status": "ok", "invite_link": invite_link}
    except HTTPException as he:
        raise he
    except Exception as e:
        print(f"❌ Invite Error: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/employees/{employee_id}")
async def delete_employee(employee_id: int, request: Request, db: Session = Depends(get_db)):
    """Delete an employee and sync Stripe usage"""
    try:
        token = get_token_from_cookies(request)
        if not token or not verify_token(token):
            raise HTTPException(status_code=401, detail="Not authenticated")
        
        token_data = verify_token(token)
        company_id = token_data["company_id"]
        
        # RBAC Check
        current_sup = db.query(Supervisor).filter(Supervisor.id == token_data["supervisor_id"]).first()
        if not current_sup or current_sup.role != 'admin':
            raise HTTPException(status_code=403, detail="Viewer accounts cannot delete employees")
            
        employee = db.query(Employee).filter(Employee.id == employee_id, Employee.company_id == company_id).first()
        if not employee:
            raise HTTPException(status_code=404, detail="Employee not found")
            
        db.delete(employee)
        db.commit()
        
        # Sync Stripe Usage - Remove 1 employee from invoice immediately
        try:
            sync_stripe_quantity(db, company_id)
        except Exception as e:
            print(f"⚠️ Failed to sync Stripe usage: {e}")
            
        return {"status": "ok", "message": "Employee deleted"}
    except HTTPException as he:
        raise he
    except Exception as e:
        print(f"❌ Delete Error: {e}")
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

# ===============================
# STRIPE BILLING ENDPOINTS  
# ===============================
import stripe

stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
STRIPE_PRICE_ID_BASIC = os.getenv("STRIPE_PRICE_ID_BASIC")  # For Basic plan
STRIPE_PRICE_ID_PRO = os.getenv("STRIPE_PRICE_ID_PRO")      # For Pro plan (default upgrade)
STRIPE_PRICE_ID = os.getenv("STRIPE_PRICE_ID") or STRIPE_PRICE_ID_PRO  # Fallback
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET")

# Cache for resolved price IDs to avoid frequent API calls
_price_id_cache = {}

def resolve_price_id(price_or_product_id: str) -> Optional[str]:
    """
    Resolve a potential Product ID (prod_...) to its active Price ID (price_...).
    If the input is already a Price ID (price_... or plan_...), returns it as is.
    """
    if not price_or_product_id:
        return None
        
    # specific fix for user's explicit request if they stuck with prod_
    if price_or_product_id.startswith("prod_"):
        if price_or_product_id in _price_id_cache:
            return _price_id_cache[price_or_product_id]
            
        try:
            if not stripe.api_key:
                return None
            
            prices = stripe.Price.list(product=price_or_product_id, active=True, limit=1)
            if prices.data:
                resolved_id = prices.data[0].id
                _price_id_cache[price_or_product_id] = resolved_id
                print(f"🔧 Resolved Product {price_or_product_id} -> Price {resolved_id}")
                return resolved_id
            else:
                print(f"❌ No active price found for product {price_or_product_id}")
        except Exception as e:
            print(f"❌ Error resolving price ID: {e}")
            
    return price_or_product_id

def sync_stripe_quantity(db: Session, company_id: int):
    """
    Sync Stripe usage/quantity with local employee count.
    Delegates to the main update_stripe_usage function.
    """
    update_stripe_usage(company_id, db)

@app.get("/api/subscription-status")
async def get_subscription_status(request: Request, db: Session = Depends(get_db)):
    """Get current company subscription status"""
    token = get_token_from_cookies(request)
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    token_data = verify_token(token)
    if not token_data:
        raise HTTPException(status_code=401, detail="Invalid token")
    
    company = db.query(Company).filter(Company.id == token_data["company_id"]).first()
    employee_count = db.query(Employee).filter(Employee.company_id == company.id).count()
    
    return {
        "plan": company.subscription_plan or "free",
        "status": company.subscription_status or "active",
        "max_employees": company.max_employees or 5,
        "current_employees": employee_count,
        "can_add_employees": employee_count < (company.max_employees or 5)
    }

@app.post("/api/stripe/create-checkout")
async def create_checkout_session(request: Request, db: Session = Depends(get_db)):
    """Create Stripe Checkout Session for subscription upgrade"""
    # Parse request body for plan selection
    try:
        body = await request.json()
        plan = body.get("plan", "pro")  # Default to pro
    except:
        plan = "pro"
    
    # Select price based on plan
    if plan == "basic":
        price_id = resolve_price_id(STRIPE_PRICE_ID_BASIC)
    else:
        price_id = resolve_price_id(STRIPE_PRICE_ID_PRO) or resolve_price_id(STRIPE_PRICE_ID)
    
    if not stripe.api_key or not price_id:
        raise HTTPException(status_code=500, detail=f"Stripe not configured for {plan} plan. Please set STRIPE_SECRET_KEY and STRIPE_PRICE_ID_{plan.upper()}")
    
    token = get_token_from_cookies(request)
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    token_data = verify_token(token)
    if not token_data:
        raise HTTPException(status_code=401, detail="Invalid token")
    
    company = db.query(Company).filter(Company.id == token_data["company_id"]).first()
    supervisor = db.query(Supervisor).filter(Supervisor.id == token_data["supervisor_id"]).first()
    
    # Create or get Stripe Customer
    if not company.stripe_customer_id:
        customer = stripe.Customer.create(
            email=supervisor.email if supervisor else None,
            name=company.name,
            metadata={"company_id": str(company.id)}
        )
        company.stripe_customer_id = customer.id
        db.commit()
    
    # Determine base URL
    base_url = str(request.base_url).rstrip('/')
    
    # Create Checkout Session
    session = stripe.checkout.Session.create(
        customer=company.stripe_customer_id,
        payment_method_types=["card"],
        line_items=[{
            "price": price_id,
            "quantity": 1,  # Required by Stripe
        }],
        mode="subscription",
        success_url=f"{base_url}/?payment=success&plan={plan}",
        cancel_url=f"{base_url}/?payment=cancelled",
        metadata={"plan": plan}
    )
    
    return {"checkout_url": session.url}

@app.post("/api/stripe/webhook")
async def stripe_webhook(request: Request, db: Session = Depends(get_db)):
    """Handle Stripe webhook events"""
    if not STRIPE_WEBHOOK_SECRET:
        raise HTTPException(status_code=500, detail="Webhook secret not configured")
    
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")
    
    try:
        event = stripe.Webhook.construct_event(payload, sig_header, STRIPE_WEBHOOK_SECRET)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid payload")
    except stripe.error.SignatureVerificationError:
        raise HTTPException(status_code=400, detail="Invalid signature")
    
    # Handle subscription events
    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        customer_id = session.get("customer")
        
        if customer_id:
            company = db.query(Company).filter(Company.stripe_customer_id == customer_id).first()
            if company:
                company.subscription_plan = "pro"
                company.subscription_status = "active"
                company.max_employees = 1000  # Effectively unlimited for Pro
                db.commit()
                print(f"✅ Subscription activated for company: {company.name}")
    
    elif event["type"] == "customer.subscription.updated":
        subscription = event["data"]["object"]
        customer_id = subscription.get("customer")
        status = subscription.get("status")
        
        if customer_id:
            company = db.query(Company).filter(Company.stripe_customer_id == customer_id).first()
            if company:
                company.subscription_status = status
                
                # Sync plan from Stripe subscription when active
                if status == "active" and subscription.get("items"):
                    items = subscription["items"].get("data", [])
                    if items:
                        price_id = items[0].get("price", {}).get("id")
                        # Determine plan based on price ID
                        resolved_basic = resolve_price_id(STRIPE_PRICE_ID_BASIC)
                        resolved_pro = resolve_price_id(STRIPE_PRICE_ID_PRO) or resolve_price_id(STRIPE_PRICE_ID)
                        
                        if price_id == resolved_basic:
                            company.subscription_plan = "basic"
                            company.max_employees = 100
                            print(f"✅ Plan synced: {company.name} -> Basic")
                        elif price_id == resolved_pro:
                            company.subscription_plan = "pro"
                            company.max_employees = 1000
                            print(f"✅ Plan synced: {company.name} -> Pro")
                        else:
                            print(f"⚠️ Unknown price ID: {price_id}")
                
                if status in ["canceled", "unpaid"]:
                    company.subscription_plan = "free"
                    company.max_employees = 5
                db.commit()
    
    elif event["type"] == "customer.subscription.deleted":
        subscription = event["data"]["object"]
        customer_id = subscription.get("customer")
        
        if customer_id:
            company = db.query(Company).filter(Company.stripe_customer_id == customer_id).first()
            if company:
                company.subscription_plan = "free"
                company.subscription_status = "canceled"
                company.max_employees = 5
                db.commit()
                print(f"⚠️ Subscription canceled for company: {company.name}")
    
    elif event["type"] == "invoice.payment_failed":
        invoice = event["data"]["object"]
        customer_id = invoice.get("customer")
        
        if customer_id:
            company = db.query(Company).filter(Company.stripe_customer_id == customer_id).first()
            if company:
                company.subscription_status = "past_due"
                db.commit()
    
    return {"status": "success"}

@app.post("/api/stripe/report-usage")
async def report_employee_usage(db: Session = Depends(get_db)):
    """
    Report employee count to Stripe for metered billing.
    Call this endpoint daily via cron job (e.g., Render Cron Jobs or external scheduler).
    """
    if not stripe.api_key:
        raise HTTPException(status_code=500, detail="Stripe not configured")
    
    companies = db.query(Company).filter(
        Company.subscription_plan == "pro",
        Company.stripe_customer_id.isnot(None)
    ).all()
    
    reported = 0
    errors = []
    
    for company in companies:
        try:
            employee_count = db.query(Employee).filter(Employee.company_id == company.id).count()
            
            # Get active subscription
            subscriptions = stripe.Subscription.list(
                customer=company.stripe_customer_id, 
                status="active",
                limit=1
            )
            
            if subscriptions.data:
                sub_item_id = subscriptions.data[0]["items"]["data"][0]["id"]
                
                # Report usage (set to current count)
                # Use raw API for compatibility with flexible billing mode
                import requests
                resp = requests.post(
                    f"https://api.stripe.com/v1/subscription_items/{sub_item_id}/usage_records",
                    auth=(stripe.api_key, ""),
                    data={
                        "quantity": employee_count,
                        "timestamp": int(datetime.datetime.utcnow().timestamp()),
                        "action": "set"
                    }
                )
                
                if resp.ok:
                    reported += 1
                    print(f"📊 Reported {employee_count} employees for {company.name}")
                else:
                    errors.append({"company": company.name, "error": f"HTTP {resp.status_code}: {resp.text}"})
        except Exception as e:
            errors.append({"company": company.name, "error": str(e)})
    
    return {
        "status": "usage_reported",
        "companies_processed": reported,
        "errors": errors if errors else None
    }

@app.get("/api/stripe/portal")
async def create_customer_portal(request: Request, db: Session = Depends(get_db)):
    """Create Stripe Customer Portal session for managing subscription"""
    if not stripe.api_key:
        raise HTTPException(status_code=500, detail="Stripe not configured")
    
    token = get_token_from_cookies(request)
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    token_data = verify_token(token)
    if not token_data:
        raise HTTPException(status_code=401, detail="Invalid token")
    
    company = db.query(Company).filter(Company.id == token_data["company_id"]).first()
    
    if not company.stripe_customer_id:
        raise HTTPException(status_code=400, detail="No subscription found")
    
    base_url = str(request.base_url).rstrip('/')
    
    session = stripe.billing_portal.Session.create(
        customer=company.stripe_customer_id,
        return_url=f"{base_url}/"
    )
    
    return {"portal_url": session.url}

class ChangePlanRequest(BaseModel):
    plan: str  # 'basic' or 'pro'

@app.post("/api/stripe/change-plan")
async def change_subscription_plan(data: ChangePlanRequest, request: Request, db: Session = Depends(get_db)):
    """Change the subscription plan directly via Stripe API"""
    if not stripe.api_key:
        raise HTTPException(status_code=500, detail="Stripe not configured")
    
    token = get_token_from_cookies(request)
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    token_data = verify_token(token)
    if not token_data:
        raise HTTPException(status_code=401, detail="Invalid token")
    
    # RBAC Check - only admins can change plans
    current_sup = db.query(Supervisor).filter(Supervisor.id == token_data["supervisor_id"]).first()
    if not current_sup or current_sup.role != 'admin':
        raise HTTPException(status_code=403, detail="Only admins can change subscription plans")
    
    company = db.query(Company).filter(Company.id == token_data["company_id"]).first()
    
    if not company or not company.stripe_customer_id:
        raise HTTPException(status_code=400, detail="No subscription found")
    
    # Get the target price ID
    if data.plan == "basic":
        new_price_id = resolve_price_id(STRIPE_PRICE_ID_BASIC)
        new_max_employees = 100
    elif data.plan == "pro":
        new_price_id = resolve_price_id(STRIPE_PRICE_ID_PRO) or resolve_price_id(STRIPE_PRICE_ID)
        new_max_employees = 1000
    else:
        raise HTTPException(status_code=400, detail="Invalid plan. Must be 'basic' or 'pro'")
    
    if not new_price_id:
        raise HTTPException(status_code=500, detail=f"Price ID for {data.plan} plan not configured")
    
    try:
        # Get current subscription
        subscriptions = stripe.Subscription.list(
            customer=company.stripe_customer_id,
            status="active",
            limit=1
        )
        
        if not subscriptions.data:
            raise HTTPException(status_code=400, detail="No active subscription found")
        
        subscription = subscriptions.data[0]
        subscription_item_id = subscription["items"]["data"][0]["id"]
        
        # Update the subscription to the new price
        stripe.Subscription.modify(
            subscription.id,
            items=[{
                "id": subscription_item_id,
                "price": new_price_id
            }],
            proration_behavior="create_prorations"  # Prorated billing
        )
        
        # Update local database
        company.subscription_plan = data.plan
        company.max_employees = new_max_employees
        db.commit()
        
        # Sync employee count to new subscription
        update_stripe_usage(company.id, db)
        
        print(f"✅ Plan changed: {company.name} -> {data.plan.upper()}")
        
        return {
            "status": "success",
            "message": f"Successfully changed to {data.plan.upper()} plan",
            "new_plan": data.plan,
            "max_employees": new_max_employees
        }
        
    except stripe.error.StripeError as e:
        print(f"❌ Stripe error changing plan: {e}")
        raise HTTPException(status_code=400, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)