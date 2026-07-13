"""HTTP utilities for last30days skill (stdlib only)."""

import json
import os
import sys
import time
import urllib.error
import urllib.request
from typing import Any, Dict, Optional
from urllib.parse import urlencode

DEFAULT_TIMEOUT = 30
DEBUG = os.environ.get("LAST30DAYS_DEBUG", "").lower() in ("1", "true", "yes")


def log(msg: str):
    """Log debug message to stderr."""
    if DEBUG:
        sys.stderr.write(f"[DEBUG] {msg}\n")
        sys.stderr.flush()
MAX_RETRIES = 3
RETRY_DELAY = 1.0
USER_AGENT = "last30days-skill/1.0 (Claude Code Skill)"


class HTTPError(Exception):
    """HTTP request error with status code."""
    def __init__(self, message: str, status_code: Optional[int] = None, body: Optional[str] = None):
        super().__init__(message)
        self.status_code = status_code
        self.body = body


def _build_request(
    method: str,
    url: str,
    headers: Optional[Dict[str, str]],
    json_data: Optional[Dict[str, Any]],
) -> urllib.request.Request:
    """Build a urllib Request object from parameters."""
    headers = headers or {}
    headers.setdefault("User-Agent", USER_AGENT)

    data = None
    if json_data is not None:
        data = json.dumps(json_data).encode('utf-8')
        headers.setdefault("Content-Type", "application/json")

    req = urllib.request.Request(url, data=data, headers=headers, method=method)

    log(f"{method} {url}")
    if json_data:
        log(f"Payload keys: {list(json_data.keys())}")

    return req


def _read_http_error_body(e: urllib.error.HTTPError) -> Optional[str]:
    """Read the body from an HTTPError, returning None on failure."""
    try:
        return e.read().decode('utf-8')
    except:
        return None


def _attempt_request(
    req: urllib.request.Request,
    timeout: int,
) -> Dict[str, Any]:
    """Execute a single request attempt, returning parsed JSON or raising."""
    with urllib.request.urlopen(req, timeout=timeout) as response:
        body = response.read().decode('utf-8')
        log(f"Response: {response.status} ({len(body)} bytes)")
        return json.loads(body) if body else {}


def _handle_http_error(
    e: urllib.error.HTTPError,
    attempt: int,
    retries: int,
) -> HTTPError:
    """Handle an HTTPError, raising immediately for non-retryable errors."""
    body = _read_http_error_body(e)
    log(f"HTTP Error {e.code}: {e.reason}")
    if body:
        log(f"Error body: {body[:500]}")
    error = HTTPError(f"HTTP {e.code}: {e.reason}", e.code, body)

    # Don't retry client errors (4xx) except rate limits
    if 400 <= e.code < 500 and e.code != 429:
        raise error

    if attempt < retries - 1:
        time.sleep(RETRY_DELAY * (attempt + 1))

    return error


def _handle_retryable_error(
    e: Exception,
    attempt: int,
    retries: int,
) -> HTTPError:
    """Handle a retryable error (URLError, OSError, etc.)."""
    log(f"{type(e).__name__}: {e}")
    error = HTTPError(f"{type(e).__name__}: {e}")
    if attempt < retries - 1:
        time.sleep(RETRY_DELAY * (attempt + 1))
    return error


def request(
    method: str,
    url: str,
    headers: Optional[Dict[str, str]] = None,
    json_data: Optional[Dict[str, Any]] = None,
    timeout: int = DEFAULT_TIMEOUT,
    retries: int = MAX_RETRIES,
) -> Dict[str, Any]:
    """Make an HTTP request and return JSON response.

    Args:
        method: HTTP method (GET, POST, etc.)
        url: Request URL
        headers: Optional headers dict
        json_data: Optional JSON body (for POST)
        timeout: Request timeout in seconds
        retries: Number of retries on failure

    Returns:
        Parsed JSON response

    Raises:
        HTTPError: On request failure
    """
    req = _build_request(method, url, headers, json_data)

    last_error = None
    for attempt in range(retries):
        try:
            return _attempt_request(req, timeout)
        except urllib.error.HTTPError as e:
            last_error = _handle_http_error(e, attempt, retries)
        except urllib.error.URLError as e:
            last_error = _handle_retryable_error(e, attempt, retries)
        except json.JSONDecodeError as e:
            log(f"JSON decode error: {e}")
            last_error = HTTPError(f"Invalid JSON response: {e}")
            raise last_error
        except (OSError, TimeoutError, ConnectionResetError) as e:
            last_error = _handle_retryable_error(e, attempt, retries)

    if last_error:
        raise last_error
    raise HTTPError("Request failed with no error details")


def get(url: str, headers: Optional[Dict[str, str]] = None, **kwargs) -> Dict[str, Any]:
    """Make a GET request."""
    return request("GET", url, headers=headers, **kwargs)


def post(url: str, json_data: Dict[str, Any], headers: Optional[Dict[str, str]] = None, **kwargs) -> Dict[str, Any]:
    """Make a POST request with JSON body."""
    return request("POST", url, headers=headers, json_data=json_data, **kwargs)


def get_reddit_json(path: str) -> Dict[str, Any]:
    """Fetch Reddit thread JSON.

    Args:
        path: Reddit path (e.g., /r/subreddit/comments/id/title)

    Returns:
        Parsed JSON response
    """
    # Ensure path starts with /
    if not path.startswith('/'):
        path = '/' + path

    # Remove trailing slash and add .json
    path = path.rstrip('/')
    if not path.endswith('.json'):
        path = path + '.json'

    url = f"https://www.reddit.com{path}?raw_json=1"

    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "application/json",
    }

    return get(url, headers=headers)