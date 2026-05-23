"""
services/ora_lessons_loader.py — iter 327n → iter 331a (folder-driven)

Tiered memory injection for ORA's SYSTEM_PROMPT.

iter 331a — Folder-driven loading
---------------------------------
Previous version had a hard-coded `_TIER1_FILES` list. Adding a new
memory file required a code change. Now the loader scans:

    /app/memory/tier1/    — always-injected (every conversation)
    /app/memory/tier2/    — keyword-gated (loaded on relevant turns)
    /app/memory/tier3/    — reference-only, never auto-injected

Adding a new always-on rule book = drop a `.md` file in `tier1/`.
Adding a new keyword-gated playbook = drop a `.md` file in `tier2/`
   PLUS a one-line entry in `/app/memory/tier2/TIER2_TRIGGERS.json`.

Per-file caps and total budget unchanged from iter 327n.

ORA portability rule: this module reads only from disk paths under
`/app/memory/` and `/app/backend/ora_skills/`. Zero platform-specific
imports. Migration = `cp -r /app/memory /app/backend/ora_skills` to
new host, set `ORA_MEMORY_ROOT` env var if path differs.
"""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import List

logger = logging.getLogger(__name__)

# ── Configuration (env-overridable for portability) ─────────────────
_MEMORY_ROOT  = Path(os.environ.get("ORA_MEMORY_ROOT", "/app/memory"))
_TIER1_DIR    = _MEMORY_ROOT / "tier1"
_TIER2_DIR    = _MEMORY_ROOT / "tier2"
_TIER2_RULES_FILE = _TIER2_DIR / "TIER2_TRIGGERS.json"

_TIER1_CAP_TOTAL    = int(os.environ.get("ORA_TIER1_CAP_TOTAL", "8000"))
_TIER1_CAP_PER_FILE = int(os.environ.get("ORA_TIER1_CAP_PER_FILE", "1500"))
_TIER2_CAP_PER_FILE = int(os.environ.get("ORA_TIER2_CAP_PER_FILE", "4000"))

# Per-file caps that override the global cap (legacy iter-327n behaviour
# kept SYSTEM_MAP.md at 1500 chars even when others were also 1500).
# Map: filename -> char cap. Filenames are case-sensitive.
_PER_FILE_OVERRIDES = {
    "SYSTEM_MAP.md": 1500,
}


# ── Helpers ─────────────────────────────────────────────────────────

def _read_capped(path: Path, cap: int) -> str | None:
    """Read a file and clamp to `cap` chars. Returns None on any
    failure (missing, permission, decode error). Never raises."""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        logger.debug(f"[lessons-loader] skip {path}: {e}")
        return None
    text = text.strip()
    if not text:
        return None
    if len(text) > cap:
        text = text[:cap] + f"\n…[truncated {len(text) - cap} chars]"
    return text


def _format_block(label: str, body: str) -> str:
    """Wrap a file body in a clear header/footer so the LLM can
    distinguish injected lessons from conversation."""
    return (
        f"\n\n=== {label} ===\n"
        f"{body}\n"
        f"=== END {label} ===\n"
    )


def _label_from_filename(p: Path) -> str:
    """`WATCHDOG_MODE.md` → `WATCHDOG MODE`. Skill prefixes stripped."""
    stem = p.stem
    if stem.startswith("dev_"):
        stem = stem[4:]
    if stem.startswith("322ey-"):
        stem = stem[6:]
    return stem.replace("-", " ").replace("_", " ").upper()


def _discover(dir_path: Path) -> list[Path]:
    """Return sorted list of `.md` files inside `dir_path`. Follows
    symlinks (we use them for backward-compat to skill files). Returns
    empty list if directory missing."""
    if not dir_path.is_dir():
        return []
    out: list[Path] = []
    for entry in sorted(dir_path.iterdir()):
        if entry.is_file() and entry.suffix.lower() == ".md":
            out.append(entry)
    return out


# ── Tier 1 — computed once at import, never recomputed per turn ─────

def build_lessons_block() -> str:
    """Assemble the always-injected Tier 1 block.

    Returns a single string ready to be appended to SYSTEM_PROMPT. The
    block is hard-capped at `_TIER1_CAP_TOTAL` characters even if
    individual files come in under their per-file cap — predictable
    token cost is more valuable than 100% inclusion.

    iter 331a — Folder-driven. Scans `tier1/` and injects every `.md`
    file found (alphabetical order = predictable injection order).
    """
    import hashlib
    parts: list[str] = []
    sources: list[str] = []
    manifest: list[dict] = []
    for path in _discover(_TIER1_DIR):
        cap = _PER_FILE_OVERRIDES.get(path.name, _TIER1_CAP_PER_FILE)
        body = _read_capped(path, cap)
        label = _label_from_filename(path)
        if body is None:
            manifest.append({"label": label, "path": str(path),
                              "loaded": False, "size": 0, "sha256": None})
            continue
        parts.append(_format_block(label, body))
        sources.append(path.name)
        manifest.append({
            "label": label,
            "path":  str(path),
            "loaded": True,
            "size":  len(body),
            "sha256": hashlib.sha256(body.encode("utf-8")).hexdigest(),
        })
    global _LAST_INJECTION_MANIFEST, _LAST_TOTAL_CHARS
    _LAST_INJECTION_MANIFEST = manifest
    if not parts:
        _LAST_TOTAL_CHARS = 0
        logger.info("[lessons-loader] tier-1 empty — no lesson files found")
        return ""
    assembled = (
        "\n\n# ─────────────────────────────────────────────\n"
        "# FOUNDER'S RULE BOOK — ORA must follow these\n"
        "# rules in every reply. They override the model's\n"
        "# default behaviour where they conflict.\n"
        "# ─────────────────────────────────────────────"
        + "".join(parts)
    )
    if len(assembled) > _TIER1_CAP_TOTAL:
        assembled = (
            assembled[:_TIER1_CAP_TOTAL]
            + f"\n…[total block truncated to {_TIER1_CAP_TOTAL} chars]"
        )
    _LAST_TOTAL_CHARS = len(assembled)
    logger.info(
        f"[ora-agent] Injected {len(assembled)} chars from "
        f"{len(parts)} lesson files: {', '.join(sources)}"
    )
    return assembled


# iter 327o — Module-level mirrors of the last boot's tier-1 state.
_LAST_INJECTION_MANIFEST: list[dict] = []
_LAST_TOTAL_CHARS: int = 0


def last_injection_manifest() -> list[dict]:
    """Return a defensive copy of the most recent tier-1 manifest."""
    return [dict(r) for r in _LAST_INJECTION_MANIFEST]


def tier1_total_chars() -> int:
    return _LAST_TOTAL_CHARS


# ── Tier 2 — keyword-gated, called once per user turn ────────────────

def _load_tier2_rules() -> list[tuple[tuple[str, ...], str, Path, int]]:
    """Load tier-2 trigger rules from `tier2/TIER2_TRIGGERS.json` if
    present, otherwise fall back to the hard-coded legacy table so we
    never lose behaviour across the iter-327n → iter-331a transition.

    JSON schema:
        [
          {
            "file": "DEPLOYMENT_RUNBOOK.md",
            "keywords": ["deploy", "restart", "503"],
            "label": "DEPLOYMENT RUNBOOK",
            "cap": 3000
          },
          ...
        ]
    """
    rules: list[tuple[tuple[str, ...], str, Path, int]] = []
    if _TIER2_RULES_FILE.exists():
        try:
            raw = json.loads(_TIER2_RULES_FILE.read_text(encoding="utf-8"))
            for r in raw:
                fname = r.get("file", "")
                if not fname:
                    continue
                p = _TIER2_DIR / fname
                rules.append((
                    tuple(r.get("keywords") or ()),
                    r.get("label") or _label_from_filename(p),
                    p,
                    int(r.get("cap") or _TIER2_CAP_PER_FILE),
                ))
            return rules
        except Exception as e:
            logger.warning(f"[lessons-loader] tier-2 rules parse failed: {e}")

    # Legacy fallback — preserves iter-327n behaviour if JSON missing.
    rules.extend([
        (("security", "auth", "jwt", "password", "secret", "token", "encryption"),
         "SECURITY PATTERNS", _MEMORY_ROOT / "SECURITY_PATTERNS.md", _TIER2_CAP_PER_FILE),
        (("campaign", "outreach", "email blast", "blast", "marketing",
          "opt out", "opt-out", "unsubscribe", "casl"),
         "CASL + OUTREACH RULES (from SECURITY PATTERNS)",
         _MEMORY_ROOT / "SECURITY_PATTERNS.md", _TIER2_CAP_PER_FILE),
        (("fix", "debug", "broken", "crash", "why does", "how does", "error"),
         "ARCHITECTURE (summary)", _MEMORY_ROOT / "ARCHITECTURE.md", 2000),
    ])
    return rules


def tier2_rule_table() -> list[dict]:
    """Return the configured tier-2 rules so the admin panel can show
    which keywords gate which file."""
    out: list[dict] = []
    for keywords, label, path, cap in _load_tier2_rules():
        out.append({
            "label":    label,
            "path":     str(path),
            "cap":      cap,
            "keywords": list(keywords),
            "exists":   path.exists(),
        })
    return out


def relevant_tier2_blocks(user_text: str) -> str:
    """Return Tier 2 injections that match the user's turn, or "" if
    nothing relevant. Same-file dedup: if the same file matches two
    rules in one turn it's only injected once.
    """
    if not user_text:
        return ""
    needle = user_text.lower()
    parts: list[str] = []
    seen_paths: set[str] = set()
    fired_labels: list[str] = []
    for keywords, label, path, cap in _load_tier2_rules():
        spath = str(path)
        if spath in seen_paths:
            continue
        if any(k in needle for k in keywords):
            body = _read_capped(path, cap)
            if body:
                parts.append(_format_block(label, body))
                seen_paths.add(spath)
                fired_labels.append(label)
    if parts:
        logger.info(
            f"[ora-agent] tier-2 fired for this turn: {fired_labels}"
        )
    return "".join(parts)


async def record_journal_entry_if_changed(db) -> dict:
    """iter 327o — Compare current tier-1 manifest against last entry
    in `ora_learning_journal`. Append a new doc when any file's sha256
    changed (or first-ever boot). Best-effort: returns a status dict,
    never raises.
    """
    if db is None or not _LAST_INJECTION_MANIFEST:
        return {"ok": False, "reason": "no_db_or_manifest"}
    from datetime import datetime, timezone
    try:
        last = await db.ora_learning_journal.find_one(
            {"kind": "tier1_snapshot"},
            sort=[("ts", -1)],
        )
        prev_hashes = {}
        if last and isinstance(last.get("files"), list):
            prev_hashes = {f["path"]: f.get("sha256")
                            for f in last["files"] if "path" in f}
        cur_hashes = {f["path"]: f.get("sha256")
                       for f in _LAST_INJECTION_MANIFEST if "path" in f}
        changed = [p for p, h in cur_hashes.items()
                    if prev_hashes.get(p) != h]
        if last is not None and not changed:
            return {"ok": True, "changed": False, "files_unchanged": len(cur_hashes)}
        import socket
        await db.ora_learning_journal.insert_one({
            "kind":            "tier1_snapshot",
            "ts":              datetime.now(timezone.utc).isoformat(),
            "total_chars":     _LAST_TOTAL_CHARS,
            "files":           _LAST_INJECTION_MANIFEST,
            "changed_paths":   changed,
            "first_snapshot":  last is None,
            "pod":             socket.gethostname()[:64],
            "process_user":    os.environ.get("USER") or os.environ.get("LOGNAME") or "unknown",
        })
        return {"ok": True, "changed": True,
                 "changed_paths": changed,
                 "first_snapshot": last is None}
    except Exception as e:
        logger.warning(f"[lessons-loader] journal write failed: {e}")
        return {"ok": False, "reason": str(e)[:200]}
