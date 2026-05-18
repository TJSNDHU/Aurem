"""
Founders Console — MEGA Console / Full Intelligence Scan (iter 310)
====================================================================
One topic in → 6 frameworks fire in parallel via asyncio.gather →
unified Intelligence Report + Council verdict synthesized by ORA →
saved to db.intelligence_scans + db.ora_learnings.

Public:
  await run_intelligence_scan(inputs, db) -> dict
"""
from __future__ import annotations

import asyncio
import logging
import os
import re
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ─── Prompt templates ─────────────────────────────────────────────────────
def _ctx(inp: Dict[str, Any]) -> str:
    return (
        f"Topic: {inp.get('topic','').strip()}\n"
        f"Business: {inp.get('business_context','AUREM').strip()}\n"
        f"Goal: {inp.get('goal','Revenue').strip()}\n"
        f"Urgency: {inp.get('urgency','This month').strip()}"
    )


LENSES: List[Dict[str, Any]] = [
    {
        "key": "godin",
        "title": "GODIN — Brand Angle",
        "icon": "🎯",
        "build": lambda inp: (
            "Apply Seth Godin Purple Cow framework.\n\n"
            f"{_ctx(inp)}\n\n"
            "Output ONLY this markdown (max 150 tokens, no preamble):\n\n"
            "**SYMBOL:** [Visual symbol for this idea]\n"
            "**SLOGAN:** [Under 6 words, ownable]\n"
            "**SURPRISE:** [Counterintuitive truth]\n"
            "**SALIENT IDEA:** [One sentence, specific audience]\n"
            "**STORY BEAT:** BEFORE → TENSION → AFTER"
        ),
    },
    {
        "key": "naval",
        "title": "NAVAL — Leverage Score",
        "icon": "⚓",
        "build": lambda inp: (
            "Apply Naval Ravikant wealth framework.\n\n"
            f"{_ctx(inp)}\n"
            "Person: Tj Sandhu — auto body tech → AI founder, builds AUREM "
            "(autonomous AI for Canadian SMBs).\n\n"
            "Output ONLY this markdown (max 150 tokens, no preamble):\n\n"
            "**SPECIFIC KNOWLEDGE:** [Rare intersection]\n"
            "**LEVERAGE TYPE:** [Labor/Code/Media/Capital]\n"
            "**LEVERAGE SCORE:** [1-5] · why\n"
            "**EQUITY vs RENT:** [Is this an asset?]\n"
            "**COMPOUND MECHANISM:** [How does this compound?]"
        ),
    },
    {
        "key": "agent_ops",
        "title": "AGENT OPS — Build Plan",
        "icon": "🤖",
        "build": lambda inp: (
            "Apply AI agent architecture framework.\n\n"
            f"{_ctx(inp)}\n"
            "Stack: AUREM (FastAPI + MongoDB + Claude Sonnet 4.5 + Gemini 2.0).\n\n"
            "Output ONLY this markdown (max 150 tokens, no preamble):\n\n"
            "**AGENT-SOLVABLE:** [Yes/No] · reason\n"
            "**WORKFLOW:** Trigger → Steps → Output\n"
            "**STACK:** [Minimal tools needed]\n"
            "**FAILURE POINTS:** Top 3 risks\n"
            "**SUCCESS CRITERIA:** [Measurable test]"
        ),
    },
    {
        "key": "content",
        "title": "CONTENT — Week 1 Post",
        "icon": "📝",
        "build": lambda inp: (
            "Apply Justin Welsh Content OS.\n\n"
            f"{_ctx(inp)}\n"
            "Platform: LinkedIn + X · Audience: Canadian SMB owners.\n\n"
            "Output ONLY this markdown (max 150 tokens, no preamble):\n\n"
            "**HOOK:** [First line that stops scroll]\n"
            "**INSIGHT:** [Core truth most miss]\n"
            "**SHORT POST:** [3 sentences max]\n"
            "**ENGAGEMENT HOOK:** [Question → replies]"
        ),
    },
    {
        "key": "pricing",
        "title": "PRICING — Revenue Model",
        "icon": "💰",
        "build": lambda inp: (
            "Apply outcome-based pricing framework.\n\n"
            f"{_ctx(inp)}\n"
            "Market: Canadian local businesses.\n\n"
            "Output ONLY this markdown (max 150 tokens, no preamble):\n\n"
            "**ROI:** [Dollar value this delivers]\n"
            "**PRICE POINT:** [Recommended + anchor]\n"
            "**TIER GOOD:** [one line]\n"
            "**TIER BETTER:** [one line]\n"
            "**TIER BEST:** [one line]\n"
            "**CLOSING LINE:** [One sentence to close]"
        ),
    },
    {
        "key": "ora",
        "title": "ORA — Platform Intelligence",
        "icon": "🧠",
        "build": lambda inp: (
            "You are ORA. Check AUREM platform history & architecture.\n\n"
            f"{_ctx(inp)}\n\n"
            "AUREM has: Scout (lead gen) · Envoy (outreach) · Architect "
            "(AWB website builder) · Founders Console (6-stage pipeline) · "
            "Stripe checkout · Twilio SMS · Repair Pipeline · Self-Edit engine.\n\n"
            "Output ONLY this markdown (max 150 tokens, no preamble):\n\n"
            "**SIMILAR PAST:** [Have we built this before?]\n"
            "**PLATFORM FIT:** [Where in AUREM does this live?]\n"
            "**BLOCKERS:** [What's missing to execute?]\n"
            "**RECOMMENDATION:** [Build / Skip / Modify — one sentence]"
        ),
    },
    {
        "key": "nvidia",
        "title": "NVIDIA — Technical Validator",
        "icon": "🔬",
        "provider": "nvidia_nim",
        "build": lambda inp: (
            "You are a technical validator. Analyze implementation feasibility, "
            "technical risks, and code architecture.\n\n"
            f"{_ctx(inp)}\n"
            "Stack: FastAPI + MongoDB + React + Cloudflare R2 + Stripe.\n\n"
            "Output ONLY this markdown (max 150 tokens, no preamble):\n\n"
            "**FEASIBILITY:** [HIGH / MEDIUM / LOW] · why\n"
            "**TECH RISKS:** [top 3, comma-separated]\n"
            "**ARCHITECTURE:** [one-line shape — pattern + key components]\n"
            "**CODE APPROACH:** [smallest shippable slice — one sentence]"
        ),
    },
]


# ─── ORA call helpers ─────────────────────────────────────────────────────
async def _nvidia_nim_call(prompt: str, system: str,
                             max_tokens: int = 320,
                             timeout: float = 30.0) -> str:
    """NVIDIA NIM via OpenAI-compatible /chat/completions. Free tier 40 rpm.
    Falls through with `❌ ...` markdown if missing key / 4xx / 5xx."""
    api_key = os.environ.get("NVIDIA_NIM_API_KEY", "")
    if not api_key:
        return "❌ NVIDIA_NIM_API_KEY not configured."
    model = os.environ.get("NVIDIA_NIM_MODEL", "openai/gpt-oss-120b")
    import httpx
    last = ""
    for attempt in range(3):
        try:
            async with httpx.AsyncClient(timeout=timeout) as c:
                r = await c.post(
                    "https://integrate.api.nvidia.com/v1/chat/completions",
                    headers={"Authorization": f"Bearer {api_key}",
                              "Accept": "application/json"},
                    json={
                        "model": model,
                        "max_tokens": max_tokens, "temperature": 0.3,
                        "messages": [
                            {"role": "system", "content": system},
                            {"role": "user", "content": prompt},
                        ],
                    },
                )
            if r.status_code == 429:
                await asyncio.sleep(2)
                last = "rate_limited"
                continue
            if r.status_code >= 400:
                return f"❌ NVIDIA HTTP {r.status_code}: {r.text[:120]}"
            data = r.json()
            return ((data.get("choices", [{}])[0].get("message", {})
                      .get("content", "") or "").strip())
        except Exception as e:
            last = f"{type(e).__name__}:{str(e)[:80]}"
            await asyncio.sleep(1.5)
    return f"❌ NVIDIA call failed: {last}"


async def _ora_call(prompt: str, max_tokens: int = 320,
                     timeout: float = 35.0,
                     provider: str = "claude") -> str:
    """Single LLM call. Default routes through llm_gateway (Sovereign Ollama
    → OpenRouter → Emergent fallback chain). Set provider='nvidia_nim' to
    route to NVIDIA NIM. iter 323r — was direct EMERGENT_LLM_KEY, contributed
    to the budget-exhaustion campaign freeze."""
    system_msg = (
        "You are ORA, AUREM's strategy brain. Output ONLY the requested "
        "markdown — no preamble, no greeting, no 'here is'. Specific, "
        "ship-able, Canadian voice. Numbers over claims."
    )
    if provider == "nvidia_nim":
        return await _nvidia_nim_call(prompt, system_msg,
                                        max_tokens=max_tokens, timeout=timeout)
    try:
        from services.llm_gateway import call_llm
        out = await asyncio.wait_for(
            call_llm(system_prompt=system_msg,
                     user_prompt=prompt,
                     max_tokens=max_tokens),
            timeout=timeout,
        )
        out = (out or "").strip()
        if out.startswith("(LLM unavailable"):
            return f"❌ {out}"
        return out
    except Exception as e:
        logger.warning(f"[intel] ora_call failed: {e}")
        return f"❌ ORA call failed: {type(e).__name__}: {str(e)[:120]}"


async def _run_lens(lens: Dict[str, Any], inp: Dict[str, Any]) -> Dict[str, Any]:
    started = datetime.now(timezone.utc)
    out = await _ora_call(lens["build"](inp),
                            provider=lens.get("provider", "claude"))
    return {
        "key": lens["key"], "title": lens["title"], "icon": lens["icon"],
        "provider": lens.get("provider", "claude"),
        "output": out,
        "ok": not out.startswith("❌"),
        "duration_s": round((datetime.now(timezone.utc) - started).total_seconds(), 2),
    }


async def _synthesize_council(inp: Dict[str, Any],
                                lenses: List[Dict[str, Any]]) -> Dict[str, Any]:
    """7th call — synthesize council verdict from the 6 lens outputs."""
    summary_lines = []
    for L in lenses:
        body = (L.get("output") or "").strip().replace("\n\n", "\n")[:480]
        summary_lines.append(f"### {L['title']}\n{body}")
    summary_block = "\n\n".join(summary_lines)

    prompt = (
        f"{_ctx(inp)}\n\n"
        "Six framework lenses returned these outputs:\n\n"
        f"{summary_block}\n\n"
        "Now act as the AUREM Council. Output ONLY this markdown, "
        "no preamble (max 220 tokens):\n\n"
        "**VERDICT:** [BUILD | MODIFY | SKIP]\n"
        "**RISK:** [0-10]\n"
        "**CONFIDENCE:** [0-100]%\n"
        "**KEY REASON:** [one sentence]\n"
        "**FIRST MOVE:** [one concrete action this week]\n"
        "**KILL CRITERIA:** [if X happens, abandon]"
    )
    out = await _ora_call(prompt, max_tokens=420, timeout=40.0)

    verdict = "MODIFY"
    risk = 5
    confidence = 70
    try:
        m = re.search(r"VERDICT[:\*\s]+([A-Z]+)", out)
        if m:
            v = m.group(1).upper()
            if v in ("BUILD", "MODIFY", "SKIP"):
                verdict = v
        m = re.search(r"RISK[:\*\s]+(\d{1,2})", out)
        if m:
            risk = max(0, min(10, int(m.group(1))))
        m = re.search(r"CONFIDENCE[:\*\s]+(\d{1,3})", out)
        if m:
            confidence = max(0, min(100, int(m.group(1))))
    except Exception:
        pass

    return {
        "verdict": verdict, "risk": risk, "confidence": confidence,
        "raw_markdown": out,
    }


# ─── Public entrypoint ────────────────────────────────────────────────────
async def run_intelligence_scan(inputs: Dict[str, Any],
                                  db) -> Dict[str, Any]:
    """Fire all 6 lenses in parallel, then synthesize council verdict."""
    topic = (inputs or {}).get("topic", "").strip()
    if not topic:
        return {"ok": False, "error": "topic_required"}

    started = datetime.now(timezone.utc)

    # Stage 1: 6 parallel ORA calls
    lens_results = await asyncio.gather(
        *[_run_lens(L, inputs) for L in LENSES],
        return_exceptions=False,
    )

    # Stage 2: council synthesis (depends on Stage 1)
    council = await _synthesize_council(inputs, lens_results)

    duration = round((datetime.now(timezone.utc) - started).total_seconds(), 2)
    scan_id = uuid.uuid4().hex[:14]

    failed = [L["key"] for L in lens_results if not L.get("ok")]
    ok = len(failed) == 0

    record = {
        "scan_id": scan_id,
        "inputs": inputs,
        "lenses": lens_results,
        "council": council,
        "duration_s": duration,
        "ok": ok,
        "failed_lenses": failed,
        "ts": started.isoformat(),
    }

    # Persist scan + ora_learning
    try:
        if db is not None:
            await db.intelligence_scans.insert_one(dict(record))
            try:
                from services.founders_pipeline import record_learning
                await record_learning(db, {
                    "task_title": f"Intelligence Scan: {topic[:80]}",
                    "raw_input": str(inputs)[:300],
                    "optimized_prompt": f"6-lens parallel scan · verdict={council['verdict']}",
                    "council_verdict": council["verdict"],
                    "risk_score": council["risk"],
                    "outcome": "success" if ok else "partial",
                    "files_changed": [],
                    "duration_seconds": duration,
                    "build_path": "intelligence_scan",
                    "build_summary": {
                        "scan_id": scan_id,
                        "confidence": council["confidence"],
                        "failed_lenses": failed,
                    },
                })
            except Exception as e:
                logger.debug(f"[intel] record_learning failed: {e}")
    except Exception as e:
        logger.warning(f"[intel] persist failed: {e}")

    record.pop("_id", None)
    return record


async def _auto_route_to_build(db, inputs: Dict[str, Any],
                                  council: Dict[str, Any],
                                  scan_id: str) -> Dict[str, Any]:
    """When MEGA verdict=BUILD and risk<=4, fire the 6-stage propose+approve
    chain using the topic + first move as the build instruction. Returns
    a dict with build outcome (or skipped reason)."""
    # Extract first move from council markdown
    raw = (council.get("raw_markdown") or "")
    first_move = ""
    for line in raw.split("\n"):
        if "FIRST MOVE" in line.upper():
            first_move = line.split(":", 1)[-1].strip(" *_")[:300]
            break

    topic = (inputs or {}).get("topic", "")[:200]
    instruction = (
        f"{topic}\n\nFirst move (from MEGA Council, conf="
        f"{council.get('confidence')}%): {first_move or '(none extracted)'}"
    )

    try:
        from services.founders_pipeline import (
            preprocess_input, multi_model_race, enhance_council,
        )
        from services.council import council as council_svc
    except Exception as e:
        return {"ok": False, "stage": "import", "error": str(e)[:160]}

    task = await preprocess_input(instruction)
    race = await multi_model_race(task, db)
    cdec = await council_svc.deliberate(
        action_kind=f"founders_console:{task['intent'].lower()}",
        payload={"title": task["title"],
                  "description": task["description"][:300],
                  "scope": task["scope"], "priority": task["priority"],
                  "files_planned":
                      (race.get("gemini_plan") or {}).get("files") or []},
        cost_usd=0.05, llm_voters=False,
    )
    enriched = enhance_council(cdec, task, race)

    if enriched.get("verdict") != "APPROVED":
        return {"ok": False, "stage": "council_disagree",
                "verdict": enriched.get("verdict"),
                "blockers": enriched.get("auto_build_blockers") or []}

    if not enriched.get("auto_build_eligible"):
        return {"ok": False, "stage": "blocked_blast_radius",
                "blockers": enriched.get("auto_build_blockers") or [],
                "optimized_prompt": enriched.get("optimized_prompt", "")[:200]}

    from services.self_edit_engine import self_edit_apply
    files = (race.get("gemini_plan") or {}).get("files") or []
    out = await self_edit_apply(
        prompt=enriched["optimized_prompt"],
        expected_files=files, db=db, dry_run=False,
    )
    return {
        "ok": bool(out.get("ok")),
        "stage": "self_edit",
        "files_changed": out.get("files_changed") or [],
        "rolled_back": out.get("rolled_back", False),
        "scan_id": scan_id,
        "summary": out.get("summary", "")[:200] if isinstance(out.get("summary"), str) else None,
    }


async def prepare_intelligence_stub(inputs: Dict[str, Any], db) -> Dict[str, Any]:
    """Insert a 'running' stub row and return scan_id. Caller schedules runner."""
    topic = (inputs or {}).get("topic", "").strip()
    if not topic:
        return {"ok": False, "error": "topic_required"}
    scan_id = uuid.uuid4().hex[:14]
    started = datetime.now(timezone.utc)
    stub = {
        "scan_id": scan_id, "status": "running",
        "inputs": inputs, "ts": started.isoformat(),
        "lenses": [], "council": {}, "duration_s": 0, "ok": None,
    }
    try:
        await db.intelligence_scans.insert_one(dict(stub))
    except Exception as e:
        logger.warning(f"[intel] stub insert failed: {e}")
    return {"ok": True, "scan_id": scan_id, "status": "running",
            "ts": started.isoformat()}


async def run_intelligence_scan_into(scan_id: str,
                                       inputs: Dict[str, Any], db) -> None:
    """Background task: run 6 lenses + council, persist into existing stub row."""
    started = datetime.now(timezone.utc)
    try:
        lens_results = await asyncio.gather(
            *[_run_lens(L, inputs) for L in LENSES],
            return_exceptions=False,
        )
        council = await _synthesize_council(inputs, lens_results)
        duration = round(
            (datetime.now(timezone.utc) - started).total_seconds(), 2)
        failed = [L["key"] for L in lens_results if not L.get("ok")]
        ok = len(failed) == 0

        # Auto-route to Stage-5 build when verdict=BUILD AND risk<=4
        auto_build: Optional[Dict[str, Any]] = None
        if ok and council.get("verdict") == "BUILD" and council.get("risk", 10) <= 4:
            try:
                auto_build = await _auto_route_to_build(
                    db, inputs, council, scan_id,
                )
            except Exception as e:
                logger.warning(f"[intel] auto-build failed: {e}")
                auto_build = {"ok": False, "error": str(e)[:160]}

        try:
            await db.intelligence_scans.update_one(
                {"scan_id": scan_id},
                {"$set": {
                    "status": "done", "lenses": lens_results,
                    "council": council, "duration_s": duration,
                    "ok": ok, "failed_lenses": failed,
                    "auto_build": auto_build,
                    "completed_at": datetime.now(timezone.utc).isoformat(),
                }},
            )
        except Exception as e:
            logger.warning(f"[intel] persist failed: {e}")

        topic = (inputs or {}).get("topic", "")[:80]
        try:
            from services.founders_pipeline import record_learning
            await record_learning(db, {
                "task_title": f"Intelligence Scan: {topic}",
                "raw_input": str(inputs)[:300],
                "optimized_prompt": f"6-lens parallel scan · verdict={council['verdict']}",
                "council_verdict": council["verdict"],
                "risk_score": council["risk"],
                "outcome": "success" if ok else "partial",
                "files_changed": [],
                "duration_seconds": duration,
                "build_path": "intelligence_scan",
                "build_summary": {
                    "scan_id": scan_id,
                    "confidence": council["confidence"],
                    "failed_lenses": failed,
                },
            })
        except Exception as e:
            logger.debug(f"[intel] record_learning failed: {e}")
    except Exception as e:
        logger.exception(f"[intel] runner crashed: {e}")
        try:
            await db.intelligence_scans.update_one(
                {"scan_id": scan_id},
                {"$set": {"status": "error", "error": str(e)[:240],
                          "completed_at": datetime.now(timezone.utc).isoformat()}},
            )
        except Exception:
            pass


async def start_intelligence_scan(inputs: Dict[str, Any], db) -> Dict[str, Any]:
    """Legacy fire-and-forget kick-off. Prefer prepare_intelligence_stub +
    BackgroundTasks for ASGI compatibility."""
    stub = await prepare_intelligence_stub(inputs, db)
    if not stub.get("ok"):
        return stub
    asyncio.create_task(run_intelligence_scan_into(stub["scan_id"], inputs, db))
    return stub
