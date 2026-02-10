-- Migration: Change screenshots table from base64 image_data to blob_url
-- Run AFTER running migrate_screenshots_to_blob.py to preserve existing data

-- Step 1: Add blob_url column (if not exists)
ALTER TABLE screenshots ADD COLUMN IF NOT EXISTS blob_url TEXT;

-- Step 2: Drop the old image_data column (only after data migration)
-- Uncomment this AFTER running migrate_screenshots_to_blob.py
-- ALTER TABLE screenshots DROP COLUMN IF EXISTS image_data;
