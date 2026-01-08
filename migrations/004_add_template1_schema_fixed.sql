-- Migration: Add Template 1 Schema (Fixed)
-- Description: Adds tables and fields needed for Template 1 scope matrix
-- Version: 1.1 - Removed users table dependency

-- Add template_scope_categories table
CREATE TABLE IF NOT EXISTS template_scope_categories (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE,
    description TEXT,
    display_order INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Add template_scopes table (aligned with Template 1.xlsx columns)
CREATE TABLE IF NOT EXISTS template_scopes (
    id SERIAL PRIMARY KEY,
    scope_key VARCHAR(100) NOT NULL UNIQUE,
    name VARCHAR(200) NOT NULL,
    description TEXT,
    category_id INTEGER REFERENCES template_scope_categories(id),
    is_required BOOLEAN DEFAULT FALSE,
    data_type VARCHAR(20) DEFAULT 'boolean',
    validation_rules JSONB,
    display_order INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Add company_scope_responses table (stores Template 1 scope responses)
CREATE TABLE IF NOT EXISTS company_scope_responses (
    id SERIAL PRIMARY KEY,
    company_id INTEGER NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    template_scope_id INTEGER NOT NULL REFERENCES template_scopes(id) ON DELETE CASCADE,
    response_value JSONB,
    confidence DECIMAL(3, 2) NOT NULL DEFAULT 1.0,
    source_document_type VARCHAR(50),
    source_url VARCHAR(2048),
    extraction_method VARCHAR(50),
    reasoning TEXT,
    is_verified BOOLEAN DEFAULT FALSE,
    -- Removed verified_by foreign key to avoid dependency on users table
    verified_by INTEGER,
    verified_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(company_id, template_scope_id)
);

-- Add index for faster lookups
CREATE INDEX IF NOT EXISTS idx_company_scope_responses_company ON company_scope_responses(company_id);
CREATE INDEX IF NOT EXISTS idx_company_scope_responses_scope ON company_scope_responses(template_scope_id);

-- Add function to update updated_at timestamps
CREATE OR REPLACE FUNCTION update_modified_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create triggers for updated_at
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'update_company_scope_responses_modtime') THEN
        CREATE TRIGGER update_company_scope_responses_modtime
        BEFORE UPDATE ON company_scope_responses
        FOR EACH ROW EXECUTE FUNCTION update_modified_column();
    END IF;
END$$;

-- Add comments to explain the schema
COMMENT ON TABLE template_scope_categories IS 'Categories for organizing scopes in the Template 1 matrix';
COMMENT ON TABLE template_scopes IS 'Individual scopes from Template 1.xlsx, representing columns in the matrix';
COMMENT ON TABLE company_scope_responses IS 'Stores company-specific responses to each scope, representing the matrix values';

-- Insert initial categories (example - should match Template 1.xlsx structure)
INSERT INTO template_scope_categories (name, description, display_order) VALUES
('Registration', 'User registration and account management', 10),
('Data Collection', 'Types of data collected from users', 20),
('Data Usage', 'How collected data is used', 30),
('Data Sharing', 'Third-party sharing of user data', 40),
('User Rights', 'User rights and controls over their data', 50),
('Security', 'Data security measures', 60),
('Retention', 'Data retention policies', 70),
('International', 'Cross-border data transfers', 80)
ON CONFLICT (name) DO NOTHING;

-- Enable ROW LEVEL SECURITY for future access control
ALTER TABLE company_scope_responses ENABLE ROW LEVEL SECURITY;
