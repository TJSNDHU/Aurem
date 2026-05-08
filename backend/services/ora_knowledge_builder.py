"""
iter 282al-23 — ORA Knowledge Builder
=====================================
Weekly intelligence snapshot synthesised from the last 30 days of
AUREM data. The output file `ora_skills/ora_knowledge_snapshot.md` is
auto-loaded by `services.ora_god_mode._load_knowledge_snapshot()` and
injected into every brain system prompt — so every ORA reply benefits
from the prior week's hard-won patterns.

Sections built (any one of which can fail and be skipped silently):
  1. Top-Performing Outreach Patterns
  2. CASL Patterns (what passes / what fails)
  3. Canadian Market Patterns (industry × city)
  4. Site-Score Patterns (most common issues by category)
  5. Timing Patterns (best hour-of-day for replies)

Public API
----------
    build_knowledge_snapshot(db) -> dict
"""
from __future__ import annotations

import logging
from collections import Counter, defaultdict
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

_SKILLS_DIR     = Path(__file__).resolve().parent.parent / "ora_skills"
_SNAPSHOT_FILE  = _SKILLS_DIR / "ora_knowledge_snapshot.md"
_MAX_SNAPSHOT_WORDS = 2000


# ─────────────────────────────────────────────────────────────────────
# Section builders — each is independent + never raises
# ─────────────────────────────────────────────────────────────────────
async def _build_outreach_patterns(db, since) -> str:
    """Section 1 — channel × step × industry × replied vs not."""
    try:
        rows = await db.outreach_history.find(
            {"sent_at": {"$gte": since}},
            {"_id": 0, "channel": 1, "step": 1, "industry": 1, "city": 1,
             "reply_received": 1, "body": 1},
        ).to_list(length=10000)
    except Exception as e:
        logger.debug(f"[snapshot] outreach query: {e}")
        return ""
    if not rows:
        return ""
    replied = [r for r in rows if r.get("reply_received")]
    if not replied:
        return ""
    channels = Counter(r.get("channel") for r in replied)
    industries = Counter((r.get("industry") or "").lower() for r in replied if r.get("industry"))
    avg_words = 0
    if replied:
        avg_words = sum(len(str(r.get("body") or "").split()) for r in replied) // max(1, len(replied))
    lines = ["## TOP PERFORMING OUTREACH PATTERNS (last 30d)",
             f"- Total messages: {len(rows)} · Replies: {len(replied)} · "
             f"Reply rate: {round(100 * len(replied) / max(1, len(rows)), 1)}%",
             f"- Best channel by reply volume: {channels.most_common(1)[0][0] if channels else '—'}",
             f"- Avg word count of replied messages: {avg_words}"]
    if industries:
        top_inds = ", ".join(f"{k} ({v})" for k, v in industries.most_common(3))
        lines.append(f"- Top responding industries: {top_inds}")
    return "\n".join(lines) + "\n"


async def _build_casl_patterns(db, since) -> str:
    """Section 2 — CASL pass/fail rates + common failure causes."""
    try:
        rows = await db.casl_scores.find(
            {"ts": {"$gte": since}},
            {"_id": 0, "channel": 1, "passed": 1, "reason": 1},
        ).to_list(length=5000)
    except Exception:
        # Fallback: read brain_sessions
        try:
            rows = await db.brain_sessions.find(
                {"ts": {"$gte": since}, "casl_checked": True},
                {"_id": 0, "casl_passed": 1},
            ).to_list(length=5000)
        except Exception:
            return ""
    if not rows:
        return ""
    total = len(rows)
    passed = sum(1 for r in rows if r.get("passed", r.get("casl_passed")))
    reasons = Counter(r.get("reason") for r in rows
                      if not r.get("passed", r.get("casl_passed")) and r.get("reason"))
    lines = ["## CASL PATTERNS (last 30d)",
             f"- Pass rate: {round(100 * passed / total, 1)}% ({passed}/{total})",
             f"- Failures: {total - passed}"]
    if reasons:
        top_reasons = ", ".join(f"{k} ({v})" for k, v in reasons.most_common(3))
        lines.append(f"- Most common failure reasons: {top_reasons}")
    lines.append("- Always include identification + STOP path on outreach.")
    return "\n".join(lines) + "\n"


async def _build_market_patterns(db, since) -> str:
    """Section 3 — industry × city × no-website distribution."""
    try:
        rows = await db.campaign_leads.find(
            {"created_at": {"$gte": since}},
            {"_id": 0, "category": 1, "city": 1, "website": 1},
        ).to_list(length=20000)
    except Exception as e:
        logger.debug(f"[snapshot] market query: {e}")
        return ""
    if not rows:
        return ""
    categories = Counter((r.get("category") or "").lower() for r in rows if r.get("category"))
    cities = Counter((r.get("city") or "").title() for r in rows if r.get("city"))
    no_site = sum(1 for r in rows if not r.get("website"))
    lines = ["## CANADIAN MARKET PATTERNS (last 30d)",
             f"- New leads scouted: {len(rows)} · "
             f"Without website: {no_site} ({round(100 * no_site / max(1, len(rows)), 1)}%)"]
    if categories:
        lines.append("- Top industries: " + ", ".join(
            f"{k} ({v})" for k, v in categories.most_common(5)))
    if cities:
        lines.append("- Top cities: " + ", ".join(
            f"{k} ({v})" for k, v in cities.most_common(5)))
    return "\n".join(lines) + "\n"


async def _build_site_score_patterns(db, since) -> str:
    """Section 4 — most common issues + worst-scoring categories."""
    try:
        rows = await db.site_audits.find(
            {"audit_ts": {"$gte": since}},
            {"_id": 0, "overall_score": 1, "issues": 1, "lead_id": 1},
        ).to_list(length=5000)
    except Exception:
        return ""
    if not rows:
        return ""
    issues_ct: Counter = Counter()
    for r in rows:
        for i in (r.get("issues") or []):
            t = (i.get("title") or "").strip()
            if t:
                issues_ct[t] += 1
    avg_score = sum(r.get("overall_score") or 0 for r in rows) // max(1, len(rows))
    lines = ["## SITE-SCORE PATTERNS (last 30d)",
             f"- Audits run: {len(rows)} · Avg score: {avg_score}/100"]
    if issues_ct:
        lines.append("- Most common issues: " + ", ".join(
            f"{k} ({v})" for k, v in issues_ct.most_common(5)))
    return "\n".join(lines) + "\n"


async def _build_timing_patterns(db, since) -> str:
    """Section 5 — hour-of-day reply rate (UTC)."""
    try:
        rows = await db.outreach_history.find(
            {"sent_at": {"$gte": since}},
            {"_id": 0, "sent_at": 1, "reply_received": 1, "channel": 1},
        ).to_list(length=20000)
    except Exception:
        return ""
    if not rows:
        return ""
    by_hour: Dict[int, List[bool]] = defaultdict(list)
    for r in rows:
        ts = r.get("sent_at")
        if not ts:
            continue
        try:
            hour = ts.hour if hasattr(ts, "hour") else datetime.fromisoformat(str(ts)).hour
        except Exception:
            continue
        by_hour[hour].append(bool(r.get("reply_received")))
    if not by_hour:
        return ""
    hour_rates = sorted(
        ((h, round(100 * sum(v) / max(1, len(v)), 1), len(v))
         for h, v in by_hour.items()),
        key=lambda x: -x[1],
    )
    top3 = hour_rates[:3]
    lines = ["## TIMING PATTERNS (last 30d, UTC)",
             "- Best hours to send (highest reply rate):"]
    for h, rate, n in top3:
        lines.append(f"  - {h:02d}:00 UTC — {rate}% reply rate ({n} sends)")
    return "\n".join(lines) + "\n"


# ─────────────────────────────────────────────────────────────────────
# Public entry point
# ─────────────────────────────────────────────────────────────────────
async def build_knowledge_snapshot(db) -> Dict[str, Any]:
    """Builds + writes `ora_knowledge_snapshot.md`. Never raises."""
    if db is None:
        return {"ok": False, "reason": "no_db"}

    since = datetime.now(timezone.utc) - timedelta(days=30)
    sections: List[str] = []
    builders = [
        ("outreach", _build_outreach_patterns),
        ("casl",     _build_casl_patterns),
        ("market",   _build_market_patterns),
        ("sitescore", _build_site_score_patterns),
        ("timing",   _build_timing_patterns),
    ]
    section_names_built: List[str] = []
    for name, fn in builders:
        try:
            block = await fn(db, since)
            if block and block.strip():
                sections.append(block)
                section_names_built.append(name)
        except Exception as e:
            logger.debug(f"[snapshot] section {name} failed: {e}")

    if not sections:
        return {"ok": False, "reason": "no_data", "sections_built": []}

    header = (
        f"# ORA Knowledge Snapshot\n"
        f"_Built: {datetime.now(timezone.utc).date().isoformat()} · "
        f"Window: last 30 days · Auto-injected into every ORA brain reply._\n\n"
    )
    body = "\n".join(sections)

    # Word cap
    words = body.split()
    if len(words) > _MAX_SNAPSHOT_WORDS:
        body = " ".join(words[:_MAX_SNAPSHOT_WORDS]) + "\n\n_…truncated…_\n"

    full = header + body
    try:
        _SKILLS_DIR.mkdir(parents=True, exist_ok=True)
        _SNAPSHOT_FILE.write_text(full, encoding="utf-8")
    except Exception as e:
        return {"ok": False, "reason": f"fs_err:{e}"}

    word_count = len(full.split())
    out = {
        "ok":              True,
        "sections_built":  section_names_built,
        "word_count":      word_count,
        "ts":              datetime.now(timezone.utc),
    }
    try:
        await db.knowledge_builds.insert_one(dict(out))
    except Exception:
        pass
    return out
