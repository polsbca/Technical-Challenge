-- Configure authentication for remote connections
-- Run after database initialization

-- This file configures pg_hba.conf entry updates via SQL
-- Since we can't directly modify pg_hba.conf after startup without a restart,
-- we'll use PostgreSQL's ALTER SYSTEM to set the password_encryption method

-- Note: pg_hba.conf modifications require a restart to take effect
-- This script will be run by the init script runner
