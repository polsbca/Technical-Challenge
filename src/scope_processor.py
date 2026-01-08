"""
Scope Processing Module

Handles the processing and storage of company scope responses.
"""

import logging
from typing import Dict, List, Optional, Any
from datetime import datetime

from sqlalchemy.orm import Session
from sqlalchemy import text

from src.llm_extraction import ScopeExtractor, extract_scope_responses

logger = logging.getLogger(__name__)

async def process_company_scopes(
    session: Session,
    company_id: int,
    policy_text: str,
    scope_extractor: ScopeExtractor
) -> None:
    """Process and store scope responses for a company.
    
    Args:
        session: Database session
        company_id: ID of the company to process
        policy_text: The policy text to analyze
        scope_extractor: Initialized ScopeExtractor instance
    """
    try:
        logger.info(f"Starting scope processing for company {company_id}")
        
        # Extract scope responses using LLM
        logger.info("Extracting scope responses...")
        responses = await extract_scope_responses(
            session=session,
            company_id=company_id,
            policy_text=policy_text,
            scope_extractor=scope_extractor
        )
        
        if not responses:
            logger.warning(f"No scope responses extracted for company {company_id}")
            return
        
        # Store responses in the database
        logger.info(f"Storing {len(responses)} scope responses...")
        for response in responses:
            await store_scope_response(session, response)
        
        logger.info(f"Successfully processed scopes for company {company_id}")
        
    except Exception as e:
        logger.error(f"Error processing company scopes: {str(e)}", exc_info=True)
        raise

async def store_scope_response(
    session: Session,
    response: Dict[str, Any]
) -> None:
    """Store a single scope response in the database.
    
    Args:
        session: Database session
        response: Dictionary containing scope response data
    """
    try:
        # Prepare the response value
        response_value = {
            "value": response.get("response", False),
            "metadata": {
                "confidence": response.get("confidence", 0.0),
                "reasoning": response.get("reasoning", ""),
                "extracted_at": datetime.utcnow().isoformat()
            }
        }
        
        # Insert or update the scope response
        await session.execute(
            text("""
                INSERT INTO company_scope_responses (
                    company_id,
                    template_scope_id,
                    response_value,
                    confidence,
                    source_document_type,
                    extraction_method,
                    reasoning,
                    created_at,
                    updated_at
                ) VALUES (
                    :company_id,
                    :scope_id,
                    :response_value::jsonb,
                    :confidence,
                    'privacy_policy',
                    :source,
                    :reasoning,
                    NOW(),
                    NOW()
                )
                ON CONFLICT (company_id, template_scope_id) 
                DO UPDATE SET
                    response_value = EXCLUDED.response_value,
                    confidence = EXCLUDED.confidence,
                    extraction_method = EXCLUDED.extraction_method,
                    reasoning = EXCLUDED.reasoning,
                    updated_at = NOW()
            """),
            {
                "company_id": response["company_id"],
                "scope_id": response["scope_id"],
                "response_value": response_value,
                "confidence": response.get("confidence", 0.0),
                "source": response.get("source", "llm"),
                "reasoning": response.get("reasoning", "")
            }
        )
        
        await session.commit()
        logger.debug(f"Stored response for scope {response.get('scope_id')}")
        
    except Exception as e:
        await session.rollback()
        logger.error(f"Error storing scope response: {str(e)}", exc_info=True)
        raise

async def get_company_scope_responses(
    session: Session,
    company_id: int
) -> List[Dict[str, Any]]:
    """Retrieve all scope responses for a company.
    
    Args:
        session: Database session
        company_id: ID of the company
    
    Returns:
        List of scope responses with details
    """
    try:
        result = await session.execute(
            text("""
                SELECT 
                    r.id,
                    r.company_id,
                    r.template_scope_id,
                    s.name as scope_name,
                    r.response_value->>'value' as response,
                    r.confidence,
                    r.reasoning,
                    r.source_document_type,
                    r.extraction_method,
                    r.created_at,
                    r.updated_at
                FROM company_scope_responses r
                JOIN template_scopes s ON r.template_scope_id = s.id
                WHERE r.company_id = :company_id
                ORDER BY s.name
            """),
            {"company_id": company_id}
        )
        
        return [dict(row) for row in result.mappings()]
        
    except Exception as e:
        logger.error(f"Error retrieving company scope responses: {str(e)}", exc_info=True)
        raise
