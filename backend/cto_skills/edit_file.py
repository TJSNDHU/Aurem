"""Edit file skill — atomic search/replace with diff preview."""
import difflib
import os
from typing import Any

from .registry import skill


@skill(
    name="edit_file",
    description=(
        "Search-and-replace inside a file. Returns a unified diff and "
        "the bytes written. Refuses to operate outside /app."
    ),
)
async def edit_file(path: str, old: str, new: str,
                       dry_run: bool = False) -> dict[str, Any]:
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
    return {"ok": True, "path": path, "dry_run": dry_run,
             "bytes_written": len(updated) if not dry_run else 0,
             "diff": diff[:4000]}
