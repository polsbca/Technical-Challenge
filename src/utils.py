"""
Utility functions and helpers for the application.
"""

import json
import logging
import logging.handlers
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional
from functools import wraps
import time

from src.config import settings, LOGS_DIR


# ============================================================================
# Logging Setup
# ============================================================================

def setup_logging(name: str = __name__) -> logging.Logger:
    """
    Configure and return a logger instance.
    
    Args:
        name: Logger name (typically __name__)
    
    Returns:
        logging.Logger: Configured logger
    """
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, settings.log_level))

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(getattr(logging, settings.log_level))
    console_format = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    console_handler.setFormatter(console_format)

    # File handler
    LOGS_DIR.mkdir(exist_ok=True)
    log_file = LOGS_DIR / f"pipeline_{datetime.now().strftime('%Y%m%d')}.log"
    file_handler = logging.handlers.RotatingFileHandler(
        log_file,
        maxBytes=10 * 1024 * 1024,  # 10 MB
        backupCount=5,
    )
    file_handler.setLevel(getattr(logging, settings.log_level))
    file_format = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    file_handler.setFormatter(file_format)

    # Add handlers
    logger.addHandler(console_handler)
    logger.addHandler(file_handler)

    return logger


logger = setup_logging(__name__)


# ============================================================================
# Decorators
# ============================================================================

def retry(max_attempts: int = 3, delay: float = 1.0, backoff: float = 2.0):
    """
    Retry decorator with exponential backoff.
    
    Args:
        max_attempts: Maximum number of attempts
        delay: Initial delay in seconds
        backoff: Backoff multiplier
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            attempt = 0
            current_delay = delay
            
            while attempt < max_attempts:
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    attempt += 1
                    if attempt >= max_attempts:
                        logger.error(f"Failed after {max_attempts} attempts: {str(e)}")
                        raise
                    
                    logger.warning(
                        f"Attempt {attempt}/{max_attempts} failed for {func.__name__}, "
                        f"retrying in {current_delay}s: {str(e)}"
                    )
                    time.sleep(current_delay)
                    current_delay *= backoff
        
        return wrapper
    return decorator


def timeit(func):
    """Decorator to measure function execution time."""
    @wraps(func)
    def wrapper(*args, **kwargs):
        start = time.time()
        result = func(*args, **kwargs)
        elapsed = time.time() - start
        logger.info(f"{func.__name__} took {elapsed:.2f}s")
        return result
    return wrapper


# ============================================================================
# JSON and Data Utilities
# ============================================================================

def save_json(data: Any, filepath: Path, indent: int = 2) -> None:
    """
    Save data to JSON file.
    
    Args:
        data: Data to save
        filepath: Path to output file
        indent: JSON indentation level
    """
    filepath.parent.mkdir(parents=True, exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=indent, ensure_ascii=False)
    logger.info(f"Saved JSON to {filepath}")


def load_json(filepath: Path) -> Any:
    """
    Load data from JSON file.
    
    Args:
        filepath: Path to JSON file
    
    Returns:
        Loaded JSON data
    """
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)


def merge_dicts(*dicts: Dict) -> Dict:
    """
    Merge multiple dictionaries (later keys override earlier ones).
    
    Args:
        *dicts: Variable number of dictionaries
    
    Returns:
        Merged dictionary
    """
    result = {}
    for d in dicts:
        result.update(d)
    return result


# ============================================================================
# String Utilities
# ============================================================================

def sanitize_filename(filename: str) -> str:
    """
    Remove/replace invalid filename characters.
    
    Args:
        filename: Original filename
    
    Returns:
        Sanitized filename
    """
    import re
    return re.sub(r"[^\w\s.-]", "", filename).strip()


def extract_domain_from_url(url: str) -> Optional[str]:
    """
    Extract domain from URL.
    
    Args:
        url: Full URL
    
    Returns:
        Domain name or None
    """
    try:
        from urllib.parse import urlparse
        parsed = urlparse(url)
        domain = parsed.netloc.replace("www.", "")
        return domain
    except Exception as e:
        logger.error(f"Failed to extract domain from {url}: {str(e)}")
        return None


def normalize_url(url: str) -> str:
    """
    Normalize URL (ensure https://, remove trailing slash, etc.).
    
    Args:
        url: Original URL
    
    Returns:
        Normalized URL
    """
    if not url.startswith(("http://", "https://")):
        url = f"https://{url}"
    url = url.rstrip("/")
    return url


# ============================================================================
# Validation Utilities
# ============================================================================

def is_valid_email(email: str) -> bool:
    """
    Validate email address.
    
    Args:
        email: Email to validate
    
    Returns:
        True if valid email format
    """
    import re
    pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    return re.match(pattern, email) is not None


def is_valid_url(url: str) -> bool:
    """
    Validate URL format.
    
    Args:
        url: URL to validate
    
    Returns:
        True if valid URL format
    """
    import re
    pattern = r"^https?://[^\s/$.?#].[^\s]*$"
    return re.match(pattern, url) is not None


def is_valid_country_code(code: str) -> bool:
    """
    Validate ISO 3166-1 alpha-2 country code.
    
    Args:
        code: Country code to validate
    
    Returns:
        True if valid country code
    """
    valid_codes = {
        "US", "GB", "CA", "AU", "DE", "FR", "IT", "ES", "NL", "BE",
        "CH", "AT", "SE", "NO", "DK", "FI", "PL", "CZ", "RU", "JP",
        "CN", "IN", "BR", "MX", "ZA", "NZ", "SG", "HK", "KR", "TH",
        # Add more as needed
    }
    return code.upper() in valid_codes


# ============================================================================
# Progress and Reporting
# ============================================================================

class ProgressTracker:
    """Track progress of batch operations."""
    
    def __init__(self, total: int, name: str = "Processing"):
        self.total = total
        self.name = name
        self.current = 0
        self.start_time = datetime.now()
    
    def update(self, increment: int = 1):
        """Update progress."""
        self.current += increment
        elapsed = (datetime.now() - self.start_time).total_seconds()
        rate = self.current / elapsed if elapsed > 0 else 0
        remaining = (self.total - self.current) / rate if rate > 0 else 0
        
        percentage = (self.current / self.total) * 100
        logger.info(
            f"{self.name}: {self.current}/{self.total} ({percentage:.1f}%) - "
            f"Rate: {rate:.1f} items/s - ETA: {remaining:.0f}s"
        )
    
    def finish(self):
        """Mark as finished."""
        elapsed = (datetime.now() - self.start_time).total_seconds()
        logger.info(f"{self.name} completed in {elapsed:.1f}s")


# ============================================================================
# Confidence Score Aggregation
# ============================================================================

def aggregate_confidence_scores(scores: list[float], method: str = "mean") -> float:
    """
    Aggregate multiple confidence scores.
    
    Args:
        scores: List of confidence scores (0-1)
        method: Aggregation method ('mean', 'max', 'min', 'weighted_mean')
    
    Returns:
        Aggregated confidence score
    """
    if not scores:
        return 0.0
    
    if method == "mean":
        return sum(scores) / len(scores)
    elif method == "max":
        return max(scores)
    elif method == "min":
        return min(scores)
    elif method == "weighted_mean":
        # Higher scores weighted more heavily
        weights = [s ** 2 for s in scores]
        total_weight = sum(weights)
        return sum(s * w for s, w in zip(scores, weights)) / total_weight if total_weight > 0 else 0.0
    else:
        raise ValueError(f"Unknown aggregation method: {method}")
