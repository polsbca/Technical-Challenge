"""
Vector Storage Module

Manages policy text chunking, embedding, and vector storage in Qdrant.
Supports semantic search for policy retrieval.
"""

import logging
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
import json

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct
import requests

from src.config import settings
from src.utils import retry

logger = logging.getLogger(__name__)


@dataclass
class TextChunk:
    """Represents a chunk of text with metadata."""
    text: str
    chunk_index: int
    token_count: int
    policy_id: int
    metadata: Dict


@dataclass
class SearchResult:
    """Represents a search result from Qdrant."""
    chunk_id: str
    text: str
    score: float
    metadata: Dict


class VectorStorage:
    """Manages vector storage in Qdrant."""

    def __init__(self):
        """Initialize Qdrant client."""
        # Use URL-based connection to ensure HTTP protocol is used
        url = f"http://{settings.qdrant_host}:{settings.qdrant_port}"
        self.client = QdrantClient(url=url)
        self.collection_name = settings.qdrant_collection_name
        self.vector_size = settings.embedding_dimension
        self._ensure_collection()

    def _ensure_collection(self):
        """Ensure collection exists in Qdrant."""
        try:
            self.client.get_collection(self.collection_name)
            logger.info(f"Collection {self.collection_name} already exists")
        except Exception:
            logger.info(f"Creating collection {self.collection_name}")
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=VectorParams(
                    size=self.vector_size,
                    distance=Distance.COSINE
                ),
            )

    @retry(max_attempts=3, delay=1.0, backoff=2.0)
    def upsert_chunk(self, chunk: TextChunk, embedding: List[float]) -> bool:
        """
        Upsert a text chunk with its embedding.

        Args:
            chunk: TextChunk to store
            embedding: Vector embedding

        Returns:
            Success status
        """
        try:
            domain = chunk.metadata.get('domain')
            doc_type = chunk.metadata.get('doc_type')
            url = chunk.metadata.get('url') or chunk.metadata.get('source_url')
            company_id = chunk.metadata.get('company_id')

            point = PointStruct(
                id=hash(f"{chunk.policy_id}_{chunk.chunk_index}") % (2**31),
                vector=embedding,
                payload={
                    'text': chunk.text,
                    'chunk_index': chunk.chunk_index,
                    'token_count': chunk.token_count,
                    'policy_id': chunk.policy_id,
                    'domain': domain,
                    'doc_type': doc_type,
                    'url': url,
                    'company_id': company_id,
                    'metadata': json.dumps(chunk.metadata),
                }
            )

            self.client.upsert(
                collection_name=self.collection_name,
                points=[point]
            )

            return True

        except Exception as e:
            logger.error(f"Error upserting chunk: {e}")
            return False

    @retry(max_attempts=3, delay=1.0, backoff=2.0)
    def search(self, query_embedding: List[float], top_k: int = 5) -> List[SearchResult]:
        """
        Search for similar chunks.

        Args:
            query_embedding: Query vector
            top_k: Number of results to return

        Returns:
            List of SearchResult
        """
        try:
            results = self.client.query_points(
                collection_name=self.collection_name,
                query=query_embedding,
                limit=top_k,
            )

            search_results = []
            for point in results.points:
                metadata = json.loads(point.payload.get('metadata', '{}'))
                search_results.append(SearchResult(
                    chunk_id=str(point.id),
                    text=point.payload.get('text', ''),
                    score=point.score,
                    metadata=metadata
                ))

            return search_results

        except Exception as e:
            logger.error(f"Error searching: {e}")
            return []

    def delete_policy_chunks(self, policy_id: int) -> bool:
        """Delete all chunks for a policy."""
        try:
            self.client.delete(
                collection_name=self.collection_name,
                points_selector={
                    'filter': {
                        'must': [
                            {
                                'key': 'policy_id',
                                'match': {'value': policy_id}
                            }
                        ]
                    }
                }
            )
            return True
        except Exception as e:
            logger.error(f"Error deleting chunks: {e}")
            return False


class TextChunker:
    """Splits text into chunks for embedding."""

    def __init__(self, chunk_size: int = 512, overlap: int = 128):
        """
        Initialize chunker.

        Args:
            chunk_size: Target chunk size in tokens
            overlap: Overlap between chunks in tokens
        """
        self.chunk_size = chunk_size
        self.overlap = overlap

    def chunk_text(self, text: str, policy_id: int) -> List[TextChunk]:
        """
        Split text into chunks.

        Args:
            text: Text to chunk
            policy_id: Associated policy ID

        Returns:
            List of TextChunk
        """
        # Simple word-based chunking (rough token estimation)
        words = text.split()
        chunks = []

        chunk_index = 0
        i = 0

        while i < len(words):
            # Get chunk
            chunk_words = words[i:i + self.chunk_size]
            chunk_text = ' '.join(chunk_words)

            chunks.append(TextChunk(
                text=chunk_text,
                chunk_index=chunk_index,
                token_count=len(chunk_words),
                policy_id=policy_id,
                metadata={'start_word': i, 'end_word': i + len(chunk_words)}
            ))

            # Move forward with overlap
            i += self.chunk_size - self.overlap
            chunk_index += 1

        logger.info(f"Chunked text into {len(chunks)} chunks")
        return chunks


class EmbeddingClient:
    """Generates embeddings for text."""

    def __init__(self):
        """Initialize embedding client."""
        self.embedding_model = settings.embedding_model
        # Handle both full URL and host-only formats
        ollama_host = settings.ollama_host
        if ollama_host.startswith('http'):
            self.ollama_host = ollama_host
        else:
            self.ollama_host = f"http://{ollama_host}:11434"

    @retry(max_attempts=3, delay=1.0, backoff=2.0)
    def embed(self, text: str) -> Optional[List[float]]:
        """
        Generate embedding for text.

        Args:
            text: Text to embed

        Returns:
            Embedding vector or None
        """
        try:
            # Use Ollama for embedding
            response = requests.post(
                f"{self.ollama_host}/api/embeddings",
                json={
                    "model": self.embedding_model,
                    "prompt": text
                },
                timeout=30
            )

            if response.status_code == 200:
                data = response.json()
                return data.get('embedding')

            logger.error(f"Embedding error: {response.status_code}")
            return None

        except Exception as e:
            logger.error(f"Error generating embedding: {e}")
            return None


def chunk_and_store(text: str, policy_id: int, vector_storage: VectorStorage, embedding_client: EmbeddingClient) -> int:
    """
    Chunk text and store vectors.

    Args:
        text: Text to chunk
        policy_id: Policy ID
        vector_storage: VectorStorage instance
        embedding_client: EmbeddingClient instance

    Returns:
        Number of chunks stored
    """
    chunker = TextChunker()
    chunks = chunker.chunk_text(text, policy_id)

    stored_count = 0
    for chunk in chunks:
        embedding = embedding_client.embed(chunk.text)
        if embedding:
            if vector_storage.upsert_chunk(chunk, embedding):
                stored_count += 1

    return stored_count
