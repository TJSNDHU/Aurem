"""
services/ora_skills.py — iter 326hh (Phase 3 P3.3).

Skills marketplace. Canadian domain experts publish "skills" (named
bundles of prompts + tool-call playbooks + system knowledge) that
tenants install to extend ORA's behaviour without code changes.

Example skills:
  - "GST/HST filing automation"        (tax accountant)
  - "WSIB compliance checker"          (HR consultant)
  - "GTA seasonal campaign templates"  (marketing agency)

Storage
───────
  db.ora_skills                — published catalog (one row per skill,
                                  versioned by `versions[]`)
  db.tenant_installed_skills   — per-tenant installs
                                  (one row per (tenant_id, skill_id))

Public API
──────────
    set_db(database)
    await publish_skill(...)             — author publishes / updates a skill
    await list_skills(category=None, limit=50)
    await get_skill(skill_id)
    await install_skill(tenant_id, skill_id, version=None)
    await list_installed_for_tenant(tenant_id)
    await uninstall_skill(tenant_id, skill_id)
"""
from __future__ import annotations

import logging
import re
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

logger = logging.getLogger(__name__)

_SKILLS    = "ora_skills"
_INSTALLS  = "tenant_installed_skills"
_db = None
_indexes_ensured = False

_SLUG_RE = re.compile(r"[^a-z0-9_-]+")


def set_db(database) -> None:
    global _db, _indexes_ensured
    _db = database
    _indexes_ensured = False


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _slug(s: str) -> str:
    return _SLUG_RE.sub("-", (s or "").lower()).strip("-")[:64]


async def _ensure_indexes() -> None:
    global _indexes_ensured
    if _indexes_ensured or _db is None:
        return
    try:
        await _db[_SKILLS].create_index("skill_id", unique=True)
        await _db[_SKILLS].create_index("category")
        await _db[_SKILLS].create_index([("name", "text"),
                                         ("description", "text")])
        await _db[_INSTALLS].create_index(
            [("tenant_id", 1), ("skill_id", 1)], unique=True,
        )
        _indexes_ensured = True
    except Exception as e:
        logger.warning(f"[skills] index ensure failed: {e}")


async def publish_skill(
    *,
    name: str,
    description: str,
    category: str,
    author_email: str,
    version: str = "1.0.0",
    manifest: Optional[dict] = None,
    content: Optional[dict] = None,
    skill_id: Optional[str] = None,
    pricing: Optional[dict] = None,
) -> dict:
    """Publish a new skill OR add a new version to an existing one."""
    if _db is None:
        return {"ok": False, "error": "db_not_ready"}
    if not name or not description or not category:
        return {"ok": False, "error": "name, description, category required"}
    if not author_email:
        return {"ok": False, "error": "author_email required"}
    await _ensure_indexes()
    sid = skill_id or _slug(f"{author_email.split('@')[0]}-{name}")
    if not sid:
        return {"ok": False, "error": "could not derive skill_id"}
    now = _now()
    version_doc = {
        "version":      str(version)[:16],
        "manifest":     dict(manifest or {}),
        "content":      dict(content or {}),
        "published_at": now,
    }
    existing = await _db[_SKILLS].find_one({"skill_id": sid}, {"_id": 0})
    if existing:
        # Append a new version, update metadata.
        await _db[_SKILLS].update_one(
            {"skill_id": sid},
            {
                "$push": {"versions": version_doc},
                "$set": {
                    "name":         name[:120],
                    "description":  description[:1000],
                    "category":     category[:60],
                    "latest_version": version_doc["version"],
                    "updated_at":   now,
                    "pricing":      dict(pricing or {}),
                },
            },
        )
        return {"ok": True, "skill_id": sid,
                "latest_version": version_doc["version"], "created": False}
    # Brand new skill row.
    await _db[_SKILLS].insert_one({
        "skill_id":       sid,
        "name":           name[:120],
        "description":    description[:1000],
        "category":       category[:60],
        "author_email":   author_email[:120],
        "latest_version": version_doc["version"],
        "versions":       [version_doc],
        "downloads":      0,
        "pricing":        dict(pricing or {}),
        "created_at":     now,
        "updated_at":     now,
    })
    return {"ok": True, "skill_id": sid,
            "latest_version": version_doc["version"], "created": True}


async def list_skills(category: Optional[str] = None, limit: int = 50) -> list:
    """Browse the catalog. Top-downloaded first."""
    if _db is None:
        return []
    await _ensure_indexes()
    limit = max(1, min(int(limit or 50), 200))
    q: dict[str, Any] = {}
    if category:
        q["category"] = category
    out: list = []
    cur = (
        _db[_SKILLS]
        .find(q, {
            "_id": 0, "skill_id": 1, "name": 1, "description": 1,
            "category": 1, "author_email": 1, "latest_version": 1,
            "downloads": 1, "pricing": 1, "updated_at": 1,
        })
        .sort([("downloads", -1), ("updated_at", -1)])
        .limit(limit)
    )
    async for d in cur:
        ua = d.get("updated_at")
        if isinstance(ua, datetime):
            d["updated_at"] = ua.isoformat()
        out.append(d)
    return out


async def get_skill(skill_id: str) -> Optional[dict]:
    """Full skill record including all versions."""
    if _db is None or not skill_id:
        return None
    doc = await _db[_SKILLS].find_one({"skill_id": skill_id}, {"_id": 0})
    if not doc:
        return None
    # Stringify datetimes
    for v in (doc.get("versions") or []):
        p = v.get("published_at")
        if isinstance(p, datetime):
            v["published_at"] = p.isoformat()
    for k in ("created_at", "updated_at"):
        if isinstance(doc.get(k), datetime):
            doc[k] = doc[k].isoformat()
    return doc


async def install_skill(
    tenant_id: str, skill_id: str, version: Optional[str] = None,
) -> dict:
    """Install a skill (or upgrade to a specific version) for a tenant.
    Idempotent — re-installing the same version is a no-op."""
    if _db is None:
        return {"ok": False, "error": "db_not_ready"}
    if not tenant_id or not skill_id:
        return {"ok": False, "error": "tenant_id and skill_id required"}
    await _ensure_indexes()
    skill = await _db[_SKILLS].find_one({"skill_id": skill_id}, {"_id": 0})
    if not skill:
        return {"ok": False, "error": "skill not found"}
    target_version = version or skill.get("latest_version")
    # Verify the version exists in the skill's history.
    available = {v.get("version") for v in (skill.get("versions") or [])}
    if target_version not in available:
        return {"ok": False, "error": f"version {target_version} not published"}
    now = _now()
    await _db[_INSTALLS].update_one(
        {"tenant_id": tenant_id, "skill_id": skill_id},
        {
            "$set": {
                "tenant_id":   tenant_id,
                "skill_id":    skill_id,
                "version":     target_version,
                "installed_at": now,
                "enabled":     True,
            },
        },
        upsert=True,
    )
    await _db[_SKILLS].update_one(
        {"skill_id": skill_id}, {"$inc": {"downloads": 1}},
    )
    return {"ok": True, "tenant_id": tenant_id, "skill_id": skill_id,
            "version": target_version}


async def list_installed_for_tenant(tenant_id: str) -> list:
    """What skills does this tenant have active?"""
    if _db is None or not tenant_id:
        return []
    await _ensure_indexes()
    out: list = []
    async for d in _db[_INSTALLS].find(
        {"tenant_id": tenant_id, "enabled": True},
        {"_id": 0, "skill_id": 1, "version": 1, "installed_at": 1},
    ).sort("installed_at", -1):
        ia = d.get("installed_at")
        if isinstance(ia, datetime):
            d["installed_at"] = ia.isoformat()
        out.append(d)
    return out


async def uninstall_skill(tenant_id: str, skill_id: str) -> dict:
    """Soft-disable an install. Keeps the row so re-install doesn't
    lose history, but the skill no longer applies."""
    if _db is None:
        return {"ok": False, "error": "db_not_ready"}
    res = await _db[_INSTALLS].update_one(
        {"tenant_id": tenant_id, "skill_id": skill_id},
        {"$set": {"enabled": False, "disabled_at": _now()}},
    )
    return {"ok": True, "modified": res.modified_count}
