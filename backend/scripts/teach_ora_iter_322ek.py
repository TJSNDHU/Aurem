"""
teach_ora_iter_322ek — Hard-save 2 critical skills:
  1. ora-tools-usage          (iter 322ej) — how to use the new tools
  2. zero-hallucination-charter (iter 322ek) — THE LAW (ranks first)

Charter MUST land at position [0] of skill_ids so it dominates the
system_addendum every LLM call.
"""
from __future__ import annotations

import asyncio
import hashlib
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, "/app/backend")

from motor.motor_asyncio import AsyncIOMotorClient


SKILLS = [
    # Order matters — Charter FIRST. The broadcast preserves this order.
    {
        "iter":     "322ek",
        "id":       "aurem-322ek-zero-hallucination-charter",
        "name":     "AUREM Core Law — Zero Hallucination Charter",
        "category": "core_law",
        "description": (
            "THE LAW. Hardcoded above all other skills. Every claim must come "
            "from a real tool invocation in this session — never from training "
            "data, never invented. Includes 10 practical rules + anti-patterns + "
            "escalation chain. When other skills conflict, this charter wins."
        ),
        "md_path":  "/app/backend/ora_skills/dev_zero-hallucination-charter.md",
    },
    {
        "iter":     "322ej",
        "id":       "aurem-322ej-ora-tools-usage",
        "name":     "ORA Read-Only Tool Surface (P1 — 9 working tools)",
        "category": "investigation_tools",
        "description": (
            "9 admin-gated read-only tools live at POST /api/ora-tools/execute: "
            "grep_codebase, view_file, view_dir, curl_internal, db_count, "
            "db_distinct, git_log, health_check, lint_python. All audit-logged "
            "to ora_tool_invocations. Path + collection allowlists enforced. "
            "Use these BEFORE answering any question about AUREM state."
        ),
        "md_path":  "/app/backend/ora_skills/dev_ora-tools-usage.md",
    },
]


async def main() -> None:
    db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
    import server
    server.db = db
    now = datetime.now(timezone.utc).isoformat()

    print(f"=== iter 322ej/322ek — Hard-saving 2 critical skills ===\n")

    # ── Channel 1+2: training files + skills library ─────────────────
    for S in SKILLS:
        body = open(S["md_path"]).read()
        body_hash = hashlib.sha256(body.encode()).hexdigest()[:16]

        # ora_training_files
        text = f"AUREM Skill — {S['name']} (iter {S['iter']})\n\n{body}"
        await db.ora_training_files.update_one(
            {"file_id": f"learning-brief-{S['iter']}"},
            {"$set": {
                "file_id":      f"learning-brief-{S['iter']}",
                "user_id":      "system_main_agent",
                "source_type":  "learning_brief",
                "filename":     f"learning-{S['iter']}-{S['id']}.md",
                "file_ext":     ".md",
                "file_category": "document",
                "file_size":    len(text),
                "language":     "english",
                "purpose":      "ora_self_learning",
                "notes":        S["description"][:200],
                "status":       "ready",
                "crawled_text": text,
                "text_chars":   len(text),
                "created_at":   now,
                "updated_at":   now,
            }},
            upsert=True,
        )
        print(f"[{S['iter']}] ora_training_files     ← {len(text)} chars")

        # ora_skills_library (official schema)
        await db.ora_skills_library.update_one(
            {"id": S["id"]},
            {"$set": {
                "id":           S["id"],
                "name":         S["name"],
                "category":     S["category"],
                "description":  S["description"],
                "body":         body,
                "source":       f"aurem-internal-iter-{S['iter']}",
                "added_at":     now,
                "iter":         S["iter"],
                "content_hash": body_hash,
            }},
            upsert=True,
        )
        print(f"[{S['iter']}] ora_skills_library     ← {S['id']}")

    # ── Channel 3: broadcast (Charter at index 0) ────────────────────
    new_ids = [S["id"] for S in SKILLS]   # [charter, tools-usage] order
    existing = await db.ora_skills_broadcast.find_one({"_id": "active"}) or {}
    existing_ids = [s for s in (existing.get("skill_ids") or []) if s not in new_ids]
    # Charter FIRST, tools-usage second, then everything else
    final_ids = new_ids + existing_ids

    docs = await db.ora_skills_library.find(
        {"id": {"$in": final_ids}},
        {"_id": 0, "id": 1, "name": 1, "description": 1, "category": 1, "body": 1},
    ).to_list(length=len(final_ids))
    by_id = {d["id"]: d for d in docs}
    ordered = [by_id[sid] for sid in final_ids if sid in by_id]

    bits: list[str] = []
    for i, d in enumerate(ordered):
        # Charter gets larger head (it's the law) — everyone else 600 chars
        head_chars = 1200 if "zero-hallucination" in d["id"] else 600
        head = (d.get("body") or "")[:head_chars].strip()
        prefix = "## ⚖️ CORE LAW (read first):\n" if i == 0 else ""
        bits.append(
            f"{prefix}### SKILL: {d['name']} ({d['category']})\n"
            f"{d.get('description', '')}\n{head}"
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
        }},
        upsert=True,
    )
    await db.ora_skills_broadcast_history.insert_one({
        "_id":           f"bcast_{now}_322ek",
        "skill_ids":     final_ids,
        "target_agents": "ALL",
        "broadcast_at":  now,
        "broadcast_by":  "main_agent_iter_322ek",
        "action":        "broadcast_charter_first",
    })

    try:
        from services.agent_skill_broadcast import invalidate_cache
        invalidate_cache()
        print(f"\n[broadcast] cache invalidated — next LLM call sees new skills")
    except Exception:
        pass

    print(f"[broadcast] active = {len(final_ids)} skills, "
          f"{len(addendum)} chars, charter@index0 = "
          f"{final_ids[0] == 'aurem-322ek-zero-hallucination-charter'}")

    # ── Channel 4: SECONDARY Atlas mirror ────────────────────────────
    print(f"\n=== Mirror to SECONDARY Atlas ===")
    sec_url = os.environ.get("SECONDARY_MONGO_URL")
    if not sec_url:
        print("  ⚠ SECONDARY_MONGO_URL not set — skipping")
    else:
        from pymongo import MongoClient

        def _mirror() -> dict:
            sec = MongoClient(sec_url, serverSelectionTimeoutMS=15000)
            sdb = sec[os.environ.get("DB_NAME", "aurem_db")]
            results = {}
            for S in SKILLS:
                text = (f"AUREM Skill — {S['name']} (iter {S['iter']})\n\n"
                        + open(S["md_path"]).read())
                existing = sdb.ora_training_files.find_one(
                    {"file_id": f"learning-brief-{S['iter']}"}
                )
                doc = {
                    **(existing or {}),
                    "file_id":      f"learning-brief-{S['iter']}",
                    "user_id":      "system_main_agent",
                    "source_type":  "learning_brief",
                    "filename":     f"learning-{S['iter']}-{S['id']}.md",
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
                if not existing:
                    doc["created_at"] = now
                sdb.ora_training_files.replace_one(
                    {"file_id": f"learning-brief-{S['iter']}"},
                    doc, upsert=True,
                )
                results[S["iter"]] = "mirrored"
            sec.close()
            return results

        try:
            r = await asyncio.to_thread(_mirror)
            for iter_id, status in r.items():
                print(f"  [{iter_id}] secondary ora_training_files ← {status}")
        except Exception as e:
            print(f"  ⚠ secondary mirror failed: {e}")

    # ── Final verification — count records on BOTH clusters ──────────
    print(f"\n=== Verification ===")
    for S in SKILLS:
        n_pri = await db.ora_training_files.count_documents(
            {"file_id": f"learning-brief-{S['iter']}"}
        )
        n_skill = await db.ora_skills_library.count_documents({"id": S["id"]})
        print(f"  PRIMARY  [{S['iter']}]  training_files={n_pri}  skills_library={n_skill}")

    bcast = await db.ora_skills_broadcast.find_one({"_id": "active"})
    print(f"  PRIMARY  broadcast: {bcast.get('skill_count')} skills, "
          f"charter@0 = {bcast.get('charter_first')}")

    if sec_url:
        from pymongo import MongoClient

        def _check() -> dict:
            sec = MongoClient(sec_url, serverSelectionTimeoutMS=15000)
            sdb = sec[os.environ.get("DB_NAME", "aurem_db")]
            r = {}
            for S in SKILLS:
                r[S["iter"]] = sdb.ora_training_files.count_documents(
                    {"file_id": f"learning-brief-{S['iter']}"}
                )
            sec.close()
            return r

        r = await asyncio.to_thread(_check)
        for iter_id, n in r.items():
            print(f"  SECONDARY [{iter_id}]  training_files={n}")


if __name__ == "__main__":
    asyncio.run(main())
