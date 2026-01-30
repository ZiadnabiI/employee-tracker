from sqlalchemy import create_engine
from database import Base

# I have pre-filled this with the URL you provided in the logs.
# SUPABASE_URL = "postgresql://postgres:4PVWriHNrcHRTAFD@db.fobrhwotpsyhwmwwdrjp.supabase.co:5432/postgres"

print("Please paste your Supabase Connection String (Transaction Pooler recommended):")
SUPABASE_URL = input("URL: ").strip()

# If user copies the one with [YOUR-PASSWORD], warn them
if "[YOUR-PASSWORD]" in SUPABASE_URL:
    print("❌ Error: You must replace '[YOUR-PASSWORD]' with your actual database password.")
    exit(1)

print(f"🚀 Connecting to Supabase: {SUPABASE_URL}")

try:
    engine = create_engine(SUPABASE_URL)
    print("🔨 Creating tables...")
    Base.metadata.create_all(bind=engine)
    print("✅ SUCCESS! Tables created in Supabase.")
except Exception as e:
    print(f"❌ Error: {e}")
