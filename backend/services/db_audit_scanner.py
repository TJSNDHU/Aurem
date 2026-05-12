"""
db_audit_scanner.py — Real DB hygiene audit for ORA's dev_system-scan skill.

Implements the 5-layer scan methodology used by the founder + main agent:

  1. DB enumerate     — counts, sizes, last-write, indexes
  2. Code grep        — write/read/index counts per collection
  3. Categorize       — pure-dead vs ghost-read vs dormant-write
  4. Resurrection     — verify previously-dropped collections stayed gone
  5. Duplicates       — semantic-pattern detection (audit_*, scan_*, etc.)

Returns a single dict with all layers populated. Used by:
  • services/skill_router._gather_live_system_scan() — ORA chat
  • routers/db_audit_router          — admin REST endpoint
  • scripts/run_db_audit.py          — CLI / cron

NEVER raises. Every layer is wrapped — partial results > nothing.
Cap-bounded everywhere (max 60s end-to-end on Atlas).
"""
from __future__ import annotations

import asyncio
import logging
import os
import re
import subprocess
import time
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)

# Hard caps so this can't take down the chat handler
_PER_COLL_TIMEOUT_S = 0.5
_TOTAL_SCAN_TIMEOUT_S = 45.0
_GREP_TIMEOUT_S = 6.0


async def _safe_count(db, coll: str) -> int:
    try:
        return await asyncio.wait_for(
            db[coll].estimated_document_count(),
            timeout=_PER_COLL_TIMEOUT_S,
        )
    except Exception:
        return -1


def _grep_refs(coll: str) -> dict:
    """Run real subprocess greps for write/read/index references. Hard
    timeout. Returns counts only — no source paths (LLM context budget)."""
    write_re = re.compile(
        rf"(\.{coll}\.|\[['\"]{coll}['\"]\]\s*\.)\s*"
        rf"(insert_one|insert_many|update_one|update_many|replace_one|"
        rf"find_one_and_update|delete_one|delete_many|bulk_write)"
    )
    read_re = re.compile(
        rf"(\.{coll}\.|\[['\"]{coll}['\"]\]\s*\.)\s*"
        rf"(find|count_documents|aggregate|estimated_document_count|distinct)\b"
    )
    idx_re = re.compile(
        rf"(\.{coll}\.|\[['\"]{coll}['\"]\]\s*\.)\s*create_index"
    )
    try:
        r = subprocess.run(
            ["grep", "-rnHw", coll, "--include=*.py", "/app/backend"],
            capture_output=True, text=True, timeout=_GREP_TIMEOUT_S,
        )
    except Exception:
        return {"writes": 0, "reads": 0, "indexes": 0, "files": 0}

    files = set()
    w = r_count = i = 0
    for line in r.stdout.split("\n"):
        if ":" not in line:
            continue
        parts = line.split(":", 2)
        if len(parts) < 3:
            continue
        path, _, body = parts
        if "tests/" in path or "/_audit" in path or "/verify" in path:
            continue
        files.add(path)
        if write_re.search(body):
            w += 1
        elif read_re.search(body):
            r_count += 1
        elif idx_re.search(body):
            i += 1
    return {"writes": w, "reads": r_count, "indexes": i, "files": len(files)}


async def scan_db_audit(db, *, max_empties: int = 30,
                          full_grep: bool = False) -> dict[str, Any]:
    """Full 5-layer DB hygiene scan.

    Args:
        db: Motor AsyncIOMotorDatabase handle.
        max_empties: cap on how many empty collections to grep-classify.
                      Larger = slower (each grep is ~50-200ms).
        full_grep: when False (default), only the top `max_empties`
                    empty collections by name get grep-classified. Set
                    True for nightly cron runs only.
    """
    started = time.time()
    out: dict[str, Any] = {
        "scanner_iter": "322eh",
        "ts": datetime.now(timezone.utc).isoformat(),
        "ok": False,
    }
    if db is None:
        out["error"] = "db unavailable"
        return out

    # ── Layer 1: enumerate ──────────────────────────────────────────
    try:
        cols = await asyncio.wait_for(
            db.list_collection_names(),
            timeout=5.0,
        )
    except Exception as e:
        out["error"] = f"list_collection_names failed: {type(e).__name__}"
        return out

    empty, tiny, small, alive = [], [], [], []
    sizes: dict[str, int] = {}
    for c in cols:
        n = await _safe_count(db, c)
        sizes[c] = n
        if n == 0:
            empty.append(c)
        elif n < 5:
            tiny.append(c)
        elif n < 50:
            small.append(c)
        else:
            alive.append(c)

    out["layer1_enumerate"] = {
        "total": len(cols),
        "empty": len(empty),
        "tiny_1_4": len(tiny),
        "small_5_49": len(small),
        "alive_50plus": len(alive),
        "top_5_by_size": sorted(
            [(c, n) for c, n in sizes.items() if n > 0],
            key=lambda x: -x[1],
        )[:5],
    }

    # ── Layer 2 + 3: grep + categorize empties ─────────────────────
    pure_dead = []      # 0W + 0R
    ghost_reads = []    # 0W + R>0
    dormant_writes = [] # W>0 (untriggered or broken)

    to_classify = sorted(empty)[: (None if full_grep else max_empties)]
    classify_budget_left = lambda: time.time() - started < _TOTAL_SCAN_TIMEOUT_S

    for c in to_classify:
        if not classify_budget_left():
            break
        # subprocess.run is sync — push to thread to keep event loop free
        try:
            refs = await asyncio.wait_for(
                asyncio.to_thread(_grep_refs, c),
                timeout=_GREP_TIMEOUT_S + 1.0,
            )
        except Exception:
            refs = {"writes": -1, "reads": -1, "indexes": -1, "files": -1}
        w, r = refs.get("writes", 0), refs.get("reads", 0)
        if w == 0 and r == 0:
            pure_dead.append(c)
        elif w == 0 and r > 0:
            ghost_reads.append({"coll": c, "reads": r})
        else:
            dormant_writes.append({"coll": c, "writes": w, "reads": r})

    out["layer2_categorize"] = {
        "classified": len(to_classify),
        "remaining_unclassified": max(0, len(empty) - len(to_classify)),
        "pure_dead": pure_dead,
        "ghost_reads": ghost_reads,
        "dormant_writes": dormant_writes,
    }

    # ── Layer 4: resurrection-check for known-dropped names ─────────
    HISTORICAL_DROPS = [
        "abandoned_carts", "products", "orders", "carts", "discount_codes",
        "analytics_visits", "apollo_people_cache", "aurem_api_keys",
        "aurem_consent_records", "aurem_contacts", "aurem_gmail_messages",
        "aurem_integrations", "aurem_key_usage", "aurem_unified_inbox",
        "aurem_whatsapp_connections", "aurem_whatsapp_messages",
        "blog_posts", "campaign_runs", "hermes_deepsleep_memory",
        "lifecycle_history", "marketing_broadcasts",
        "mention_status_history", "scout_runs", "subscribers",
        "unlinked_mentions", "bio_scans", "evolver_genes",
        "marketing_social_posts",
    ]
    came_back = [c for c in HISTORICAL_DROPS if c in cols]
    out["layer4_resurrection"] = {
        "checked": len(HISTORICAL_DROPS),
        "stayed_gone": len(HISTORICAL_DROPS) - len(came_back),
        "came_back": came_back,
        "status": "✓ clean" if not came_back else "⚠ resurrectors detected",
    }

    # ── Layer 5: duplicate semantic patterns ────────────────────────
    patterns = {
        "audit_log": ["audit_trail", "admin_audit_log", "aurem_audit_logs",
                       "audit_chain", "audit_chain_archive", "vault_audit_log",
                       "rbac_audit_log", "cleanup_audit_log", "self_audit_log",
                       "founder_audit"],
        "campaigns": ["campaigns", "campaign_leads", "campaign_outcomes",
                       "campaign_brief_log", "armed_campaigns",
                       "drip_campaigns_log", "forecast_campaigns",
                       "proximity_campaigns"],
        "heartbeats": ["heartbeats", "heartbeats_archive", "pillar_heartbeats",
                        "sentinel_heartbeats", "agent_heartbeats",
                        "scheduler_heartbeats"],
        "scans": ["customer_scans", "scan_history", "scan_sessions",
                   "scan_queue", "quick_scans", "intelligence_scans",
                   "forensic_miner_scans", "friend_scans",
                   "collective_scan_buffer", "collective_scan_results",
                   "client_scan_results", "system_scans", "deep_scout_log",
                   "scout_source_runs"],
        "skills": ["ora_skills_library", "ora_skills_broadcast",
                    "ora_skills_broadcast_history", "agent_skills",
                    "agent_skill_snapshots", "skill_invocations",
                    "skill_route_cache"],
    }
    dup_report = {}
    for cat, names in patterns.items():
        present = []
        for n in names:
            if n in sizes:
                present.append({"coll": n, "docs": sizes[n]})
        if len(present) > 1:
            present.sort(key=lambda x: -x["docs"])
            dup_report[cat] = {
                "variant_count": len(present),
                "canonical_guess": present[0]["coll"] if present[0]["docs"] > 0 else None,
                "variants": present,
            }
    out["layer5_duplicates"] = dup_report

    out["ok"] = True
    out["elapsed_s"] = round(time.time() - started, 2)
    return out


# ─── Mandatory 3-proof footer ────────────────────────────────────────
async def gather_proofs(db) -> dict[str, Any]:
    """Run the 3 proofs every scan MUST include (founder convention).

      1. relevant grep / curl / db count   — proves a real query happened
      2. health check                       — proves backend is up
      3. git log --oneline -3              — proves what's deployed

    All shelled out for authenticity — no in-memory mocks.
    """
    proofs: dict[str, Any] = {}

    # 1. db count (the canonical "I really hit Mongo" proof)
    try:
        n = await db.list_collection_names() if db is not None else []
        proofs["db_count"] = {
            "cmd": "list_collection_names()",
            "result": len(n),
        }
    except Exception as e:
        proofs["db_count"] = {"error": str(e)[:120]}

    # 2. health check — REAL curl
    try:
        r = await asyncio.to_thread(
            subprocess.run,
            ["curl", "-s", "-o", "/dev/null", "-w", "%{http_code}",
             "http://localhost:8001/api/platform/health"],
            capture_output=True, text=True, timeout=5,
        )
        proofs["health_check"] = {
            "cmd": "curl -s http://localhost:8001/api/platform/health",
            "http_status": r.stdout.strip() or "no_response",
        }
    except Exception as e:
        proofs["health_check"] = {"error": str(e)[:120]}

    # 3. git log --oneline -3
    try:
        r = await asyncio.to_thread(
            subprocess.run,
            ["git", "log", "--oneline", "-3"],
            capture_output=True, text=True, timeout=5,
            cwd="/app",
        )
        proofs["git_log"] = {
            "cmd": "git log --oneline -3",
            "output": [
                ln for ln in (r.stdout or "").strip().split("\n") if ln
            ][:3],
        }
    except Exception as e:
        proofs["git_log"] = {"error": str(e)[:120]}

    return proofs


# ─── Markdown formatter (for ORA chat injection) ─────────────────────
def format_for_ora(scan: dict, proofs: dict) -> str:
    """Render the scan + proofs as a single text block the LLM injects
    under '=== DB AUDIT SCAN ==='. Keep it human-readable + LLM-parsable."""
    L1 = scan.get("layer1_enumerate", {})
    L2 = scan.get("layer2_categorize", {})
    L4 = scan.get("layer4_resurrection", {})
    L5 = scan.get("layer5_duplicates", {})

    lines = ["=== DB AUDIT SCAN (5-LAYER, REAL DATA) ==="]
    lines.append(
        f"[L1 Enumerate] total={L1.get('total','?')} · "
        f"empty={L1.get('empty','?')} · "
        f"tiny={L1.get('tiny_1_4','?')} · "
        f"alive={L1.get('alive_50plus','?')}"
    )
    pd = L2.get("pure_dead") or []
    gh = L2.get("ghost_reads") or []
    dw = L2.get("dormant_writes") or []
    lines.append(
        f"[L2 Categorize] pure_dead={len(pd)} · "
        f"ghost_reads={len(gh)} · "
        f"dormant_writes={len(dw)} · "
        f"unclassified={L2.get('remaining_unclassified',0)}"
    )
    if pd:
        lines.append(f"  pure_dead: {', '.join(pd[:8])}"
                      + (f" (+{len(pd)-8} more)" if len(pd) > 8 else ""))
    if gh:
        lines.append("  ghost_reads: " + ", ".join(
            f"{g['coll']}({g['reads']}R)" for g in gh[:6]
        ))

    lines.append(
        f"[L4 Resurrection] stayed_gone={L4.get('stayed_gone')}/"
        f"{L4.get('checked')} · {L4.get('status','?')}"
    )
    if L4.get("came_back"):
        lines.append("  ⚠ came_back: " + ", ".join(L4["came_back"]))

    if L5:
        lines.append(f"[L5 Duplicates] {len(L5)} duplicate clusters:")
        for cat, info in L5.items():
            lines.append(
                f"  {cat}: {info['variant_count']} variants · "
                f"canonical={info.get('canonical_guess','?')}"
            )

    # 3 mandatory proofs
    lines.append("")
    lines.append("=== PROOFS (founder rule — never skip) ===")
    p1 = proofs.get("db_count", {})
    lines.append(
        f"1. db_count: `{p1.get('cmd','?')}` → "
        f"{p1.get('result', p1.get('error','?'))}"
    )
    p2 = proofs.get("health_check", {})
    lines.append(
        f"2. health_check: `{p2.get('cmd','?')}` → "
        f"HTTP {p2.get('http_status', p2.get('error','?'))}"
    )
    p3 = proofs.get("git_log", {})
    git = p3.get("output") or [p3.get("error", "?")]
    lines.append("3. git_log:")
    for ln in git:
        lines.append(f"   {ln}")

    lines.append(f"\nElapsed: {scan.get('elapsed_s','?')}s")
    return "\n".join(lines)
