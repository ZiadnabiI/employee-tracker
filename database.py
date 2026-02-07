from sqlalchemy import create_engine, Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import sessionmaker, declarative_base, relationship
import datetime
import os

# Use DATABASE_URL from environment if available (for Production/Postgres)
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./analytics.db")

# Fix for SQLAlchemy: postgres:// → postgresql://
if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

if "sqlite" in DATABASE_URL:
    print(f"⚠️  Using LOCAL SQLite database: {DATABASE_URL}")
else:
    masked_url = DATABASE_URL.split("@")[-1] if "@" in DATABASE_URL else "..."
    print(f"✅  Using CLOUD Postgres database: ...@{masked_url}")

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()

# --- Company Model ---
class Company(Base):
    __tablename__ = "companies"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    
    # SaaS / Subscription Fields
    subscription_plan = Column(String, default="free") # free, pro, enterprise
    subscription_status = Column(String, default="active") # active, past_due, canceled
    subscription_end_date = Column(DateTime, nullable=True)
    stripe_customer_id = Column(String, nullable=True)
    max_employees = Column(Integer, default=5)
    screenshot_frequency = Column(Integer, default=600) # Seconds between screenshots
    dlp_enabled = Column(Integer, default=0) # 0=Disabled, 1=Enabled (Manual DB toggle)
    
    # Relationships
    employees = relationship("Employee", back_populates="company")
    supervisors = relationship("Supervisor", back_populates="company")
    departments = relationship("Department", back_populates="company")

# --- Department Model ---
class Department(Base):
    __tablename__ = "departments"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String)
    company_id = Column(Integer, ForeignKey("companies.id"))
    
    company = relationship("Company", back_populates="departments")

# --- Supervisor Model (Dashboard Users) ---
class Supervisor(Base):
    __tablename__ = "supervisors"
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True)
    password_hash = Column(String)
    name = Column(String)
    company_id = Column(Integer, ForeignKey("companies.id"))
    is_super_admin = Column(Integer, default=0)  # 1 = can see all companies
    role = Column(String, default="owner") # owner, admin, viewer
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    
    # Relationship
    company = relationship("Company", back_populates="supervisors")

# --- Employee Model ---
class Employee(Base):
    __tablename__ = "employees"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    activation_key = Column(String, unique=True, index=True)
    hardware_id = Column(String, nullable=True)
    is_active = Column(Integer, default=0) # 0=Inactive, 1=Active
    department = Column(String, nullable=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=True)
    
    # Auth & Invitation
    email = Column(String, unique=True, index=True, nullable=True)
    password_hash = Column(String, nullable=True)
    invite_token = Column(String, index=True, nullable=True)
    invite_expires = Column(DateTime, nullable=True)
    is_registered = Column(Integer, default=0) # 0=Pending, 1=Registered
    
    # Activity Stats
    last_heartbeat = Column(DateTime, nullable=True)  # Track when app last pinged
    pending_screenshot = Column(Integer, default=0)   # 1 if screenshot requested
    
    # Relationship
    company = relationship("Company", back_populates="employees")

# --- Activity Log Model ---
class EmployeeLog(Base):
    __tablename__ = "logs"
    id = Column(Integer, primary_key=True, index=True)
    employee_name = Column(String)
    status = Column(String)  # WORK_START, BREAK_START, BREAK_END, etc.
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)

# --- App Usage Log Model ---
class AppLog(Base):
    __tablename__ = "app_logs"
    id = Column(Integer, primary_key=True, index=True)
    employee_name = Column(String, index=True)
    app_name = Column(String)         # e.g., "chrome.exe"
    window_title = Column(String)     # e.g., "YouTube - Google Chrome"
    duration_seconds = Column(Integer, default=0)  # How long on this app
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)

# --- Screenshot Model ---
class Screenshot(Base):
    __tablename__ = "screenshots"
    id = Column(Integer, primary_key=True, index=True)
    employee_name = Column(String, index=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=True)
    image_data = Column(String)  # Base64 encoded image
    manual_request = Column(Integer, default=0)  # 1 if manually requested by supervisor
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)

# --- AuthToken Model (for persistent token storage) ---
class AuthToken(Base):
    __tablename__ = "auth_tokens"
    id = Column(Integer, primary_key=True, index=True)
    token = Column(String(255), unique=True, index=True)  # Fixed length for efficiency
    supervisor_id = Column(Integer, ForeignKey("supervisors.id"))
    company_id = Column(Integer, ForeignKey("companies.id"))
    is_super_admin = Column(Integer, default=0)
    expires = Column(DateTime)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

# Create tables
Base.metadata.create_all(bind=engine)