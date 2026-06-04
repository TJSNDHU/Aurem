"""Read codebase skill — return file tree + key file contents."""
import os
from typing import Any

from .registry import skill

_ROOT = "/app"
_DEFAULT_EXCLUDES = {
    "node_modules", "__pycache__", ".git", ".venv", "build", "dist",
    ".next", "yarn.lock", "package-lock.json",
}


@skill(
    name="read_codebase",
    description=(
        "List files under a project directory, optionally returning the "
        "contents of specific files. Use to orient yourself before "
        "editing. Returns truncated file contents (max 4000 chars)."
    ),
)
async def read_codebase(path: str = "/app/backend",
                          include_files: list[str] | None = None,
                          max_depth: int = 4) -> dict[str, Any]:
    if not path.startswith(_ROOT):
        raise ValueError(f"path must be under {_ROOT}")
    if not os.path.isdir(path):
        raise FileNotFoundError(path)

    tree: list[str] = []
    base_depth = path.rstrip("/").count("/")
    for root, dirs, files in os.walk(path):
        dirs[:] = [d for d in dirs if d not in _DEFAULT_EXCLUDES
                   and not d.startswith(".")]
        depth = root.count("/") - base_depth
        if depth > max_depth:
            dirs[:] = []
            continue
        for f in sorted(files):
            if f.startswith(".") or any(f.endswith(ext) for ext in
                                          (".pyc", ".log", ".lock")):
                continue
            tree.append(os.path.join(root, f))

    contents: dict[str, str] = {}
    for f in (include_files or []):
        full = f if f.startswith("/") else os.path.join(path, f)
        if os.path.isfile(full):
            try:
                with open(full, "r", encoding="utf-8") as fh:
                    contents[full] = fh.read()[:4000]
            except Exception as e:
                contents[full] = f"<read_failed: {e}>"

    return {"path": path, "file_count": len(tree),
             "tree": tree[:200], "contents": contents}
