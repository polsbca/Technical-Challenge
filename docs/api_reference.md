# API Reference

## PHP Endpoints

### POST /api.php/chat
Send a message to the chat interface.

**Request:**
```json
{
  "message": "What is your privacy policy?",
  "company_id": "123",
  "session_id": "abc123"
}
```

**Response:**
```json
{
  "response": "Based on the privacy policy...",
  "sources": [
    {
      "url": "https://example.com/privacy",
      "title": "Privacy Policy",
      "snippet": "Relevant text snippet..."
    }
  ]
}
```

### GET /api.php/companies
List all companies.

**Response:**
```json
{
  "companies": [
    {
      "id": 1,
      "name": "Company Name",
      "domain": "example.com"
    }
  ]
}
```

### GET /api.php/companies/{id}/scopes
Get scope data for a company.

**Response:**
```json
{
  "company_id": 1,
  "scopes": {
    "Registration": true,
    "Data_Sharing": false
  }
}
```

## Python API Endpoints (if using directly)

### POST /api/v1/discover
Discover policy pages for domains.

### POST /api/v1/process/{company_id}
Process a company's policies.

### GET /api/v1/chat
Chat with policy documents.
