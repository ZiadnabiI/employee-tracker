
import sqlite3

db_path = "analytics.db"

sql_commands = [
    "ALTER TABLE companies ADD COLUMN subscription_plan VARCHAR DEFAULT 'free'",
    "ALTER TABLE companies ADD COLUMN subscription_status VARCHAR DEFAULT 'active'",
    "ALTER TABLE companies ADD COLUMN subscription_end_date TIMESTAMP",
    "ALTER TABLE companies ADD COLUMN stripe_customer_id VARCHAR",
    "ALTER TABLE companies ADD COLUMN max_employees INTEGER DEFAULT 5"
]

def apply_fix():
    print(f"Connecting to {db_path}...")
    try:
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        
        for cmd in sql_commands:
            try:
                print(f"Executing: {cmd}")
                cur.execute(cmd)
            except sqlite3.OperationalError as e:
                if "duplicate column" in str(e).lower():
                    print(f"  ⚠️ Skipped (already exists)")
                else:
                    print(f"  ❌ Error: {e}")
        
        conn.commit()
        conn.close()
        print("✅ Database patch completed.")
        
    except Exception as e:
        print(f"❌ Connection failed: {e}")

if __name__ == "__main__":
    apply_fix()
