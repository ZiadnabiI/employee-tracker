import sqlite3

db_path = "analytics.db"

def add_column_if_not_exists(cursor, table, column, definition):
    try:
        cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")
        print(f"✅ Added column {column} to {table}")
    except sqlite3.OperationalError as e:
        if "duplicate column" in str(e).lower():
            print(f"ℹ️  Column {column} already exists in {table}")
        else:
            print(f"❌ Failed to add {column}: {e}")

try:
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    
    # Add columns one by one
    print("🔄 Running migration...")
    
    add_column_if_not_exists(cur, "employees", "email", "VARCHAR(255)")
    add_column_if_not_exists(cur, "employees", "password_hash", "VARCHAR(255)")
    add_column_if_not_exists(cur, "employees", "invite_token", "VARCHAR(255)")
    add_column_if_not_exists(cur, "employees", "invite_expires", "DATETIME")
    add_column_if_not_exists(cur, "employees", "is_registered", "INTEGER DEFAULT 0")

    # Create indices
    try:
        cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_employees_email ON employees(email)")
        print("✅ Created index idx_employees_email")
    except Exception as e:
        print(f"⚠️ Index error: {e}")

    try:
        cur.execute("CREATE INDEX IF NOT EXISTS idx_employees_invite_token ON employees(invite_token)")
        print("✅ Created index idx_employees_invite_token")
    except Exception as e:
        print(f"⚠️ Index error: {e}")

    conn.commit()
    conn.close()
    print("🎉 Migration completed successfully!")
    
except Exception as e:
    print(f"❌ Migration failed: {e}")
