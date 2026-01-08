# Policy Discovery & LLM-Driven Structuring System

A comprehensive Python + PHP system for discovering legal policy pages, extracting structured data using LLMs, enriching missing fields, and providing semantic search via a chat interface.

## Project Goals

1. **Discover** policy pages (Privacy Policy, Terms & Conditions) automatically for each domain
2. **Extract** structured scope information via LLM processing
3. **Enrich** missing fields (emails, country, delete links)
4. **Store** in PostgreSQL + Qdrant vector database
5. **Expose** via PHP chat interface with semantic search

## System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│              CSV Input (List 1.csv)                          │
│         509 companies, 8 fields (many empty)                 │
└────────────────────────┬────────────────────────────────────┘
                         │
        ┌────────────────┴────────────────┐
        │                                 │
        ▼                                 ▼
   ┌─────────────┐              ┌──────────────────┐
   │  Discovery  │              │ Field Enrichment │
   │  Module     │              │ (Emails, Country,│
   │             │              │  Delete Links)   │
   │ • Sitemap   │              │                  │
   │ • Footer    │              │ • Pattern Match  │
   │ • Heuristic │              │ • LLM Extraction │
   │ • Link Text │              │ • Validation     │
   └────────────┬┘              └──────────┬───────┘
                │                          │
                ▼                          ▼
          ┌──────────────┐          ┌──────────────┐
          │   Scraping   │          │  Database    │
          │   & Cleaning │          │  (Company    │
          │              │          │   Data)      │
          │ • BeautifulSoup        │              │
          │ • Trafilatura          │              │
          │ • Text Extraction      │              │
          └────────────┬┘          └──────┬───────┘
                       │                  │
                       ▼                  ▼
          ┌────────────────────────────────────────┐
          │    PostgreSQL Database                 │
          │                                        │
          │  ┌─────────────────────────────────┐  │
          │  │ companies                       │  │
          │  │ company_scopes                  │  │
          │  │ policy_discovery                │  │
          │  │ enrichment_history              │  │
          │  │ processing_queue                │  │
          │  └─────────────────────────────────┘  │
          └────────────┬───────────────────────────┘
                       │
        ┌──────────────┴──────────────┐
        │                             │
        ▼                             ▼
   ┌─────────────┐          ┌──────────────────┐
   │ Vector DB   │          │  LLM Extraction  │
   │ (Qdrant)    │          │                  │
   │             │          │ • Scope Mapping  │
   │ • Chunks    │          │ • Field Extract  │
   │ • Embeddings│          │ • Confidence     │
   │ • Search    │          │   Scoring        │
   └──────────────┘         └────────┬─────────┘
        │                            │
        └──────────────┬─────────────┘
                       │
                       ▼
         ┌─────────────────────────────┐
         │  PHP Chat Interface         │
         │                             │
         │ • Query with context        │
         │ • Semantic search (Qdrant)  │
         │ • LLM-powered responses     │
         │ • Source citations          │
         └─────────────────────────────┘
```

## Project Structure

```
Challenge2/
├── src/                      # Python source code
│   ├── __init__.py
│   ├── config.py            # Configuration via Pydantic
│   ├── utils.py             # Shared utilities & decorators
│   ├── policy_discovery.py  # Policy URL discovery
│   ├── scraper.py           # Web scraping & cleaning
│   ├── vector_storage.py    # Qdrant integration
│   ├── llm_extraction.py    # LLM-driven structuring
│   ├── enrichment.py        # Field enrichment
│   ├── database.py          # PostgreSQL ORM
│   ├── main.py              # Main orchestration
│   └── ollama_client.py     # Local LLM interface
│
├── php/                      # PHP web interface
│   ├── config.php           # Database & service config
│   ├── index.html           # Chat UI
│   ├── api.php              # REST endpoints
│   └── .htaccess            # URL rewriting
│
├── migrations/               # Database migrations
│   ├── 001_init_schema.sql  # Core schema
│   └── 002_seed_scopes.sql  # Scope data
│
├── tests/                    # Test suite
│   ├── test_policy_discovery.py
│   ├── test_scraper.py
│   ├── test_llm_extraction.py
│   └── test_end_to_end.py
│
├── outputs/                  # Generated files
│   ├── companies_enriched.json
│   └── example_outputs/
│
├── docs/                     # Documentation
│   ├── API.md
│   ├── SETUP.md
│   └── ARCHITECTURE.md
│
├── .gitignore               # Git ignore rules
├── requirements.txt         # Python dependencies
├── docker-compose.yml       # Full stack orchestration
├── .env.example            # Environment template
└── README.md               # This file
```

## n8n Automation (Optional)

The project includes optional n8n workflows for automation:

1. **Policy Discovery**: Automated discovery of policy pages
2. **LLM Processing**: Scheduled extraction of policy information  
3. **Chat Webhook**: Handles chat interface requests

See the [n8n documentation](n8n/README.md) for setup and usage.

## Quick Start

### Prerequisites
- Docker & Docker Compose
- Python 3.10+ (for local development)
- PostgreSQL 15 client tools (optional)

### Setup

1. **Clone and configure:**
   ```bash
   cp .env.example .env
   # Edit .env with your settings
   ```

2. **Start the stack:**
   ```bash
   docker-compose up -d
   ```

3. **Run database migrations:**
   ```bash
   docker exec challenge2_postgres psql -U challenge_user -d challenge2 < migrations/001_init_schema.sql
   docker exec challenge2_postgres psql -U challenge_user -d challenge2 < migrations/002_seed_scopes.sql
   ```

4. **Install Python dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

5. **Process companies:**
   ```bash
   python src/main.py --input List\ 1.csv --domains google.com spotify.com stripe.com
   ```

6. **Access chat interface:**
   - Open http://localhost:80 in your browser

## Core Modules

### Policy Discovery (`src/policy_discovery.py`)
Automatically discovers policy page URLs through:
- Sitemap parsing (robots.txt → sitemap.xml)
- Footer link extraction
- Common path heuristics (/privacy, /terms, /legal, etc.)
- Link text search (matches "Privacy Policy", "Terms & Conditions")

**Output:** Canonical policy URLs with confidence scores

### Template Loader (`src/template_loader.py` & `src/template_matrix_loader.py`)

**Basic Scope Loading** (`template_loader.py`)
- Reads Template 1.xlsx scope definitions
- Flexible Excel parsing (auto-detects headers, column order)
- Fallback to defaults if not found

**Matrix Loader** (`template_matrix_loader.py`)
- Reads Template 1.xlsx as policy-scope matrix
- Provides bidirectional mappings (scope→companies, company→scopes)
- Normalizes scope names for SQL columns
- Generates ALTER TABLE statements

**Critical Concept:**
- Template 1.xlsx defines **available scopes** (reference/validation)
- LLM determines **which scopes apply** based on policy analysis
- Scope applicability comes from **LLM extraction**, NOT template

**Output:** Scope definitions for database seeding and validation

### Scraper (`src/scraper.py`)
Extracts clean text from policy pages:
- Boilerplate removal (navigation, ads, scripts)
- HTML-to-text conversion
- Language detection
- Text validation (minimum word count)

**Output:** Clean policy text with metadata

### Vector Storage (`src/vector_storage.py`)
Indexes policy text in Qdrant for semantic search:
- Chunking strategy (512 tokens, 128 overlap)
- Embedding generation (Ollama or OpenAI)
- Vector storage in Qdrant
- Semantic search queries

**Output:** Indexed vectors ready for search

### LLM Extraction (`src/llm_extraction.py`)
Uses LLM to analyze policy text and determine scope applicability:
- Loads available scopes from Template 1.xlsx (reference universe)
- For each company, analyzes scraped policy text chunks
- Determines which Template 1 scopes apply based on policy content
- Generates confidence scores (0.0-1.0)
- Produces reasoning for each scope determination

**Data Flow:**
1. Template 1.xlsx defines scope universe (what scopes exist)
2. LLM analyzes policy chunks from Qdrant vector DB
3. For each scope: "Does this policy mention this scope?"
4. Stores applicability results in company_scopes table

**Output:** Structured scope assignments with confidence & reasoning

### Enrichment (`src/enrichment.py`)
Extracts missing company fields:
- Email addresses (support@, contact@, privacy@)
- Country detection (from domain, policy text)
- Data deletion links (GDPR, CCPA requirements)

**Output:** Updated company records

## Configuration

All settings managed via `.env` file:

```
# PostgreSQL
POSTGRES_USER=challenge_user
POSTGRES_PASSWORD=secure_password
POSTGRES_HOST=postgres
POSTGRES_PORT=5432
POSTGRES_DB=challenge2

# Qdrant
QDRANT_HOST=qdrant
QDRANT_PORT=6333
QDRANT_COLLECTION=policy_chunks

# Ollama (local LLM)
OLLAMA_HOST=http://ollama:11434
OLLAMA_MODEL=mistral

# OpenAI (optional fallback)
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-3.5-turbo

# Embedding
EMBEDDING_MODEL=nomic-embed-text
EMBEDDING_DIMENSION=1536

# Processing
CHUNK_SIZE=512
CHUNK_OVERLAP=128
MIN_CONTENT_WORDS=500
CONFIDENCE_THRESHOLD=0.60
```

## Database Schema

### companies
- `id` (int, PK)
- `name` (varchar)
- `domain` (varchar, unique)
- `email` (varchar, nullable)
- `country` (varchar[2], nullable)
- `delete_link` (varchar, nullable)
- `processed` (boolean)

### scopes
- Scope definitions **seeded from Template 1.xlsx**
- Includes: name, description, category
- Source of truth for available scope categories
- Ensures all companies use standardized scope definitions

### company_scopes
- Maps companies to applicable scopes based on **LLM analysis**
- **NOT pre-determined by Template 1 matrix**
- Populated by LLM extraction process
- Includes: scope_id, applies (TRUE/FALSE), confidence (0.0-1.0), reasoning

### policy_discovery
- Tracks discovered policy URLs
- Discovery method (sitemap, footer, heuristic, link_text)
- HTTP status and confidence

### policy_chunks
- Individual text chunks from policies
- Token counts, embeddings, metadata
- Full-text search index

## Testing

```bash
# Run all tests
pytest tests/ -v

# With coverage
pytest tests/ --cov=src --cov-report=html

# Specific test
pytest tests/test_policy_discovery.py -v
```

## Implementation Phases

**Phase 1 (Week 1):** Project setup, dependencies, core configuration
**Phase 2 (Week 2-3):** Policy discovery, scraping, vector storage
**Phase 3 (Week 4):** LLM extraction, enrichment, database integration
**Phase 4 (Week 5):** End-to-end testing, optimization, documentation
**Phase 5 (Week 6):** Chat interface, deployment, final validation

## Test Domains

Processing focuses on 3 domains initially:
1. **Google** (google.com) - Complex multilingual policies
2. **Spotify** (spotify.com) - Media company with regional policies
3. **Stripe** (stripe.com) - Financial services with regulatory focus

## CRITICAL: Template 1.xlsx Role

**Template 1.xlsx is a REFERENCE, NOT a data source**

### What Template 1.xlsx Does
- Defines available scope categories (seeded into `scopes` table)
- Provides scope definitions for reference/validation
- Ensures standardized scope vocabulary
- Used to validate LLM extraction results

### What Template 1.xlsx Does NOT Do
- Does NOT determine which scopes apply to companies
- Does NOT pre-populate the `company_scopes` table
- Does NOT act as a company-scope applicability matrix

### Correct Data Flow
```
Template 1.xlsx (Scope Definitions)
    ↓ [SEED]
scopes table
    ↑
    │
List 1.csv (Companies) → Policy Discovery → Scraping → Vector DB (Qdrant)
    ↓
[LLM Analyzes Policy Text]
    ↓
[LLM Determines: Which Template 1 scopes apply?]
    ↓ [POPULATE]
company_scopes table (populated from LLM results, not Template)
```

**Key Point:** Scope applicability comes from **LLM analysis of policy text**, validated against Template 1.xlsx scope definitions.

---

**Started:** 2026-01-04
**Last Updated:** 2026-01-08 (Template 1.xlsx clarification)
**Test Coverage:** Unit tests ready for Phase 2 integration testing
