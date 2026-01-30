from sqlalchemy import create_engine, Column, Integer, String, DateTime
from sqlalchemy.orm import sessionmaker, declarative_base
import datetime

import os

# Use DATABASE_URL from environment if available (for Production/Postgres)
# Fallback to local SQLite if not set (for testing)
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./analytics.db")

# Fix for SQLAlchemy: it requires 'postgresql://', but some providers (Supabase/Heroku) return 'postgres://'
if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# DEBUG: Print checking
if "sqlite" in DATABASE_URL:
    print(f"⚠️  Using LOCAL SQLite database: {DATABASE_URL}")
else:
    masked_url = DATABASE_URL.split("@")[-1] if "@" in DATABASE_URL else "..."
    print(f"✅  Using CLOUD Postgres database: ...@{masked_url}")

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()

class EmployeeLog(Base):
    __tablename__ = "logs"
    id = Column(Integer, primary_key=True, index=True)
    employee_name = Column(String)

    status = Column(String)  # "WORK_START", "BREAK_START", "BREAK_END", etc.
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)

class Employee(Base):
    __tablename__ = "employees"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    activation_key = Column(String, unique=True, index=True)
    hardware_id = Column(String, nullable=True) # Binds the key to a specific device
    is_active = Column(Integer, default=0) # 0 = False, 1 = True (using Integer for SQLite boolean compat)
    department = Column(String, nullable=True)

Base.metadata.create_all(bind=engine)