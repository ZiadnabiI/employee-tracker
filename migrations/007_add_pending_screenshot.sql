-- Migration: Add pending_screenshot to employees table
-- Run this on Supabase

ALTER TABLE employees ADD COLUMN IF NOT EXISTS pending_screenshot INTEGER DEFAULT 0;
