"""
github_lockdown.py — iter 327d

Hard read-only lock on every GitHub WRITE operation ORA might
attempt. Founder directive (verbatim):

    "Lock these permanently until I explicitly unlock:
       - git push (any branch)
       - git commit (over the wire — local-only is OK)
       - PR creation
       - branch creation or deletion
       - any write operation to GitHub
     If ORA tries to push/commit/write:
       - hard block — do not execute
       - show: 'Push access is locked. Founder approval required to enable.'
       - send Telegram alert that push was attempted"

Design:
  * Single source of truth is `is_github_locked()` — reads the
    `ora_governance` Mongo collection (key="github_lock_state"). Default
    is True (locked) — fail-safe.
  * Public `assert_github_writes_allowed(operation)` raises
    `GitHubLockedError` when the lock is engaged.  Callers catch it
    and surface a friendly message to ORA + the founder.
  * Every block fires a Telegram alert via the iter-326pp plumbing
    (5-min dedup so a flapping ORA doesn't spam the founder).
  * Founder unlock flow: POST /api/admin/ora/github-unlock with an
    admin JWT — sets locked=False with audit row. (Not wired in this
    iter — only the lock direction matters for safety.)

This module is intentionally TINY. The point is to be the single
trusted gate every write path checks.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)

_db = None
_DEFAULT_LOCKED = True       # fail-safe: if the doc is missing, we treat
                              # everything as locked.

# Operations the founder explicitly locked. Tools and callers should
# pass one of these slugs to `assert_github_writes_allowed`.
LOCKED_OPERATIONS = {
    "git_push":            "push to any branch",
    "git_remote_commit":   "commit and push to GitHub",
    "git_branch_create":   "create a remote branch",
    "git_branch_delete":   "delete a remote branch",
    "pr_create":           "open a pull request",
    "pr_merge":            "merge a pull request",
    "pr_close":            "close a pull request",
    "github_api_write":    "any write to the GitHub API",
}


class GitHubLockedError(Exception):
    """Raised when ORA tries to perform a locked GitHub write op."""

    def __init__(self, operation: str, friendly: str):
        self.operation = operation
        self.friendly = friendly
        super().__init__(friendly)


def set_db(database):
    global _db
    _db = database


# ───────────────────────────────────────────────────────────────────
# Lock state
# ───────────────────────────────────────────────────────────────────

async def is_github_locked() -> bool:
    """Return True iff GitHub writes are currently locked.
    Reads from `ora_governance.github_lock_state` — default True
    when the row is missing (fail-safe).

    iter 327f — 15-minute auto-relock TTL. If the row says
    `locked=False` but `unlock_expires_at` is in the past, lazily flip
    the row back to locked (and write an audit entry) before
    returning. This guarantees the founder's "one-click 15 minute
    unlock" never leaves writes open forever.
    """
    if _db is None:
        return _DEFAULT_LOCKED
    try:
        row = await _db.ora_governance.find_one(
            {"_id": "github_lock_state"},
            {"_id": 0, "locked": 1, "unlock_expires_at": 1, "unlocked_by": 1},
        )
    except Exception as e:
        logger.warning(f"[github-lock] read failed: {e} — defaulting to locked")
        return _DEFAULT_LOCKED
    if not row:
        return _DEFAULT_LOCKED
    locked = bool(row.get("locked", _DEFAULT_LOCKED))
    if locked:
        return True
    # Unlocked — check TTL.
    expires_at_iso = row.get("unlock_expires_at")
    if expires_at_iso:
        try:
            expires_at = datetime.fromisoformat(expires_at_iso)
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=timezone.utc)
        except Exception:
            expires_at = None
        if expires_at and datetime.now(timezone.utc) >= expires_at:
            await _auto_relock_expired(row.get("unlocked_by") or "unknown",
                                        expires_at_iso)
            return True
    return False


async def _auto_relock_expired(prev_unlocker: str, expired_at_iso: str) -> None:
    """Idempotent helper — flips the row back to locked and writes an
    audit entry. Safe to call concurrently (last writer wins; the
    audit row may dedupe on a 5s grain via mongo TTL if desired)."""
    if _db is None:
        return
    try:
        await _db.ora_governance.update_one(
            {"_id": "github_lock_state", "locked": False},
            {"$set": {
                "locked":            True,
                "auto_relocked_at":  datetime.now(timezone.utc).isoformat(),
                "auto_relock_reason": "ttl_expired",
            },
             "$unset": {"unlock_expires_at": ""}},
        )
        await _db.ora_governance_audit.insert_one({
            "action":           "github_auto_relock_ttl",
            "previous_unlocker": prev_unlocker,
            "expired_at":        expired_at_iso,
            "ts":                datetime.now(timezone.utc).isoformat(),
        })
        logger.warning(
            f"[github-lock] auto-relocked after TTL (prev unlocker={prev_unlocker!r})"
        )
    except Exception as e:
        logger.debug(f"[github-lock] auto-relock failed: {e}")


async def get_lock_status() -> dict:
    """For UI / status endpoints. Always returns the safe defaults
    even on Mongo failure."""
    locked = await is_github_locked()
    # iter 327f — surface the 15-min unlock TTL for the UI countdown.
    expires_at_iso = None
    seconds_until_relock = None
    if not locked and _db is not None:
        try:
            row = await _db.ora_governance.find_one(
                {"_id": "github_lock_state"},
                {"_id": 0, "unlock_expires_at": 1, "unlocked_by": 1},
            ) or {}
            expires_at_iso = row.get("unlock_expires_at")
            if expires_at_iso:
                try:
                    exp = datetime.fromisoformat(expires_at_iso)
                    if exp.tzinfo is None:
                        exp = exp.replace(tzinfo=timezone.utc)
                    delta = (exp - datetime.now(timezone.utc)).total_seconds()
                    seconds_until_relock = max(0, int(delta))
                except Exception:
                    pass
        except Exception:
            pass
    return {
        "locked":              locked,
        "mode":                "read_only" if locked else "write_unlocked",
        "locked_operations":   sorted(LOCKED_OPERATIONS),
        "ui_label":            "Read Only" if locked else "Write Enabled",
        "icon":                "lock" if locked else "unlock",
        "unlock_expires_at":   None if locked else expires_at_iso,
        "seconds_until_relock": None if locked else seconds_until_relock,
    }


# ───────────────────────────────────────────────────────────────────
# Guards
# ───────────────────────────────────────────────────────────────────

async def assert_github_writes_allowed(operation: str) -> None:
    """Raise `GitHubLockedError` if `operation` is locked. Operation
    must be one of LOCKED_OPERATIONS; unknown slugs raise too
    (fail-closed).  Side-effects: fires Telegram alert on block."""
    locked = await is_github_locked()
    if not locked:
        return
    detail = LOCKED_OPERATIONS.get(operation, operation)
    friendly = (
        f"Push access is locked. Founder approval required to enable "
        f"({operation}: {detail})."
    )
    _fire_block_alert(operation, detail)
    raise GitHubLockedError(operation, friendly)


def _fire_block_alert(operation: str, detail: str) -> None:
    """Telegram alert via the iter-326pp silent_failure plumbing.
    Best-effort — never raises."""
    try:
        from services.silent_failure_alerts import _fire, _send
        body = (
            f"ORA tried a *locked GitHub write* — blocked.\n\n"
            f"Operation: {operation}\n"
            f"Detail: {detail}\n"
            f"When: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}\n\n"
            f"This is a HARD lock — write access stays disabled until the "
            f"founder explicitly unlocks via the admin endpoint."
        )
        _fire(_send(body,
                     alert_type="github_write_blocked",
                     fingerprint=f"gh_lock:{operation}"))
    except Exception as e:
        logger.debug(f"[github-lock] alert dispatch failed: {e}")


# ───────────────────────────────────────────────────────────────────
# Audit (for the founder's review later)
# ───────────────────────────────────────────────────────────────────

async def log_block_attempt(operation: str, actor: str = "ora",
                              context: str = "") -> None:
    """Persist the block attempt to `ora_github_block_log` for audit.
    Best-effort — never raises."""
    if _db is None:
        return
    try:
        await _db.ora_github_block_log.insert_one({
            "operation": operation,
            "actor":     actor,
            "context":   context[:600],
            "ts":        datetime.now(timezone.utc).isoformat(),
        })
    except Exception as e:
        logger.debug(f"[github-lock] audit insert failed: {e}")


__all__ = [
    "GitHubLockedError",
    "LOCKED_OPERATIONS",
    "is_github_locked",
    "get_lock_status",
    "assert_github_writes_allowed",
    "log_block_attempt",
]
