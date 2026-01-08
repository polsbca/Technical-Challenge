"""
LLM Extraction Module

Uses LLM to extract structured information from policy text:
- Scope identification (maps text to predefined scopes from Template 1.xlsx)
- Confidence scoring
- Reasoning generation
"""

import json
import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import requests
from langchain_core.language_models import BaseChatModel
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field, ValidationError
from sqlalchemy.orm import Session

from src.config import settings
from src.utils import aggregate_confidence_scores, retry
from src.template_loader import load_scopes_from_template

logger = logging.getLogger(__name__)

class ScopeResponse(BaseModel):
    """Represents a single scope response extracted from policy text.
    
    Attributes:
        scope_key: Unique identifier for the scope
        response: Whether the scope applies (True/False)
        confidence: Confidence score between 0 and 1
        reasoning: Explanation for the response
    """
    scope_key: str = Field(..., description="Unique identifier for the scope")
    response: bool = Field(..., description="Whether the scope applies (True/False)")
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Confidence score between 0 and 1"
    )
    reasoning: str = Field(..., description="Explanation for the response")

class ScopeExtractionError(Exception):
    """Custom exception for scope extraction errors."""
    pass

class ScopeExtractor:
    """Handles extraction of scope responses from policy text using LLMs."""

    def __init__(self, llm: BaseChatModel, model_name: str = "gpt-4"):
        """Initialize the ScopeExtractor with an LLM.
        
        Args:
            llm: The language model to use for extraction
            model_name: Name of the model being used (for logging)
        """
        self.llm = llm
        self.model_name = model_name
        self.parser = JsonOutputParser(pydantic_object=ScopeResponse)
        
        # Initialize the prompt template
        self.prompt = self._create_prompt_template()
    
    def _create_prompt_template(self) -> ChatPromptTemplate:
        """Create and return the prompt template for scope extraction."""
        return ChatPromptTemplate.from_template(
            """
            Analyze the following privacy policy text and determine if it contains information
            about the specified scope. Respond with a JSON object containing:
            - scope_key: the original scope key
            - response: true/false
            - confidence: a confidence score between 0 and 1
            - reasoning: brief explanation of your decision

            Scope: {scope_name}
            Scope Description: {scope_description}
            
            Policy Text:
            {policy_text}
            
            Respond only with valid JSON matching this schema:
            {{
                "scope_key": "string",
                "response": "boolean",
                "confidence": "float",
                "reasoning": "string"
            }}
            """
        )
    
    async def extract_scope_response(
        self,
        scope: Dict[str, Any],
        policy_text: str,
        max_retries: int = 3
    ) -> Dict[str, Any]:
        """Extract a single scope response from policy text.
        
        Args:
            scope: Dictionary containing scope information (id, name, description, etc.)
            policy_text: The policy text to analyze
            max_retries: Maximum number of retry attempts on failure
            
        Returns:
            Dictionary containing the extracted scope response
            
        Raises:
            ScopeExtractionError: If extraction fails after all retries
        """
        if not policy_text.strip():
            raise ValueError("Policy text cannot be empty")
        
        # Truncate policy text to fit within context window
        truncated_text = policy_text[:12000]  # Conservative limit
        
        for attempt in range(max_retries):
            try:
                chain = self.prompt | self.llm | self.parser
                result = await chain.ainvoke({
                    "scope_name": scope.get("name", ""),
                    "scope_description": scope.get("description", ""),
                    "policy_text": truncated_text
                })
                
                # Validate the response
                validated = ScopeResponse(**result)
                
                return {
                    "scope_id": scope["id"],
                    "response": validated.response,
                    "confidence": float(validated.confidence),
                    "reasoning": validated.reasoning,
                    "source": f"llm:{self.model_name}"
                }
                
            except (ValueError, KeyError, ValidationError) as e:
                logger.warning(
                    f"Validation error extracting scope {scope.get('name')} "
                    f"(attempt {attempt + 1}/{max_retries}): {str(e)}"
                )
                if attempt == max_retries - 1:
                    raise ScopeExtractionError(
                        f"Failed to extract valid response for scope {scope.get('name')} "
                        f"after {max_retries} attempts: {str(e)}"
                    )
                continue
                
            except Exception as e:
                logger.error(
                    f"Unexpected error extracting scope {scope.get('name')}: {str(e)}",
                    exc_info=True
                )
                if attempt == max_retries - 1:
                    raise ScopeExtractionError(
                        f"Unexpected error processing scope {scope.get('name')}: {str(e)}"
                    )
                continue


async def extract_scope_responses(
    session: Session,
    company_id: int,
    policy_text: str,
    scope_extractor: ScopeExtractor,
    batch_size: int = 5
) -> List[Dict[str, Any]]:
    """Extract scope responses for all scopes for a given company.
    
    Args:
        session: Database session
        company_id: ID of the company
        policy_text: The policy text to analyze
        scope_extractor: Initialized ScopeExtractor instance
        batch_size: Number of scopes to process in parallel
        
    Returns:
        List of extracted scope responses
    """
    from sqlalchemy import text
    import asyncio
    from typing import List, Dict, Any
    
    try:
        # Get all scopes from the database
        result = session.execute(
            text("""
                SELECT id, scope_key, name, description 
                FROM template_scopes
                ORDER BY id
            """)
        )
        scopes = [dict(row) for row in result.mappings()]
        
        if not scopes:
            logger.warning("No scopes found in the database")
            return []
            
        logger.info(f"Processing {len(scopes)} scopes for company {company_id}")
        
        # Process scopes in batches
        responses = []
        for i in range(0, len(scopes), batch_size):
            batch = scopes[i:i + batch_size]
            logger.debug(f"Processing batch {i//batch_size + 1}/{(len(scopes)-1)//batch_size + 1}")
            
            # Process batch in parallel
            batch_tasks = [
                scope_extractor.extract_scope_response(scope, policy_text)
                for scope in batch
            ]
            
            batch_results = await asyncio.gather(
                *batch_tasks,
                return_exceptions=True
            )
            
            # Process results
            for scope, result in zip(batch, batch_results):
                if isinstance(result, Exception):
                    logger.error(
                        f"Error processing scope {scope.get('name')}:",
                        exc_info=result
                    )
                    responses.append({
                        "scope_id": scope["id"],
                        "response": False,
                        "confidence": 0.0,
                        "reasoning": f"Error during extraction: {str(result)}",
                        "source": "error"
                    })
                else:
                    result["company_id"] = company_id
                    responses.append(result)
        
        return responses
        
    except Exception as e:
        logger.error(f"Error in extract_scope_responses: {str(e)}", exc_info=True)
        raise ScopeExtractionError(f"Failed to extract scope responses: {str(e)}")


@dataclass
class ScopeExtraction:
    """Represents extracted scope information."""
    scope_name: str
    applies: bool
    confidence: float
    reasoning: str


class LLMExtraction:
    """Extracts structured data from policies using LLM."""

    # Scopes loaded dynamically from Template 1.xlsx
    SCOPES = None  # Will be lazily loaded
    SCOPE_DESCRIPTIONS = None  # Will be lazily loaded

    def __init__(self, use_ollama: bool = True):
        """
        Initialize LLM extraction.

        Args:
            use_ollama: Use Ollama (local) instead of OpenAI
        """
        # Load scopes from template on initialization
        if LLMExtraction.SCOPES is None:
            self._load_scopes()

        self.use_ollama = use_ollama
        # Handle both full URL and host-only formats
        ollama_host = settings.ollama_host
        if ollama_host.startswith('http'):
            self.ollama_host = ollama_host
        else:
            self.ollama_host = f"http://{ollama_host}:11434"
        self.ollama_model = settings.ollama_model
        self.temperature = settings.llm_temperature
        self.max_tokens = settings.llm_max_tokens
        self.timeout = settings.llm_timeout

    @classmethod
    def _load_scopes(cls):
        """Load scopes from Template 1.xlsx."""
        try:
            scopes_data = load_scopes_from_template()
            cls.SCOPES = [scope['name'] for scope in scopes_data]
            cls.SCOPE_DESCRIPTIONS = {
                scope['name']: scope.get('description', '')
                for scope in scopes_data
            }
            logger.info(f"Loaded {len(cls.SCOPES)} scopes from Template 1.xlsx")
        except Exception as e:
            logger.warning(f"Could not load scopes from template: {e}. Using defaults.")
            # Fallback to defaults
            cls.SCOPES = [
                'User Identification',
                'Site Navigation',
                'User Profile',
                'Service Delivery',
                'Communication',
                'Analytics',
                'Marketing',
                'Compliance',
            ]
            cls.SCOPE_DESCRIPTIONS = {}

    @classmethod
    def get_scopes(cls) -> List[str]:
        """Get list of available scopes."""
        if cls.SCOPES is None:
            cls._load_scopes()
        return cls.SCOPES

    @retry(max_attempts=3, delay=2.0, backoff=2.0)
    def extract_scopes(self, policy_text: str) -> List[ScopeExtraction]:
        """
        Extract scope information from policy text.

        Args:
            policy_text: Policy text to analyze

        Returns:
            List of ScopeExtraction
        """
        logger.info("Extracting scopes from policy text")

        # Build prompt
        prompt = self._build_scope_extraction_prompt(policy_text)

        # Call LLM
        response = self._call_llm(prompt)

        if not response:
            logger.warning("Failed to get LLM response")
            return []

        # Parse response
        extractions = self._parse_scope_response(response)

        logger.info(f"Extracted {len(extractions)} scope assignments")
        return extractions

    def extract_fields(self, policy_text: str) -> Dict[str, Optional[str]]:
        """
        Extract company fields from policy text.

        Args:
            policy_text: Policy text to analyze

        Returns:
            Dictionary of extracted fields
        """
        logger.info("Extracting company fields from policy text")

        fields = {
            'email': None,
            'country': None,
            'delete_link': None,
        }

        # Extract email
        if settings.extract_emails:
            fields['email'] = self._extract_email(policy_text)

        # Extract country
        if settings.extract_country:
            fields['country'] = self._extract_country(policy_text)

        # Extract delete link
        if settings.extract_delete_link:
            fields['delete_link'] = self._extract_delete_link(policy_text)

        return fields

    def _build_scope_extraction_prompt(self, policy_text: str) -> str:
        """Build prompt for scope extraction."""
        scopes = self.get_scopes()
        
        # Include descriptions if available
        scopes_list = []
        for scope in scopes:
            description = self.SCOPE_DESCRIPTIONS.get(scope, '') if self.SCOPE_DESCRIPTIONS else ''
            if description:
                scopes_list.append(f"- {scope}: {description}")
            else:
                scopes_list.append(f"- {scope}")
        
        scopes_text = '\n'.join(scopes_list)

        prompt = f"""Analyze the following privacy policy text and determine which data collection scopes apply.

Policy Text:
{policy_text[:2000]}...

Data Collection Scopes to evaluate:
{scopes_text}

For each scope, provide:
1. Whether it applies (yes/no)
2. Confidence (0.0-1.0)
3. Brief reasoning

Format your response as JSON with this structure:
{{
  "scopes": [
    {{
      "name": "scope name",
      "applies": true/false,
      "confidence": 0.0-1.0,
      "reasoning": "explanation"
    }}
  ]
}}

Respond ONLY with valid JSON, no additional text."""

        return prompt

    def _call_llm(self, prompt: str) -> Optional[str]:
        """Call LLM with prompt."""
        try:
            if self.use_ollama:
                return self._call_ollama(prompt)
            else:
                return self._call_openai(prompt)
        except Exception as e:
            logger.error(f"Error calling LLM: {e}")
            return None

    def _call_ollama(self, prompt: str) -> Optional[str]:
        """Call Ollama for LLM inference."""
        try:
            response = requests.post(
                f"{self.ollama_host}/api/generate",
                json={
                    "model": self.ollama_model,
                    "prompt": prompt,
                    "temperature": self.temperature,
                    "num_predict": self.max_tokens,
                    "stream": False,
                },
                timeout=self.timeout,
            )

            if response.status_code == 200:
                data = response.json()
                return data.get('response', '')

            logger.error(f"Ollama error: {response.status_code}")
            return None

        except Exception as e:
            logger.error(f"Error calling Ollama: {e}")
            return None

    def _call_openai(self, prompt: str) -> Optional[str]:
        """Call OpenAI for LLM inference (fallback)."""
        try:
            import openai

            openai.api_key = settings.openai_api_key

            response = openai.ChatCompletion.create(
                model=settings.openai_model,
                messages=[
                    {"role": "system", "content": "You are a data privacy policy analyzer."},
                    {"role": "user", "content": prompt}
                ],
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                timeout=self.timeout,
            )

            return response.choices[0].message.content

        except Exception as e:
            logger.error(f"Error calling OpenAI: {e}")
            return None

    @staticmethod
    def _parse_scope_response(response: str) -> List[ScopeExtraction]:
        """Parse LLM response for scope extractions."""
        try:
            # Handle empty response
            if not response or not response.strip():
                logger.warning("Empty LLM response")
                return []
            
            # Extract JSON from response
            start = response.find('{')
            end = response.rfind('}') + 1
            
            # Check if we found valid JSON markers
            if start == -1 or end == 0:
                logger.warning(f"No JSON found in response: {response[:100]}")
                return []
            
            json_str = response[start:end]
            
            # Try to parse JSON
            try:
                data = json.loads(json_str)
            except json.JSONDecodeError as je:
                logger.error(f"JSON decode error: {je}. Response: {json_str[:200]}")
                return []

            extractions = []
            for scope in data.get('scopes', []):
                extractions.append(ScopeExtraction(
                    scope_name=scope.get('name', ''),
                    applies=scope.get('applies', False),
                    confidence=float(scope.get('confidence', 0.0)),
                    reasoning=scope.get('reasoning', ''),
                ))

            return extractions

        except Exception as e:
            logger.error(f"Error parsing scope response: {e}")
            return []

    @staticmethod
    def _extract_email(policy_text: str) -> Optional[str]:
        """Extract email address from policy text."""
        import re

        # Common email patterns
        patterns = [
            r'privacy@[\w\.-]+\.\w+',
            r'contact@[\w\.-]+\.\w+',
            r'support@[\w\.-]+\.\w+',
            r'[\w\.-]+@[\w\.-]+\.\w+',  # Generic email
        ]

        for pattern in patterns:
            matches = re.findall(pattern, policy_text, re.IGNORECASE)
            if matches:
                return matches[0].lower()

        return None

    @staticmethod
    def _extract_country(policy_text: str) -> Optional[str]:
        """Extract country code from policy text."""
        # Look for country mentions
        countries = {
            'US': ['United States', 'USA', 'U.S.A', 'United States', 'american'],
            'GB': ['United Kingdom', 'UK', 'British'],
            'EU': ['European Union', 'GDPR', 'european'],
            'CA': ['Canada', 'canadian'],
            'AU': ['Australia', 'australian'],
        }

        text_lower = policy_text.lower()
        for code, keywords in countries.items():
            if any(kw.lower() in text_lower for kw in keywords):
                return code

        return None

    @staticmethod
    def _extract_delete_link(policy_text: str) -> Optional[str]:
        """Extract data deletion/request link from policy text."""
        import re

        # Look for URLs in context of deletion/request
        delete_keywords = ['delete', 'deletion', 'erase', 'removal', 'request', 'dsar']
        lines = policy_text.split('\n')

        for i, line in enumerate(lines):
            if any(kw in line.lower() for kw in delete_keywords):
                # Look for URL in this line or nearby
                url_pattern = r'https?://[^\s)"\']+'
                matches = re.findall(url_pattern, line)
                if matches:
                    return matches[0]

        return None


def extract_scopes(policy_text: str) -> List[ScopeExtraction]:
    """Convenience function to extract scopes."""
    extractor = LLMExtraction()
    return extractor.extract_scopes(policy_text)


def extract_fields(policy_text: str) -> Dict[str, Optional[str]]:
    """Convenience function to extract fields."""
    extractor = LLMExtraction()
    return extractor.extract_fields(policy_text)
