-- Migration: Add dlp_enabled to companies table
-- Default false. Toggle manually in DB to enable.

ALTER TABLE companies ADD COLUMN IF NOT EXISTS dlp_enabled INTEGER DEFAULT 0;
