"""WebSearch module for last30days skill.

NOTE: WebSearch uses Claude's built-in WebSearch tool, which runs INSIDE Claude Code.
Unlike Reddit/X which use external APIs, WebSearch results are obtained by Claude
directly and passed to this module for normalization and scoring.

The typical flow is:
1. Claude invokes WebSearch tool with the topic
2. Claude passes results to parse_websearch_results()
3. Results are normalized into WebSearchItem objects
"""

import re
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

from . import schema


# Month name mappings for date parsing
MONTH_MAP = {
    "jan": 1, "january": 1,
    "feb": 2, "february": 2,
    "mar": 3, "march": 3,
    "apr": 4, "april": 4,
    "may": 5,
    "jun": 6, "june": 6,
    "jul": 7, "july": 7,
    "aug": 8, "august": 8,
    "sep": 9, "sept": 9, "september": 9,
    "oct": 10, "october": 10,
    "nov": 11, "november": 11,
    "dec": 12, "december": 12,
}


def extract_date_from_url(url: str) -> Optional[str]:
    """Try to extract a date from URL path.

    Many sites embed dates in URLs like:
    - /2026/01/24/article-title
    - /2026-01-24/article
    - /blog/20260124/title

    Args:
        url: URL to parse

    Returns:
        Date string in YYYY-MM-DD format, or None
    """
    # Pattern 1: /YYYY/MM/DD/ (most common)
    match = re.search(r'/(\d{4})/(\d{2})/(\d{2})/', url)
    if match:
        year, month, day = match.groups()
        if 2020 <= int(year) <= 2030 and 1 <= int(month) <= 12 and 1 <= int(day) <= 31:
            return f"{year}-{month}-{day}"

    # Pattern 2: /YYYY-MM-DD/ or /YYYY-MM-DD-
    match = re.search(r'/(\d{4})-(\d{2})-(\d{2})[-/]', url)
    if match:
        year, month, day = match.groups()
        if 2020 <= int(year) <= 2030 and 1 <= int(month) <= 12 and 1 <= int(day) <= 31:
            return f"{year}-{month}-{day}"

    # Pattern 3: /YYYYMMDD/ (compact)
    match = re.search(r'/(\d{4})(\d{2})(\d{2})/', url)
    if match:
        year, month, day = match.groups()
        if 2020 <= int(year) <= 2030 and 1 <= int(month) <= 12 and 1 <= int(day) <= 31:
            return f"{year}-{month}-{day}"

    return None


def extract_date_from_snippet(text: str) -> Optional[str]:
    """Try to extract a date from text snippet or title.

    Looks for patterns like:
    - January 24, 2026 or Jan 24, 2026
    - 24 January 2026
    - 2026-01-24
    - "3 days ago", "yesterday", "last week"

    Args:
        text: Text to parse

    Returns:
        Date string in YYYY-MM-DD format, or None
    """
    if not text:
        return None

    text_lower = text.lower()

    # Pattern 1: Month DD, YYYY (e.g., "January 24, 2026")
    match = re.search(
        r'\b(jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|'
        r'jul(?:y)?|aug(?:ust)?|sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)'
        r'\s+(\d{1,2})(?:st|nd|rd|th)?,?\s*(\d{4})\b',
        text_lower
    )
    if match:
        month_str, day, year = match.groups()
        month = MONTH_MAP.get(month_str[:3])
        if month and 2020 <= int(year) <= 2030 and 1 <= int(day) <= 31:
            return f"{year}-{month:02d}-{int(day):02d}"

    # Pattern 2: DD Month YYYY (e.g., "24 January 2026")
    match = re.search(
        r'\b(\d{1,2})(?:st|nd|rd|th)?\s+'
        r'(jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|'
        r'jul(?:y)?|aug(?:ust)?|sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)'
        r'\s+(\d{4})\b',
        text_lower
    )
    if match:
        day, month_str, year = match.groups()
        month = MONTH_MAP.get(month_str[:3])
        if month and 2020 <= int(year) <= 2030 and 1 <= int(day) <= 31:
            return f"{year}-{month:02d}-{int(day):02d}"

    # Pattern 3: YYYY-MM-DD (ISO format)
    match = re.search(r'\b(\d{4})-(\d{2})-(\d{2})\b', text)
    if match:
        year, month, day = match.groups()
        if 2020 <= int(year) <= 2030 and 1 <= int(month) <= 12 and 1 <= int(day) <= 31:
            return f"{year}-{month}-{day}"

    # Pattern 4: Relative dates ("3 days ago", "yesterday", etc.)
    today = datetime.now()

    if "yesterday" in text_lower:
        date = today - timedelta(days=1)
        return date.strftime("%Y-%m-%d")

    if "today" in text_lower:
        return today.strftime("%Y-%m-%d")

    # "N days ago"
    match = re.search(r'\b(\d+)\s*days?\s*ago\b', text_lower)
    if match:
        days = int(match.group(1))
        if days <= 60:  # Reasonable range
            date = today - timedelta(days=days)
            return date.strftime("%Y-%m-%d")

    # "N hours ago" -> today
    match = re.search(r'\b(\d+)\s*hours?\s*ago\b', text_lower)
    if match:
        return today.strftime("%Y-%m-%d")

    # "last week" -> ~7 days ago
    if "last week" in text_lower:
        date = today - timedelta(days=7)
        return date.strftime("%Y-%m-%d")

    # "this week" -> ~3 days ago (middle of week)
    if "this week" in text_lower:
        date = today - timedelta(days=3)
        return date.strftime("%Y-%m-%d")

    return None


def extract_date_signals(
    url: str,
    snippet: str,
    title: str,
) -> Tuple[Optional[str], str]:
    """Extract date from any available signal.

    Tries URL first (most reliable), then snippet, then title.

    Args:
        url: Page URL
        snippet: Page snippet/description
        title: Page title

    Returns:
        Tuple of (date_string, confidence)
        - date from URL: 'high' confidence
        - date from snippet/title: 'med' confidence
        - no date found: None, 'low' confidence
    """
    # Try URL first (most reliable)
    url_date = extract_date_from_url(url)
    if url_date:
        return url_date, "high"

    # Try snippet
    snippet_date = extract_date_from_snippet(snippet)
    if snippet_date:
        return snippet_date, "med"

    # Try title
    title_date = extract_date_from_snippet(title)
    if title_date:
        return title_date, "med"

    return None, "low"


# Domains to exclude (Reddit and X are handled separately)
EXCLUDED_DOMAINS = {
    "reddit.com",
    "www.reddit.com",
    "old.reddit.com",
    "twitter.com",
    "www.twitter.com",
    "x.com",
    "www.x.com",
    "mobile.twitter.com",
}


def extract_domain(url: str) -> str:
    """Extract the domain from a URL.

    Args:
        url: Full URL

    Returns:
        Domain string (e.g., "medium.com")
    """
    try:
        parsed = urlparse(url)
        domain = parsed.netloc.lower()
        # Remove www. prefix for cleaner display
        if domain.startswith("www."):
            domain = domain[4:]
        return domain
    except Exception:
        return ""


def is_excluded_domain(url: str) -> bool:
    """Check if URL is from an excluded domain (Reddit/X).

    Args:
        url: URL to check

    Returns:
        True if URL should be excluded
    """
    try:
        parsed = urlparse(url)
        domain = parsed.netloc.lower()
        return domain in EXCLUDED_DOMAINS
    except Exception:
        return False


def _resolve_date(
    result: Dict[str, Any],
    url: str,
    snippet: str,
    title: str,
) -> Tuple[Optional[str], str]:
    """Resolve the best date and confidence for a single result.

    Args:
        result: Raw result dict (may contain a pre-supplied date)
        url: Page URL
        snippet: Page snippet/description
        title: Page title

    Returns:
        Tuple of (date_string_or_None, confidence)
    """
    date = result.get("date")
    date_confidence = "low"

    if date and re.match(r'^\d{4}-\d{2}-\d{2}$', str(date)):
        # Provided date is valid
        date_confidence = "med"
    else:
        # Try to extract date from URL/snippet/title
        extracted_date, confidence = extract_date_signals(url, snippet, title)
        if extracted_date:
            date = extracted_date
            date_confidence = confidence

    return date, date_confidence


def _is_within_date_range(
    date: Optional[str],
    from_date: str,
    to_date: str,
) -> bool:
    """Check whether a date passes the hard date filters.

    Args:
        date: Date string (YYYY-MM-DD) or None
        from_date: Start date (YYYY-MM-DD)
        to_date: End date (YYYY-MM-DD)

    Returns:
        True if the item should be kept, False if it should be dropped
    """
    # Hard filter: if we found a date and it's too old, skip
    if date and from_date and date < from_date:
        return False  # DROP - verified old content

    # Hard filter: if date is in the future, skip (parsing error)
    if date and to_date and date > to_date:
        return False  # DROP - future date

    return True


def _build_item(
    index: int,
    title: str,
    url: str,
    snippet: str,
    date: Optional[str],
    date_confidence: str,
    relevance: float,
    why_relevant: str,
) -> Dict[str, Any]:
    """Build a normalized item dict from extracted fields.

    Args:
        index: Zero-based index of the result
        title: Page title
        url: Page URL
        snippet: Page snippet
        date: Resolved date string or None
        date_confidence: Confidence level for the date
        relevance: Relevance score (0.0–1.0)
        why_relevant: Explanation of relevance

    Returns:
        Normalized item dict
    """
    return {
        "id": f"W{index+1}",
        "title": title[:200],  # Truncate long titles
        "url": url,
        "source_domain": extract_domain(url),
        "snippet": snippet[:500],  # Truncate long snippets
        "date": date,
        "date_confidence": date_confidence,
        "relevance": relevance,
        "why_relevant": why_relevant,
    }


def _parse_single_result(
    result: Dict[str, Any],
    index: int,
    from_date: str,
    to_date: str,
) -> Optional[Dict[str, Any]]:
    """Parse a single WebSearch result into a normalized item dict.

    Args:
        result: Raw result dict
        index: Zero-based index (used for ID generation)
        from_date: Start date for filtering (YYYY-MM-DD)
        to_date: End date for filtering (YYYY-MM-DD)

    Returns:
        Normalized item dict, or None if the result should be skipped
    """
    url = result.get("url", "")
    if not url:
        return None

    # Skip Reddit/X URLs (handled separately)
    if is_excluded_domain(url):
        return None

    title = str(result.get("title", "")).strip()
    snippet = str(result.get("snippet", result.get("description", ""))).strip()

    if not title and not snippet:
        return None

    # Resolve date and confidence
    date, date_confidence = _resolve_date(result, url, snippet, title)

    # Apply hard date filters
    if not _is_within_date_range(date, from_date, to_date):
        return None

    # Get relevance if provided, default to 0.5
    relevance = result.get("relevance", 0.5)
    try:
        relevance = min(1.0, max(0.0, float(relevance)))
    except (TypeError, ValueError):
        relevance = 0.5

    why_relevant = str(result.get("why_relevant", "")).strip()

    return _build_item(
        index, title, url, snippet, date, date_confidence, relevance, why_relevant
    )


def parse_websearch_results(
    results: List[Dict[str, Any]],
    topic: str,
    from_date: str = "",
    to_date: str = "",
) -> List[Dict[str, Any]]:
    """Parse WebSearch results into normalized format.

    This function expects results from Claude's WebSearch tool.
    Each result should have: title, url, snippet, and optionally date/relevance.

    Uses "Date Detective" approach:
    1. Extract dates from URLs (high confidence)
    2. Extract dates from snippets/titles (med confidence)
    3. Hard filter: exclude items with verified old dates
    4. Keep items with no date signals (with low confidence penalty)

    Args:
        results: List of WebSearch result dicts
        topic: Original search topic (for context)
        from_date: Start date for filtering (YYYY-MM-DD)
        to_date: End date for filtering (YYYY-MM-DD)

    Returns:
        List of normalized item dicts ready for WebSearchItem creation
    """
    items = []

    for i, result in enumerate(results):
        if not isinstance(result, dict):
            continue
        item = _parse_single_result(result, i, from_date, to_date)
        if item is not None:
            items.append(item)

    return items


def normalize_websearch_items(
    items: List[Dict[str, Any]],
    from_date: str,