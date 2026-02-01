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
    
    # Relationships
    employees = relationship("Employee", back_populates="company")
    supervisors = relationship("Supervisor", back_populates="company")

# --- Supervisor Model (Dashboard Users) ---
class Supervisor(Base):
    __tablename__ = "supervisors"
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True)
    password_hash = Column(String)
    name = Column(String)
    company_id = Column(Integer, ForeignKey("companies.id"))
    is_super_admin = Column(Integer, default=0)  # 1 = can see all companies
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
    is_active = Column(Integer, default=0)
    department = Column(String, nullable=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=True)
    last_heartbeat = Column(DateTime, nullable=True)  # Track when app last pinged
    
    # Relationship
    company = relationship("Company", back_populates="employees")

# --- Activity Log Model ---
class EmployeeLog(Base):
    __tablename__ = "logs"
    id = Column(Integer, primary_key=True, index=True)
    employee_name = Column(String)
    status = Column(String)  # WORK_START, BREAK_START, BREAK_END, etc.
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)

# Create tables
Base.metadata.create_all(bind=engine)