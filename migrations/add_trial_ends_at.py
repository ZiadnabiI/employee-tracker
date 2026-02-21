"""
Migration: Add trial_ends_at column to companies table.
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

with engine.connect() as conn:
    try:
        conn.execute(text("ALTER TABLE companies ADD COLUMN trial_ends_at TIMESTAMP"))
        conn.commit()
        print("✅ Added companies.trial_ends_at")
    except Exception as e:
        if "duplicate column" in str(e).lower() or "already exists" in str(e).lower():
            print("⏭️  companies.trial_ends_at already exists, skipping")
        else:
            print(f"❌ Error: {e}")

print("\n✅ Migration complete!")
