"""
Policy Discovery Module

Automatically discovers policy page URLs for a given domain through multiple methods:
- Sitemap parsing (robots.txt → sitemap.xml)
- Footer link extraction
- Common path heuristics
- Link text search

Exports canonical policy URLs with confidence scores.
"""

import logging
from typing import Dict, Optional
from dataclasses import dataclass
from enum import Enum
from urllib.parse import urljoin, urlparse
import requests
from bs4 import BeautifulSoup

from src.config import settings
from src.utils import retry, normalize_url

logger = logging.getLogger(__name__)


class DiscoveryMethod(Enum):
    """Enumeration of policy discovery methods."""
    SITEMAP = "sitemap"
    FOOTER = "footer"
    HEURISTIC = "heuristic"
    LINK_TEXT = "link_text"


@dataclass
class DiscoveredPolicy:
    """Represents a discovered policy page."""
    url: str
    doc_type: str  # 'privacy', 'terms', 'dpa', etc.
    discovered_via: DiscoveryMethod
    confidence: float
    http_status: Optional[int] = None
    is_canonical: bool = True
    metadata: Optional[Dict] = None


class PolicyDiscovery:
    """Discovers policy pages for a given domain."""

    DOMAIN_OVERRIDES = {
        'google.com': {
            'privacy': 'https://policies.google.com/privacy',
            'terms': 'https://policies.google.com/terms',
        },
    }

    # Common policy page paths to check
    HEURISTIC_PATHS = [
        "/privacy",
        "/privacy-policy",
        "/privacy_policy",
        "/policies/privacy",
        "/policy/privacy",
        "/terms",
        "/terms-of-service",
        "/terms_of_service",
        "/tos",
        "/terms-of-use",
        "/policies/terms",
        "/policy/terms",
        "/legal",
        "/legal-notices",
        "/legal/privacy",
        "/data-privacy",
        "/data-protection",
        "/dpa",
        "/cookies",
        "/cookie-policy",
    ]

    # Keywords to match in link text
    POLICY_KEYWORDS = {
        'privacy': ['privacy', 'data protection', 'gdpr', 'privacy policy'],
        'terms': ['terms', 'terms of service', 'tos', 'terms of use', 'eula'],
        'dpa': ['data processing', 'dpa', 'data agreement'],
    }

    URL_KEYWORDS = {
        'privacy': ['privacy', 'privacy-policy', 'privacy_policy', 'data-privacy', 'data-protection', 'cookie'],
        'terms': ['terms', 'terms-of-service', 'terms_of_service', 'terms-of-use', 'tos', 'eula'],
        'dpa': ['dpa', 'data-processing', 'data_processing', 'processing', 'processor'],
    }

    def __init__(self, domain: str):
        """Initialize with domain."""
        self.domain = normalize_url(domain)
        self.base_url = self._normalize_domain(domain)
        self.session = requests.Session()
        self.session.headers.update({'User-Agent': settings.user_agent})
        self.session.timeout = settings.http_timeout

    @staticmethod
    def _normalize_domain(domain: str) -> str:
        """Normalize domain to base URL."""
        if not domain.startswith(('http://', 'https://')):
            domain = f'https://{domain}'
        parsed = urlparse(domain)
        return f"{parsed.scheme}://{parsed.netloc}"

    @retry(max_attempts=3, delay=1.0, backoff=2.0)
    def discover(self) -> Dict[str, DiscoveredPolicy]:
        """
        Discover policy pages using all available methods.

        Returns:
            Dictionary mapping doc_type to DiscoveredPolicy
        """
        logger.info(f"Discovering policies for {self.domain}")
        discovered = {}

        override_key = urlparse(self.base_url).netloc.lower().replace('www.', '')
        override = self.DOMAIN_OVERRIDES.get(override_key)
        if override:
            for doc_type, url in override.items():
                discovered[doc_type] = DiscoveredPolicy(
                    url=url,
                    doc_type=doc_type,
                    discovered_via=DiscoveryMethod.HEURISTIC,
                    confidence=0.99,
                )

        # Try discovery methods based on configuration
        methods = settings.discovery_methods_list

        for method in methods:
            try:
                if method == 'sitemap':
                    policies = self._discover_via_sitemap()
                elif method == 'footer':
                    policies = self._discover_via_footer()
                elif method == 'heuristic':
                    policies = self._discover_via_heuristic()
                elif method == 'link_text':
                    policies = self._discover_via_link_text()
                else:
                    continue

                # Merge discoveries (higher confidence wins)
                for doc_type, policy in policies.items():
                    if override and doc_type in override:
                        continue
                    if doc_type not in discovered or policy.confidence > discovered[doc_type].confidence:
                        discovered[doc_type] = policy

            except Exception as e:
                logger.warning(f"Error during {method} discovery: {e}")
                continue

        logger.info(f"Discovered {len(discovered)} policies for {self.domain}")
        return discovered

    def _infer_doc_type_from_url(self, url: str) -> Optional[str]:
        path = (urlparse(url).path or "").lower()

        if any(k in path for k in self.URL_KEYWORDS['privacy']):
            return 'privacy'
        if any(k in path for k in self.URL_KEYWORDS['terms']):
            return 'terms'
        if any(k in path for k in self.URL_KEYWORDS['dpa']):
            return 'dpa'
        return None

    def _fetch_head_or_get(self, url: str) -> Optional[requests.Response]:
        try:
            resp = self.session.head(url, timeout=settings.discovery_timeout, allow_redirects=True)
            if resp.status_code in (405, 403):
                resp = self.session.get(url, timeout=settings.discovery_timeout, allow_redirects=True, stream=True)
            return resp
        except Exception:
            return None

    def _is_non_policy_candidate(self, url: str) -> bool:
        lower = url.lower()
        if any(ext in lower for ext in ('.xml', '.gz')):
            return True
        if 'sitemap' in lower:
            return True
        return False

    def _score_policy_candidate(self, url: str, doc_type: str, base_confidence: float) -> float:
        parsed = urlparse(url)
        host = (parsed.netloc or '').lower()
        path = (parsed.path or '').lower()

        score = base_confidence

        # Strong positives for canonical policy locations
        if host.startswith('policies.'):
            score += 0.25
        if '/policies/' in path or path.startswith('/policies'):
            score += 0.20
        if '/legal' in path:
            score += 0.15

        # Prefer short, likely-canonical paths
        if doc_type == 'privacy' and path.rstrip('/') in ('/privacy', '/privacy-policy', '/privacy_policy'):
            score += 0.20
        if doc_type == 'terms' and path.rstrip('/') in ('/terms', '/terms-of-service', '/terms_of_service', '/tos'):
            score += 0.20
        if doc_type == 'dpa' and path.rstrip('/') in ('/dpa', '/data-processing', '/data_processing'):
            score += 0.15

        # Penalize common false positives
        if any(bad in path for bad in ('/finance/', '/quote/', '/whitepaper', '/photos/', '/sitemap')):
            score -= 0.35
        if self._is_non_policy_candidate(url):
            score -= 0.50

        return max(0.0, min(0.99, score))

    def _discover_via_sitemap(self) -> Dict[str, DiscoveredPolicy]:
        """Discover policies via sitemap.xml."""
        policies = {}

        try:
            # Try robots.txt for sitemap location
            robots_url = urljoin(self.base_url, '/robots.txt')
            resp = self.session.get(robots_url, timeout=settings.discovery_timeout)

            sitemap_urls = []
            for line in resp.text.split('\n'):
                if line.lower().startswith('sitemap:'):
                    sitemap_urls.append(line.split(':', 1)[1].strip())

            # Add common sitemap locations
            sitemap_urls.extend([
                urljoin(self.base_url, '/sitemap.xml'),
                urljoin(self.base_url, '/sitemap_index.xml'),
            ])

            # Parse sitemaps
            for sitemap_url in sitemap_urls:
                try:
                    resp = self.session.get(sitemap_url, timeout=settings.discovery_timeout)
                    if not resp.ok:
                        continue
                    soup = BeautifulSoup(resp.content, 'xml')

                    # If it's a sitemap index, follow each nested sitemap once
                    if soup.find('sitemapindex'):
                        for loc in soup.find_all('loc'):
                            child_url = loc.text.strip()
                            try:
                                child_resp = self.session.get(child_url, timeout=settings.discovery_timeout)
                                if not child_resp.ok:
                                    continue
                                child_soup = BeautifulSoup(child_resp.content, 'xml')
                                for child_loc in child_soup.find_all('loc'):
                                    url = child_loc.text.strip()
                                    if self._is_non_policy_candidate(url):
                                        continue
                                    doc_type = self._infer_doc_type_from_url(url)
                                    if doc_type:
                                        conf = self._score_policy_candidate(url, doc_type, 0.85)
                                        if doc_type not in policies or conf > policies[doc_type].confidence:
                                            policies[doc_type] = DiscoveredPolicy(
                                                url=url,
                                                doc_type=doc_type,
                                                discovered_via=DiscoveryMethod.SITEMAP,
                                                confidence=conf,
                                            )
                            except Exception as e:
                                logger.debug(f"Error parsing nested sitemap {child_url}: {e}")
                        continue

                    for loc in soup.find_all('loc'):
                        url = loc.text.strip()
                        if self._is_non_policy_candidate(url):
                            continue
                        doc_type = self._infer_doc_type_from_url(url)
                        if doc_type:
                            conf = self._score_policy_candidate(url, doc_type, 0.85)
                            if doc_type not in policies or conf > policies[doc_type].confidence:
                                policies[doc_type] = DiscoveredPolicy(
                                    url=url,
                                    doc_type=doc_type,
                                    discovered_via=DiscoveryMethod.SITEMAP,
                                    confidence=conf,
                                )

                except Exception as e:
                    logger.debug(f"Error parsing sitemap {sitemap_url}: {e}")
                    continue

        except Exception as e:
            logger.debug(f"Error during sitemap discovery: {e}")

        return policies

    def _discover_via_footer(self) -> Dict[str, DiscoveredPolicy]:
        """Discover policies via footer links."""
        policies = {}

        try:
            resp = self.session.get(self.base_url, timeout=settings.discovery_timeout)
            soup = BeautifulSoup(resp.content, 'html.parser')

            # Look for footer
            footer = soup.find('footer') or soup.find(class_=lambda x: x and 'footer' in x.lower())

            if footer:
                for link in footer.find_all('a'):
                    href = link.get('href', '')
                    text = link.get_text().lower()

                    if not href:
                        continue

                    full_url = urljoin(self.base_url, href)

                    for doc_type, keywords in self.POLICY_KEYWORDS.items():
                        if any(kw in text for kw in keywords):
                            confidence = 0.80 if 'policy' in text else 0.70
                            policies[doc_type] = DiscoveredPolicy(
                                url=full_url,
                                doc_type=doc_type,
                                discovered_via=DiscoveryMethod.FOOTER,
                                confidence=confidence,
                            )

        except Exception as e:
            logger.debug(f"Error during footer discovery: {e}")

        return policies

    def _discover_via_heuristic(self) -> Dict[str, DiscoveredPolicy]:
        """Discover policies via common path heuristics."""
        policies = {}

        for path in self.HEURISTIC_PATHS:
            url = urljoin(self.base_url, path)

            try:
                resp = self._fetch_head_or_get(url)
                if resp is None:
                    continue

                if resp.status_code == 200:
                    doc_type = self._infer_doc_type_from_url(resp.url) or self._infer_doc_type_from_url(url)
                    if not doc_type:
                        continue

                    policies[doc_type] = DiscoveredPolicy(
                        url=resp.url,  # Use redirected URL
                        doc_type=doc_type,
                        discovered_via=DiscoveryMethod.HEURISTIC,
                        confidence=0.60,
                        http_status=resp.status_code,
                        is_canonical=resp.url == url,  # Not canonical if redirected
                    )

            except Exception as e:
                logger.debug(f"Error checking heuristic path {path}: {e}")
                continue

        return policies

    def _discover_via_link_text(self) -> Dict[str, DiscoveredPolicy]:
        """Discover policies via link text matching."""
        policies = {}

        try:
            resp = self.session.get(self.base_url, timeout=settings.discovery_timeout)
            soup = BeautifulSoup(resp.content, 'html.parser')

            for link in soup.find_all('a'):
                href = link.get('href', '')
                text = link.get_text().lower().strip()

                if not href or not text:
                    continue

                full_url = urljoin(self.base_url, href)

                for doc_type, keywords in self.POLICY_KEYWORDS.items():
                    if any(kw in text for kw in keywords):
                        policies[doc_type] = DiscoveredPolicy(
                            url=full_url,
                            doc_type=doc_type,
                            discovered_via=DiscoveryMethod.LINK_TEXT,
                            confidence=0.75,
                        )

        except Exception as e:
            logger.debug(f"Error during link text discovery: {e}")

        return policies


def discover_policies(domain: str) -> Dict[str, DiscoveredPolicy]:
    """Convenience function to discover policies for a domain."""
    discovery = PolicyDiscovery(domain)
    return discovery.discover()
