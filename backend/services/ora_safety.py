"""
services/ora_safety.py — iter 331a Sprint 3.7

Two safety layers ORA's tool layer goes through:

  1. Path-traversal guard — every tool that reads or writes a path
     calls `assert_path_safe(path)`. Anything that resolves outside
     ORA_TOOLS_ROOT (default `/app`) is rejected with a plain English
     error + Telegram alert.

  2. Secrets scrubber — every tool that returns string content runs
     it through `scrub_secrets(text)` before the LLM sees it. Stripe
     keys, Mongo URIs, JWTs, bearer tokens, passwords and any
     high-entropy 32+ char alphanumeric strings are replaced with
     typed placeholders like `[REDACTED_STRIPE_KEY]`.

Portability: zero Emergent imports. ORA_TOOLS_ROOT is env-overridable
so the same module ships unchanged to Hetzner/Docker/local-dev.
"""
from __future__ import annotations

import asyncio
import logging
import os
import re
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# ── Configuration ───────────────────────────────────────────────────
_ROOT       = Path(os.environ.get("ORA_TOOLS_ROOT", "/app")).resolve()
_LOG_DIR    = Path(os.environ.get("ORA_LOG_DIR", "/var/log/supervisor")).resolve()
_TMP_OK     = Path("/tmp").resolve()    # /tmp is a legitimate sandbox area

# Read-only paths ORA may *view* but not write.
_READ_ONLY_WHITELIST = (_LOG_DIR,)

# Always-forbidden paths (read or write).
_FORBIDDEN_PREFIXES = (
    Path("/sys").resolve(),
    Path("/proc").resolve(),
    Path("/root").resolve(),
    Path("/dev").resolve(),
)


class PathOutsideRoot(Exception):
    """Raised when a path resolves outside the allowed roots."""


def _is_under(child: Path, parent: Path) -> bool:
    try:
        child.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def assert_path_safe(path: str | Path, mode: str = "read") -> Path:
    """Validate `path` is within ORA's allowed sandbox.

    Args:
      path: candidate path (str or Path)
      mode: "read" or "write"

    Raises:
      PathOutsideRoot — when the resolved absolute path escapes the
      allowed roots. Telegrams the founder so we know if ORA tried
      to escape.

    Returns:
      The resolved Path on success.
    """
    raw = str(path or "").strip()
    if not raw:
        raise PathOutsideRoot("empty path")
    # Block obvious traversal tokens early — even if they would resolve safely.
    if ".." in raw.split("/"):
        # Allow ".." as long as the resolved result stays in root, but
        # still log + audit so we have a trail.
        logger.info(f"[ora-safety] traversal token in path: {raw}")
    p = Path(raw)
    if not p.is_absolute():
        p = (_ROOT / p).resolve()
    else:
        p = p.resolve()

    # Forbidden prefixes — never allowed.
    for forbid in _FORBIDDEN_PREFIXES:
        if _is_under(p, forbid):
            _alert_sync("Path traversal blocked",
                         f"mode={mode} path={raw} → {p} (under {forbid})")
            raise PathOutsideRoot(
                f"Blocked: '{raw}' resolves under {forbid} — never allowed."
            )

    # Read mode: allowed in _ROOT, _LOG_DIR, _TMP_OK.
    # Write mode: allowed in _ROOT and _TMP_OK only (logs are append-only OS).
    if mode == "read":
        allowed = (_ROOT, _LOG_DIR, _TMP_OK)
    else:
        allowed = (_ROOT, _TMP_OK)
    if not any(_is_under(p, root) for root in allowed):
        _alert_sync("Path outside sandbox",
                     f"mode={mode} path={raw} → {p}")
        raise PathOutsideRoot(
            f"Blocked: path '{raw}' is outside ORA's sandbox "
            f"({', '.join(str(a) for a in allowed)}). Use ORA_TOOLS_ROOT to extend."
        )
    return p


def _alert_sync(title: str, body: str) -> None:
    """Best-effort sync Telegram alert. Never raises."""
    try:
        from services.telegram_bot_service import send_telegram_alert
        coro = send_telegram_alert(f"🛡️ ORA Safety — {title}\n\n{body}")
        if asyncio.iscoroutine(coro):
            # Fire-and-forget — schedule on existing loop if any.
            try:
                loop = asyncio.get_event_loop()
                loop.create_task(coro)
            except RuntimeError:
                pass
    except Exception as e:
        logger.debug(f"[ora-safety] alert skipped: {e}")


# ────────────────────────────────────────────────────────────────────
# Secrets scrubber
# ────────────────────────────────────────────────────────────────────

# Order matters: more-specific patterns first, generic last.
_SECRET_PATTERNS: list[tuple[re.Pattern, str]] = [
    # Stripe
    (re.compile(r"\bsk_live_[a-zA-Z0-9_-]{16,}\b"),       "[REDACTED_STRIPE_KEY]"),
    (re.compile(r"\bsk_test_[a-zA-Z0-9_-]{16,}\b"),       "[REDACTED_STRIPE_TEST]"),
    (re.compile(r"\bpk_live_[a-zA-Z0-9_-]{16,}\b"),       "[REDACTED_STRIPE_PUB]"),
    (re.compile(r"\bwhsec_[a-zA-Z0-9_-]{16,}\b"),         "[REDACTED_STRIPE_WHSEC]"),
    # MongoDB connection strings
    (re.compile(r"mongodb\+srv://[^\s'\"<>]+",  re.IGNORECASE),
                                                          "[REDACTED_MONGO_URL]"),
    (re.compile(r"mongodb://[^\s'\"<>]+",       re.IGNORECASE),
                                                          "[REDACTED_MONGO_URL]"),
    # Emergent LLM key value (only the value, not the env-var name)
    (re.compile(r"EMERGENT_LLM_KEY\s*=\s*\S+"),           "EMERGENT_LLM_KEY=[REDACTED_KEY]"),
    # Bearer / JWT
    (re.compile(r"\bBearer\s+[a-zA-Z0-9_\-\.~+/]{20,}={0,2}"),
                                                          "Bearer [REDACTED_TOKEN]"),
    (re.compile(r"\beyJ[a-zA-Z0-9_\-]{20,}\.[a-zA-Z0-9_\-]{10,}\.[a-zA-Z0-9_\-]{5,}\b"),
                                                          "[REDACTED_JWT]"),
    # Generic password / secret = value
    (re.compile(r"(['\"]?password['\"]?\s*[:=]\s*['\"]?)([^\s'\",;]{4,})",
                re.IGNORECASE),
                                                          r"\1[REDACTED_PASSWORD]"),
    (re.compile(r"(['\"]?secret['\"]?\s*[:=]\s*['\"]?)([^\s'\",;]{6,})",
                re.IGNORECASE),
                                                          r"\1[REDACTED_SECRET]"),
    (re.compile(r"(['\"]?api[_-]?key['\"]?\s*[:=]\s*['\"]?)([^\s'\",;]{8,})",
                re.IGNORECASE),
                                                          r"\1[REDACTED_API_KEY]"),
    # Twilio (AC + 32 hex)
    (re.compile(r"\bAC[0-9a-fA-F]{32}\b"),                "[REDACTED_TWILIO_SID]"),
    # Generic high-entropy 32+ char alphanumeric (catch-all, last)
    # We require 40+ to avoid wrecking commit hashes (40 hex) — but
    # we exclude pure-hex (likely commit hash / sha) by allowing only
    # mixed case+digits.
    (re.compile(r"\b(?=.*[A-Z])(?=.*[a-z])(?=.*[0-9])[A-Za-z0-9_\-]{40,}\b"),
                                                          "[REDACTED_HIGH_ENTROPY]"),
]


def scrub_secrets(content: str | bytes | None) -> tuple[str, int]:
    """Replace any secret-shaped token with a typed placeholder.

    Returns:
      (scrubbed_text, count_of_redactions)
    """
    if content is None:
        return "", 0
    if isinstance(content, bytes):
        try:
            text = content.decode("utf-8", errors="replace")
        except Exception:
            return "[REDACTED_BINARY]", 1
    else:
        text = str(content)
    n_redacted = 0
    for pat, repl in _SECRET_PATTERNS:
        new_text, count = pat.subn(repl, text)
        if count:
            n_redacted += count
            text = new_text
    return text, n_redacted


def scrub_dict(payload: dict, fields: list[str] | None = None) -> tuple[dict, int]:
    """Scrub specified string-valued fields of a dict (or all if fields=None).

    Recurses into nested dicts/lists. Returns (scrubbed_dict, total_redactions).
    """
    total = 0
    fields_set = set(fields) if fields is not None else None

    def _walk(obj: Any) -> Any:
        nonlocal total
        if isinstance(obj, str):
            scrubbed, n = scrub_secrets(obj)
            total += n
            return scrubbed
        if isinstance(obj, dict):
            out = {}
            for k, v in obj.items():
                if fields_set is None or k in fields_set:
                    out[k] = _walk(v)
                else:
                    out[k] = v
            return out
        if isinstance(obj, list):
            return [_walk(x) for x in obj]
        return obj

    return _walk(payload), total


__all__ = [
    "assert_path_safe", "PathOutsideRoot",
    "scrub_secrets", "scrub_dict",
]
