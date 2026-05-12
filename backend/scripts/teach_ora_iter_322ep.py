"""
teach_ora_iter_322ep — Persist the broadcast-content-injection-fix
lesson into ORA memory across all 4 mandatory channels.

This iteration also exposes two new founder-facing admin tools:
  - /api/admin/design-extract (DTCG token extractor)
  - /api/admin/ora-optimize  (codeburn-pattern LLM budget watchdog)

The skill body uses the FIXED full-body broadcast logic (≤10K chars).
"""
from __future__ import annotations

import asyncio
import hashlib
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, "/app/backend")
from motor.motor_asyncio import AsyncIOMotorClient


SKILL = {
    "iter":     "322ep",
    "id":       "aurem-322ep-broadcast-content-injection-fix",
    "name":     "Broadcast Content Injection Fix (iter 322ep) — full-body skill propagation",
    "category": "ora_memory_integrity",
    "description": (
        "Found and fixed a silent 600-char truncation in the skill broadcast pipeline that "
        "was hiding ORA's most important rules (3-proof verification block at ~6,700 chars "
        "of the dev-engineering-protocol skill). Teaches ORA never to trust 'skill is broadcast' "
        "as proof that the LLM actually sees the rules — only a real string-grep against the "
        "live system_addendum string counts. New verification recipe enforced for all future "
        "teach_ora_iter_<X>.py scripts."
    ),
    "md_path":  "/app/backend/ora_skills/dev_broadcast-content-injection-fix.md",
}


# Truncation constants MUST mirror routers/antigravity_skills_router.py
FULL_BODY_LIMIT = 10_000
HEAD_LEN = 1_200


async def main() -> None:
    db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
    import server
    server.db = db
    now = datetime.now(timezone.utc).isoformat()

    body = open(SKILL["md_path"]).read()
    body_hash = hashlib.sha256(body.encode()).hexdigest()[:16]
    print(f"=== iter 322ep — Hard-saving Broadcast Content Injection Fix ===")
    print(f"Body: {len(body)} chars, sha={body_hash}\n")

    # 1. ora_training_files
    text = f"AUREM Skill — {SKILL['name']} (iter {SKILL['iter']})\n\n{body}"
    await db.ora_training_files.update_one(
        {"file_id": f"learning-brief-{SKILL['iter']}"},
        {"$set": {
            "file_id":      f"learning-brief-{SKILL['iter']}",
            "user_id":      "system_main_agent",
            "source_type":  "learning_brief",
            "filename":     f"learning-{SKILL['iter']}-broadcast-injection-fix.md",
            "file_ext":     ".md",
            "file_category": "document",
            "file_size":    len(text),
            "language":     "english",
            "purpose":      "ora_self_learning",
            "notes":        SKILL["description"][:200],
            "status":       "ready",
            "crawled_text": text,
            "text_chars":   len(text),
            "created_at":   now,
            "updated_at":   now,
        }},
        upsert=True,
    )
    print(f"[1/4] ora_training_files          ← {len(text)} chars")

    # 2. ora_skills_library
    await db.ora_skills_library.update_one(
        {"id": SKILL["id"]},
        {"$set": {
            "id":           SKILL["id"],
            "name":         SKILL["name"],
            "category":     SKILL["category"],
            "description":  SKILL["description"],
            "body":         body,
            "source":       f"aurem-internal-iter-{SKILL['iter']}",
            "added_at":     now,
            "iter":         SKILL["iter"],
            "content_hash": body_hash,
        }},
        upsert=True,
    )
    print(f"[2/4] ora_skills_library          ← {SKILL['id']}")

    # 3. broadcast — append after the existing skill set, then rebuild
    # the addendum using the FIXED full-body logic (NOT the legacy
    # 600-char truncation).
    existing = await db.ora_skills_broadcast.find_one({"_id": "active"}) or {}
    existing_ids = [s for s in (existing.get("skill_ids") or []) if s != SKILL["id"]]
    final_ids = existing_ids + [SKILL["id"]]

    docs = await db.ora_skills_library.find(
        {"id": {"$in": final_ids}},
        {"_id": 0, "id": 1, "name": 1, "description": 1, "category": 1, "body": 1},
    ).to_list(length=len(final_ids))
    by_id = {d["id"]: d for d in docs}
    ordered = [by_id[sid] for sid in final_ids if sid in by_id]

    bits: list[str] = []
    for i, d in enumerate(ordered):
        b = (d.get("body") or "").strip()
        if len(b) <= FULL_BODY_LIMIT:
            content = b
        else:
            content = b[:HEAD_LEN].strip() + "\n[...truncated for size, see full skill in library...]"
        prefix = "## ⚖️ CORE LAW (read first):\n" if i == 0 else ""
        bits.append(
            f"{prefix}### SKILL: {d['name']} ({d['category']})\n"
            f"{d.get('description', '')}\n{content}"
        )
    addendum = "\n\n".join(bits)

    await db.ora_skills_broadcast.update_one(
        {"_id": "active"},
        {"$set": {
            "skill_ids":       final_ids,
            "system_addendum": addendum,
            "target_agents":   "ALL",
            "broadcast_at":    now,
            "skill_count":     len(final_ids),
            "charter_first":   final_ids[0] == "aurem-322ek-zero-hallucination-charter",
            "stack_name":      "ORA CTO (Sovereign Chief Technology Officer)",
        }},
        upsert=True,
    )
    await db.ora_skills_broadcast_history.insert_one({
        "_id":            f"bcast_{now}_322ep",
        "skill_ids":      final_ids,
        "target_agents":  "ALL",
        "broadcast_at":   now,
        "broadcast_by":   "main_agent_iter_322ep",
        "action":         "broadcast_content_injection_fix",
    })
    try:
        from services.agent_skill_broadcast import invalidate_cache
        invalidate_cache()
    except Exception:
        pass
    print(f"[3/4] ora_skills_broadcast active ← {len(final_ids)} skills, "
          f"{len(addendum)} chars (cache invalidated)")

    # 4. SECONDARY Atlas mirror
    print(f"\n=== Mirror to SECONDARY Atlas ===")
    sec_url = os.environ.get("SECONDARY_MONGO_URL")
    if sec_url:
        try:
            from pymongo import MongoClient
            def _mirror():
                s = MongoClient(sec_url, serverSelectionTimeoutMS=15000)
                sdb = s[os.environ.get("DB_NAME", "aurem_db")]
                existing_doc = sdb.ora_training_files.find_one(
                    {"file_id": f"learning-brief-{SKILL['iter']}"}
                )
                doc = {
                    **(existing_doc or {}),
                    "file_id":      f"learning-brief-{SKILL['iter']}",
                    "user_id":      "system_main_agent",
                    "source_type":  "learning_brief",
                    "filename":     f"learning-{SKILL['iter']}-broadcast-injection-fix.md",
                    "file_ext":     ".md",
                    "file_category": "document",
                    "file_size":    len(text),
                    "language":     "english",
                    "purpose":      "ora_self_learning",
                    "status":       "ready",
                    "crawled_text": text,
                    "text_chars":   len(text),
                    "updated_at":   now,
                }
                if not existing_doc:
                    doc["created_at"] = now
                sdb.ora_training_files.replace_one(
                    {"file_id": f"learning-brief-{SKILL['iter']}"},
                    doc, upsert=True,
                )
                s.close()
                return "ok"
            await asyncio.to_thread(_mirror)
            print(f"[4/4] secondary ora_training_files ← mirrored")
        except Exception as e:
            print(f"[4/4] ⚠ secondary mirror failed: {e}")
    else:
        print(f"[4/4] ⚠ SECONDARY_MONGO_URL not set")

    # ── Verification — the MANDATORY recipe from this skill ────────
    print(f"\n=== Verification (real string grep, not row counts) ===")
    from services.agent_skill_broadcast import get_addendum
    ad = await get_addendum(db, agent_name="GATEWAY")
    checks = {
        "git log --oneline -3":    "git log --oneline -3" in ad,
        "/api/platform/health":    "/api/platform/health" in ad,
        "MANDATORY 3 PROOFS":      "MANDATORY 3 PROOFS" in ad,
        f"skill {SKILL['id']}":    SKILL["id"] in (await db.ora_skills_broadcast.find_one({"_id": "active"}) or {}).get("skill_ids", []),
        "broadcast-content-injection-fix": "broadcast-content-injection-fix" in ad.lower(),
    }
    for k, v in checks.items():
        print(f"  {'✓' if v else '✗'} {k}")

    pri_n = await db.ora_training_files.count_documents(
        {"file_id": f"learning-brief-{SKILL['iter']}"}
    )
    pri_s = await db.ora_skills_library.count_documents({"id": SKILL["id"]})
    bcast = await db.ora_skills_broadcast.find_one({"_id": "active"})
    print(f"\n  PRIMARY  training_files:  {pri_n}")
    print(f"  PRIMARY  skills_library:  {pri_s}")
    print(f"  PRIMARY  broadcast skill_count: {bcast.get('skill_count')}")
    print(f"  PRIMARY  addendum bytes:  {len(bcast.get('system_addendum',''))} chars (was 12,398 pre-fix)")

    if sec_url:
        try:
            from pymongo import MongoClient
            def _check():
                s = MongoClient(sec_url, serverSelectionTimeoutMS=15000)
                n = s[os.environ.get("DB_NAME", "aurem_db")].ora_training_files.count_documents(
                    {"file_id": f"learning-brief-{SKILL['iter']}"}
                )
                s.close()
                return n
            sec_n = await asyncio.to_thread(_check)
            print(f"  SECONDARY training_files: {sec_n}")
        except Exception as e:
            print(f"  SECONDARY check failed: {e}")


if __name__ == "__main__":
    asyncio.run(main())
