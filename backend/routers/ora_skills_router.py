"""
ORA Skills Router — exposes the markdown skill library at /app/backend/ora_skills/.

`/api/ora/skills/list` returns names + categories.
`/api/ora/skills/get/{name}` returns the markdown body of one skill.
`/api/ora/skills/health` — used by the Pillars Map Dev Stack health grid.
"""
from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Dict, List

from fastapi import APIRouter, HTTPException

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/ora/skills", tags=["ORA Skills"])

SKILLS_DIR = Path(__file__).resolve().parent.parent / "ora_skills"


def _list_skills() -> List[Dict[str, str]]:
    if not SKILLS_DIR.exists():
        return []
    out: List[Dict[str, str]] = []
    for f in sorted(SKILLS_DIR.glob("*.md")):
        name = f.stem
        cat = name.split("_", 1)[0] if "_" in name else "general"
        out.append({"name": name, "category": cat, "path": str(f.relative_to(SKILLS_DIR.parent))})
    return out


@router.get("/list")
async def list_skills():
    return {"ok": True, "skills_dir": str(SKILLS_DIR), "count": len(_list_skills()),
            "skills": _list_skills()}


@router.get("/get/{name}")
async def get_skill(name: str):
    # Block directory traversal
    if "/" in name or ".." in name or name.startswith("."):
        raise HTTPException(400, "invalid skill name")
    f = SKILLS_DIR / f"{name}.md"
    if not f.exists():
        raise HTTPException(404, f"no such skill: {name}")
    try:
        body = f.read_text(encoding="utf-8")
    except Exception as e:
        raise HTTPException(500, f"read failed: {e}")
    return {"ok": True, "name": name, "body": body, "size_bytes": len(body)}


@router.get("/health")
async def health():
    skills = _list_skills()
    return {
        "ok": True,
        "status": "green" if skills else "red",
        "count": len(skills),
        "dir_exists": SKILLS_DIR.exists(),
        "loaded_at": str(SKILLS_DIR),
    }
