-- Migration: Add screenshot_frequency to companies table
-- Default 600 seconds (10 minutes)

ALTER TABLE companies ADD COLUMN IF NOT EXISTS screenshot_frequency INTEGER DEFAULT 600;
