-- Add role column to supervisors table
ALTER TABLE supervisors ADD COLUMN role VARCHAR DEFAULT 'owner';
