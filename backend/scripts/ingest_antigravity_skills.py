"""
Ingest Antigravity Awesome Skills (1,453+ SKILL.md playbooks) into MongoDB.

Source: https://github.com/sickn33/antigravity-awesome-skills

Writes to two collections:
  - ora_skills_library  : full SKILL.md content + metadata (one doc per skill)
  - ora_skills_meta     : ingestion run summary

Idempotent — safe to re-run. Uses bulk_write with upserts.

Usage:
    python3 -m scripts.ingest_antigravity_skills [--source-dir /tmp/antigravity-skills]

If source-dir doesn't exist, the script will shallow-clone the repo.
"""
import asyncio
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import UpdateOne

REPO_URL = "https://github.com/sickn33/antigravity-awesome-skills.git"
DEFAULT_SRC = "/tmp/antigravity-skills"
MAX_CONTENT_BYTES = 200_000  # 200KB cap per SKILL.md to avoid bloat


def _ensure_repo(src_dir: str) -> None:
    """Shallow-clone repo if missing."""
    if Path(src_dir, "skills_index.json").exists():
        return
    if Path(src_dir).exists():
        shutil.rmtree(src_dir)
    print(f"[ingest] Cloning {REPO_URL} → {src_dir}")
    subprocess.run(
        ["git", "clone", "--depth", "1", REPO_URL, src_dir],
        check=True,
        capture_output=True,
    )


def _read_skill_body(skill_path: str) -> str:
    """Read the SKILL.md content for a given skill folder."""
    md_path = Path(skill_path, "SKILL.md")
    if not md_path.exists():
        # Try README.md as fallback
        md_path = Path(skill_path, "README.md")
    if not md_path.exists():
        return ""
    try:
        data = md_path.read_text(encoding="utf-8", errors="ignore")
        if len(data.encode("utf-8")) > MAX_CONTENT_BYTES:
            data = data[:MAX_CONTENT_BYTES] + "\n\n... [TRUNCATED]"
        return data
    except Exception:
        return ""


async def ingest(src_dir: str = DEFAULT_SRC) -> dict:
    _ensure_repo(src_dir)
    idx_path = Path(src_dir, "skills_index.json")
    if not idx_path.exists():
        raise FileNotFoundError(f"skills_index.json not found at {idx_path}")

    with open(idx_path, "r", encoding="utf-8") as f:
        skills = json.load(f)

    mongo_url = os.environ.get("MONGO_URL")
    db_name = os.environ.get("DB_NAME")
    if not mongo_url or not db_name:
        raise RuntimeError("MONGO_URL / DB_NAME must be set in env")

    client = AsyncIOMotorClient(mongo_url)
    db = client[db_name]
    coll = db.ora_skills_library

    # Ensure indexes
    await coll.create_index("id", unique=True)
    await coll.create_index("category")
    await coll.create_index("risk")
    await coll.create_index([("name", "text"), ("description", "text")])

    ops = []
    skipped_no_body = 0
    now = datetime.now(timezone.utc).isoformat()

    for entry in skills:
        skill_id = entry.get("id")
        if not skill_id:
            continue
        skill_path = Path(src_dir, entry.get("path", "skills/" + skill_id))
        body = _read_skill_body(str(skill_path))
        if not body:
            skipped_no_body += 1
        doc = {
            "id": skill_id,
            "name": entry.get("name", skill_id),
            "description": entry.get("description", ""),
            "category": entry.get("category", "uncategorized"),
            "risk": entry.get("risk", "unknown"),
            "source": entry.get("source", "antigravity"),
            "date_added": entry.get("date_added", ""),
            "plugin_targets": (entry.get("plugin") or {}).get("targets", {}),
            "body": body,
            "body_size": len(body),
            "synced_at": now,
            "upstream_repo": "sickn33/antigravity-awesome-skills",
            "upstream_path": entry.get("path", ""),
        }
        ops.append(UpdateOne({"id": skill_id}, {"$set": doc}, upsert=True))

    # Bulk write in chunks of 500
    upserted = 0
    modified = 0
    for i in range(0, len(ops), 500):
        chunk = ops[i:i + 500]
        if not chunk:
            continue
        res = await coll.bulk_write(chunk, ordered=False)
        upserted += res.upserted_count
        modified += res.modified_count

    # Write meta summary
    summary = {
        "total_in_index": len(skills),
        "upserted": upserted,
        "modified": modified,
        "skipped_no_body": skipped_no_body,
        "ingested_at": now,
        "source": REPO_URL,
    }
    await db.ora_skills_meta.update_one(
        {"_id": "latest"},
        {"$set": summary},
        upsert=True,
    )
    await db.ora_skills_meta.insert_one({
        **summary,
        "_id": f"run_{now}",
    })

    client.close()
    return summary


if __name__ == "__main__":
    src = DEFAULT_SRC
    if len(sys.argv) > 1 and sys.argv[1].startswith("--source-dir="):
        src = sys.argv[1].split("=", 1)[1]
    sys.path.insert(0, "/app/backend")
    # Load .env
    try:
        from dotenv import load_dotenv
        load_dotenv("/app/backend/.env")
    except Exception:
        pass
    result = asyncio.run(ingest(src))
    print(json.dumps(result, indent=2))
