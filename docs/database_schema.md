# Database Schema

## Core Tables

### companies
Stores company information from List 1.csv.

```sql
CREATE TABLE companies (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    domain VARCHAR(255) UNIQUE NOT NULL,
    generic_email VARCHAR(255),
    contact_email VARCHAR(255),
    privacy_email VARCHAR(255),
    delete_link VARCHAR(2048),
    country VARCHAR(2),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### policy_discovery
Stores discovered policy URLs.

```sql
CREATE TABLE policy_discovery (
    id SERIAL PRIMARY KEY,
    company_id INTEGER REFERENCES companies(id),
    url VARCHAR(2048),
    document_type VARCHAR(50), -- 'privacy' or 'terms'
    discovery_method VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### template_scopes
Template 1 scope definitions.

```sql
CREATE TABLE template_scopes (
    id SERIAL PRIMARY KEY,
    scope_key VARCHAR(100) UNIQUE NOT NULL,
    name VARCHAR(200) NOT NULL,
    description TEXT,
    display_order INTEGER DEFAULT 0
);
```

### company_scope_responses
LLM-extracted scope responses.

```sql
CREATE TABLE company_scope_responses (
    id SERIAL PRIMARY KEY,
    company_id INTEGER REFERENCES companies(id),
    template_scope_id INTEGER REFERENCES template_scopes(id),
    response_value JSONB,
    confidence DECIMAL(3,2),
    source_url VARCHAR(2048),
    reasoning TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

## Indexes

- `idx_companies_domain` on companies(domain)
- `idx_policy_discovery_company` on policy_discovery(company_id)
- `idx_scope_responses_company` on company_scope_responses(company_id)
