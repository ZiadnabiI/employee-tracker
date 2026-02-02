-- Create app_logs table for tracking application usage
CREATE TABLE IF NOT EXISTS app_logs (
    id SERIAL PRIMARY KEY,
    employee_name VARCHAR NOT NULL,
    app_name VARCHAR NOT NULL,
    window_title VARCHAR,
    duration_seconds INTEGER DEFAULT 0,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create index for faster queries by employee
CREATE INDEX IF NOT EXISTS idx_app_logs_employee ON app_logs(employee_name);
CREATE INDEX IF NOT EXISTS idx_app_logs_timestamp ON app_logs(timestamp);
