-- Migration for Multi-Tenant Dashboard
-- Run this in Supabase SQL Editor

-- 1. Create companies table
CREATE TABLE IF NOT EXISTS companies (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) UNIQUE NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 2. Create supervisors table
CREATE TABLE IF NOT EXISTS supervisors (
    id SERIAL PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    name VARCHAR(255) NOT NULL,
    company_id INTEGER REFERENCES companies(id),
    is_super_admin INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 3. Add company_id to employees table (if not exists)
DO $$ 
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'employees' AND column_name = 'company_id'
    ) THEN
        ALTER TABLE employees ADD COLUMN company_id INTEGER REFERENCES companies(id);
    END IF;
END $$;

-- 4. Create index for faster lookups
CREATE INDEX IF NOT EXISTS idx_supervisors_email ON supervisors(email);
CREATE INDEX IF NOT EXISTS idx_supervisors_company ON supervisors(company_id);
CREATE INDEX IF NOT EXISTS idx_employees_company ON employees(company_id);

-- 5. Insert demo company and admin supervisor
-- Password hash for 'admin123' using SHA-256 with salt 'employee_tracker_salt'
INSERT INTO companies (name) VALUES ('Demo Company') ON CONFLICT (name) DO NOTHING;

INSERT INTO supervisors (email, password_hash, name, company_id, is_super_admin)
SELECT 'admin@demo.com', 
       '52c48963942ae4abaceb86dbe90147f1fa865add9e7a317faf8b3677b2d75dab3',
       'Admin User',
       (SELECT id FROM companies WHERE name = 'Demo Company'),
       1
WHERE NOT EXISTS (SELECT 1 FROM supervisors WHERE email = 'admin@demo.com');
