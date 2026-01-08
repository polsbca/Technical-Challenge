# LLM Prompts

## Scope Extraction Prompt

```
You are analyzing privacy policies and terms of service to determine if specific data practices apply.

For each scope provided, determine if it applies based on the policy text.

Respond with JSON:
{
  "scope_name": {
    "value": true/false,
    "confidence": 0.0-1.0,
    "reasoning": "Explanation based on policy text",
    "source_text": "Relevant quote from policy"
  }
}

Scopes to evaluate:
- Registration
- Legal_and_Security_Purposes
- Data_Sharing
- User_Rights
- Data_Retention
- Third_Party_Access
- Communication
- Storage
```

## Field Enrichment Prompt

```
Extract the following information from the policy text:

1. generic_email: General contact email
2. contact_email: Legal/privacy contact email
3. privacy_email: Privacy-specific email
4. delete_link: Account deletion URL
5. country: Company's country/jurisdiction

For each field, provide:
- value: Extracted value or null
- confidence: 0.0-1.0
- source_url: Where found
- reasoning: Why you believe this is correct
```

## Chat Prompt

```
You are a helpful assistant that answers questions about company policies based on the provided context.

Context:
{policy_chunks}

Structured Data:
{scope_data}

Question: {user_question}

Provide a helpful answer citing the relevant policy sections. Include URLs for verification.
```
