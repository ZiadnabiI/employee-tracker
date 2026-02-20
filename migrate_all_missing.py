import os
try:
    import psycopg2
except ImportError:
    psycopg2 = None
import sqlite3

# Define all missing columns correctly for both engines:
migrations = [
    # Company missing columns
    {"table": "companies", "column": "screenshot_frequency", "sqlite_type": "INTEGER DEFAULT 600", "pg_type": "INTEGER DEFAULT 600"},
    {"table": "companies", "column": "dlp_enabled", "sqlite_type": "INTEGER DEFAULT 0", "pg_type": "INTEGER DEFAULT 0"},
    {"table": "companies", "column": "slack_webhook_url", "sqlite_type": "VARCHAR", "pg_type": "VARCHAR"},
    
    # Supervisors missing columns
    {"table": "supervisors", "column": "role", "sqlite_type": "VARCHAR DEFAULT 'owner'", "pg_type": "VARCHAR DEFAULT 'owner'"},
    
    # Employees missing columns
    {"table": "employees", "column": "company_id", "sqlite_type": "INTEGER", "pg_type": "INTEGER"},
    {"table": "employees", "column": "pending_screenshot", "sqlite_type": "INTEGER DEFAULT 0", "pg_type": "INTEGER DEFAULT 0"},
    {"table": "employees", "column": "last_heartbeat", "sqlite_type": "DATETIME", "pg_type": "TIMESTAMP"},
    
    # Screenshots missing columns
    {"table": "screenshots", "column": "blob_url", "sqlite_type": "VARCHAR", "pg_type": "VARCHAR"}
]

def migrate_sqlite():
    db_path = "analytics.db"
    print(f"\n🚀 Connecting to SQLite: {db_path}...")
    try:
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        
        for m in migrations:
            cmd = f"ALTER TABLE {m['table']} ADD COLUMN {m['column']} {m['sqlite_type']}"
            try:
                cur.execute(cmd)
                print(f"  ✅ Added {m['column']} to {m['table']}")
            except sqlite3.OperationalError as e:
                if "duplicate column" in str(e).lower():
                    print(f"  ⚠️ Skipped {m['column']} (already exists)")
                else:
                    print(f"  ❌ Error adding {m['column']}: {e}")
                    
        conn.commit()
        conn.close()
        print("✅ Local SQLite database patch completed.")
        
    except Exception as e:
        print(f"❌ Connection failed: {e}")

def migrate_postgres(url):
    if not psycopg2:
        print("❌ Cannot connect to Postgres. Please install psycopg2-binary: `pip install psycopg2-binary`")
        return
        
    print(f"\n🚀 Connecting to Supabase Postgres...")
    try:
        conn = psycopg2.connect(url)
        conn.autocommit = True
        cur = conn.cursor()
        
        for m in migrations:
            cmd = f"ALTER TABLE {m['table']} ADD COLUMN IF NOT EXISTS {m['column']} {m['pg_type']}"
            try:
                cur.execute(cmd)
                print(f"  ✅ Added {m['column']} to {m['table']}")
            except Exception as e:
                print(f"  ❌ Error adding {m['column']}: {e}")
                
        conn.close()
        print("✅ Production Supabase database patch completed.")
        
    except Exception as e:
        print(f"❌ Connection failed: {e}")

if __name__ == "__main__":
    print("Welcome to the Comprehensive Database Schema Fixer")
    print("1: Fix Local Database (SQLite)")
    print("2: Fix Production Database (Supabase / Postgres)")
    
    choice = input("Select an option (1 or 2): ").strip()
    
    if choice == "1":
        migrate_sqlite()
    elif choice == "2":
        url = input("Paste your Supabase Connection String (Transaction Pooler recommended):\nURL: ").strip()
        if "[YOUR-PASSWORD]" in url:
            print("❌ Error: You must replace '[YOUR-PASSWORD]' with your actual database password.")
        else:
            migrate_postgres(url)
    else:
        print("Invalid selection.")
