-- Migration: Create screenshots table
-- Run this on Supabase

CREATE TABLE IF NOT EXISTS screenshots (
    id SERIAL PRIMARY KEY,
    employee_name VARCHAR NOT NULL,
    company_id INTEGER REFERENCES companies(id),
    image_data TEXT,
    manual_request INTEGER DEFAULT 0,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_screenshots_employee ON screenshots(employee_name);
CREATE INDEX IF NOT EXISTS idx_screenshots_timestamp ON screenshots(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_screenshots_company ON screenshots(company_id);
