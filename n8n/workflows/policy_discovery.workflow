{
  "name": "Policy Discovery Workflow",
  "nodes": [
    {
      "parameters": {
        "method": "POST",
        "url": "http://api:8000/api/v1/discover",
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
        },
        "sendBody": true,
        "specifyBody": "json",
        "jsonBody": "={\"domains\": [\"example.com\", \"github.com\"]}"
      },
      "id": "discover-1",
      "name": "Discover Policies",
      "type": "n8n-nodes-base.httpRequest",
      "typeVersion": 4.1,
      "position": [250, 300]
    },
    {
      "parameters": {
        "jsCode": "// Process discovery results\nconst results = items.map(item => {\n  const data = item.json;\n  return {\n    json: {\n      domain: data.domain || 'unknown',\n      privacy_policy: data.privacy_policy || null,\n      terms_of_service: data.terms_of_service || null,\n      discovery_method: data.discovery_method || 'unknown',\n      status: data.status || 'failed',\n      processed_at: new Date().toISOString()\n    }\n  };\n});\n\nreturn results;"
      },
      "id": "process-1",
      "name": "Process Results",
      "type": "n8n-nodes-base.code",
      "typeVersion": 2,
      "position": [450, 300]
    }
  ],
  "pinData": {},
  "connections": {
    "Discover Policies": {
      "main": [
        [
          {
            "node": "Process Results",
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
  "id": "policy-discovery-workflow",
  "tags": []
}
