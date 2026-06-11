"""Edit/write file skills — atomic search/replace + full-file write,
both with BIN-scoped audit logging per iter D-81b."""
import difflib
import os
from datetime import datetime, timezone
from typing import Any, Optional

from .registry import skill

_db = None


def set_db(database) -> None:
    global _db
    _db = database


async def _audit(action: str, path: str, *,
                  diff: str = "", bytes_written: int = 0,
                  business_id: Optional[str] = None,
                  by: Optional[str] = None) -> None:
    """Best-effort audit row. NEVER raises — file-write must not be
    blocked by audit-log issues."""
    if _db is None:
        return
    try:
        await _db.cto_file_edit_audit.insert_one({
            "action": action,
            "path": path,
            "business_id": business_id or "AUR-FNDR-001",
            "by": by or "cto_agent",
            "bytes_written": bytes_written,
            "diff_head": (diff or "")[:2000],
            "at": datetime.now(timezone.utc).isoformat(),
        })
    except Exception:
        pass


@skill(
    name="edit_file",
    description=(
        "Search-and-replace inside a file. Returns a unified diff and "
        "the bytes written. Refuses to operate outside /app/. Logs "
        "every write to cto_file_edit_audit with BIN context."
    ),
)
async def edit_file(path: str, old: str, new: str,
                       dry_run: bool = False,
                       business_id: Optional[str] = None,
                       by: Optional[str] = None) -> dict[str, Any]:
    if not path.startswith("/app/"):
        raise ValueError("path must be under /app/")
    if not os.path.isfile(path):
        raise FileNotFoundError(path)
    with open(path, "r", encoding="utf-8") as f:
        src = f.read()
    if old not in src:
        return {"ok": False, "error": "old_string_not_found",
                 "path": path}
    if src.count(old) > 1:
        return {"ok": False, "error": "old_string_not_unique",
                 "occurrences": src.count(old), "path": path}
    updated = src.replace(old, new, 1)
    diff = "\n".join(difflib.unified_diff(
        src.splitlines(), updated.splitlines(),
        fromfile=path, tofile=path, n=2,
    ))
    if not dry_run:
        with open(path, "w", encoding="utf-8") as f:
            f.write(updated)
        await _audit("edit_file", path,
                      diff=diff, bytes_written=len(updated),
                      business_id=business_id, by=by)
    return {"ok": True, "path": path, "dry_run": dry_run,
             "bytes_written": len(updated) if not dry_run else 0,
             "diff": diff[:4000]}


@skill(
    name="write_file",
    description=(
        "Overwrite or create a file with new content. Refuses paths "
        "outside /app/. iter D-81b — for new-file creation or full "
        "rewrites where edit_file's search/replace can't reach. "
        "Logs every write to cto_file_edit_audit."
    ),
)
async def write_file(path: str, content: str,
                       overwrite: bool = False,
                       business_id: Optional[str] = None,
                       by: Optional[str] = None) -> dict[str, Any]:
    if not path.startswith("/app/"):
        raise ValueError("path must be under /app/")
    existed = os.path.isfile(path)
    if existed and not overwrite:
        return {"ok": False, "error": "file_exists_set_overwrite_true",
                 "path": path}
    os.makedirs(os.path.dirname(path), exist_ok=True)
    prev_src = ""
    if existed:
        with open(path, "r", encoding="utf-8") as f:
            prev_src = f.read()
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    diff = "\n".join(difflib.unified_diff(
        prev_src.splitlines(), content.splitlines(),
        fromfile=path, tofile=path, n=2,
    ))
    await _audit("write_file", path,
                  diff=diff, bytes_written=len(content),
                  business_id=business_id, by=by)
    return {"ok": True, "path": path, "created": not existed,
             "bytes_written": len(content),
             "diff": diff[:4000]}
