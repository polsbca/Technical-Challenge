"""
Centralized configuration management for the application.
Loads settings from environment variables with sensible defaults.
"""

import os
from pathlib import Path
from typing import Optional
from functools import lru_cache
from urllib.parse import quote
from pydantic_settings import BaseSettings
from pydantic import Field, validator


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # ========================================================================
    # PostgreSQL Configuration
    # ========================================================================
    postgres_user: str = Field(default="challenge_user", alias="POSTGRES_USER")
    postgres_password: str = Field(default="secure_password", alias="POSTGRES_PASSWORD")
    postgres_host: str = Field(default="localhost", alias="POSTGRES_HOST")
    postgres_port: int = Field(default=5432, alias="POSTGRES_PORT")
    postgres_db: str = Field(default="challenge2", alias="POSTGRES_DB")

    @property
    def postgres_url(self) -> str:
        """PostgreSQL connection URL."""
        # URL encode password to handle special characters like @
        encoded_password = quote(self.postgres_password, safe='')
        return (
            f"postgresql://{self.postgres_user}:{encoded_password}@"
            f"{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    # ========================================================================
    # Qdrant Configuration
    # ========================================================================
    qdrant_host: str = Field(default="localhost", alias="QDRANT_HOST")
    qdrant_port: int = Field(default=6333, alias="QDRANT_PORT")
    qdrant_api_key: str = Field(default="default-key", alias="QDRANT_API_KEY")
    qdrant_collection_name: str = Field(default="policy_chunks", alias="QDRANT_COLLECTION_NAME")

    @property
    def qdrant_url(self) -> str:
        """Qdrant URL."""
        return f"http://{self.qdrant_host}:{self.qdrant_port}"

    # ========================================================================
    # Ollama Configuration
    # ========================================================================
    ollama_host: str = Field(default="http://localhost:11434", alias="OLLAMA_HOST")
    ollama_model: str = Field(default="mistral", alias="OLLAMA_MODEL")

    # ========================================================================
    # OpenAI Configuration (Optional)
    # ========================================================================
    openai_api_key: Optional[str] = Field(default=None, alias="OPENAI_API_KEY")
    openai_model: str = Field(default="gpt-3.5-turbo", alias="OPENAI_MODEL")

    # ========================================================================
    # Embedding Configuration
    # ========================================================================
    embedding_model: str = Field(default="nomic-embed-text", alias="EMBEDDING_MODEL")
    embedding_dimension: int = Field(default=1536, alias="EMBEDDING_DIMENSION")

    # ========================================================================
    # Text Processing Configuration
    # ========================================================================
    chunk_size: int = Field(default=512, alias="CHUNK_SIZE")
    chunk_overlap: int = Field(default=128, alias="CHUNK_OVERLAP")
    min_content_words: int = Field(default=500, alias="MIN_CONTENT_WORDS")
    top_k_chunks: int = Field(default=5, alias="TOP_K_CHUNKS")
    confidence_threshold: float = Field(default=0.60, alias="CONFIDENCE_THRESHOLD")

    # ========================================================================
    # Application Configuration
    # ========================================================================
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    environment: str = Field(default="development", alias="ENVIRONMENT")

    # ========================================================================
    # Web Scraping Configuration
    # ========================================================================
    http_timeout: int = Field(default=30, alias="HTTP_TIMEOUT")
    max_retries: int = Field(default=2, alias="MAX_RETRIES")
    user_agent: str = Field(
        default=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
        alias="USER_AGENT",
    )

    # ========================================================================
    # Discovery Configuration
    # ========================================================================
    discovery_timeout: int = Field(default=10, alias="DISCOVERY_TIMEOUT")
    discovery_methods: str = Field(default="sitemap,footer,heuristic,link_text", alias="DISCOVERY_METHODS")

    @property
    def discovery_methods_list(self) -> list[str]:
        """Discovery methods as a list."""
        return [method.strip() for method in self.discovery_methods.split(",")]

    # ========================================================================
    # LLM Extraction Configuration
    # ========================================================================
    llm_temperature: float = Field(default=0.3, alias="LLM_TEMPERATURE")
    llm_max_tokens: int = Field(default=2000, alias="LLM_MAX_TOKENS")
    llm_timeout: int = Field(default=60, alias="LLM_TIMEOUT")
    llm_timeout_fallback: bool = Field(default=True, alias="LLM_TIMEOUT_FALLBACK")

    # ========================================================================
    # Database Connection Pool
    # ========================================================================
    db_pool_size: int = Field(default=10, alias="DB_POOL_SIZE")
    db_max_overflow: int = Field(default=20, alias="DB_MAX_OVERFLOW")
    db_pool_recycle: int = Field(default=3600, alias="DB_POOL_RECYCLE")

    # ========================================================================
    # Redis Configuration (Optional)
    # ========================================================================
    redis_host: str = Field(default="localhost", alias="REDIS_HOST")
    redis_port: int = Field(default=6379, alias="REDIS_PORT")
    redis_db: int = Field(default=0, alias="REDIS_DB")

    @property
    def redis_url(self) -> str:
        """Redis URL."""
        return f"redis://{self.redis_host}:{self.redis_port}/{self.redis_db}"

    # ========================================================================
    # Enrichment Configuration
    # ========================================================================
    extract_emails: bool = Field(default=True, alias="EXTRACT_EMAILS")
    extract_country: bool = Field(default=True, alias="EXTRACT_COUNTRY")
    extract_delete_link: bool = Field(default=True, alias="EXTRACT_DELETE_LINK")

    class Config:
        """Pydantic settings config."""
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False

    @validator("confidence_threshold")
    def validate_confidence(cls, v):
        """Ensure confidence threshold is between 0 and 1."""
        if not 0 <= v <= 1:
            raise ValueError("confidence_threshold must be between 0 and 1")
        return v

    @validator("log_level")
    def validate_log_level(cls, v):
        """Ensure log level is valid."""
        valid_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        if v.upper() not in valid_levels:
            raise ValueError(f"log_level must be one of {valid_levels}")
        return v.upper()

    @validator("environment")
    def validate_environment(cls, v):
        """Ensure environment is valid."""
        valid_envs = {"development", "production", "testing"}
        if v.lower() not in valid_envs:
            raise ValueError(f"environment must be one of {valid_envs}")
        return v.lower()


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """
    Get application settings (cached).
    
    Returns:
        Settings: Application configuration object
    """
    return Settings()


# Convenience access
settings = get_settings()


# ============================================================================
# Path Configuration
# ============================================================================

PROJECT_ROOT = Path(__file__).parent.parent
SRC_DIR = PROJECT_ROOT / "src"
LOGS_DIR = PROJECT_ROOT / "logs"
DATA_DIR = PROJECT_ROOT / "data"
OUTPUTS_DIR = PROJECT_ROOT / "outputs"
MIGRATIONS_DIR = PROJECT_ROOT / "migrations"
DOCS_DIR = PROJECT_ROOT / "docs"

# Create directories if they don't exist
for directory in [LOGS_DIR, DATA_DIR, OUTPUTS_DIR]:
    directory.mkdir(exist_ok=True)
