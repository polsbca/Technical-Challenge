{
  "name": "LLM Extraction Workflow",
  "nodes": [
    {
      "parameters": {
        "operation": "getAll",
        "database": "postgres",
        "limit": 10
      },
      "id": "postgres-1",
      "name": "Get Companies",
      "type": "n8n-nodes-base.postgres",
      "typeVersion": 2.5,
      "position": [250, 300]
    },
    {
      "parameters": {
        "method": "POST",
        "url": "http://api:8000/api/v1/process/{{ $json.id }}",
        "sendHeaders": true,
        "headerParameters": {
          "parameters": [
            {
              "name": "Content-Type",
              "value": "application/json"
            },
            {
              "name": "X-API-Key",
              "value": "={{ $env.N8N_API_KEY }}"
            }
          ]
        }
      },
      "id": "process-1",
      "name": "Process Company",
      "type": "n8n-nodes-base.httpRequest",
      "typeVersion": 4.1,
      "position": [450, 300]
    },
    {
      "parameters": {
        "jsCode": "// Log processing results\nconsole.log('Processed company:', $json.name);\nreturn items;"
      },
      "id": "log-1",
      "name": "Log Results",
      "type": "n8n-nodes-base.code",
      "typeVersion": 2,
      "position": [650, 300]
    }
  ],
  "pinData": {},
  "connections": {
    "Get Companies": {
      "main": [
        [
          {
            "node": "Process Company",
            "type": "main",
            "index": 0
          }
        ]
      ]
    },
    "Process Company": {
      "main": [
        [
          {
            "node": "Log Results",
            "type": "main",
            "index": 0
          }
        ]
      ]
    }
  },
  "active": false,
  "settings": {
    "executionOrder": "v1"
  },
  "versionId": "1",
  "id": "llm-extraction-workflow",
  "tags": []
}
