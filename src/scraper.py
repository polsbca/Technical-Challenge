"""
Web Scraper Module

Extracts clean text content from policy pages with:
- Boilerplate removal (navigation, ads, scripts)
- HTML-to-text conversion
- Language detection
- Text validation
"""

import logging
from typing import Dict, Optional, Tuple
from dataclasses import dataclass
import requests
from bs4 import BeautifulSoup
import trafilatura

from src.config import settings
from src.utils import retry

logger = logging.getLogger(__name__)


@dataclass
class ScrapedContent:
    """Represents scraped and cleaned content."""
    text: str
    html: Optional[str]
    language: Optional[str]
    word_count: int
    title: Optional[str]
    metadata: Dict


class Scraper:
    """Scrapes and cleans policy page content."""

    def __init__(self):
        """Initialize scraper."""
        self.session = requests.Session()
        self.session.headers.update({'User-Agent': settings.user_agent})
        self.timeout = settings.http_timeout
        self.max_retries = settings.max_retries

    @retry(max_attempts=3, delay=1.0, backoff=2.0)
    def scrape(self, url: str) -> Optional[ScrapedContent]:
        """
        Scrape and clean content from URL.

        Args:
            url: URL to scrape

        Returns:
            ScrapedContent or None if scraping fails
        """
        logger.info(f"Scraping {url}")

        try:
            # Fetch page
            response = self.session.get(url, timeout=self.timeout)
            response.raise_for_status()

            # Extract main content using trafilatura
            extracted = trafilatura.extract(response.text)

            if not extracted:
                logger.warning(f"Failed to extract content from {url}")
                return None

            # Count words
            word_count = len(extracted.split())

            if word_count < settings.min_content_words:
                logger.warning(f"Content too short ({word_count} words) from {url}")
                return None

            # Parse HTML for title
            soup = BeautifulSoup(response.text, 'html.parser')
            title = None
            if soup.title:
                title = soup.title.string

            logger.info(f"Successfully scraped {word_count} words from {url}")

            # Basic metadata
            metadata = {'url': url, 'status_code': response.status_code}

            return ScrapedContent(
                text=extracted,
                html=response.text,
                language=None,
                word_count=word_count,
                title=title,
                metadata=metadata
            )

            return ScrapedContent(
                text=extracted,
                html=response.text,
                language=metadata.get('language') if metadata else None,
                word_count=word_count,
                title=title,
                metadata=metadata or {}
            )

        except requests.RequestException as e:
            logger.error(f"Request error scraping {url}: {e}")
            return None
        except Exception as e:
            logger.error(f"Error scraping {url}: {e}")
            return None

    @staticmethod
    def clean_text(text: str) -> str:
        """
        Clean text content.

        Args:
            text: Raw text content

        Returns:
            Cleaned text
        """
        # Remove extra whitespace
        lines = text.split('\n')
        cleaned_lines = [line.strip() for line in lines if line.strip()]
        return '\n'.join(cleaned_lines)

    @staticmethod
    def estimate_language(text: str) -> Optional[str]:
        """
        Estimate language of text.

        Args:
            text: Text to analyze

        Returns:
            Language code or None
        """
        try:
            from langdetect import detect
            return detect(text)
        except Exception:
            return None


def scrape_url(url: str) -> Optional[ScrapedContent]:
    """Convenience function to scrape a URL."""
    scraper = Scraper()
    return scraper.scrape(url)
