{
  "name": "Chat Webhook",
  "nodes": [
    {
      "parameters": {
        "httpMethod": "POST",
        "path": "chat",
        "responseMode": "onReceived",
        "options": {}
      },
      "id": "webhook-1",
      "name": "Chat Webhook",
      "type": "n8n-nodes-base.webhook",
      "typeVersion": 2,
      "position": [250, 300]
    },
    {
      "parameters": {
        "method": "POST",
        "url": "http://api:8000/api/v1/chat",
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
        "jsonBody": "={{ { message: $json.message, company_id: $json.company_id, session_id: $json.session_id } }}"
      },
      "id": "http-1",
      "name": "Call Chat API",
      "type": "n8n-nodes-base.httpRequest",
      "typeVersion": 4.1,
      "position": [450, 300]
    }
  ],
  "pinData": {},
  "connections": {
    "Chat Webhook": {
      "main": [
        [
          {
            "node": "Call Chat API",
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
  "id": "chat-webhook-workflow",
  "tags": []
}
