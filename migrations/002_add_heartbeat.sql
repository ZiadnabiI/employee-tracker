-- Add heartbeat tracking column
ALTER TABLE employees ADD COLUMN IF NOT EXISTS last_heartbeat TIMESTAMP;

-- Note: For SQLite, use:
-- ALTER TABLE employees ADD COLUMN last_heartbeat DATETIME;
