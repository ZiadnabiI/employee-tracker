"""
Migration: Add password_reset_token and password_reset_expires to supervisors table.
Run this once against your production database.
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine, text

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./analytics.db")
if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

engine = create_engine(DATABASE_URL)

COLUMNS = [
    ("supervisors", "password_reset_token", "VARCHAR"),
    ("supervisors", "password_reset_expires", "TIMESTAMP"),
]

with engine.connect() as conn:
    for table, column, col_type in COLUMNS:
        try:
            conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}"))
            conn.commit()
            print(f"✅ Added {table}.{column}")
        except Exception as e:
            if "duplicate column" in str(e).lower() or "already exists" in str(e).lower():
                print(f"⏭️  {table}.{column} already exists, skipping")
            else:
                print(f"❌ Error adding {table}.{column}: {e}")

print("\n✅ Migration complete!")
