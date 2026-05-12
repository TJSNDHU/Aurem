# AUREM — ORA Learning Workflow (PERMANENT RULE)

**Status**: HARD RULE. Every future iteration MUST follow this.

After EVERY significant work session (bug fix, feature, refactor, deployment),
the lessons learned must be persisted into ORA's permanent memory across
all official channels — primary AND backup MongoDB.

---

## The 4 Mandatory Channels (Official, not custom)

### 1. `ora_training_files` (canonical learning corpus)
- Schema: `{file_id, user_id, source_type, filename, file_ext, file_category, language, purpose, status, crawled_text, text_chars, created_at}`
- Use `source_type="learning_brief"` and `purpose="ora_self_learning"`
- Stable `file_id = "learning-brief-<iter>"` so upsert is idempotent
- **This is the ONLY corpus the ORA training UI + embedding pipeline reads.**

### 2. `ora_skills_library` (AntiGravity skills — OFFICIAL schema)
- Required fields: `{id, name, category, description, body}` (NOT `title`/`addendum`)
- Stable `id = "aurem-<iter>-<slug>"`
- Matches the existing 1,453 Antigravity skills format so `/api/admin/antigravity-skills/broadcast` accepts them

### 3. `ora_skills_broadcast` (live system_addendum for ALL 28 agents)
- Singleton doc `_id="active"`, schema: `{skill_ids, system_addendum, target_agents, broadcast_at, skill_count}`
- **`target_agents` MUST be the string `"ALL"` NOT the list `["ALL"]`** (bug fix iter 322ef-bonus)
- Always MERGE with existing skills, never overwrite
- Call `services.agent_skill_broadcast.invalidate_cache()` after update
- Call `services.memoir_service.skill_broadcast_set(addendum, ids)` to mirror to Git-versioned memoir

### 4. SECONDARY Atlas mirror (`SECONDARY_MONGO_URL`)
- Configured at `.env:161` — "Backupmy" cluster (Kaur1985 account)
- Atlas tier has **500-collection HARD cap** — even when only 387 collections are visible, Atlas reserves additional slots; new collections can fail with `cannot create a new collection -- already using 500 collections of 500`
- **CONSEQUENCE**: New ORA collections may NOT mirror. Workaround: write all learnings to `ora_training_files` (already on secondary) — that's the canonical learning corpus and survives DR failover
- `ora_skills_library` + `ora_skills_broadcast` are LIVE config — recreated from `ora_training_files` on DR restore

---

## The Script

`/app/backend/scripts/teach_ora_iter_322.py` — template.

For every new iter (322eg, 322eh, etc.):
1. Copy the script to `scripts/teach_ora_iter_<new_iter>.py`
2. Replace the `LESSONS = [...]` block with the new iter's lessons
3. Run it: `cd /app/backend && set -a && source .env && set +a && python3 scripts/teach_ora_iter_<new>.py`
4. Verify with the embedded verification at the bottom of the script

## When to fire it

After EVERY iter that meets ANY of these criteria:
- Bug root cause discovered (the WHY, not just the fix)
- Pattern emerged that future agents should re-apply
- Workflow refined (better way to do X)
- Production-affecting change (deployment, perf, security)
- Architectural insight (why we chose path A over B)

Do NOT fire for trivial style changes, lint fixes, or single-line tweaks.

---

## Verification (post-run)

```python
# 1. ora_training_files on PRIMARY
await db.ora_training_files.count_documents({"source_type":"learning_brief"})

# 2. ora_training_files on SECONDARY (proves backup mirror)
from pymongo import MongoClient
s = MongoClient(os.environ["SECONDARY_MONGO_URL"])
print(s[db_name].ora_training_files.count_documents({"file_id":{"$regex":"^learning-brief-"}}))

# 3. Live broadcast picks up new skills
from services.agent_skill_broadcast import get_addendum
ad = await get_addendum(db, agent_name="GATEWAY")
# Should include the new skill IDs

# 4. End-to-end: call the LLM gateway with a Q the new skill answers — should cite the iter
```

## Iter index (running log)

| Iter | Date | Lessons |
|---|---|---|
| 322ea | 2026-02 | Atlas pool & scheduler hygiene (K8s probe fix) |
| 322ec | 2026-02 | LLM gateway response cache (1075x speedup) |
| 322ed | 2026-02 | Wire orphans into revenue products |
| 322ee | 2026-02 | DB dead-load cleanup (drop AND patch index-creators) |
| 322ef | 2026-02 | Official-schema teach + secondary-Atlas constraint discovery |

---

## Atlas 500-collection cap monitoring

The secondary cluster is approaching/at hard cap. Two long-term fixes:
1. **Upgrade Atlas tier** to M10+ (no cap)
2. **Prune secondary**: drop dead collections from secondary that no longer exist on primary (currently 113 phantom slots reserved)

Until then, all ORA learning rides on `ora_training_files` which is already on secondary.

---

**Last updated**: iter 322ef, 2026-02
**Owner**: main_agent
**Enforcement**: PRD.md references this file. Hard requirement.
