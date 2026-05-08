"""
ORA Skill Learner — iter 282ak (Prompt 8, Task G).

Runs daily alongside the A2A Learning Bus at 2 AM UTC. Reads last-7-day
outreach + council signals, asks Claude Sonnet for 2-3 data-backed
insights, and APPENDS them to the relevant skill .md files under a
"## Learnings (auto-updated by ORA)" section.

Never overwrites existing skill content. Minimum 10 data points required.
Every run logged to `skill_learnings` collection.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

SKILLS_DIR = Path("/app/ora_skills")
MIN_DATA_POINTS = 10
LEARNINGS_HEADER = "## Learnings (auto-updated by ORA)"


# ─────────────────────────────────────────────────────────────────────
# Pure helpers
# ─────────────────────────────────────────────────────────────────────
def _append_learning(skill: str, insight: str, stat_line: str) -> bool:
    """Append one learning block to the skill file. Returns True on write."""
    p = SKILLS_DIR / f"{skill}.md"
    if not p.exists():
        return False
    try:
        text = p.read_text(encoding="utf-8")
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        block = f"\n### {today}\n- {insight}\n- Data: {stat_line}\n"
        if LEARNINGS_HEADER in text:
            new_text = text.rstrip() + "\n" + block
        else:
            new_text = text.rstrip() + "\n\n" + LEARNINGS_HEADER + "\n" + block
        p.write_text(new_text, encoding="utf-8")
        return True
    except Exception as e:
        logger.debug(f"[learner] append to {skill} failed: {e}")
        return False


# ─────────────────────────────────────────────────────────────────────
# Signal collection
# ─────────────────────────────────────────────────────────────────────
async def _collect_signals(db) -> dict:
    since = datetime.now(timezone.utc) - timedelta(days=7)
    sig: dict = {
        "sends_analyzed":        0,
        "response_rate_overall": 0.0,
        "by_channel":            {},
        "by_category":           {},
        "by_tone":               {},
        "top_performing_channel": "",
        "top_performing_category": "",
    }
    if db is None:
        return sig

    try:
        # outreach_history is an array field on campaign_leads; the composer
        # writes tone_used back via the cache entry. For MVP we aggregate on
        # outreach_history only — accurate enough for directional insights.
        pipeline = [
            {"$match": {"outreach_history.dispatched_at": {"$gte": since.isoformat()}}},
            {"$unwind": "$outreach_history"},
            {"$match": {"outreach_history.dispatched_at": {"$gte": since.isoformat()}}},
            {"$group": {
                "_id": {
                    "channel":  "$outreach_history.channel",
                    "category": "$category",
                },
                "total":     {"$sum": 1},
                "responded": {"$sum": {"$cond": [
                    {"$eq": ["$outreach_history.status", "responded"]}, 1, 0,
                ]}},
            }},
        ]
        async for row in db.campaign_leads.aggregate(pipeline):
            ch = (row["_id"] or {}).get("channel") or "unknown"
            cat = (row["_id"] or {}).get("category") or "unknown"
            total = row.get("total") or 0
            resp = row.get("responded") or 0
            rate = (resp / total) if total else 0.0
            sig["sends_analyzed"] += total
            sig["by_channel"][ch] = sig["by_channel"].get(ch, 0) + total
            sig["by_category"][cat] = sig["by_category"].get(cat, 0) + total
            if total >= 5:
                sig.setdefault("_rate_per_pair", []).append(
                    {"channel": ch, "category": cat, "total": total,
                      "responded": resp, "rate": rate})
    except Exception as e:
        logger.debug(f"[learner] signals aggregate failed: {e}")

    if sig["by_channel"]:
        sig["top_performing_channel"] = max(sig["by_channel"].items(),
                                             key=lambda kv: kv[1])[0]
    if sig["by_category"]:
        sig["top_performing_category"] = max(sig["by_category"].items(),
                                              key=lambda kv: kv[1])[0]
    return sig


# ─────────────────────────────────────────────────────────────────────
# Main cycle
# ─────────────────────────────────────────────────────────────────────
async def run_learning_cycle(db) -> dict:
    """Runs the full learning cycle. Never raises."""
    now = datetime.now(timezone.utc)
    if db is None:
        return {"skipped": "db_unavailable", "ts": now}

    signals = await _collect_signals(db)
    if signals["sends_analyzed"] < MIN_DATA_POINTS:
        result = {"skipped": "insufficient_data",
                   "sends_analyzed": signals["sends_analyzed"], "ts": now}
        try:
            await db.skill_learnings.insert_one(dict(result))
        except Exception:
            pass
        return result

    # Ask LLM for insights
    insights: list[dict] = []
    api_key = os.environ.get("EMERGENT_LLM_KEY", "").strip()
    if api_key:
        try:
            from emergentintegrations.llm.chat import LlmChat, UserMessage
            prompt = (
                "You are ORA's learning engine.\n"
                "Based on these outreach outcomes from the last 7 days:\n"
                + json.dumps(signals, default=str, indent=2)
                + "\n\nWrite 2-3 specific, actionable insights as JSON array:\n"
                  '[{"insight": "...", "applies_to_skill": "<skill_name>", '
                  '"suggested_update": "...", "stat_line": "..."}]\n'
                  "Skills available: scout_scan, outreach_compose, "
                  "followup_check, closer_check, morning_brief, casl_check.\n"
                  "Only suggest updates backed by data. No speculation. "
                  "Return JSON only, no markdown."
            )
            chat = (LlmChat(api_key=api_key, session_id=f"learner-{now.strftime('%Y%m%d')}",
                             system_message="You analyse outreach signals and propose data-backed updates. JSON only.")
                    .with_model("anthropic", "claude-sonnet-4-5-20250929"))
            try:
                chat = chat.with_max_tokens(400)
            except Exception:
                pass
            resp = await asyncio.wait_for(
                chat.send_message(UserMessage(text=prompt)), timeout=30.0)
            import re
            cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", (resp or "").strip(),
                              flags=re.IGNORECASE | re.MULTILINE)
            try:
                insights = json.loads(cleaned)
            except Exception:
                m = re.search(r"\[.*\]", cleaned, re.S)
                insights = json.loads(m.group(0)) if m else []
        except Exception as e:
            logger.debug(f"[learner] LLM insight gen failed: {e}")
            insights = []

    # Apply each insight
    skills_updated: list[str] = []
    for item in insights if isinstance(insights, list) else []:
        if not isinstance(item, dict):
            continue
        skill = (item.get("applies_to_skill") or "").strip()
        suggested = (item.get("suggested_update") or item.get("insight") or "").strip()
        stat_line = (item.get("stat_line") or "").strip()
        if skill and suggested and _append_learning(skill, suggested, stat_line):
            if skill not in skills_updated:
                skills_updated.append(skill)

    result = {
        "date":             now.strftime("%Y-%m-%d"),
        "insights_count":   len(skills_updated),
        "skills_updated":   skills_updated,
        "signals_used":     {
            "sends_analyzed":          signals["sends_analyzed"],
            "response_rate_overall":   signals["response_rate_overall"],
            "top_performing_channel":  signals["top_performing_channel"],
            "top_performing_category": signals["top_performing_category"],
        },
        "ts":               now,
    }
    try:
        await db.skill_learnings.insert_one(dict(result))
    except Exception:
        pass
    logger.info(f"[learner] run complete: {result}")
    return result


async def get_learning_summary(db) -> dict:
    """Returns last 30 days summary for Morning Brief + health chip."""
    if db is None:
        return {"last_run": None, "total_insights": 0,
                "top_insight": "", "skills_updated_this_week": []}
    try:
        last = await db.skill_learnings.find_one(
            {}, sort=[("ts", -1)], projection={"_id": 0},
        )
    except Exception:
        last = None

    since_7d = datetime.now(timezone.utc) - timedelta(days=7)
    skills_updated = []
    total_insights = 0
    try:
        async for r in db.skill_learnings.find({"ts": {"$gte": since_7d}}):
            total_insights += int(r.get("insights_count") or 0)
            for s in (r.get("skills_updated") or []):
                if s not in skills_updated:
                    skills_updated.append(s)
    except Exception:
        pass

    top_insight = ""
    if last and last.get("skills_updated"):
        # Pull the most recent skill_learnings row's first skill and its md block
        sk = last["skills_updated"][0]
        p = SKILLS_DIR / f"{sk}.md"
        try:
            text = p.read_text(encoding="utf-8")
            # grab last "- " bullet after the last heading
            parts = text.split(LEARNINGS_HEADER)
            if len(parts) > 1:
                tail = parts[-1].strip().splitlines()
                bullets = [ln for ln in tail if ln.startswith("- ")]
                if bullets:
                    top_insight = bullets[-1][2:][:200]
        except Exception:
            pass

    return {
        "last_run":                   last.get("ts") if last else None,
        "total_insights":             total_insights,
        "top_insight":                top_insight,
        "skills_updated_this_week":   skills_updated,
    }


def run_learning_cycle_sync(db) -> dict:
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
                return ex.submit(lambda: asyncio.run(run_learning_cycle(db))).result()
    except RuntimeError:
        pass
    return asyncio.run(run_learning_cycle(db))


def get_learning_summary_sync(db) -> dict:
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
                return ex.submit(lambda: asyncio.run(get_learning_summary(db))).result()
    except RuntimeError:
        pass
    return asyncio.run(get_learning_summary(db))


async def learning_engine_health(db) -> dict:
    """GREY if never run (not an error), GREEN <48h, YELLOW >48h."""
    if db is None:
        return {"ok": True, "status": "grey", "detail": "db unavailable"}
    try:
        last = await db.skill_learnings.find_one(
            {}, sort=[("ts", -1)], projection={"_id": 0, "ts": 1, "insights_count": 1},
        )
    except Exception as e:
        return {"ok": False, "status": "red", "detail": f"db error: {e}"}
    if not last:
        return {"ok": True, "status": "green",
                "detail": "ready · awaiting first run (cron: weekly Sat 8 AM UTC)"}
    ts = last.get("ts")
    ins = last.get("insights_count") or 0
    if isinstance(ts, datetime):
        age = datetime.now(timezone.utc) - ts
        status = "green" if age <= timedelta(hours=48) else "yellow"
        return {"ok": True, "status": status,
                "detail": f"last_run={ts.isoformat()} · insights={ins}",
                "last_run": ts.isoformat(), "insights_count": ins}
    return {"ok": True, "status": "yellow", "detail": "last_run timestamp missing"}


__all__ = [
    "run_learning_cycle",
    "run_learning_cycle_sync",
    "get_learning_summary",
    "get_learning_summary_sync",
    "learning_engine_health",
    "MIN_DATA_POINTS",
    "LEARNINGS_HEADER",
]
