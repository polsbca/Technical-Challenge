"""
Main Orchestration Module

Coordinates all components for end-to-end policy discovery, extraction, and enrichment.
Loads scope definitions dynamically from Template 1.xlsx.
"""

import asyncio
import logging
import csv
import sys
import argparse
from pathlib import Path
from typing import List, Dict, Optional, Any, Coroutine

from src.config import settings, get_settings
from src.policy_discovery import PolicyDiscovery, DiscoveredPolicy
from src.scraper import Scraper
from src.vector_storage import VectorStorage, TextChunker, EmbeddingClient
from src.llm_extraction import LLMExtraction, ScopeExtraction
from src.enrichment import FieldEnricher
from src.database import (
    DatabaseManager, Company, CompanyScope, PolicyDiscovery as PolicyDiscoveryDB,
    PolicyChunk, EnrichmentHistory, Scope, get_session, init_database
)
from src.utils import ProgressTracker, setup_logging, timeit
from src.template_loader import load_scopes_from_template

logger = logging.getLogger(__name__)


class PolicyProcessingPipeline:
    """Main pipeline for processing companies and policies."""

    def __init__(self):
        """Initialize pipeline."""
        self.settings = get_settings()
        self.discovery = None
        self.scraper = Scraper()
        self.llm_extractor = LLMExtraction()
        self.field_enricher = FieldEnricher()
        self.vector_storage = VectorStorage()
        self.embedding_client = EmbeddingClient()
        self.chunker = TextChunker()
        self.db = DatabaseManager()
        self.session = None
        self.llm_model = getattr(settings, 'llm_model', 'gpt-4')
        self.enable_llm_fallback = getattr(settings, 'enable_llm_fallback', True)

    def initialize(self):
        """Initialize pipeline resources."""
        logger.info("Initializing pipeline...")
        
        # Initialize LLM extraction (loads scopes from template)
        try:
            llm_scopes = self.llm_extractor.get_scopes()
            logger.info(f"Loaded {len(llm_scopes)} scopes from Template 1.xlsx")
        except Exception as e:
            logger.warning(f"Could not load scopes from template: {e}")

        init_database()
        self.session = get_session()
        logger.info("Pipeline initialized")

    def process_companies(self, csv_path: str, domains: Optional[List[str]] = None, fast_ingest: bool = False):
        """
        Process companies from CSV file asynchronously.

        Args:
            csv_path: Path to CSV file
            domains: List of specific domains to process (optional)
            fast_ingest: If True, skips LLM scope extraction to speed up ingestion
        """
        async def process_all():
            # Load companies from CSV
            companies = self._load_companies_from_csv(csv_path)
            if domains:
                companies = [c for c in companies if c['domain'] in domains]

            logger.info(f"Processing {len(companies)} companies")
            tracker = ProgressTracker(len(companies))
            
            # Process companies one at a time (but policies concurrently)
            for company in companies:
                try:
                    await self._process_company(company, tracker, len(companies), fast_ingest)
                except Exception as e:
                    logger.error(f"Error processing {company.get('domain')}: {e}")
                    tracker.update(1)
                    continue

            tracker.finish()
            logger.info("Company processing complete")

        # Run the async function
        asyncio.run(process_all())

    def _load_companies_from_csv(self, csv_path: str) -> List[Dict]:
        """Load companies from CSV file."""
        companies = []

        try:
            with open(csv_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    companies.append({
                        'name': row.get('name', '').strip(),
                        'domain': row.get('domain', '').strip(),
                        'email': row.get('email', '').strip() or None,
                        'country': row.get('country', '').strip() or None,
                        'delete_link': row.get('delete_link', '').strip() or None,
                    })

            logger.info(f"Loaded {len(companies)} companies from CSV")
            return companies

        except Exception as e:
            logger.error(f"Error loading CSV: {e}")
            return []

    @timeit
    async def _process_company(
        self, 
        company_data: Dict, 
        progress: ProgressTracker, 
        total: int, 
        fast_ingest: bool = False
    ) -> None:
        """
        Process a single company asynchronously.

        Args:
            company_data: Company data dictionary
            progress: Progress tracker
            total: Total number of items for progress tracking
            fast_ingest: If True, skips LLM scope extraction
        """
        domain = company_data['domain']
        logger.info(f"Processing {domain}")

        try:
            # Step 1: Discover policies
            discovery = PolicyDiscovery(domain)
            discovered_policies = discovery.discover()

            if not discovered_policies:
                logger.warning(f"No policies discovered for {domain}")
                if progress:
                    progress.update(1, f"No policies found for {domain}")
                return

            logger.info(f"Discovered {len(discovered_policies)} policies for {domain}")

            # Store company in DB
            company_db = self._store_company(company_data)

            # Process policies concurrently
            tasks = []
            for doc_type, policy_info in discovered_policies.items():
                task = self._process_policy(
                    company_db, 
                    policy_info, 
                    progress, 
                    total, 
                    fast_ingest=fast_ingest
                )
                tasks.append(task)

            # Run all policy processing tasks concurrently
            await asyncio.gather(*tasks, return_exceptions=True)

            # Update progress after all policies are processed
            if progress:
                progress.update(1, f"Completed {domain}")

        except Exception as e:
            logger.error(f"Error processing company {domain}: {e}", exc_info=True)
            if progress:
                progress.update(1, f"Error: {str(e)}")
            raise


    def _store_company(self, company_data: Dict) -> Company:
        """Store company in database."""
        try:
            # Check if already exists
            existing = self.session.query(Company).filter_by(domain=company_data['domain']).first()
            if existing:
                return existing

            company = Company(
                name=company_data['name'],
                domain=company_data['domain'],
                email=company_data.get('email'),
                country=company_data.get('country'),
                delete_link=company_data.get('delete_link'),
            )

            self.session.add(company)
            self.session.commit()

            logger.info(f"Stored company: {company_data['domain']}")
            return company

        except Exception as e:
            logger.error(f"Error storing company: {e}")
            self.session.rollback()
            raise

    async def _process_policy(
        self, 
        company: Company, 
        policy_info: DiscoveredPolicy, 
        progress: Optional[ProgressTracker] = None, 
        total: int = 1,
        fast_ingest: bool = False
    ) -> None:
        """
        Process a discovered policy asynchronously.

        Args:
            company: Company database object
            policy_info: DiscoveredPolicy information
            progress: Optional progress tracker
            total: Total number of items for progress tracking
            fast_ingest: If True, skips LLM scope extraction
        """
        logger.info(f"Processing policy: {policy_info.doc_type} ({policy_info.url})")
        
        if fast_ingest:
            logger.info("Fast ingest mode: using simplified processing")

        try:
            # Step 1: Scrape policy
            scraped = self.scraper.scrape(policy_info.url)
            if not scraped:
                logger.warning(f"Failed to scrape {policy_info.url}")
                return

            logger.info(f"Scraped {scraped.word_count} words from {policy_info.url}")

            # Step 2: Store policy discovery record
            policy_db = self._store_policy_discovery(company, policy_info, scraped.word_count)

            # Step 3: Process scopes using the new ScopeExtractor
            if not fast_ingest:
                try:
                    # Initialize the LLM and ScopeExtractor
                    from langchain.chat_models import ChatOpenAI
                    from src.llm_extraction import ScopeExtractor
                    from src.scope_processor import process_company_scopes
                    
                    # Initialize LLM
                    llm = ChatOpenAI(
                        model_name=self.llm_model,
                        temperature=0.1,
                        request_timeout=60
                    )
                    
                    # Initialize scope extractor
                    scope_extractor = ScopeExtractor(llm=llm)
                    
                    # Process scopes
                    await process_company_scopes(
                        session=self.session,
                        company_id=company.id,
                        policy_text=scraped.text,
                        scope_extractor=scope_extractor
                    )
                    
                    logger.info(f"Completed scope processing for company {company.id}")
                    
                except Exception as e:
                    logger.error(f"Error during scope processing: {e}", exc_info=True)
                    if progress:
                        progress.update(1, f"Error in scope processing: {str(e)}")
            else:
                logger.info("Skipping scope extraction in fast_ingest mode")

            # Step 4: Chunk and store in vector DB (only store in fast_ingest mode)
            if fast_ingest:
                chunks = self.chunker.chunk_text(scraped.text, policy_db.id)
                for chunk in chunks:
                    chunk.metadata.update({
                        'domain': company.domain,
                        'company_id': company.id,
                        'doc_type': policy_info.doc_type,
                        'url': policy_info.url,
                        'source_url': policy_info.url,
                        'fast_ingest': True
                    })
                    embedding = self.embedding_client.embed(chunk.text)
                    if embedding:
                        self.vector_storage.upsert_chunk(chunk, embedding)
                        logger.debug(f"Stored chunk {chunk.chunk_index} for policy {policy_db.id}")

            # Step 5: Enrich company fields (only in fast_ingest mode)
            if fast_ingest:
                enriched_fields = await self.field_enricher.enrich_company(
                    {
                        'domain': company.domain,
                        'email': company.email,
                        'country': company.country,
                        'delete_link': company.delete_link,
                    },
                    scraped.text
                )
                self._update_company_enrichment(company, enriched_fields)

            if progress:
                progress.update(1, f"Processed {policy_info.doc_type}")

        except Exception as e:
            logger.error(f"Error processing policy: {e}", exc_info=True)
            if progress:
                progress.update(1, f"Error: {str(e)}")
            raise

        logger.info(f"Policy processing complete for {policy_info.doc_type}")

    def _store_policy_discovery(self, company: Company, policy_info: DiscoveredPolicy, word_count: int) -> PolicyDiscoveryDB:
        """Store policy discovery record."""
        try:
            existing = self.session.query(PolicyDiscoveryDB).filter_by(
                company_id=company.id,
                doc_type=policy_info.doc_type,
            ).first()

            if existing:
                existing.url = policy_info.url
                existing.discovered_via = policy_info.discovered_via.value
                existing.http_status = policy_info.http_status
                existing.is_canonical = policy_info.is_canonical
                existing.confidence = policy_info.confidence
                self.session.commit()
                return existing

            policy_db = PolicyDiscoveryDB(
                company_id=company.id,
                doc_type=policy_info.doc_type,
                url=policy_info.url,
                discovered_via=policy_info.discovered_via.value,
                http_status=policy_info.http_status,
                is_canonical=policy_info.is_canonical,
                confidence=policy_info.confidence,
            )

            self.session.add(policy_db)
            self.session.commit()

            return policy_db

        except Exception as e:
            logger.error(f"Error storing policy discovery: {e}")
            self.session.rollback()
            raise

    def _store_scope_extractions(self, company: Company, scopes: List[ScopeExtraction]):
        """Store scope extraction results."""
        try:
            for scope_extraction in scopes:
                # Find scope by name
                scope = self.session.query(
                    self.session.query(Scope).model.__class__
                ).filter_by(name=scope_extraction.scope_name).first()

                if not scope:
                    logger.warning(f"Scope not found: {scope_extraction.scope_name}")
                    continue

                # Store or update company_scope
                company_scope = self.session.query(CompanyScope).filter_by(
                    company_id=company.id,
                    scope_id=scope.id
                ).first()

                if company_scope:
                    company_scope.applies = scope_extraction.applies
                    company_scope.confidence = scope_extraction.confidence
                    company_scope.reasoning = scope_extraction.reasoning
                else:
                    company_scope = CompanyScope(
                        company_id=company.id,
                        scope_id=scope.id,
                        applies=scope_extraction.applies,
                        confidence=scope_extraction.confidence,
                        reasoning=scope_extraction.reasoning,
                    )
                    self.session.add(company_scope)

            self.session.commit()

        except Exception as e:
            logger.error(f"Error storing scope extractions: {e}")
            self.session.rollback()

    def _update_company_enrichment(self, company: Company, enriched_fields: Dict):
        """Update company with enriched fields."""
        try:
            changes = False

            if enriched_fields.get('email') and not company.email:
                company.email = enriched_fields['email']
                changes = True

            if enriched_fields.get('country') and not company.country:
                company.country = enriched_fields['country']
                changes = True

            if enriched_fields.get('delete_link') and not company.delete_link:
                company.delete_link = enriched_fields['delete_link']
                changes = True

            if changes:
                company.updated_at = None  # Will use onupdate default
                self.session.commit()
                logger.info(f"Updated enrichment for {company.domain}")

        except Exception as e:
            logger.error(f"Error updating company enrichment: {e}")
            self.session.rollback()

    def cleanup(self):
        """Clean up pipeline resources."""
        if self.session:
            self.session.close()
        self.db.close()
        logger.info("Pipeline cleanup complete")


def main():
    """Main entry point."""
    # Set up argument parsing
    parser = argparse.ArgumentParser(description='Policy Discovery and Enrichment Pipeline')
    parser.add_argument('--input', required=True, help='Input CSV file path')
    parser.add_argument('--domains', nargs='*', help='Specific domains to process')
    parser.add_argument('--env', default='development', help='Environment (development/production)')
    parser.add_argument('--fast-ingest', action='store_true', help='Skip LLM scope extraction during ingestion (faster)')
    parser.add_argument('--llm-model', default='gpt-4', help='LLM model to use for extraction')
    parser.add_argument('--no-llm-fallback', action='store_false', dest='enable_llm_fallback', 
                       help='Disable LLM fallback for enrichment')
    parser.add_argument('--log-level', default='INFO', 
                       choices=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'],
                       help='Logging level')

    args = parser.parse_args()

    # Set environment and configuration
    settings.environment = args.env
    settings.llm_model = args.llm_model
    settings.enable_llm_fallback = args.enable_llm_fallback

    # Initialize logging
    log_level = getattr(logging, args.log_level.upper(), logging.INFO)
    setup_logging(level=log_level)
    logger.setLevel(log_level)

    # Log configuration
    logger.info("Starting Policy Processing Pipeline")
    logger.info(f"Environment: {settings.environment}")
    logger.info(f"LLM Model: {settings.llm_model}")
    logger.info(f"LLM Fallback: {'Enabled' if settings.enable_llm_fallback else 'Disabled'}")
    logger.info(f"Fast Ingest: {'Enabled' if args.fast_ingest else 'Disabled'}")

    # Initialize and run pipeline
    pipeline = PolicyProcessingPipeline()
    
    try:
        # Initialize pipeline components
        pipeline.initialize()
        
        # Process companies
        pipeline.process_companies(
            csv_path=args.input,
            domains=args.domains,
            fast_ingest=args.fast_ingest
        )
        
        logger.info("Pipeline completed successfully")
        
    except KeyboardInterrupt:
        logger.info("Pipeline interrupted by user")
        sys.exit(130)  # Standard exit code for SIGINT
        
    except Exception as e:
        logger.critical(f"Pipeline failed: {e}", exc_info=True)
        sys.exit(1)
        
    finally:
        try:
            pipeline.cleanup()
        except Exception as e:
            logger.error(f"Error during cleanup: {e}", exc_info=True)
            sys.exit(1)

    logger.info("Pipeline complete")


if __name__ == '__main__':
    main()
