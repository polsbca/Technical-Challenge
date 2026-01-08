"""
Database Module

SQLAlchemy ORM models and database operations.
Handles PostgreSQL connections and data persistence.
Scopes are loaded dynamically from Template 1.xlsx.
"""

import logging
from typing import List, Optional, Dict
from datetime import datetime
from sqlalchemy import create_engine, Column, Integer, String, Boolean, Float, Text, DateTime, JSON, ForeignKey, UniqueConstraint, Index
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship

from src.config import settings
from src.template_matrix_loader import TemplateMatrixLoader, normalize_scope_name
import pandas as pd

logger = logging.getLogger(__name__)

Base = declarative_base()


class Scope(Base):
    """Represents a data collection scope."""
    __tablename__ = 'scopes'

    id = Column(Integer, primary_key=True)
    name = Column(String(100), unique=True, nullable=False)
    description = Column(Text)
    category = Column(String(50))
    created_at = Column(DateTime, default=datetime.utcnow)

    company_scopes = relationship('CompanyScope', back_populates='scope', cascade='all, delete-orphan')


class Company(Base):
    """Represents a company."""
    __tablename__ = 'companies'

    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)
    domain = Column(String(255), unique=True, nullable=False)
    email = Column(String(255))
    country = Column(String(2))
    delete_link = Column(String(2048))
    data_source = Column(String(50), default='csv')
    processed = Column(Boolean, default=False)
    processed_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    company_scopes = relationship('CompanyScope', back_populates='company', cascade='all, delete-orphan')
    policy_discoveries = relationship('PolicyDiscovery', back_populates='company', cascade='all, delete-orphan')
    enrichment_history = relationship('EnrichmentHistory', back_populates='company', cascade='all, delete-orphan')
    processing_queue = relationship('ProcessingQueue', back_populates='company', cascade='all, delete-orphan')

    __table_args__ = (
        Index('idx_companies_domain', 'domain'),
        Index('idx_companies_processed', 'processed'),
    )


class CompanyScope(Base):
    """Many-to-many relationship between companies and scopes."""
    __tablename__ = 'company_scopes'

    id = Column(Integer, primary_key=True)
    company_id = Column(Integer, ForeignKey('companies.id', ondelete='CASCADE'), nullable=False)
    scope_id = Column(Integer, ForeignKey('scopes.id', ondelete='CASCADE'), nullable=False)
    applies = Column(Boolean, default=False, nullable=False)
    confidence = Column(Float, default=0.0, nullable=False)
    reasoning = Column(Text)
    source = Column(String(50), default='llm')
    extracted_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)

    company = relationship('Company', back_populates='company_scopes')
    scope = relationship('Scope', back_populates='company_scopes')

    __table_args__ = (
        UniqueConstraint('company_id', 'scope_id', name='uq_company_scope'),
        Index('idx_company_scopes_company_id', 'company_id'),
        Index('idx_company_scopes_scope_id', 'scope_id'),
    )


class PolicyDiscovery(Base):
    """Represents a discovered policy page."""
    __tablename__ = 'policy_discovery'

    id = Column(Integer, primary_key=True)
    company_id = Column(Integer, ForeignKey('companies.id', ondelete='CASCADE'), nullable=False)
    doc_type = Column(String(50), nullable=False)
    url = Column(String(2048), nullable=False)
    discovered_via = Column(String(50))
    http_status = Column(Integer)
    is_canonical = Column(Boolean, default=True)
    confidence = Column(Float, default=0.5, nullable=False)
    error_message = Column(Text)
    discovered_at = Column(DateTime, default=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)

    company = relationship('Company', back_populates='policy_discoveries')
    policy_chunks = relationship('PolicyChunk', back_populates='policy_discovery', cascade='all, delete-orphan')

    __table_args__ = (
        UniqueConstraint('company_id', 'doc_type', name='uq_company_doctype'),
        Index('idx_policy_discovery_company_id', 'company_id'),
        Index('idx_policy_discovery_doc_type', 'doc_type'),
    )


class PolicyChunk(Base):
    """Represents a chunk of policy text."""
    __tablename__ = 'policy_chunks'

    id = Column(Integer, primary_key=True)
    policy_discovery_id = Column(Integer, ForeignKey('policy_discovery.id', ondelete='CASCADE'), nullable=False)
    chunk_text = Column(Text, nullable=False)
    chunk_index = Column(Integer, nullable=False)
    token_count = Column(Integer, nullable=False)
    embedding_id = Column(String(255))
    embedding_hash = Column(String(64))
    chunk_metadata = Column(JSON)
    created_at = Column(DateTime, default=datetime.utcnow)

    policy_discovery = relationship('PolicyDiscovery', back_populates='policy_chunks')

    __table_args__ = (
        UniqueConstraint('policy_discovery_id', 'chunk_index', name='uq_policy_chunk_index'),
        Index('idx_policy_chunks_policy_discovery_id', 'policy_discovery_id'),
    )


class EnrichmentHistory(Base):
    """Tracks field enrichment operations."""
    __tablename__ = 'enrichment_history'

    id = Column(Integer, primary_key=True)
    company_id = Column(Integer, ForeignKey('companies.id', ondelete='CASCADE'), nullable=False)
    field_name = Column(String(50), nullable=False)
    old_value = Column(String(2048))
    new_value = Column(String(2048))
    confidence = Column(Float)
    source = Column(String(100))
    enriched_at = Column(DateTime, default=datetime.utcnow)

    company = relationship('Company', back_populates='enrichment_history')

    __table_args__ = (
        Index('idx_enrichment_history_company_id', 'company_id'),
    )


class ProcessingQueue(Base):
    """Queue for background processing tasks."""
    __tablename__ = 'processing_queue'

    id = Column(Integer, primary_key=True)
    company_id = Column(Integer, ForeignKey('companies.id', ondelete='CASCADE'), nullable=False)
    task_type = Column(String(50), nullable=False)
    status = Column(String(20), default='pending')
    priority = Column(Integer, default=0)
    attempt_count = Column(Integer, default=0)
    max_attempts = Column(Integer, default=3)
    error_message = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    started_at = Column(DateTime)
    completed_at = Column(DateTime)

    company = relationship('Company', back_populates='processing_queue')

    __table_args__ = (
        Index('idx_processing_queue_status', 'status'),
        Index('idx_processing_queue_company_id', 'company_id'),
    )


class DatabaseManager:
    """Manages database connections and operations."""

    def __init__(self):
        """Initialize database manager."""
        self.engine = create_engine(
            settings.postgres_url,
            pool_size=settings.db_pool_size,
            max_overflow=settings.db_max_overflow,
            pool_recycle=settings.db_pool_recycle,
            echo=settings.environment == 'development',
        )
        self.SessionLocal = sessionmaker(bind=self.engine)

    def init_db(self):
        """Initialize database schema and seed scopes from Template 1.xlsx."""
        try:
            Base.metadata.create_all(self.engine)
            logger.info("Database schema initialized")

            # Seed scopes from Template 1.xlsx
            self._seed_scopes_from_template()

        except Exception as e:
            logger.error(f"Error initializing database: {e}")
            raise

    def _seed_scopes_from_template(self):
        """Seed scopes table from Template 1.xlsx policy-scope matrix."""
        try:
            session = self.SessionLocal()

            # Load the policy-scope matrix
            loader = TemplateMatrixLoader()
            scope_to_companies = loader.get_scope_to_companies_mapping()

            # Get original scope names from template
            df = pd.read_excel(loader.template_path)
            original_scopes = df[df.columns[0]].dropna().tolist()

            # Insert scopes if not already present
            scopes_added = 0
            for original_name in original_scopes:
                normalized = normalize_scope_name(original_name)
                if not normalized:
                    continue

                existing = session.query(Scope).filter_by(name=original_name).first()

                if not existing:
                    scope = Scope(
                        name=original_name,
                        description=None,
                        category=None,
                    )
                    session.add(scope)
                    logger.debug(f"Added scope: {original_name}")
                    scopes_added += 1

            session.commit()
            logger.info(f"Seeded {scopes_added} scopes from Template 1.xlsx policy-scope matrix")

        except FileNotFoundError as e:
            logger.warning(f"Template 1.xlsx not found, skipping dynamic seeding: {e}")
            logger.info("Using SQL migration for scope seeding instead")
        except Exception as e:
            logger.error(f"Error seeding scopes from template: {e}")
            session.rollback()
            raise
        finally:
            session.close()

    def get_session(self):
        """Get database session."""
        return self.SessionLocal()

    def close(self):
        """Close database connections."""
        self.engine.dispose()


# Global database manager instance
db_manager = DatabaseManager()


def get_session():
    """Get database session."""
    return db_manager.get_session()


def init_database():
    """Initialize database."""
    db_manager.init_db()
