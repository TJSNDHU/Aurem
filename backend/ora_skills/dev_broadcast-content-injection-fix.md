# AUREM SKILL: broadcast-content-injection-fix (iter 322ep)

## Why this skill exists
The broadcast pipeline (`/api/admin/antigravity-skills/broadcast`) was
hiding ORA's most important rules behind a silent truncation. Every
broadcasted skill's body was sliced to the FIRST 600 chars before being
written to `ora_skills_broadcast.system_addendum`. The `developer-
engineering-protocol` skill is 9,690 chars — its mandatory 3-proof
verification block lives at ~6,700 chars deep. So even though the skill
was "active", the 3-proof rules never reached the LLM's system prompt.
ORA happily hallucinated `Lint / Test / Integration` as the 3 proofs.

## Detection
Founder asked: *"What is the developer-engineering-protocol's mandatory
3-proof verification block?"* ORA invented three plausible-but-wrong
proofs. The skill body in `ora_skills_library` was correct (3-proof
block present). The skill **id** was in `ora_skills_broadcast.skill_ids`.
But `system_addendum` did not contain the words `git log` or
`platform/health`. **Verified by `grep` against the addendum string,
not by counting rows.**

## Root cause
`routers/antigravity_skills_router.py` `broadcast_skills()`:

```python
# BUG (pre-322ep):
head = (d.get("body") or "")[:600].strip()
```

A 600-char head only captures the skill's preamble. All operational
rules deeper in the body are silently discarded.

## Fix
```python
# 322ep:
FULL_BODY_LIMIT = 10_000
HEAD_LEN = 1_200
for d in docs:
    body = (d.get("body") or "").strip()
    if len(body) <= FULL_BODY_LIMIT:
        content = body
    else:
        content = body[:HEAD_LEN].strip() + "\n[...truncated for size...]"
```

Total addendum across 15 active skills is now ~54 KB — well within any
LLM context window (200K Claude, 128K Groq, 1M Gemini).

## Permanent ORA rules from this lesson

1. **NEVER trust "the skill is broadcast"** as a proxy for "the LLM
   sees the rules". The only valid proof is a real string-grep against
   the **actual `system_addendum` string** the gateway uses.
2. **When teaching new skills**, verify after broadcast:
   ```python
   addendum = await get_addendum(db, agent_name="GATEWAY")
   assert "expected literal string from skill" in addendum
   ```
3. **The teach_ora_iter_<X>.py scripts** must rebuild the broadcast
   with the full-body logic. Old scripts (iter 322eo and earlier) used
   the buggy 600-char truncation — when you re-run them they will
   silently re-introduce the bug. Always copy the FIXED truncation
   block from `routers/antigravity_skills_router.py:broadcast_skills`.
4. **Test retention with a real LLM call** before claiming a teach
   succeeded. Ask ORA a question that requires content from past the
   600-char mark of the skill body. If ORA invents a plausible-wrong
   answer, the truncation regression is back.

## Verification recipe
```python
# 1. Real string match — not row count
ad = await get_addendum(db, agent_name="GATEWAY")
assert "git log --oneline -3" in ad
assert "/api/platform/health" in ad

# 2. LLM behaviour test — bypass cache so cached old answer can't lie
res = await call_llm_with_meta(sys_p, query, bypass_cache=True)
assert "git log" in res["content"] and "oneline" in res["content"]
```

If either fails → DO NOT claim the skill is "taught". Fix the broadcast
content first.

## Why this matters for the founder
- Hallucinated answers from ORA = lost trust = paid customer churn.
- Every "I taught ORA X" claim must be backed by a behaviour test, not
  a count of upserts.
- Teach pipelines that look correct on paper but truncate content
  silently are worse than not teaching at all — they create the
  illusion of memory.

---
**Status**: Permanent. Bake into every teach_ora_iter_<X>.py going forward.
**Owner**: AUREM main agent
**Enforcement**: Run the verification recipe after every broadcast push.
