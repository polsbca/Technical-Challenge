"""
Enrichment Module

Extracts and validates missing company fields using multiple strategies:
1. Email addresses (regex + LLM fallback)
2. Country information (TLD + text analysis + LLM fallback)
3. Data deletion links (pattern matching + LLM fallback)

Features:
- Multi-strategy extraction with confidence scoring
- Fallback to LLM when patterns don't match
- Configurable via settings
- Comprehensive logging
"""

import logging
from typing import Dict, Optional, List, Tuple
import re
from dataclasses import dataclass
from enum import Enum

from src.config import settings
from src.utils import is_valid_email, is_valid_country_code

logger = logging.getLogger(__name__)

class ExtractionSource(Enum):
    """Source of the extracted information."""
    PATTERN = "pattern"
    LLM = "llm"
    TLD = "tld"
    FALLBACK = "fallback"

@dataclass
class ExtractionResult:
    """Result of a field extraction with confidence score."""
    value: str
    confidence: float
    source: ExtractionSource
    
    def to_dict(self) -> Dict:
        return {
            "value": self.value,
            "confidence": self.confidence,
            "source": self.source.value
        }


class FieldEnricher:
    """Enriches company records with missing fields."""

    def __init__(self):
        """Initialize enricher."""
        pass

    def extract_emails(self, text: str) -> List[ExtractionResult]:
        """
        Extract and validate emails from text with confidence scoring.

        Args:
            text: Text to search for emails

        Returns:
            List of ExtractionResult objects with emails and their confidence scores
        """
        results = []
        seen_emails = set()

        # Common email patterns with confidence scores
        email_patterns = [
            # Specific privacy-related emails (highest confidence)
            (r'privacy[\s\-]*(?:@|at|\(at\)|\[at\]|&#x40;|%40)[\s\-]*([a-z0-9.-]+\.[a-z]{2,})', 0.95),
            (r'dpo[\s\-]*(?:@|at|\(at\)|\[at\]|&#x40;|%40)[\s\-]*([a-z0-9.-]+\.[a-z]{2,})', 0.95),
            
            # Common support/contact emails (high confidence)
            (r'(?:contact|support|help|info)[\s\-]*(?:@|at|\(at\)|\[at\]|&#x40;|%40)[\s\-]*([a-z0-9.-]+\.[a-z]{2,})', 0.90),
            
            # Generic email patterns (medium confidence)
            (r'[a-z0-9._%+-]+(?:\s*@|\s*\[?\s*at\s*\]?\s*)[a-z0-9.-]+\.[a-z]{2,}', 0.80),
            (r'[a-z0-9._%+-]+\s*(?:\(at\)|\[at\]| at |@|&#x40;|%40)\s*[a-z0-9.-]+\.[a-z]{2,}', 0.75),
            
            # Obfuscated emails (lower confidence)
            (r'[a-z0-9._%+-]+\s*\[?\s*(?:at|dot)\s*\]?\s*[a-z0-9.-]+\s*\[?\s*(?:at|dot)\s*\]?\s*[a-z]{2,}', 0.65),
        ]

        for pattern, base_confidence in email_patterns:
            try:
                matches = re.finditer(pattern, text, re.IGNORECASE)
                for match in matches:
                    # Clean up the email
                    email = match.group(0).lower()
                    email = re.sub(r'\s*(?:at|@|\(at\)|\[at\]|&#x40;|%40)\s*', '@', email)
                    email = re.sub(r'\s*dot\s*', '.', email)
                    email = re.sub(r'[\[\]()\\]', '', email)  # Remove any remaining brackets/parentheses
                    
                    # Skip if not a valid email or already seen
                    if not is_valid_email(email) or email in seen_emails:
                        continue
                    
                    seen_emails.add(email)
                    
                    # Adjust confidence based on email domain
                    domain = email.split('@')[-1]
                    domain_confidence = 0.0
                    
                    # Common free email providers (lower confidence)
                    if any(domain.startswith(d) for d in ['gmail.', 'yahoo.', 'outlook.', 'hotmail.']):
                        domain_confidence = -0.2
                    # Company domain (higher confidence)
                    elif re.search(r'\b' + re.escape(domain) + r'\b', text, re.IGNORECASE):
                        domain_confidence = 0.1
                    
                    final_confidence = max(0.1, min(1.0, base_confidence + domain_confidence))
                    
                    results.append(ExtractionResult(
                        value=email,
                        confidence=final_confidence,
                        source=ExtractionSource.PATTERN
                    ))
            except Exception as e:
                logger.warning(f"Error processing email pattern {pattern}: {e}")
                continue

        return sorted(results, key=lambda x: x.confidence, reverse=True)

    async def enrich_email_with_llm(self, text: str) -> Optional[ExtractionResult]:
        """
        Use LLM to extract email when pattern matching fails.
        
        Args:
            text: Text to analyze
            
        Returns:
            ExtractionResult with the best email or None
        """
        try:
            from langchain.chat_models import ChatOpenAI
            from langchain.schema import HumanMessage, SystemMessage
            
            llm = ChatOpenAI(
                model_name=settings.llm_model,
                temperature=0.1,
                request_timeout=30
            )
            
            messages = [
                SystemMessage(content="""You are an AI assistant that extracts contact emails from privacy policies. 
                Return only the most relevant email address or 'None' if none found."""),
                HumanMessage(content=f"""Extract the most relevant contact email from this privacy policy text. 
                Focus on privacy-related contacts like privacy@, dpo@, or legal@ addresses.
                Return only the email or 'None' if not found.
                
                Text: {text[:4000]}""")
            ]
            
            response = await llm.agenerate([messages])
            email = response.generations[0][0].text.strip()
            
            if email.lower() == 'none' or not is_valid_email(email):
                return None
                
            return ExtractionResult(
                value=email.lower(),
                confidence=0.9,  # High confidence for LLM-extracted emails
                source=ExtractionSource.LLM
            )
            
        except Exception as e:
            logger.warning(f"Error in LLM email extraction: {e}")
            return None

    async def enrich_email(
        self, 
        text: str, 
        current_email: Optional[str] = None,
        use_llm_fallback: bool = True
    ) -> Optional[ExtractionResult]:
        """
        Extract and validate email from text with confidence scoring.

        Args:
            text: Text to search
            current_email: Existing email to prefer
            use_llm_fallback: Whether to use LLM if pattern matching fails

        Returns:
            ExtractionResult with the best email or None
        """
        # Check if we have a valid current email
        if current_email and is_valid_email(current_email):
            return ExtractionResult(
                value=current_email.lower(),
                confidence=1.0,
                source=ExtractionSource.FALLBACK
            )

        # Extract emails using patterns
        email_results = self.extract_emails(text)
        
        # Return the best result if we have high confidence
        if email_results and email_results[0].confidence >= 0.8:
            return email_results[0]
            
        # Try LLM fallback if enabled and no good matches
        if use_llm_fallback and settings.enable_llm_fallback:
            llm_result = await self.enrich_email_with_llm(text)
            if llm_result:
                return llm_result
        
        # Return the best available result or None
        return email_results[0] if email_results else None

    def extract_countries(self, text: str, domain: str) -> List[ExtractionResult]:
        """
        Extract country information from text and domain with confidence scoring.

        Args:
            text: Text to search
            domain: Company domain

        Returns:
            List of ExtractionResult objects with countries and confidence scores
        """
        results = []
        seen_codes = set()
        text_lower = text.lower()
        
        # ISO 3166-1 alpha-2 country codes with common names and variants
        countries = {
            # North America
            'US': {
                'names': ['united states', 'usa', 'u.s.a', 'u.s.', 'america', 'united states of america'],
                'adjectives': ['american'],
                'tld': 'us',
                'confidence': 0.9
            },
            'CA': {
                'names': ['canada'],
                'adjectives': ['canadian'],
                'tld': 'ca',
                'confidence': 0.9
            },
            'MX': {
                'names': ['mexico'],
                'adjectives': ['mexican'],
                'tld': 'mx',
                'confidence': 0.85
            },
            
            # Europe
            'GB': {
                'names': ['united kingdom', 'uk', 'u.k.', 'great britain', 'england', 'scotland', 'wales', 'northern ireland'],
                'adjectives': ['british', 'english', 'scottish', 'welsh', 'northern irish'],
                'tld': 'uk',
                'confidence': 0.9
            },
            'DE': {
                'names': ['germany', 'deutschland'],
                'adjectives': ['german', 'deutsche', 'deutschen'],
                'tld': 'de',
                'confidence': 0.9
            },
            'FR': {
                'names': ['france'],
                'adjectives': ['french', 'française'],
                'tld': 'fr',
                'confidence': 0.9
            },
            'ES': {
                'names': ['spain', 'españa', 'espana'],
                'adjectives': ['spanish', 'español', 'espanol'],
                'tld': 'es',
                'confidence': 0.85
            },
            'IT': {
                'names': ['italy', 'italia'],
                'adjectives': ['italian', 'italiano'],
                'tld': 'it',
                'confidence': 0.85
            },
            
            # Asia
            'JP': {
                'names': ['japan', 'nippon', 'nihon'],
                'adjectives': ['japanese'],
                'tld': 'jp',
                'confidence': 0.9
            },
            'CN': {
                'names': ['china', 'peoples republic of china', 'prc', 'zhongguo', 'zhōngguó'],
                'adjectives': ['chinese'],
                'tld': 'cn',
                'confidence': 0.9
            },
            'IN': {
                'names': ['india', 'bharat'],
                'adjectives': ['indian'],
                'tld': 'in',
                'confidence': 0.9
            },
            'SG': {
                'names': ['singapore'],
                'adjectives': ['singaporean'],
                'tld': 'sg',
                'confidence': 0.85
            },
            
            # Add more countries as needed...
        }

        # Check domain TLD first (high confidence)
        tld = domain.split('.')[-1].lower()
        for code, data in countries.items():
            if data['tld'] == tld:
                results.append(ExtractionResult(
                    value=code,
                    confidence=0.95,  # High confidence for TLD match
                    source=ExtractionSource.TLD
                ))
                seen_codes.add(code)

        # Check for country mentions in text
        for code, data in countries.items():
            if code in seen_codes:
                continue
                
            # Check for country names
            name_matches = sum(1 for name in data['names'] if re.search(r'\b' + re.escape(name.lower()) + r'\b', text_lower))
            adj_matches = sum(1 for adj in data['adjectives'] if re.search(r'\b' + re.escape(adj.lower()) + r'\b', text_lower))
            
            if name_matches > 0 or adj_matches > 0:
                # Calculate confidence based on number of matches and type of match
                confidence = data['confidence']
                if name_matches > 0 and adj_matches > 0:
                    confidence += 0.05  # Slight boost for multiple types of matches
                
                results.append(ExtractionResult(
                    value=code,
                    confidence=min(0.99, confidence),  # Cap at 0.99 to leave room for TLD matches
                    source=ExtractionSource.PATTERN
                ))
                seen_codes.add(code)

        # Check for country codes (e.g., "based in DE")
        country_code_pattern = r'\b([A-Z]{2})\b'
        for match in re.finditer(country_code_pattern, text.upper()):
            code = match.group(1)
            if code in countries and code not in seen_codes and is_valid_country_code(code):
                results.append(ExtractionResult(
                    value=code,
                    confidence=0.8,
                    source=ExtractionSource.PATTERN
                ))
                seen_codes.add(code)

        return sorted(results, key=lambda x: x.confidence, reverse=True)

    async def enrich_country_with_llm(self, text: str) -> Optional[ExtractionResult]:
        """
        Use LLM to extract country when pattern matching is inconclusive.
        
        Args:
            text: Text to analyze
            
        Returns:
            ExtractionResult with the best country code or None
        """
        try:
            from langchain.chat_models import ChatOpenAI
            from langchain.schema import HumanMessage, SystemMessage
            
            llm = ChatOpenAI(
                model_name=settings.llm_model,
                temperature=0.1,
                request_timeout=30
            )
            
            messages = [
                SystemMessage(content="""You are an AI assistant that extracts country information from text. 
                Return only the ISO 3166-1 alpha-2 country code or 'None' if not found."""),
                HumanMessage(content=f"""Extract the primary country mentioned in this text. 
                Focus on the country of incorporation, headquarters, or main jurisdiction.
                Return only the 2-letter country code or 'None' if not found.
                
                Text: {text[:4000]}""")
            ]
            
            response = await llm.agenerate([messages])
            country_code = response.generations[0][0].text.strip().upper()
            
            if country_code == 'NONE' or not is_valid_country_code(country_code):
                return None
                
            return ExtractionResult(
                value=country_code,
                confidence=0.85,  # Slightly lower than pattern matching
                source=ExtractionSource.LLM
            )
            
        except Exception as e:
            logger.warning(f"Error in LLM country extraction: {e}")
            return None

    async def enrich_country(
        self, 
        text: str, 
        domain: str, 
        current_country: Optional[str] = None,
        use_llm_fallback: bool = True
    ) -> Optional[ExtractionResult]:
        """
        Extract and validate country from text and domain with confidence scoring.

        Args:
            text: Text to search
            domain: Company domain
            current_country: Existing country code
            use_llm_fallback: Whether to use LLM if pattern matching is inconclusive

        Returns:
            ExtractionResult with the best country code or None
        """
        # Check if we have a valid current country
        if current_country and is_valid_country_code(current_country):
            return ExtractionResult(
                value=current_country.upper(),
                confidence=1.0,
                source=ExtractionSource.FALLBACK
            )

        # Extract countries using patterns
        country_results = self.extract_countries(text, domain)
        
        # Return the best result if we have high confidence
        if country_results and country_results[0].confidence >= 0.85:
            return country_results[0]
            
        # Try LLM fallback if enabled and no good matches
        if use_llm_fallback and settings.enable_llm_fallback:
            llm_result = await self.enrich_country_with_llm(text)
            if llm_result:
                return llm_result
        
        # Return the best available result or None
        return country_results[0] if country_results else None

    def extract_delete_links(self, text: str) -> List[ExtractionResult]:
        """
        Extract data deletion/request links from policy text with confidence scoring.

        Args:
            text: Policy text to search

        Returns:
            List of ExtractionResult objects with links and confidence scores
        """
        results = []
        seen_links = set()
        text_lower = text.lower()
        
        # Common patterns for data deletion/request sections
        section_patterns = [
            # High confidence patterns (specific to data deletion/requests)
            (r'(?:data\s*(?:subject\s*)?access|dsar|sard|right to be forgotten|right to erasure|data deletion|data erasure|data removal)[\s\w-]*(?:form|request|portal|page|link|button|click here|visit|go to|at|:)[^\n]*?((?:https?://|www\.)[^\s)"\']+)', 0.95),
            
            # Medium confidence patterns (common in privacy policy sections)
            (r'(?:privacy|data|personal information)[\s\w-]*(?:request|access|delete|remove|erase|modify|update|correct)[\s\w-]*(?:form|request|portal|page|link|button|click here|visit|go to|at|:)[^\n]*?((?:https?://|www\.)[^\s)"\']+)', 0.85),
            
            # Lower confidence patterns (general URL patterns in relevant sections)
            (r'(?:contact|support|help|privacy|data)[\s\w-]*(?:form|request|portal|page|link|button|click here|visit|go to|at|:)[^\n]*?((?:https?://|www\.)[^\s)"\']+)', 0.7),
        ]
        
        # First, look for links in specific sections
        for pattern, confidence in section_patterns:
            for match in re.finditer(pattern, text_lower):
                url = match.group(1)
                if not url.startswith(('http://', 'https://')):
                    url = 'https://' + url.lstrip('/')
                
                if url in seen_links:
                    continue
                    
                seen_links.add(url)
                
                # Adjust confidence based on URL path
                path_confidence = 0.0
                path = url.lower().split('?')[0]  # Remove query parameters
                
                # Check for common path segments that indicate data requests
                path_keywords = [
                    'privacy', 'data', 'delete', 'remove', 'erasure', 
                    'request', 'access', 'dsar', 'gdpr', 'ccpa',
                    'rights', 'portability', 'download', 'export'
                ]
                
                if any(kw in path for kw in path_keywords):
                    path_confidence += 0.1
                
                final_confidence = min(0.99, confidence + path_confidence)
                
                results.append(ExtractionResult(
                    value=url,
                    confidence=final_confidence,
                    source=ExtractionSource.PATTERN
                ))
        
        # Also look for common button/link text near URLs
        button_patterns = [
            (r'(?:click here|request access|download data|delete my data|right to be forgotten|right to erasure|data subject access request|dsar|sard)[^\n]*?((?:https?://|www\.)[^\s)"\']+)', 0.9),
            (r'<a[^>]*?href=["\']((?:https?://|www\.)[^"\']+)["\'][^>]*?>(?:[^<]*?(?:data|privacy|access|delete|remove|erase|forget|dsar|sard|gdpr|ccpa)[^<]*?)</a>', 0.85),
        ]
        
        for pattern, confidence in button_patterns:
            for match in re.finditer(pattern, text_lower):
                url = match.group(1)
                if not url.startswith(('http://', 'https://')):
                    url = 'https://' + url.lstrip('/')
                
                if url in seen_links:
                    continue
                    
                seen_links.add(url)
                results.append(ExtractionResult(
                    value=url,
                    confidence=confidence,
                    source=ExtractionSource.PATTERN
                ))
        
        return sorted(results, key=lambda x: x.confidence, reverse=True)

    async def enrich_delete_link_with_llm(self, text: str) -> Optional[ExtractionResult]:
        """
        Use LLM to extract data deletion link when pattern matching fails.
        
        Args:
            text: Text to analyze
            
        Returns:
            ExtractionResult with the best link or None
        """
        try:
            from langchain.chat_models import ChatOpenAI
            from langchain.schema import HumanMessage, SystemMessage
            
            llm = ChatOpenAI(
                model_name=settings.llm_model,
                temperature=0.1,
                request_timeout=30
            )
            
            messages = [
                SystemMessage(content="""You are an AI assistant that extracts data deletion/access request links from privacy policies. 
                Return only the URL or 'None' if not found."""),
                HumanMessage(content=f"""Extract the URL for submitting data deletion or access requests from this privacy policy text. 
                Look for links to forms, portals, or contact pages specifically for data subject requests.
                Return only the URL or 'None' if not found.
                
                Text: {text[:4000]}""")
            ]
            
            response = await llm.agenerate([messages])
            url = response.generations[0][0].text.strip()
            
            if url.lower() == 'none' or not url.startswith(('http://', 'https://')):
                return None
                
            return ExtractionResult(
                value=url,
                confidence=0.85,  # High confidence for LLM-extracted links
                source=ExtractionSource.LLM
            )
            
        except Exception as e:
            logger.warning(f"Error in LLM delete link extraction: {e}")
            return None

    async def enrich_delete_link(
        self, 
        text: str, 
        current_delete_link: Optional[str] = None,
        use_llm_fallback: bool = True
    ) -> Optional[ExtractionResult]:
        """
        Extract and validate data deletion link from policy text with confidence scoring.

        Args:
            text: Policy text to search
            current_delete_link: Existing deletion link (if any)
            use_llm_fallback: Whether to use LLM if pattern matching fails

        Returns:
            ExtractionResult with the best link or None
        """
        # Return existing link if valid
        if current_delete_link and current_delete_link.startswith(('http://', 'https://')):
            return ExtractionResult(
                value=current_delete_link,
                confidence=1.0,
                source=ExtractionSource.FALLBACK
            )

        # Extract links using patterns
        link_results = self.extract_delete_links(text)
        
        # Return the best result if we have high confidence
        if link_results and link_results[0].confidence >= 0.8:
            return link_results[0]
            
        # Try LLM fallback if enabled and no good matches
        if use_llm_fallback and settings.enable_llm_fallback:
            llm_result = await self.enrich_delete_link_with_llm(text)
            if llm_result:
                return llm_result
        
        # Return the best available result or None
        return link_results[0] if link_results else None

    async def enrich_company(
        self, 
        company_data: Dict, 
        policy_text: str,
        use_llm_fallback: bool = True
    ) -> Dict:
        """
        Asynchronously enrich company record with all available fields.

        Args:
            company_data: Current company data
            policy_text: Policy text for extraction
            use_llm_fallback: Whether to use LLM when pattern matching is inconclusive

        Returns:
            Updated company data with metadata about the extraction
        """
        from datetime import datetime
        
        enriched = company_data.copy()
        extraction_metadata = {
            'extracted_at': datetime.utcnow().isoformat(),
            'fields': {}
        }

        try:
            # Process email extraction if enabled
            if settings.extract_emails:
                try:
                    email_result = await self.enrich_email(
                        policy_text, 
                        company_data.get('email'),
                        use_llm_fallback=use_llm_fallback
                    )
                    
                    if email_result:
                        enriched['email'] = email_result.value
                        extraction_metadata['fields']['email'] = {
                            'value': email_result.value,
                            'confidence': email_result.confidence,
                            'source': email_result.source.value,
                            'extracted_at': datetime.utcnow().isoformat()
                        }
                        logger.info(f"Extracted email: {email_result.value} (confidence: {email_result.confidence:.2f})")
                    elif 'email' in company_data:
                        extraction_metadata['fields']['email'] = {
                            'value': company_data['email'],
                            'source': 'existing',
                            'extracted_at': datetime.utcnow().isoformat()
                        }
                except Exception as e:
                    logger.error(f"Error extracting email: {e}", exc_info=True)
                    extraction_metadata['fields']['email'] = {
                        'error': str(e),
                        'extracted_at': datetime.utcnow().isoformat()
                    }

            # Process country extraction if enabled
            if settings.extract_country and 'domain' in company_data:
                try:
                    country_result = await self.enrich_country(
                        policy_text,
                        company_data['domain'],
                        company_data.get('country'),
                        use_llm_fallback=use_llm_fallback
                    )
                    
                    if country_result:
                        enriched['country'] = country_result.value
                        extraction_metadata['fields']['country'] = {
                            'value': country_result.value,
                            'confidence': country_result.confidence,
                            'source': country_result.source.value,
                            'extracted_at': datetime.utcnow().isoformat()
                        }
                        logger.info(f"Extracted country: {country_result.value} (confidence: {country_result.confidence:.2f})")
                    elif 'country' in company_data:
                        extraction_metadata['fields']['country'] = {
                            'value': company_data['country'],
                            'source': 'existing',
                            'extracted_at': datetime.utcnow().isoformat()
                        }
                except Exception as e:
                    logger.error(f"Error extracting country: {e}", exc_info=True)
                    extraction_metadata['fields']['country'] = {
                        'error': str(e),
                        'extracted_at': datetime.utcnow().isoformat()
                    }

            # Process delete link extraction if enabled
            if settings.extract_delete_link:
                try:
                    delete_link_result = await self.enrich_delete_link(
                        policy_text,
                        company_data.get('delete_link'),
                        use_llm_fallback=use_llm_fallback
                    )
                    
                    if delete_link_result:
                        enriched['delete_link'] = delete_link_result.value
                        extraction_metadata['fields']['delete_link'] = {
                            'value': delete_link_result.value,
                            'confidence': delete_link_result.confidence,
                            'source': delete_link_result.source.value,
                            'extracted_at': datetime.utcnow().isoformat()
                        }
                        logger.info(f"Extracted delete link: {delete_link_result.value} (confidence: {delete_link_result.confidence:.2f})")
                    elif 'delete_link' in company_data:
                        extraction_metadata['fields']['delete_link'] = {
                            'value': company_data['delete_link'],
                            'source': 'existing',
                            'extracted_at': datetime.utcnow().isoformat()
                        }
                except Exception as e:
                    logger.error(f"Error extracting delete link: {e}", exc_info=True)
                    extraction_metadata['fields']['delete_link'] = {
                        'error': str(e),
                        'extracted_at': datetime.utcnow().isoformat()
                    }

            # Add extraction metadata to the enriched data
            enriched['_extraction_metadata'] = extraction_metadata
            
        except Exception as e:
            logger.error(f"Unexpected error in enrich_company: {e}", exc_info=True)
            enriched['_extraction_error'] = str(e)
            
        return enriched


async def enrich_company_async(
    company_data: Dict, 
    policy_text: str, 
    use_llm_fallback: bool = True
) -> Dict:
    """
    Asynchronous convenience function to enrich a company.
    
    Args:
        company_data: Dictionary containing company data
        policy_text: Policy text to extract information from
        use_llm_fallback: Whether to use LLM when pattern matching is inconclusive
        
    Returns:
        Enriched company data with extraction metadata
    """
    enricher = FieldEnricher()
    return await enricher.enrich_company(company_data, policy_text, use_llm_fallback)


def enrich_company(company_data: Dict, policy_text: str) -> Dict:
    """
    Synchronous convenience function to enrich a company.
    
    Note: This is a wrapper around the async version for backward compatibility.
    For new code, prefer using enrich_company_async() directly.
    
    Args:
        company_data: Dictionary containing company data
        policy_text: Policy text to extract information from
        
    Returns:
        Enriched company data with extraction metadata
    """
    import asyncio
    
    # Create a new event loop for the synchronous wrapper
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    try:
        # Run the async function and get the result
        result = loop.run_until_complete(
            enrich_company_async(company_data, policy_text)
        )
        return result
    except Exception as e:
        logger.error(f"Error in enrich_company: {e}", exc_info=True)
        # Return the original data with error information
        company_data['_extraction_error'] = str(e)
        return company_data
    finally:
        # Clean up the event loop
        loop.close()
