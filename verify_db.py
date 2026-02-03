from sqlalchemy import inspect
from database import engine

def check_db():
    print("🔍 Inspecting Database Schema...")
    inspector = inspect(engine)
    
    if "employees" not in inspector.get_table_names():
        print("❌ Table 'employees' NOT found!")
        return

    columns = [col['name'] for col in inspector.get_columns("employees")]
    
    required_fields = ["email", "password_hash", "invite_token", "is_registered"]
    missing = [field for field in required_fields if field not in columns]
    
    if missing:
        print(f"❌ Missing columns in 'employees' table: {missing}")
        print("💡 You need to run the migration script.")
    else:
        print("✅ All required columns (email, password, etc.) are present.")
        print("📊 Current Columns:", ", ".join(columns))

if __name__ == "__main__":
    check_db()
