import sqlite3

db_path = "analytics.db"

sql_commands = [
    "ALTER TABLE companies ADD COLUMN screenshot_frequency INTEGER DEFAULT 600",
    "ALTER TABLE companies ADD COLUMN dlp_enabled INTEGER DEFAULT 0",
    "ALTER TABLE companies ADD COLUMN slack_webhook_url VARCHAR"
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
