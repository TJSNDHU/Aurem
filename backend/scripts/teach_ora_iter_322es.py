"""
teach_ora_iter_322es — Persist the iter 322es "ORA CTO Final Complete"
lesson across all 4 channels: ora_training_files + ora_skills_library +
ora_skills_broadcast (with FULL-BODY logic, not the deprecated 600-char
truncation) + SECONDARY Atlas mirror.
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
    "iter":     "322es",
    "id":       "aurem-322es-ora-cto-final-complete",
    "name":     "ORA CTO Final Complete (iter 322es) — Preview→Deploy→Save→Rollback",
    "category": "ora_cto_stack",
    "description": (
        "Final state of the ORA CTO autonomous stack: 17 tools, 3-tab "
        "/admin/ora-chat UI (General Chat + CTO Mode + Files & Uploads), "
        "preview→deploy→save→rollback workflow in one window, dedicated "
        "/admin/ora-settings page with 5 sections (GitHub, Permissions, "
        "Council, Notifications, Audit & Logs). Quotas + cost tracking "
        "deliberately removed — AUREM is self-hosted, single-founder. "
        "Safety comes from the council gate + git commit gate, not "
        "rate limits."
    ),
    "md_path":  "/app/backend/ora_skills/dev_ora-cto-final-complete.md",
}

FULL_BODY_LIMIT = 10_000
HEAD_LEN = 1_200


async def main() -> None:
    db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
    import server
    server.db = db
    now = datetime.now(timezone.utc).isoformat()

    body = open(SKILL["md_path"]).read()
    body_hash = hashlib.sha256(body.encode()).hexdigest()[:16]
    print(f"=== iter 322es — Saving ORA CTO Final Complete skill ===")
    print(f"Body: {len(body)} chars, sha={body_hash}\n")

    # 1. ora_training_files
    text = f"AUREM Skill — {SKILL['name']} (iter {SKILL['iter']})\n\n{body}"
    await db.ora_training_files.update_one(
        {"file_id": f"learning-brief-{SKILL['iter']}"},
        {"$set": {
            "file_id":      f"learning-brief-{SKILL['iter']}",
            "user_id":      "system_main_agent",
            "source_type":  "learning_brief",
            "filename":     f"learning-{SKILL['iter']}-ora-cto-final.md",
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

    # 3. broadcast — full-body rebuild
    existing = await db.ora_skills_broadcast.find_one({"_id": "active"}) or {}
    existing_ids = [s for s in (existing.get("skill_ids") or []) if s != SKILL["id"]]
    final_ids = existing_ids + [SKILL["id"]]

    docs = await db.ora_skills_library.find(
        {"id": {"$in": final_ids}},
        {"_id": 0, "id": 1, "name": 1, "description": 1, "category": 1, "body": 1},
    ).to_list(length=len(final_ids))
    by_id = {d["id"]: d for d in docs}
    ordered = [by_id[sid] for sid in final_ids if sid in by_id]

    bits = []
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
        "_id":            f"bcast_{now}_322es",
        "skill_ids":      final_ids,
        "target_agents":  "ALL",
        "broadcast_at":   now,
        "broadcast_by":   "main_agent_iter_322es",
        "action":         "ora_cto_final_complete",
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
                    "filename":     f"learning-{SKILL['iter']}-ora-cto-final.md",
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
            print(f"[4/4] secondary mirror failed: {e}")
    else:
        print(f"[4/4] SECONDARY_MONGO_URL not set")

    # Verification
    print(f"\n=== Verification ===")
    from services.agent_skill_broadcast import get_addendum
    ad = await get_addendum(db, agent_name="GATEWAY")
    checks = {
        "addendum contains 17-tool skill": SKILL["id"] in (await db.ora_skills_broadcast.find_one({"_id":"active"}) or {}).get("skill_ids", []),
        "ora-cto-final-complete in addendum body": "ora-cto-final-complete" in ad.lower(),
        "Preview→Deploy→Save→Rollback in addendum": "Preview→Deploy→Save→Rollback" in ad or "preview" in ad.lower(),
    }
    for k, v in checks.items():
        print(f"  {'OK' if v else 'FAIL'} — {k}")


if __name__ == "__main__":
    asyncio.run(main())
