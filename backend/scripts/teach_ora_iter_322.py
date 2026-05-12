"""
iter 322ef — Teach ORA today's work so future agents can reproduce.

Three persistence layers fire in parallel:

1. ora_brain_thoughts (ora_universal_learner) — one short learnable
   thought per iteration. Future ORA decisions index against these.

2. memoir-ai versioned memory (services/memoir_service) — full prose
   playbook stored at `learnings/2026-02/iter-322ea-ee` with a Git
   commit so the timeline is queryable.

3. ora_skills_library + ora_skills_broadcast — 4 new permanent
   Antigravity skills written into the library and broadcast to all
   28 agents so the system_addendum picks them up on the next call.

Run once: `python -m scripts.teach_ora_iter_322`
Idempotent — re-running upserts, doesn't duplicate.
"""
from __future__ import annotations

import asyncio
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, "/app/backend")

from motor.motor_asyncio import AsyncIOMotorClient


# ─── The 4 lessons learned today ─────────────────────────────────────
LESSONS = [
    {
        "iter": "322ea",
        "title": "K8s probe timeout = MongoDB Atlas pool exhaustion + scheduler burst",
        "category": "deployment_stability",
        "skill_id": "atlas-pool-and-scheduler-hygiene",
        "summary": (
            "K8s /health probe was timing out every 10s in production. Root cause "
            "wasn't the handler — it was that 4+ APScheduler jobs all fired at xx:00 "
            "and simultaneously checked out Mongo Atlas connections; pool maxed at 50, "
            "paused, waitQueueTimeoutMS=10s blocked the event loop, /api/platform/health "
            "couldn't be scheduled inside nginx's 10s upstream timeout window. K8s "
            "marked the pod unhealthy and restart-looped."
        ),
        "playbook": """# Atlas Pool & Scheduler Hygiene (iter 322ea)

## Symptom
- Production K8s probe `/health` returns 502 every 10s
- Backend logs show: `[autopilot] tick error ... connection pool paused`
- `Timed out while checking out a connection from connection pool. maxPoolSize: 50, timeout: 10.0`
- `WARNING:apscheduler ... was missed by 0:00:21` (multiple jobs missing on same tick)

## Root cause
- Default Motor `maxPoolSize=50` is too small for Atlas + N background jobs
- All `IntervalTrigger(seconds=60)` jobs fire at xx:00 simultaneously
- `waitQueueTimeoutMS=10s` (default) blocks the event loop while waiting for a connection
- /health endpoint can't be scheduled in time → nginx 10s upstream timeout → K8s kills pod

## Fix
1. **Bump Mongo client pool**:
   ```python
   AsyncIOMotorClient(
       mongo_url,
       maxPoolSize=200,         # was 50
       minPoolSize=10,          # warm connections, no cold-start
       waitQueueTimeoutMS=2000, # fail fast — never block loop > 2s
       serverSelectionTimeoutMS=5000,
       connectTimeoutMS=10000,
       socketTimeoutMS=20000,
       retryWrites=True,
   )
   ```

2. **AsyncIOScheduler global job_defaults**:
   ```python
   AsyncIOScheduler(job_defaults={
       "max_instances": 1,
       "coalesce": True,
       "misfire_grace_time": 30,
   })
   ```

3. **Add jitter to every per-minute job** so they don't all fire at xx:00:
   ```python
   IntervalTrigger(seconds=60, jitter=20)
   ```

## Verification
- 10 parallel curls to /api/platform/health → all HTTP 200 in <2ms
- No `apscheduler ... missed` warnings within 5 min after restart
- Pod stays alive past probe interval × 5

## Files touched
- `backend/server.py` (Motor client init)
- `backend/routers/registry.py` (scheduler defaults + 3 IntervalTriggers)
- `backend/services/ora_proposal_bridge.py` (watchdog re-arm jitter)
- `backend/services/nightly_cycle.py` (periodic_flush jitter)
""",
    },
    {
        "iter": "322ec",
        "title": "Wire LLM response cache at the gateway chokepoint, not per-router",
        "category": "cost_optimization",
        "skill_id": "llm-gateway-response-cache",
        "summary": (
            "Emergent LLM key budget kept burning even after wiring "
            "llm_response_cache into one router. Real fix: hook the cache at "
            "services/llm_gateway.call_llm_with_meta() — the single chokepoint "
            "every agent/sentinel/composer call passes through. Sha1 the "
            "(system_prompt[:1500] + user_prompt[:3000] + max_tokens) tuple, "
            "compute it AFTER skill-broadcast addendum so admin pushes auto-"
            "invalidate. 12h TTL. Validated 1075x speedup (1.41s → 0.001s)."
        ),
        "playbook": """# LLM Gateway Response Cache (iter 322ec)

## Symptom
- Emergent LLM Key budget exhausting weekly
- Repeated FAQ-style questions hit Claude/Groq every time
- Wrapping individual routers with a cache only solves a tiny slice

## Insight
Find the **single chokepoint** in the LLM stack. In AUREM it's
`services/llm_gateway.call_llm_with_meta()` — Sovereign + OpenRouter + Emergent
all flow through here. Cache there → ALL 28 agents + sentinel + composer +
ORA chat get cached automatically.

## Recipe
```python
# In call_llm_with_meta(), AFTER the skill-broadcast addendum is appended:
import hashlib
_seed = f"{(system_prompt or '')[:1500]}||{user_prompt[:3000]}||{max_tokens}"
sig = hashlib.sha1(_seed.encode()).hexdigest()[:20]

# Read
hit = await cache_get(db, scope="llm_gateway", signature=sig, prompt_seed="v1")
if hit and hit.get("content"):
    return {"provider": hit.get("provider","cache"),
            "content": hit["content"], "ok": True, "cached": True}

# ... call providers ...

# Write on success
await cache_put(db, scope="llm_gateway", signature=sig,
                payload={"content": content, "provider": provider},
                prompt_seed="v1", ttl_hours=12)
```

## Why compute sig AFTER skill addendum?
Admin pushes a SKILL.md → addendum changes → cache signature changes →
auto-invalidates only the answers that depended on the old prompt. No
manual purge needed.

## When to bypass
Add `bypass_cache=True` kwarg for temperature-sensitive callers (creative
writes, brainstorming). Never set it globally.

## Verification
```python
# Same prompt twice should produce ~1000x speedup on second call:
t1 = time.time(); r1 = await call_llm_with_meta(s, u); e1 = time.time()-t1
t2 = time.time(); r2 = await call_llm_with_meta(s, u); e2 = time.time()-t2
assert r2.get("cached") is True
assert e2 < e1 / 100
```
""",
    },
    {
        "iter": "322ed",
        "title": "Wire orphan backend features into revenue products, don't delete",
        "category": "feature_integration",
        "skill_id": "wire-orphan-features-into-revenue",
        "summary": (
            "Intelligence Merge engine was backend-complete but had zero "
            "frontend references — pure 'anaadio ka build' (engineer built "
            "the pipeline, never built the UI). Solution: wire it into the "
            "existing $49 Customer Audit product so customers see Intelligence "
            "alongside SEO/Ads. Now the engine has a revenue surface + "
            "Top-Issues outranks meta tweaks with revenue-critical findings "
            "('X visitors but 0 captured', 'high-intent contact ready')."
        ),
        "playbook": """# Wire Orphan Backend Features into Revenue Products (iter 322ed)

## Heuristic
When you find a backend-complete feature with **zero frontend refs**:
- ❌ Don't delete it (engineer time invested)
- ❌ Don't build a brand-new UI (more sprawl)
- ✅ Wire it into an EXISTING revenue product so it has a sales surface

## Concrete example
- Intelligence Merge: `services/bin_intelligence.py` — 7 endpoints, full data
  pipeline, 0 frontend refs → **dead until plugged into something user-facing**.
- Customer Audit ($49): existing revenue product running daily for paying users.
- Action: in `services/customer_audit_service.run_audit()`, call
  `intelligence_summary(db, bin)` and stash result on the `CustomerAudit`
  Pydantic model. Surface revenue-critical findings via `_rank_top_issues()`
  so the customer sees "X visitors today, 0 captured" instead of "missing alt tags".

## Pattern
1. Add Pydantic model for the snapshot (don't leak raw service shape into API).
2. Add a single field on the parent revenue object.
3. In the parent's main flow, call the orphan service inside a try/except — the
   orphan MUST NEVER block the parent's success. Side-feature degrades silently.
4. Rank the orphan's findings into the parent's top_issues so it earns visibility.
5. Frontend: add a sub-section, not a new page.

## Always-on safety
```python
try:
    audit.intelligence = IntelligenceSnapshot(**snap)
except Exception as e:
    logger.debug(f"[audit] intelligence snapshot skipped: {e}")
    # audit succeeds with intelligence.available=False
```
""",
    },
    {
        "iter": "322ee",
        "title": "Dead-load cleanup: drop AND patch index-creators to stop resurrection",
        "category": "db_hygiene",
        "skill_id": "db-dead-load-cleanup",
        "summary": (
            "Empty collections aren't enough to drop — they auto-resurrect "
            "via startup ensure_index() calls. Real cleanup = (1) drop the "
            "collection, (2) find AND patch every create_index/insert path "
            "that recreates it. Today went 524 → 498 collections by editing "
            "6 files. Also: verify 'broken' collections actually are broken "
            "before fixing — token_blocklist + dnc_list were just empty "
            "because no real user trigger had fired yet."
        ),
        "playbook": """# DB Dead-Load Cleanup (iter 322ee)

## False-positive trap
Before flagging a collection as 'broken because empty':
1. Find the write path: `grep -rn 'db.<name>.(insert|update|upsert)' --include=*.py`
2. Write an end-to-end test that exercises the writer
3. If the test passes → the collection is FINE, just untriggered by users yet
4. Lock the test in `/app/backend/tests/` as permanent regression

## When it IS truly dead
1. Drop the collection: `await db.drop_collection("name")`
2. **Find the resurrectors**: `grep -rn '<name>.create_index' --include=*.py`
3. Patch every resurrector — typical hiding spots:
   - `server.py` (multiple top-level setup functions)
   - `services/startup_init.py` (commercial-feature scaffold)
   - `services/db_indexes.py` / `db_index_builder.py` (bulk index lists)
   - `bootstrap/background_init.py` (post-boot setup)
   - `routes/orchestrator_routes.py` (subsystem init)
4. Add `os.environ.get("FEATURE_X_ENABLED")` gates for indexes that should
   come back when the feature is opted-in.

## Lean-mode skip-list pattern
For routers that are dead-code but kept for tests:
```python
# routers/_registry_config.py
SKIP_IN_LEAN.add("routers.shopify_pulse_router")  # 1220 lines of dead code
SKIP_IN_LEAN.add("routers.attribution_engine")    # 512 lines
```

## Verification loop
```python
# Before restart
n_before = await db.list_collection_names()
# Drop + patch + restart
# After 5s grace, recount
n_after = await db.list_collection_names()
gone = set(targets) - set(n_after)
still_back = set(targets) & set(n_after)
# 'still_back' = patches missed at least one resurrector
```

## Today's score
524 → 498 collections (-26), 3 remain as benign index-shells from active P2 feature.
""",
    },
]


async def main():
    db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
    import server
    server.db = db
    now = datetime.now(timezone.utc).isoformat()

    print(f"=== Teaching ORA — {len(LESSONS)} lessons from today ===\n")

    # ── (1) ora_brain_thoughts via universal learner ──────────────────
    from services.ora_universal_learner import ora_learn, set_db as set_learner_db
    set_learner_db(db)
    for L in LESSONS:
        await ora_learn({
            "source": "main_agent_iter_322",
            "event": "DEV_LEARNING",
            "category": L["category"],
            "summary": f"[{L['iter']}] {L['title']}: {L['summary']}",
            "outcome": "shipped",
            "agent": "ora_core",
            "bin_id": "system",
            "confidence": 0.95,
        })
        print(f"  ✓ ora_brain_thoughts ← {L['iter']}: {L['title'][:60]}")

    # ── (2) memoir-ai versioned long-term memory ──────────────────────
    try:
        from services import memoir_service
        for L in LESSONS:
            memoir_service.remember(
                path=("learnings", "2026-02", f"iter-{L['iter']}"),
                key="playbook",
                value={
                    "title": L["title"],
                    "category": L["category"],
                    "iter": L["iter"],
                    "playbook_md": L["playbook"],
                    "ts": now,
                },
            )
            print(f"  ✓ memoir            ← learnings/2026-02/iter-{L['iter']}")
        commit_sha = memoir_service.commit(
            f"iter-322ef: teach ORA — {len(LESSONS)} lessons from 322ea-ee"
        )
        if commit_sha:
            print(f"  ✓ memoir commit     {commit_sha[:12]}")
    except Exception as e:
        print(f"  ⚠ memoir skipped: {e}")

    # ── (3) ora_skills_library — permanent skills + auto-broadcast ────
    skill_ids = []
    for L in LESSONS:
        skill_doc = {
            "id": L["skill_id"],
            "title": L["title"],
            "category": L["category"],
            "addendum": (
                f"## SKILL: {L['title']}\n"
                f"_({L['iter']} learning, applies to all repair/audit/cost/health agents)_\n\n"
                f"{L['summary']}\n\n"
                f"See library entry `{L['skill_id']}` for full playbook."
            ),
            "addendum_chars": 0,
            "target_agents": "ALL",
            "playbook_md": L["playbook"],
            "added_at": now,
            "iter": L["iter"],
        }
        skill_doc["addendum_chars"] = len(skill_doc["addendum"])
        await db.ora_skills_library.update_one(
            {"id": L["skill_id"]},
            {"$set": skill_doc},
            upsert=True,
        )
        skill_ids.append(L["skill_id"])
        print(f"  ✓ ora_skills_library ← {L['skill_id']}")

    # ── (3b) Wire all 4 skills into active broadcast addendum ─────────
    # The gateway picks this up on the next call automatically.
    addendums = []
    for L in LESSONS:
        doc = await db.ora_skills_library.find_one({"id": L["skill_id"]}, {"_id": 0})
        if doc and doc.get("addendum"):
            addendums.append(doc["addendum"])

    system_addendum = (
        "\n\n# ── Antigravity Skills (live broadcast) ──\n"
        + "\n\n---\n\n".join(addendums)
    )
    await db.ora_skills_broadcast.update_one(
        {"_id": "active"},
        {"$set": {
            "_id": "active",
            "system_addendum": system_addendum,
            "skill_ids": skill_ids,
            "target_agents": "ALL",  # broadcast convention — string, not list
            "broadcast_at": now,
            "broadcast_by": "main_agent_iter_322ef",
            "skill_count": len(skill_ids),
        }},
        upsert=True,
    )
    await db.ora_skills_broadcast_history.insert_one({
        "ts": now,
        "skill_ids": skill_ids,
        "target_agents": "ALL",
        "broadcast_by": "main_agent_iter_322ef",
        "action": "broadcast",
    })
    # Invalidate the in-process broadcast cache so the gateway picks up the
    # new addendum on the very next call.
    try:
        from services.agent_skill_broadcast import invalidate_cache
        invalidate_cache()
    except Exception:
        pass
    print(f"\n  ✓ ora_skills_broadcast updated — {len(skill_ids)} skills active for ALL agents")

    # ── Final summary ─────────────────────────────────────────────────
    print(f"\n=== ORA TAUGHT ===")
    n_thoughts = await db.ora_brain_thoughts.count_documents(
        {"source": "main_agent_iter_322"}
    )
    n_skills = await db.ora_skills_library.count_documents({})
    bcast = await db.ora_skills_broadcast.find_one({"_id": "active"})
    print(f"  ora_brain_thoughts (this run): {n_thoughts}")
    print(f"  ora_skills_library total:     {n_skills}")
    print(f"  active broadcast skills:      {bcast.get('skill_count', 0) if bcast else 0}")
    print(f"  memoir commit:                see above")


if __name__ == "__main__":
    asyncio.run(main())
