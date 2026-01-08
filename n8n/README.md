# n8n Workflow Automation

This directory contains n8n workflows for automating policy discovery, LLM extraction, and chat functionality.

## Setup

1. **Start n8n**:
   ```bash
   docker-compose up -d n8n
   ```

2. **Access n8n**:
   - URL: http://localhost:5678
   - Username: `admin` (or set via N8N_USER)
   - Password: `admin123` (or set via N8N_PASSWORD)

## Workflows

### 1. Policy Discovery
- **File**: `workflows/policy_discovery.workflow`
- **Purpose**: Discovers policy pages for given domains
- **Schedule**: Daily
- **Dependencies**: Policy Discovery API

### 2. LLM Extraction
- **File**: `workflows/llm_extraction.workflow`
- **Purpose**: Processes companies and extracts policy information
- **Schedule**: Hourly
- **Dependencies**: PostgreSQL, LLM API

### 3. Chat Webhook
- **File**: `workflows/chat_webhook.workflow`
- **Purpose**: Handles chat messages from the PHP frontend
- **Endpoint**: `/chat`
- **Dependencies**: Chat API

## Security

1. **Authentication**:
   - Basic Auth is enabled by default
   - Change default credentials in `.env`
   - Use HTTPS in production

2. **API Keys**:
   - Store API keys in environment variables
   - Use `N8N_API_KEY` for internal API calls

3. **Encryption**:
   - Set a strong `N8N_ENCRYPTION_KEY`
   - Rotate keys periodically

## Importing Workflows

1. Open n8n at http://localhost:5678
2. Click "Workflows" in the left sidebar
3. Click "Import from File"
4. Select the `.workflow` files from this directory
5. Update the API keys and credentials as needed

## Configuration

### Environment Variables

Add these to your `.env` file:

```ini
# n8n Configuration
N8N_HOST=localhost
N8N_PORT=5678
N8N_PROTOCOL=http
N8N_ENCRYPTION_KEY=your-secure-encryption-key
N8N_JWT_SECRET=your-jwt-secret
N8N_USER=admin
N8N_PASSWORD=admin123
N8N_API_KEY=your-api-key
```

### Database Credentials

1. Go to "Credentials" in n8n
2. Click "Add Credential"
3. Select "Postgres"
4. Enter your database connection details:
   - Host: `postgres`
   - Port: `5432`
   - Database: `challenge2`
   - User: `challenge_user`
   - Password: `challenge_password`

## Monitoring

1. **Logs**:
   ```bash
   docker-compose logs -f n8n
   ```

2. **Health Checks**:
   - `http://localhost:5678/healthz`
   - `http://localhost:5678/metrics`

3. **Execution History**:
   - Go to "Executions" in n8n
   - View recent workflow executions
   - Click on any execution to see detailed logs

## Testing

### Test Chat Webhook

1. Import the chat_webhook workflow
2. Click on the webhook node to get the URL
3. Test with curl:
   ```bash
   curl -X POST http://localhost:5678/webhook/chat \
     -H "Content-Type: application/json" \
     -d '{
       "message": "What is your privacy policy?",
       "company_id": "123",
       "session_id": "abc123"
     }'
   ```

### Test Policy Discovery

1. Import the policy_discovery workflow
2. Click "Execute Workflow"
3. Check the execution results

## Troubleshooting

1. **Workflow Fails**:
   - Check n8n logs
   - Verify API endpoints are accessible
   - Check database connections

2. **Performance Issues**:
   - Increase resources in `docker-compose.yml`
   - Optimize workflow execution

3. **Authentication Issues**:
   - Verify credentials are correct
   - Check API keys

## Backup

To backup workflows:
```bash
docker cp challenge2_n8n:/home/node/.n8n n8n_backup
```

To restore workflows:
```bash
docker cp n8n_backup challenge2_n8n:/home/node/.n8n
docker-compose restart n8n
```

## License

[Your License Here]
