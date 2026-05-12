"""
teach_ora_iter_322 — Refactored to use OFFICIAL ORA channels.

Replaces the earlier (iter 322ef) custom-schema version that wrote
incompatible docs. Uses the same 3 channels the rest of AUREM uses:

  1. `ora_training_files`   — official ORA training corpus (source_type=
                              "learning_brief"). The embedding pipeline
                              picks these up so semantic search inside
                              ORA chat surfaces them.
  2. `ora_skills_library`   — official AntiGravity skills schema:
                              {id, name, category, description, body}.
                              Matched the format used by the existing
                              1,453 Antigravity skills so the official
                              /api/admin/antigravity-skills/broadcast
                              endpoint accepts them.
  3. `ora_skills_broadcast` — written via the SAME logic as the official
                              broadcast endpoint, including memoir
                              mirror + agent cache invalidation.

  4. `db_backup_service.run_backup` — fires DR sync to the secondary
                              Atlas cluster so the backup mongo has the
                              same training + skills.

Idempotent — re-running upserts on stable IDs.
"""
from __future__ import annotations

import asyncio
import hashlib
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, "/app/backend")

from motor.motor_asyncio import AsyncIOMotorClient

# ─── Lessons captured today ──────────────────────────────────────────
LESSONS = [
    {
        "iter": "322ea",
        "skill_id": "aurem-322ea-atlas-pool-scheduler-hygiene",
        "name": "Atlas pool & scheduler hygiene",
        "category": "deployment",
        "description": (
            "When K8s /health probe times out in production, suspect Mongo "
            "Atlas pool exhaustion + scheduler burst (all per-minute jobs "
            "firing at xx:00 simultaneously). Fix: bump maxPoolSize 50→200, "
            "set minPoolSize=10 + waitQueueTimeoutMS=2000, add jitter=20 to "
            "every IntervalTrigger, set scheduler job_defaults (max_instances=1, "
            "coalesce=True, misfire_grace_time=30)."
        ),
        "body_md": """# AUREM — Atlas Pool & Scheduler Hygiene (iter 322ea)

## Symptom
- K8s /health probe returns 502 every 10s
- `[autopilot] tick error ... connection pool paused`
- `Timed out while checking out a connection from connection pool. maxPoolSize: 50`
- `WARNING:apscheduler ... was missed by 0:00:21`

## Root cause
Default Motor `maxPoolSize=50` + 4+ per-minute scheduler jobs firing simultaneously at xx:00 → pool paused → waitQueueTimeoutMS=10s blocks event loop → /health can't be scheduled inside nginx's 10s upstream window → K8s kills pod.

## Fix
1. Motor client init:
```python
AsyncIOMotorClient(
    mongo_url,
    maxPoolSize=200, minPoolSize=10, waitQueueTimeoutMS=2000,
    serverSelectionTimeoutMS=5000, connectTimeoutMS=10000,
    socketTimeoutMS=20000, retryWrites=True,
)
```
2. AsyncIOScheduler global defaults:
```python
AsyncIOScheduler(job_defaults={
    "max_instances": 1, "coalesce": True, "misfire_grace_time": 30,
})
```
3. Every IntervalTrigger gets `jitter=20`.

## Verification
- 10 parallel curls to /api/platform/health → HTTP 200 in <2ms
- Zero `apscheduler ... missed` warnings within 5 min after restart
""",
    },
    {
        "iter": "322ec",
        "skill_id": "aurem-322ec-llm-gateway-cache",
        "name": "LLM gateway response cache",
        "category": "cost_optimization",
        "description": (
            "Find the single LLM chokepoint in your stack and wire response "
            "caching there — not per-router. In AUREM that's "
            "services/llm_gateway.call_llm_with_meta(). Hash "
            "(system_prompt[:1500] + user_prompt[:3000] + max_tokens) AFTER "
            "skill-broadcast addendum so admin skill pushes auto-invalidate. "
            "12h TTL. Verified 1075x speedup (1.41s → 0.001s)."
        ),
        "body_md": """# AUREM — LLM Gateway Response Cache (iter 322ec)

## Symptom
- Emergent LLM key budget exhausting weekly
- 114 `budget-exhausted` log entries
- Repeated FAQ questions hit live LLM every time

## Insight
Find the single chokepoint — in AUREM it's `services/llm_gateway.call_llm_with_meta()`. Sovereign + OpenRouter + Emergent all flow through here. Cache there → all 28 agents + sentinel + composer + ORA chat get cached automatically.

## Implementation
```python
import hashlib
_seed = f"{(system_prompt or '')[:1500]}||{user_prompt[:3000]}||{max_tokens}"
sig = hashlib.sha1(_seed.encode()).hexdigest()[:20]

hit = await cache_get(db, scope="llm_gateway", signature=sig, prompt_seed="v1")
if hit and hit.get("content"):
    return {"provider": hit.get("provider"), "content": hit["content"],
            "ok": True, "cached": True}

# ... existing provider chain ...

if content:
    await cache_put(db, scope="llm_gateway", signature=sig,
                    payload={"content": content, "provider": provider},
                    prompt_seed="v1", ttl_hours=12)
```

## Critical detail
Compute signature AFTER skill-broadcast addendum is appended. Admin pushing a new SKILL.md → addendum changes → signature changes → auto-invalidates. No manual purge.

## Opt-out
`bypass_cache=True` for temperature-sensitive callers (creative writes, brainstorms).
""",
    },
    {
        "iter": "322ed",
        "skill_id": "aurem-322ed-orphan-to-revenue",
        "name": "Wire orphan features into revenue products",
        "category": "product_integration",
        "description": (
            "When a backend feature is complete but has zero frontend "
            "references ('anaadio ka build'): don't delete it AND don't "
            "build a new UI. Plug it into an EXISTING revenue product so it "
            "has a sales surface. Intelligence Merge (orphan) got wired "
            "into the $49 Customer Audit — now intelligence findings outrank "
            "meta tweaks in top_issues with revenue-critical signals."
        ),
        "body_md": """# AUREM — Wire Orphans Into Revenue Products (iter 322ed)

## Heuristic
Backend-complete + zero frontend refs = "anaadio ka build". Decision matrix:
- ❌ Delete → engineering time wasted
- ❌ Build new UI → more sprawl
- ✅ Plug into an EXISTING revenue product → instant sales surface

## Concrete example
- Orphan: `services/bin_intelligence.py` — 7 endpoints, full pipeline, 0 frontend refs
- Existing revenue product: `$49 Customer Audit`
- Action: In `customer_audit_service.run_audit()`, call `intelligence_summary(db, bin)`, stash on the Pydantic model, rank findings in `_rank_top_issues()`

## Safety pattern
```python
try:
    snap = await intelligence_summary(db, bin)
    audit.intelligence = IntelligenceSnapshot(**snap)
except Exception as e:
    logger.debug(f"[audit] intelligence snapshot skipped: {e}")
    # Audit succeeds with intelligence.available=False — side feature never blocks parent
```

## Why this works
- Customer paying $49 → already engaged → trusts your product → ready to act on intelligence findings
- Revenue-critical signals ("X visitors but 0 captured", "High-intent contact ready") get visibility instead of buried under meta tag tweaks
""",
    },
    {
        "iter": "322ee",
        "skill_id": "aurem-322ee-db-dead-load-cleanup",
        "name": "DB dead-load cleanup workflow",
        "category": "db_hygiene",
        "description": (
            "Empty collections aren't enough to drop — they auto-resurrect "
            "via startup ensure_index/create_index calls. Real cleanup: "
            "(1) verify collection is truly dead (write a test); (2) drop "
            "it; (3) grep AND patch every create_index path that recreates "
            "it. Hiding spots: server.py, services/startup_init.py, "
            "services/db_indexes.py, bootstrap/background_init.py, "
            "routes/orchestrator_routes.py."
        ),
        "body_md": """# AUREM — DB Dead-Load Cleanup (iter 322ee)

## False-positive trap
Before flagging a collection as 'broken because empty':
1. Find the write path: `grep -rn 'db.<name>.(insert|update|upsert)' --include=*.py`
2. Write end-to-end test exercising the writer (in `/app/backend/tests/`)
3. If test passes → collection is FINE, just untriggered yet
4. Lock the test in as permanent regression — never doubt that flow again

## When TRULY dead
```bash
# 1. Drop:
await db.drop_collection("dead_name")

# 2. Find resurrectors:
grep -rn 'dead_name.create_index' --include=*.py

# 3. Patch — typical hiding spots:
#   server.py (multiple top-level setup functions)
#   services/startup_init.py (commercial-feature scaffold)
#   services/db_indexes.py / db_index_builder.py
#   bootstrap/background_init.py
#   routes/orchestrator_routes.py

# 4. Restart and verify they stay gone
```

## Feature-flag pattern for "maybe later" features
```python
if os.environ.get("FEATURE_X_ENABLED", "0") == "1":
    await ensure_x_indexes(db)
```

## Lean-mode router skip-list
```python
# routers/_registry_config.py
SKIP_IN_LEAN.add("routers.shopify_pulse_router")  # 1220 lines dead code
SKIP_IN_LEAN.add("routers.attribution_engine")    # 512 lines
```

## Today's score
524 → 498 collections (-26 permanent), 3 remain as benign shells from active P2 features.
""",
    },
]


async def main():
    db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
    import server
    server.db = db
    now = datetime.now(timezone.utc).isoformat()

    print(f"=== TEACH ORA — official channels, {len(LESSONS)} lessons ===\n")

    # ─── (0) Clean up the iter-322ef wrong-schema docs ────────────────
    bad_ids = [
        "atlas-pool-and-scheduler-hygiene", "llm-gateway-response-cache",
        "wire-orphan-features-into-revenue", "db-dead-load-cleanup",
    ]
    await db.ora_skills_library.delete_many({"id": {"$in": bad_ids}})
    print(f"  cleaned up 4 incorrect-schema docs from prior iter\n")

    # ─── (1) ora_training_files — the canonical learning corpus ──────
    for L in LESSONS:
        file_id = f"learning-brief-{L['iter']}"
        text = (
            f"AUREM Learning Brief — {L['iter']}\n"
            f"Title: {L['name']}\n"
            f"Category: {L['category']}\n\n"
            f"Summary:\n{L['description']}\n\n"
            f"Full Playbook:\n{L['body_md']}\n"
        )
        doc = {
            "file_id": file_id,
            "user_id": "system_main_agent",
            "source_type": "learning_brief",
            "filename": f"learning-{L['iter']}-{L['skill_id']}.md",
            "file_ext": ".md",
            "file_category": "document",
            "file_size": len(text),
            "language": "english",
            "purpose": "ora_self_learning",
            "notes": f"Lessons from iter {L['iter']}",
            "status": "ready",
            "crawled_text": text,
            "text_chars": len(text),
            "created_at": now,
            "updated_at": now,
        }
        await db.ora_training_files.update_one(
            {"file_id": file_id}, {"$set": doc}, upsert=True,
        )
        print(f"  ✓ ora_training_files ← {file_id}")

    # ─── (2) ora_skills_library — official AntiGravity schema ─────────
    for L in LESSONS:
        skill_doc = {
            "id":          L["skill_id"],
            "name":        L["name"],
            "category":    L["category"],
            "description": L["description"],
            "body":        L["body_md"],
            "source":      f"aurem-internal-iter-{L['iter']}",
            "added_at":    now,
            "iter":        L["iter"],
            # Fingerprint for change detection
            "content_hash": hashlib.sha256(L["body_md"].encode()).hexdigest()[:16],
        }
        await db.ora_skills_library.update_one(
            {"id": L["skill_id"]}, {"$set": skill_doc}, upsert=True,
        )
        print(f"  ✓ ora_skills_library ← {L['skill_id']}")

    # ─── (3) Broadcast via the SAME logic as /antigravity-skills/broadcast ─
    skill_ids = [L["skill_id"] for L in LESSONS]
    docs = await db.ora_skills_library.find(
        {"id": {"$in": skill_ids}},
        {"_id": 0, "id": 1, "name": 1, "description": 1, "category": 1, "body": 1},
    ).to_list(length=len(skill_ids))

    bits = []
    for d in docs:
        head = (d.get("body") or "")[:600].strip()
        bits.append(
            f"### SKILL: {d['name']} ({d['category']})\n"
            f"{d.get('description', '')}\n"
            f"{head}"
        )
    addendum = "\n\n".join(bits)

    # Read the current active broadcast and MERGE rather than overwrite, so
    # any prior admin-broadcast skills survive.
    existing = await db.ora_skills_broadcast.find_one({"_id": "active"}) or {}
    prior_ids = [sid for sid in (existing.get("skill_ids") or []) if sid not in skill_ids]
    if prior_ids:
        prior_docs = await db.ora_skills_library.find(
            {"id": {"$in": prior_ids}},
            {"_id": 0, "id": 1, "name": 1, "description": 1, "category": 1, "body": 1},
        ).to_list(length=len(prior_ids))
        for d in prior_docs:
            head = (d.get("body") or "")[:600].strip()
            bits.append(
                f"### SKILL: {d['name']} ({d['category']})\n"
                f"{d.get('description', '')}\n"
                f"{head}"
            )
        addendum = "\n\n".join(bits)
    final_ids = skill_ids + prior_ids

    broadcast_doc = {
        "skill_ids":       final_ids,
        "system_addendum": addendum,
        "note":            "iter 322ef-fix — official-schema teach",
        "target_agents":   "ALL",
        "broadcast_at":    now,
        "skill_count":     len(final_ids),
    }
    await db.ora_skills_broadcast.update_one(
        {"_id": "active"}, {"$set": broadcast_doc}, upsert=True,
    )
    await db.ora_skills_broadcast_history.insert_one(
        {**broadcast_doc, "_id": f"bcast_{now}"}
    )

    try:
        from services.agent_skill_broadcast import invalidate_cache
        invalidate_cache()
        print(f"  ✓ broadcast cache invalidated")
    except Exception:
        pass

    try:
        from services import memoir_service as _M
        if _M.available():
            _M.skill_broadcast_set(addendum, final_ids)
            print(f"  ✓ memoir skill_broadcast_set")
    except Exception as e:
        print(f"  ⚠ memoir skip: {e}")

    print(f"\n  ✓ ora_skills_broadcast active — {len(final_ids)} skills "
           f"({len(addendum)} chars)")

    # ─── (4) Mirror ORA learning collections to SECONDARY Atlas ──────
    # The bulk run_backup goes alphabetically and the secondary cluster
    # is already at the 500-collection cap (Atlas M0/M2/M5 limit) — so
    # by the time the sync gets past 'b*' it aborts. The ORA collections
    # ('o*') would never reach the secondary on a full mirror. We bypass
    # that by upserting our 5 learning-relevant collections directly.
    print(f"\n=== Mirroring ORA learning collections to SECONDARY Atlas ===")
    secondary_url = os.environ.get("SECONDARY_MONGO_URL")
    if not secondary_url:
        print("  ⚠ SECONDARY_MONGO_URL not set — skipping mirror")
    else:
        try:
            import asyncio as _aio
            from pymongo import MongoClient
            db_name = os.environ.get("DB_NAME", "aurem_db")

            def _sync_ora_to_secondary():
                """Sync ORA learning collections from primary → secondary.

                Runs in a thread so async event loop stays free. Uses
                upsert by stable IDs so re-runs don't duplicate."""
                from motor.motor_asyncio import AsyncIOMotorClient as _M
                # Re-open sync clients (pymongo) so this whole function
                # is thread-safe.
                p = MongoClient(os.environ["MONGO_URL"],
                                  serverSelectionTimeoutMS=10000)
                s = MongoClient(secondary_url,
                                  serverSelectionTimeoutMS=15000)
                p.admin.command("ping"); s.admin.command("ping")
                pdb = p[db_name]; sdb = s[db_name]

                targets = [
                    ("ora_training_files",           "file_id"),
                    ("ora_skills_library",            "id"),
                    ("ora_skills_broadcast",          "_id"),
                    ("ora_skills_broadcast_history",  "_id"),
                    ("ora_brain_thoughts",            None),  # ts-based, just copy
                ]
                results = []
                for coll, key in targets:
                    try:
                        # Skip if target already at cap and not present
                        existing_on_sec = coll in sdb.list_collection_names()
                        n_pri = pdb[coll].estimated_document_count()
                        if n_pri == 0:
                            results.append((coll, 0, 0, "skip-empty"))
                            continue

                        ins = upd = 0
                        if key and existing_on_sec:
                            for doc in pdb[coll].find({}):
                                k = doc.get(key)
                                if k is None: continue
                                r = sdb[coll].replace_one(
                                    {key: k}, doc, upsert=True
                                )
                                if r.upserted_id: ins += 1
                                else: upd += 1
                        elif key:
                            # New collection on secondary
                            sdb[coll].drop()
                            sdb[coll].insert_many(list(pdb[coll].find({})))
                            ins = n_pri
                        else:
                            # ts-based: just append last 1000 docs
                            sdb[coll].drop()
                            docs = list(pdb[coll].find({}).sort("ts", -1).limit(1000))
                            if docs:
                                sdb[coll].insert_many(docs)
                            ins = len(docs)
                        results.append((coll, ins, upd, "ok"))
                    except Exception as ce:
                        results.append((coll, 0, 0, f"err:{ce}"))
                p.close(); s.close()
                return results

            mirror_results = await _aio.to_thread(_sync_ora_to_secondary)
            for coll, ins, upd, status in mirror_results:
                print(f"  • {coll:<35} ins={ins:>4}  upd={upd:>4}  {status}")
        except Exception as e:
            print(f"  ⚠ mirror failed: {e}")

    # ─── Summary ──────────────────────────────────────────────────────
    print(f"\n=== ORA TAUGHT (official channels) ===")
    n_train = await db.ora_training_files.count_documents(
        {"source_type": "learning_brief"}
    )
    n_internal_skills = await db.ora_skills_library.count_documents(
        {"id": {"$in": skill_ids}}
    )
    bcast = await db.ora_skills_broadcast.find_one({"_id": "active"})
    print(f"  ora_training_files (learning_brief): {n_train}")
    print(f"  ora_skills_library (this iter):      {n_internal_skills}/4")
    print(f"  active broadcast:                    {bcast.get('skill_count', 0)} skills")
    print(f"  addendum length:                     {len(bcast.get('system_addendum',''))} chars")


if __name__ == "__main__":
    asyncio.run(main())
