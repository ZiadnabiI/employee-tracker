import os
from sqlalchemy import create_engine, text

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    print("No DATABASE_URL found. Testing locally.")
    DATABASE_URL = "sqlite:///./analytics.db"

if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

engine = create_engine(DATABASE_URL)

with engine.connect() as conn:
    try:
        conn.execute(text("ALTER TABLE companies ADD COLUMN slack_webhook_url VARCHAR;"))
        conn.commit()
        print("Successfully added slack_webhook_url to companies table.")
    except Exception as e:
        print(f"Migration error (column might already exist): {e}")
