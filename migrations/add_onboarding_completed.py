"""
Migration: Add onboarding_completed column to companies table.
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
        conn.execute(text("ALTER TABLE companies ADD COLUMN onboarding_completed INTEGER DEFAULT 0"))
        conn.commit()
        print("✅ Added companies.onboarding_completed")
    except Exception as e:
        if "duplicate column" in str(e).lower() or "already exists" in str(e).lower():
            print("⏭️  companies.onboarding_completed already exists, skipping")
        else:
            print(f"❌ Error: {e}")

    # Mark all existing companies as onboarding complete (they predate the wizard)
    try:
        conn.execute(text("UPDATE companies SET onboarding_completed = 1 WHERE onboarding_completed IS NULL OR onboarding_completed = 0"))
        conn.commit()
        print("✅ Marked existing companies as onboarding complete")
    except Exception as e:
        print(f"❌ Error updating existing companies: {e}")

print("\n✅ Migration complete!")
