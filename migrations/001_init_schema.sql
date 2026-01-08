-- Migration: Initial Database Schema
-- Description: Creates core tables for policy discovery and enrichment system
-- Version: 1.0

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Create scopes table
CREATE TABLE scopes (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE,
    description TEXT,
    category VARCHAR(50),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Create companies table
CREATE TABLE companies (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    domain VARCHAR(255) NOT NULL UNIQUE,
    email VARCHAR(255),
    country VARCHAR(2),
    delete_link VARCHAR(2048),
    data_source VARCHAR(50) DEFAULT 'csv',
    processed BOOLEAN DEFAULT FALSE,
    processed_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Create company_scopes table (many-to-many)
CREATE TABLE company_scopes (
    id SERIAL PRIMARY KEY,
    company_id INTEGER NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    scope_id INTEGER NOT NULL REFERENCES scopes(id) ON DELETE CASCADE,
    applies BOOLEAN NOT NULL DEFAULT FALSE,
    confidence DECIMAL(3, 2) NOT NULL DEFAULT 0.0,
    reasoning TEXT,
    source VARCHAR(50) DEFAULT 'llm',
    extracted_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(company_id, scope_id)
);

-- Create policy_discovery table
CREATE TABLE policy_discovery (
    id SERIAL PRIMARY KEY,
    company_id INTEGER NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    doc_type VARCHAR(50) NOT NULL, -- 'privacy', 'terms', 'dpa', etc.
    url VARCHAR(2048) NOT NULL,
    discovered_via VARCHAR(50), -- 'sitemap', 'footer', 'heuristic', 'link_text'
    http_status INTEGER,
    is_canonical BOOLEAN DEFAULT TRUE,
    confidence DECIMAL(3, 2) NOT NULL DEFAULT 0.5,
    error_message TEXT,
    discovered_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(company_id, doc_type)
);

-- Create policy_chunks table
CREATE TABLE policy_chunks (
    id SERIAL PRIMARY KEY,
    policy_discovery_id INTEGER NOT NULL REFERENCES policy_discovery(id) ON DELETE CASCADE,
    chunk_text TEXT NOT NULL,
    chunk_index INTEGER NOT NULL,
    token_count INTEGER NOT NULL,
    embedding_id VARCHAR(255),
    embedding_hash VARCHAR(64),
    metadata JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(policy_discovery_id, chunk_index)
);

-- Create enrichment_history table for tracking field updates
CREATE TABLE enrichment_history (
    id SERIAL PRIMARY KEY,
    company_id INTEGER NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    field_name VARCHAR(50) NOT NULL,
    old_value VARCHAR(2048),
    new_value VARCHAR(2048),
    confidence DECIMAL(3, 2),
    source VARCHAR(100),
    enriched_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Create processing_queue table for background jobs
CREATE TABLE processing_queue (
    id SERIAL PRIMARY KEY,
    company_id INTEGER NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    task_type VARCHAR(50) NOT NULL, -- 'discovery', 'scraping', 'extraction', 'enrichment'
    status VARCHAR(20) DEFAULT 'pending', -- 'pending', 'processing', 'completed', 'failed'
    priority INTEGER DEFAULT 0,
    attempt_count INTEGER DEFAULT 0,
    max_attempts INTEGER DEFAULT 3,
    error_message TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE
);

-- Create indexes for performance
CREATE INDEX idx_companies_domain ON companies(domain);
CREATE INDEX idx_companies_processed ON companies(processed);
CREATE INDEX idx_company_scopes_company_id ON company_scopes(company_id);
CREATE INDEX idx_company_scopes_scope_id ON company_scopes(scope_id);
CREATE INDEX idx_policy_discovery_company_id ON policy_discovery(company_id);
CREATE INDEX idx_policy_discovery_doc_type ON policy_discovery(doc_type);
CREATE INDEX idx_policy_chunks_policy_discovery_id ON policy_chunks(policy_discovery_id);
CREATE INDEX idx_enrichment_history_company_id ON enrichment_history(company_id);
CREATE INDEX idx_processing_queue_status ON processing_queue(status);
CREATE INDEX idx_processing_queue_company_id ON processing_queue(company_id);

-- Add full-text search index for policy chunks
CREATE INDEX idx_policy_chunks_text ON policy_chunks USING GIN (to_tsvector('english', chunk_text));

-- Add constraint for status enum
ALTER TABLE processing_queue ADD CONSTRAINT check_status CHECK (status IN ('pending', 'processing', 'completed', 'failed'));
