-- Setup authentication for remote connections
-- This ensures the challenge_user can connect from the host machine

-- Verify the user exists and has correct password
ALTER USER challenge_user WITH PASSWORD 'secure_password';

-- Grant necessary permissions
GRANT CONNECT ON DATABASE challenge2 TO challenge_user;
GRANT USAGE ON SCHEMA public TO challenge_user;
GRANT CREATE ON SCHEMA public TO challenge_user;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO challenge_user;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO challenge_user;

-- Make sure future tables are accessible
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL PRIVILEGES ON TABLES TO challenge_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL PRIVILEGES ON SEQUENCES TO challenge_user;

-- Display connection info
SELECT 'User setup complete. Connection string: postgresql://challenge_user:secure_password@localhost:5432/challenge2';
