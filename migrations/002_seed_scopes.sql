-- Migration: Seed Scope Data
-- Description: Insert standard data collection scopes into the scopes table
-- Version: 1.0

INSERT INTO scopes (name, description, category) VALUES
('User Identification', 'Processing for user authentication and identification purposes', 'Personal'),
('Site Navigation', 'Essential data processing for site navigation and functionality', 'Essential'),
('User Profile', 'Processing to maintain and update user profile information', 'Personal'),
('Service Delivery', 'Processing necessary to deliver the requested service or product', 'Service'),
('Communication', 'Direct communication with the user (support, updates, confirmations)', 'Communication'),
('Analytics', 'Collection and processing for website analytics and usage statistics', 'Analytics'),
('Marketing', 'Targeted marketing communications and promotional activities', 'Marketing'),
('Compliance', 'Legal compliance and regulatory requirement processing', 'Legal')
ON CONFLICT (name) DO NOTHING;
