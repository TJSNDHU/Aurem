import re
from urllib.parse import urlparse
from typing import Optional


def validate_url(url: str) -> Optional[str]:
    """Validate URL with security-sensitive checks."""
    try:
        result = urlparse(url)
        if not all([result.scheme, result.netloc]):
            return None

        # Scheme restriction
        if result.scheme not in ('http', 'https'):
            return None

        # Port validation
        if result.port and not (1 <= result.port <= 65535):
            return None

        # Path validation
        if result.path and not re.match(r'^/[a-zA-Z0-9-._~%!$&\'()*+,;=:@/]*$', result.path):
            return None

        return url.strip()
    except ValueError:
        return None


def log_invalid_url(url: str) -> None:
    """Log invalid URL attempts for security auditing."""
    pass


def normalize_url(url: str) -> Optional[str]:
    """Normalize URL for consistent storage."""
    normalized = validate_url(url)
    if not normalized:
        log_invalid_url(url)
    return normalized

FILE: backend/services/autonomous_repair_engine.py
