-- Add subscription columns to companies table
ALTER TABLE companies ADD COLUMN subscription_plan VARCHAR DEFAULT 'free';
ALTER TABLE companies ADD COLUMN subscription_status VARCHAR DEFAULT 'active';
ALTER TABLE companies ADD COLUMN subscription_end_date TIMESTAMP;
ALTER TABLE companies ADD COLUMN stripe_customer_id VARCHAR;
ALTER TABLE companies ADD COLUMN max_employees INTEGER DEFAULT 5;
