"""
AUREM Memoir Service — Git-versioned semantic memory for 28 agents + ORA.

Wraps `memoir-ai`'s ProllyTreeStore in a thin AUREM-aware façade. Each
write auto-commits to the Git-backed prolly-tree (audit trail FREE), and
hierarchical namespaces become first-class semantic paths.

Canonical namespace taxonomy (light wrapper — Mongo remains source of
truth; Memoir is the fast intelligent index):

  aurem.customers.{email}.prefs           ← industry, vertical, tone
  aurem.customers.{email}.audits.latest   ← cached audit summary
  aurem.bins.{bin_id}.history.last_audit
  aurem.agents.{agent_name}.scratchpad
  aurem.agents.scout.results.{batch_date}
  aurem.ora.sessions.{session_id}.turns   ← chat memory
  aurem.founder.saves.{save_id}           ← override audit trail
  aurem.skills.broadcast.active           ← live skill addendum cache

API surface (all methods are sync; the underlying store does its own I/O):
  remember(path, key, value, *, commit_msg=None) -> commit_sha or None
  recall  (path, key) -> value | None
  search  (path, *, limit=10) -> list[(ns, key, value)]
  history (path, key, *, limit=10) -> list[commit_dict]
  stats() -> dict
  list_paths() -> list[tuple]
"""
from __future__ import annotations

import logging
import os
import subprocess
import threading
import time
from typing import Any, Optional

logger = logging.getLogger(__name__)

# Single global store + lock — Memoir's ProllyTreeStore is not goroutine-
# safe across concurrent writes (it spawns subprocess git commands).
_LOCK = threading.RLock()
_STORE = None
_STORE_PATH = os.environ.get("MEMOIR_STORE") or "/app/data/memoir/store"
_AVAILABLE = False
_INIT_ERROR: Optional[str] = None


def _normalize_path(path: str | tuple | list) -> tuple:
    """Accept 'a.b.c' or ['a','b','c'] or ('a','b','c') and return the
    tuple form that ProllyTreeStore expects."""
    if isinstance(path, str):
        return tuple([p for p in path.split(".") if p])
    if isinstance(path, list):
        return tuple(path)
    return tuple(path)


def _ensure_store_dir() -> None:
    """Create the store on disk if missing. Uses the `memoir new` CLI to
    initialise the .git directory + data folder so ProllyTreeStore can
    open it.

    Production-safety (May 2026): in deployed K8s pods `memoir new` exits 5
    because `/app/data/` is not writable on the read-only overlay. We now
    detect this fast (writability probe) and raise a clean error so init()
    can skip Memoir without blocking startup. Set MEMOIR_SKIP=1 to disable
    the subprocess entirely (recommended for production)."""
    if os.path.isdir(os.path.join(_STORE_PATH, ".git")) and os.path.isdir(
        os.path.join(_STORE_PATH, "data")
    ):
        return
    if os.environ.get("MEMOIR_SKIP", "").strip() in ("1", "true", "yes", "on"):
        raise RuntimeError("MEMOIR_SKIP=1 (operator disabled)")
    parent = os.path.dirname(_STORE_PATH) or "/"
    try:
        os.makedirs(parent, exist_ok=True)
    except Exception as e:
        raise RuntimeError(f"cannot create parent {parent}: {e}")
    # Fast writability probe — avoids spawning subprocess that takes ~10s
    # to time out in read-only production containers.
    if not os.access(parent, os.W_OK):
        raise RuntimeError(f"parent {parent} is not writable")
    try:
        r = subprocess.run(
            ["memoir", "new", _STORE_PATH],
            check=True, capture_output=True, text=True, timeout=10,
        )
        logger.info(f"[memoir] store created at {_STORE_PATH}: {r.stdout.strip()}")
    except FileNotFoundError:
        # memoir CLI binary not present in container — silent skip.
        raise RuntimeError("memoir CLI not installed")
    except subprocess.TimeoutExpired:
        raise RuntimeError("memoir new timed out (10s)")
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"memoir new exit={e.returncode}: {(e.stderr or '').strip()[:120]}")
    except Exception as e:
        raise RuntimeError(f"memoir new failed: {e}")


def init() -> bool:
    """Initialise the global Memoir store. Idempotent. Called once during
    backend startup; returns True if the store is ready, False if Memoir
    is unavailable (in which case all helpers no-op gracefully)."""
    global _STORE, _AVAILABLE, _INIT_ERROR
    if _STORE is not None:
        return _AVAILABLE
    try:
        from memoir import ProllyTreeStore  # type: ignore
    except Exception as e:
        _INIT_ERROR = f"memoir not installed: {e}"
        logger.warning(f"[memoir] not available — {_INIT_ERROR}")
        _AVAILABLE = False
        return False
    try:
        _ensure_store_dir()
        _STORE = ProllyTreeStore(
            path=_STORE_PATH, enable_versioning=True, auto_commit=True,
        )
        _AVAILABLE = True
        logger.info(f"[memoir] store ready at {_STORE_PATH}")
    except Exception as e:
        _INIT_ERROR = str(e)[:200]
        logger.warning(f"[memoir] init failed: {_INIT_ERROR}")
        _AVAILABLE = False
    return _AVAILABLE


def available() -> bool:
    return _AVAILABLE


def info() -> dict:
    return {
        "available": _AVAILABLE,
        "store_path": _STORE_PATH,
        "init_error": _INIT_ERROR,
    }


# ─── Core operations ─────────────────────────────────────────────────
def remember(
    path: str | tuple | list,
    key: str,
    value: Any,
    *,
    commit_msg: Optional[str] = None,
) -> Optional[str]:
    """Store `value` at `path.key`. Returns the Git commit SHA (or None
    if the store is unavailable). Auto-commit is on by default."""
    if not _AVAILABLE or _STORE is None:
        return None
    ns = _normalize_path(path)
    try:
        with _LOCK:
            _STORE.put(ns, str(key), value)
            sha: Optional[str] = None
            if commit_msg:
                sha = _STORE.commit(commit_msg)
            return sha
    except Exception as e:
        logger.warning(f"[memoir] remember({ns},{key}) failed: {e}")
        return None


def recall(path: str | tuple | list, key: str) -> Any:
    """Return the value at `path.key` or None."""
    if not _AVAILABLE or _STORE is None:
        return None
    ns = _normalize_path(path)
    try:
        with _LOCK:
            return _STORE.get(ns, str(key))
    except Exception as e:
        logger.debug(f"[memoir] recall({ns},{key}) miss: {e}")
        return None


def search(
    path: str | tuple | list, *, limit: int = 10,
) -> list[tuple]:
    """Return up to `limit` (namespace, key, value) tuples under `path`."""
    if not _AVAILABLE or _STORE is None:
        return []
    ns = _normalize_path(path)
    try:
        with _LOCK:
            return _STORE.search(ns, limit=limit)
    except Exception as e:
        logger.debug(f"[memoir] search({ns}) failed: {e}")
        return []


def history(
    path: str | tuple | list, key: str, *, limit: int = 10,
) -> list[dict]:
    """Return commit history for `path.key` — newest first."""
    if not _AVAILABLE or _STORE is None:
        return []
    ns = _normalize_path(path)
    try:
        with _LOCK:
            return _STORE.get_key_history(ns, str(key), limit=limit)
    except Exception as e:
        logger.debug(f"[memoir] history({ns},{key}) failed: {e}")
        return []


def commit(message: str) -> Optional[str]:
    """Force a manual commit. Returns commit SHA or None."""
    if not _AVAILABLE or _STORE is None:
        return None
    try:
        with _LOCK:
            return _STORE.commit(message)
    except Exception as e:
        logger.warning(f"[memoir] commit failed: {e}")
        return None


def stats() -> dict:
    """Return store-level statistics."""
    if not _AVAILABLE or _STORE is None:
        return {"available": False}
    try:
        with _LOCK:
            s = _STORE.get_statistics()
        return {"available": True, **s}
    except Exception as e:
        return {"available": True, "error": str(e)[:200]}


# ─── AUREM-specific convenience helpers ──────────────────────────────
def ora_remember_turn(session_id: str, role: str, content: str) -> None:
    """Append a chat turn to ORA's session memory."""
    key = f"{int(time.time() * 1000)}_{role}"
    remember(
        ("aurem", "ora", "sessions", session_id, "turns"),
        key,
        {"role": role, "content": content[:8000], "ts": time.time()},
    )


def ora_recall_session(session_id: str, *, limit: int = 20) -> list[dict]:
    """Return last `limit` turns for an ORA session."""
    turns = search(
        ("aurem", "ora", "sessions", session_id, "turns"), limit=limit,
    )
    # turns is list[(ns, key, value)] — sort by key (which has ts prefix)
    turns_sorted = sorted(turns, key=lambda t: t[1])
    return [t[2] for t in turns_sorted]


def customer_save_audit(email: str, audit_summary: dict) -> Optional[str]:
    """Cache the latest audit summary for a customer."""
    return remember(
        ("aurem", "customers", email, "audits"),
        "latest",
        audit_summary,
        commit_msg=f"audit:{email}",
    )


def customer_recall_audit(email: str) -> Optional[dict]:
    return recall(("aurem", "customers", email, "audits"), "latest")


def founder_save_log(save_id: str, change: dict) -> Optional[str]:
    """Record a Founder Override — auto-commit gives audit trail FREE."""
    return remember(
        ("aurem", "founder", "saves"), save_id, change,
        commit_msg=f"founder-save:{save_id}",
    )


def founder_save_history(save_id: str, *, limit: int = 50) -> list[dict]:
    return history(("aurem", "founder", "saves"), save_id, limit=limit)


def skill_broadcast_set(addendum: str, skill_ids: list[str]) -> Optional[str]:
    return remember(
        ("aurem", "skills", "broadcast"), "active",
        {"system_addendum": addendum, "skill_ids": skill_ids,
         "broadcast_at": time.time()},
        commit_msg=f"broadcast:{len(skill_ids)}",
    )


def skill_broadcast_get() -> Optional[dict]:
    return recall(("aurem", "skills", "broadcast"), "active")


def agent_scratchpad(agent_name: str, key: str, value: Any = None) -> Any:
    """Read or write an agent's scratchpad value."""
    ns = ("aurem", "agents", agent_name, "scratchpad")
    if value is None:
        return recall(ns, key)
    remember(ns, key, value)
    return value
