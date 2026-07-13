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
    """Build a urllib Request object with standard headers."""
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
    """Attempt to read the response body from an HTTPError."""
    try:
        return e.read().decode('utf-8')
    except:
        return None


def _handle_http_error(e: urllib.error.HTTPError) -> HTTPError:
    """Convert an HTTPError into an HTTPError exception, logging details."""
    body = _read_http_error_body(e)
    log(f"HTTP Error {e.code}: {e.reason}")
    if body:
        log(f"Error body: {body[:500]}")
    return HTTPError(f"HTTP {e.code}: {e.reason}", e.code, body)


def _should_retry_http(status_code: int) -> bool:
    """Return True if the HTTP status code warrants a retry."""
    if 400 <= status_code < 500 and status_code != 429:
        return False
    return True


def _execute_attempt(
    req: urllib.request.Request,
    timeout: int,
) -> Dict[str, Any]:
    """Execute a single request attempt and return parsed JSON.

    Raises HTTPError, URLError, or other exceptions on failure.
    """
    with urllib.request.urlopen(req, timeout=timeout) as response:
        body = response.read().decode('utf-8')
        log(f"Response: {response.status} ({len(body)} bytes)")
        return json.loads(body) if body else {}


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
            return _execute_attempt(req, timeout)
        except urllib.error.HTTPError as e:
            last_error = _handle_http_error(e)
            if not _should_retry_http(e.code):
                raise last_error
            if attempt < retries - 1:
                time.sleep(RETRY_DELAY * (attempt + 1))
        except urllib.error.URLError as e:
            log(f"URL Error: {e.reason}")
            last_error = HTTPError(f"URL Error: {e.reason}")
            if attempt < retries - 1:
                time.sleep(RETRY_DELAY * (attempt + 1))
        except json.JSONDecodeError as e:
            log(f"JSON decode error: {e}")
            last_error = HTTPError(f"Invalid JSON response: {e}")
            raise last_error
        except (OSError, TimeoutError, ConnectionResetError) as e:
            # Handle socket-level errors (connection reset, timeout, etc.)
            log(f"Connection error: {type(e).__name__}: {e}")
            last_error = HTTPError(f"Connection error: {type(e).__name__}: {e}")
            if attempt < retries - 1:
                time.sleep(RETRY_DELAY * (attempt + 1))

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