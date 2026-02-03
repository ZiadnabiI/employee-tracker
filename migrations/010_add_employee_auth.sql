-- Migration: Add Authentication fields to employees table
-- Support for Email/Password login and Invitation System

ALTER TABLE employees ADD COLUMN IF NOT EXISTS email VARCHAR(255);
ALTER TABLE employees ADD COLUMN IF NOT EXISTS password_hash VARCHAR(255);
ALTER TABLE employees ADD COLUMN IF NOT EXISTS invite_token VARCHAR(255);
ALTER TABLE employees ADD COLUMN IF NOT EXISTS invite_expires DATETIME;
ALTER TABLE employees ADD COLUMN IF NOT EXISTS is_registered INTEGER DEFAULT 0;

-- Ensure email is unique per company (or globally unique if preferred, here globally for simplicity)
CREATE UNIQUE INDEX IF NOT EXISTS idx_employees_email ON employees(email);
CREATE INDEX IF NOT EXISTS idx_employees_invite_token ON employees(invite_token);
