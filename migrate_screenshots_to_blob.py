"""
One-time migration script: Move existing base64 screenshots from DB to Azure Blob Storage.

Run this script AFTER:
  1. Setting AZURE_STORAGE_CONNECTION_STRING and AZURE_STORAGE_CONTAINER env vars
  2. Running migration 009_screenshot_blob_url.sql (adds blob_url column)

Run this script BEFORE:
  - Dropping the image_data column from the screenshots table

Usage:
  python migrate_screenshots_to_blob.py
"""

import os
import sys
import base64

# Set up environment
if not os.getenv("AZURE_STORAGE_CONNECTION_STRING"):
    print("❌ AZURE_STORAGE_CONNECTION_STRING environment variable is required.")
    print("   Set it and run again.")
    sys.exit(1)

from database import SessionLocal, engine
from sqlalchemy import text
from blob_storage import upload_screenshot as blob_upload_screenshot

def migrate():
    db = SessionLocal()
    
    try:
        # Check if image_data column still exists
        result = db.execute(text(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name='screenshots' AND column_name='image_data'"
        )).fetchone()
        
        if not result:
            print("⚠️  Column 'image_data' not found. Nothing to migrate.")
            return
        
        # Get all screenshots that have image_data but no blob_url
        rows = db.execute(text(
            "SELECT id, employee_name, company_id, image_data, manual_request "
            "FROM screenshots WHERE image_data IS NOT NULL AND (blob_url IS NULL OR blob_url = '')"
        )).fetchall()
        
        total = len(rows)
        if total == 0:
            print("✅ No screenshots to migrate. All done!")
            return
        
        print(f"📦 Found {total} screenshots to migrate...")
        
        success = 0
        failed = 0
        
        for i, row in enumerate(rows, 1):
            try:
                # Decode base64 to bytes
                image_bytes = base64.b64decode(row.image_data)
                
                # Upload to Azure Blob Storage
                blob_url = blob_upload_screenshot(
                    employee_name=row.employee_name or "unknown",
                    company_id=row.company_id or 0,
                    image_bytes=image_bytes,
                    manual=bool(row.manual_request)
                )
                
                if blob_url:
                    # Update the DB row with the blob URL
                    db.execute(text(
                        "UPDATE screenshots SET blob_url = :url WHERE id = :id"
                    ), {"url": blob_url, "id": row.id})
                    db.commit()
                    success += 1
                    print(f"  [{i}/{total}] ✅ Migrated screenshot #{row.id} for {row.employee_name}")
                else:
                    failed += 1
                    print(f"  [{i}/{total}] ❌ Failed to upload screenshot #{row.id}")
                    
            except Exception as e:
                failed += 1
                print(f"  [{i}/{total}] ❌ Error on screenshot #{row.id}: {e}")
        
        print(f"\n{'='*50}")
        print(f"Migration complete: {success} succeeded, {failed} failed out of {total}")
        
        if failed == 0:
            print("\n✅ All screenshots migrated! You can now safely drop the image_data column:")
            print("   ALTER TABLE screenshots DROP COLUMN IF EXISTS image_data;")
        else:
            print("\n⚠️  Some screenshots failed. Fix errors and re-run this script.")
            print("   Only successfully migrated rows will be skipped on re-run.")
    
    finally:
        db.close()

if __name__ == "__main__":
    migrate()
