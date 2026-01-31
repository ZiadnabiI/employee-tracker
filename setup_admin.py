"""
Setup script to create initial company and supervisor
Run this once to initialize the system
"""
import sys
sys.path.insert(0, '.')

from database import SessionLocal, Company, Supervisor, Base, engine
from auth import hash_password

def setup():
    # Create tables
    Base.metadata.create_all(bind=engine)
    
    db = SessionLocal()
    
    try:
        # Check if company exists
        company = db.query(Company).filter(Company.name == "Demo Company").first()
        if not company:
            company = Company(name="Demo Company")
            db.add(company)
            db.commit()
            db.refresh(company)
            print(f"✅ Created company: {company.name} (ID: {company.id})")
        else:
            print(f"ℹ️  Company already exists: {company.name} (ID: {company.id})")
        
        # Check if supervisor exists
        supervisor = db.query(Supervisor).filter(Supervisor.email == "admin@demo.com").first()
        if not supervisor:
            supervisor = Supervisor(
                email="admin@demo.com",
                password_hash=hash_password("admin123"),
                name="Admin User",
                company_id=company.id,
                is_super_admin=1
            )
            db.add(supervisor)
            db.commit()
            print(f"✅ Created supervisor: {supervisor.email}")
        else:
            print(f"ℹ️  Supervisor already exists: {supervisor.email}")
        
        print("\n" + "="*50)
        print("🔐 LOGIN CREDENTIALS:")
        print("="*50)
        print(f"   Email:    admin@demo.com")
        print(f"   Password: admin123")
        print("="*50)
        print("\nYou can now login at: http://localhost:8000/login")
        
    finally:
        db.close()

if __name__ == "__main__":
    setup()
