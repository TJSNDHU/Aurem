"""
Founders Console — Content Strategy Quick Chips (iter 309)
==========================================================
5 pre-built prompt templates that bypass the 6-stage Council pipeline
and fire directly to ORA (Claude Sonnet 4.5).

Public:
  CHIP_TEMPLATES (dict)            — chip_id → spec
  await fire_chip(chip_id, inputs, db) -> dict
"""
from __future__ import annotations

import asyncio
import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

CHIP_TEMPLATES: Dict[str, Dict[str, Any]] = {
    "content_week": {
        "label": "Content Week",
        "icon": "📝",
        "category": "content",
        "needs_form": True,
        "form_fields": [
            {"name": "raw_idea",  "label": "Raw Idea",  "type": "textarea",
             "required": True, "placeholder": "e.g. agencies are running on borrowed time"},
            {"name": "platform",  "label": "Platform",  "type": "select",
             "options": ["LinkedIn", "X", "Both"], "default": "LinkedIn"},
        ],
        "build_prompt": lambda inp: (
            "You are a content strategist. Take this raw idea from AUREM founder "
            "Tejinder Sandhu — autonomous AI platform for Canadian local businesses "
            "(aurem.live). Audience: Canadian SMB owners tired of paying agencies "
            "that don't deliver.\n\n"
            f"Raw idea: {inp.get('raw_idea','').strip()}\n"
            f"Platform: {inp.get('platform','LinkedIn')}\n\n"
            "Build a full content week with these EXACT sections, in this order, "
            "using markdown headings:\n\n"
            "## LONG-FORM POST (250-300 words)\n"
            "Story open about Canadian business pain → AUREM insight → 3 lessons "
            "→ CTA to aurem.live.\n\n"
            "## SHORT POST 1 — DATA POINT\nA surprising number from AUREM pipeline.\n\n"
            "## SHORT POST 2 — CONTRARIAN\nAgency model is broken + AUREM alternative.\n\n"
            "## SHORT POST 3 — PERSONAL CONFESSION\nFounder lesson learned the hard way.\n\n"
            "## ENGAGEMENT HOOK 1\nQuestion → yes/no + explanation.\n\n"
            "## ENGAGEMENT HOOK 2\nFill-in-the-blank gap.\n\n"
            "## NEWSLETTER PARAGRAPH (~100 words)\nInsight + tip + aurem.live CTA.\n\n"
            "Rules: sound human not AI · specific to AUREM/Canadian market · "
            "no motivational fluff · each piece stands alone."
        ),
    },
    "offer_stack": {
        "label": "Offer Stack",
        "icon": "💰",
        "category": "content",
        "needs_form": False,
        "build_prompt": lambda inp: (
            "Audit AUREM's current offer stack and sharpen the 3-tier product "
            "ladder.\n\n"
            "Business: AUREM by Polaris Built Inc.\n"
            "Founder: Tejinder Sandhu, Mississauga ON\n"
            "Platform: aurem.live\n"
            "Audience: Canadian local business owners — restaurants, trades, "
            "retail, services — no website OR bad website — tired of agencies, "
            "no tech skills.\n\n"
            "Current products:\n"
            "- Free website audit report\n"
            "- $149 Basic Repair (3 fixes, 24h)\n"
            "- $299 Full Rebuild\n"
            "- $97/month hosting + updates\n\n"
            "Output the response in markdown with these EXACT headings:\n\n"
            "## TIER 1 (Free)\nName · Format · Core promise · Status\n\n"
            "## TIER 2 ($149)\nName (sharpened) · Core promise · Why Tier 1 → Tier 2\n\n"
            "## TIER 3 ($___)\nName (sharpened) · Recommended price · Core promise "
            "· Why Tier 2 → Tier 3\n\n"
            "## UPGRADE PATH\nTwo sentences.\n\n"
            "## CRITICAL BOTTLENECK\nWhat kills this stack.\n\n"
            "## FIRST PRIORITY\nFix this week."
        ),
    },
    "newsletter": {
        "label": "Newsletter",
        "icon": "📧",
        "category": "content",
        "needs_form": False,
        "build_prompt": lambda inp: (
            "Build a complete newsletter system for AUREM.\n\n"
            "Owner: Tejinder Sandhu\n"
            "Business: AUREM — autonomous AI platform\n"
            "Audience: Canadian SMB owners replacing their agency stack with AI\n"
            "Pain: paying agencies $2k+/month for zero results\n"
            "Expertise: AI automation, lead generation, website building, "
            "local business growth\nCadence: weekly.\n\n"
            "Output in markdown with EXACT headings:\n\n"
            "## NEWSLETTER POSITIONING\nName: The Sovereign Brief · Tagline · "
            "Why subscribe over alternatives.\n\n"
            "## RECURRING FORMAT (90 min to write)\n"
            "Section 1 (name · description · word count)\n"
            "Section 2 (name · description · word count)\n"
            "Section 3 (name · description · word count)\n\n"
            "## 4-WEEK CALENDAR\n"
            "Week 1 / 2 / 3 / 4: topic + angles per section.\n\n"
            "## MONETIZATION MAP\n"
            "Issue 3 (free offer intro) · Issue 7 (trust sequence) · "
            "Issue 12 (first paid mention).\n\n"
            "## ISSUE 1 OPENER\nSubject (no clickbait, curiosity via specificity) · "
            "Opening (start with story, not intro, ~75 words)."
        ),
    },
    "brand_position": {
        "label": "Brand Position",
        "icon": "🎯",
        "category": "content",
        "needs_form": False,
        "build_prompt": lambda inp: (
            "Build AUREM brand positioning.\n\n"
            "Owner: Tejinder Sandhu — auto body tech turned AI founder, "
            "Mississauga ON.\n"
            "Target: Canadian local business owners.\n"
            "Core expertise: autonomous AI systems · local business lead "
            "generation · website building + repair pipeline.\n"
            "Current positioning: 'Autonomous commercial AI platform for "
            "Canadian local businesses'.\n\n"
            "Output in markdown with EXACT headings:\n\n"
            "## NICHE STATEMENTS\n"
            "Safe (Option 1) · Sharp (Option 2) · Bold (Option 3 — RECOMMENDED, "
            "slightly uncomfortable to say).\n\n"
            "## CONTENT ANGLE\nOnly AUREM can own this. Why ownable: TJ's "
            "background makes it credible.\n\n"
            "## TOP 3 PROOF POINTS\n1. specific number/result · 2. specific "
            "number/result · 3. specific number/result.\n\n"
            "## 10-WORD BRAND PROMISE\nMax 10 words.\n\n"
            "## FIRST CONTENT MOVE\nPost to publish this week.\n\n"
            "Rules: no 'help' as main verb · Bold option must feel risky · "
            "proof points: numbers only, no vague claims."
        ),
    },
    "systems_audit": {
        "label": "Systems Audit",
        "icon": "⚙️",
        "category": "content",
        "needs_form": False,
        "build_prompt": lambda inp: (
            "Audit AUREM founder's weekly workflow and build a one-page "
            "operating system.\n\n"
            "Owner: Tejinder Sandhu\n"
            "Businesses: AUREM (aurem.live) + Reroots (reroots.ca) + A-1 "
            "Mississauga Auto Collision (day job)\n"
            "Tools: Emergent, MongoDB, Claude, Gemini, Twilio, Stripe.\n\n"
            "Weekly tasks (approximate):\n"
            "- Monitor AUREM platform health\n"
            "- Review lead pipeline + AWB output\n"
            "- Check Founders Console builds\n"
            "- Reroots inventory + orders\n"
            "- Auto body work (day job)\n"
            "- Platform improvements via Emergent\n\n"
            "Output in markdown with EXACT headings:\n\n"
            "## TASK AUDIT (table)\n"
            "Task | Time/week | A/B/C | Reason\n"
            "(A = AI-automate · B = SOP needed · C = Eliminate)\n\n"
            "## AI REPLACEMENTS\nTask → Tool → Exact prompt/logic.\n\n"
            "## SOPs (Class B tasks)\n5-step SOP each, VA-executable.\n\n"
            "## WEEKLY OPERATING RHYTHM\nMon · Tue · Wed · Thu · Fri · Sat · Sun "
            "— focus + tasks per day.\n\n"
            "## FIRST ELIMINATION\nKill this week."
        ),
    },
    # ─── Naval Ravikant — Wealth Strategy ────────────────────────────────
    "specific_knowledge": {
        "label": "Specific Knowledge",
        "icon": "🧠",
        "category": "wealth",
        "needs_form": False,
        "build_prompt": lambda inp: (
            "Naval Ravikant specific knowledge analyst.\n\n"
            "Person: Tejinder (Tj) Sandhu\n"
            "Obsessions: AI autonomy systems, auto body craft, brand building "
            "from zero, systems that run without humans.\n"
            "Weird career path: 8+ years auto body tech in GTA → taught himself "
            "AI/full-stack → founded AUREM (autonomous AI platform) + Reroots "
            "(skincare e-commerce) with zero CS degree and zero VC money.\n"
            "Undervalued skills: sees broken systems instantly + fixes them · "
            "builds complex tech without formal training · makes AI accessible "
            "for non-tech businesses.\n\n"
            "Cross-reference all 3 → find rare intersection.\n\n"
            "Output in markdown with EXACT headings:\n\n"
            "## SPECIFIC KNOWLEDGE NICHE\nOne precise sentence.\n\n"
            "## WHY THIS IS RARE\n2-3 sentences — what makes this combo unusual.\n\n"
            "## 3 LEVERAGED BUSINESS MODELS (table)\n"
            "| Model | Leverage | Market | Competition | Multiplier |\n\n"
            "Rules: reject if someone could be trained for it · code or media "
            "leverage only (no labor) · score each 1-5.\n\n"
            "## RECOMMENDED START\nTop model + first 3 steps this week."
        ),
    },
    "leverage_audit": {
        "label": "Leverage Audit",
        "icon": "⚡",
        "category": "wealth",
        "needs_form": False,
        "build_prompt": lambda inp: (
            "Naval leverage audit for Tj Sandhu.\n\n"
            "Income sources + hours/week:\n"
            "1. Auto body tech (A-1 Mississauga) → ~40h/week → active employment\n"
            "2. AUREM platform (aurem.live) → ~20h/week building → $0 today, scaling\n"
            "3. Reroots.ca (skincare e-commerce) → ~10h/week → early revenue\n"
            "4. TJ Auto Clinic Ltd (corporate invoicing) → ~2h/week admin\n\n"
            "Monthly target: replace day job income with AUREM autonomous revenue.\n"
            "Assets owned: AUREM codebase, Reroots platform, formulations, "
            "2 incorporated companies.\n\n"
            "Output in markdown with EXACT headings:\n\n"
            "## LEVERAGE AUDIT TABLE\n"
            "| Activity | Type | Hours/Week | Score | Revenue% |\n\n"
            "## LEVERAGE INDEX\n[X/5]\n\n"
            "## BIGGEST LEVERAGE LEAK\nActivity + why it's a trap + cost.\n\n"
            "## 3 UPGRADE MOVES\n"
            "1. Convert X → Y · Score before→after · Days\n"
            "2.\n3.\n\n"
            "## 30-DAY FIRST MOVE\nExact action this week.\n\n"
            "Rules: auto body = Labor = Score 1 (no exceptions) · flag anything "
            "that stops if Tj stops for 6 months · specific actions only — "
            "no directional advice."
        ),
    },
    "productize_me": {
        "label": "Productize Me",
        "icon": "📦",
        "category": "wealth",
        "needs_form": False,
        "build_prompt": lambda inp: (
            "Design a complete Productize Yourself blueprint for Tj Sandhu.\n\n"
            "Expertise: building autonomous AI systems for local businesses — "
            "lead generation, website building, outreach, self-repair. All "
            "without hiring anyone.\n\n"
            "Core transformation: takes a local business owner from 'paying "
            "agency $2k/month, zero results' to 'autonomous AI running 24/7, "
            "paying for itself'.\n\n"
            "Current platforms: aurem.live (live product) · building "
            "LinkedIn/X presence · Canadian market focus.\n"
            "Time to build: 10-15h/week.\n\n"
            "Output in markdown with EXACT headings:\n\n"
            "## CORE TRANSFORMATION\n"
            "I help [WHO] go from [BEFORE] to [AFTER] using [NAMED METHOD — "
            "must be proprietary].\n\n"
            "## 3 PRODUCT FORMATS (table)\n"
            "| Format | Leverage | Feasibility | Margin | Score |\n\n"
            "## WINNING PRODUCT\nName (with proprietary mechanism) · Contents "
            "· Delivery (without Tj present) · Price (recommended + rationale).\n\n"
            "## LAUNCH POSITIONING\nOne sentence.\n\n"
            "## WEEK 1 ROADMAP\n3 tasks to start now.\n\n"
            "Rules: fails if requires live presence · must have named framework "
            "· distribution = existing AUREM audience."
        ),
    },
    "time_leak": {
        "label": "Time Leak",
        "icon": "🕐",
        "category": "wealth",
        "needs_form": False,
        "build_prompt": lambda inp: (
            "Naval time-for-money leak detector for Tj Sandhu.\n\n"
            "Work activities:\n"
            "1. Auto body tech — employed, hourly — 40h/week\n"
            "2. AUREM platform build + monitoring — 20h/week\n"
            "3. Reroots.ca management — 10h/week\n"
            "4. Admin (TJ Auto Clinic, invoicing) — 2h/week\n"
            "5. Legal disputes (TD Insurance, real estate, Toyota GR86) — "
            "3h/week occasional\n\n"
            "Total: ~75h/week active. Income split: ~90% active (auto body), "
            "~10% building toward passive (AUREM).\n\n"
            "Output in markdown with EXACT headings:\n\n"
            "## TIME AUDIT TABLE\n"
            "| Activity | Type | Hours/Week | Equity Potential | "
            "Conversion Difficulty |\n\n"
            "## TIME-RENT RATIO\n[X% rented / Y% equity]\n\n"
            "## TOP 3 CONVERSION OPPORTUNITIES\n"
            "1. Activity → Equity equivalent · Effort: Low/Med/High · "
            "Leverage: 1-5\n2.\n3.\n\n"
            "## EQUITY GAP\nIncome in 2 years if top conversion done — with "
            "rough math.\n\n"
            "## FIRST ESCAPE MOVE\nOne action this week.\n\n"
            "Rules: auto body = time-rented, no exceptions · equity only if "
            "stops 6 months → still earns · flag disguised time-rent."
        ),
    },
    "compounding_work": {
        "label": "Compounding Work",
        "icon": "🔄",
        "category": "wealth",
        "needs_form": False,
        "build_prompt": lambda inp: (
            "Design a compounding work portfolio for Tj Sandhu.\n\n"
            "Current activities: auto body work (income today) · AUREM "
            "platform (asset building) · Reroots.ca (asset building) · "
            "content creation (starting) · platform improvements (skill).\n\n"
            "Skills building this year: AI systems architecture · autonomous "
            "agent design · Canadian SMB market expertise · founder "
            "brand/content.\n\n"
            "Distribution channels: aurem.live (product) · LinkedIn/X "
            "(starting) · Canadian local business network.\n\n"
            "Output in markdown with EXACT headings:\n\n"
            "## WORK PORTFOLIO MAP (2x2)\n"
            "Short-term vs Long-term × Low vs High leverage. Map all "
            "activities to quadrants.\n\n"
            "## COMPOUNDING GAP\nWhere under-indexed + compound cost.\n\n"
            "## 3 TWO-FOR-ONE ACTIVITIES (table)\n"
            "| Activity | Immediate Payoff | Long-term Asset | "
            "Compounding Mechanism |\n\n"
            "## WEEKLY RHYTHM\n"
            "- [X hrs] income today\n- [Y hrs] asset tomorrow\n"
            "- [Z hrs] skill compounding\n\n"
            "## KEYSTONE ASSET\nWhat to build · how it compounds · "
            "90-day plan.\n\n"
            "Rules: every activity needs a compounding mechanism · keystone "
            "must be ownable + distributable · sustainable weekly hours only."
        ),
    },
}


async def _ora_call(prompt: str, max_tokens: int = 2400,
                     timeout: float = 45.0) -> str:
    """Direct Claude Sonnet 4.5 call via Emergent LLM key."""
    api_key = os.environ.get("EMERGENT_LLM_KEY", "")
    if not api_key:
        return "❌ EMERGENT_LLM_KEY not configured."
    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage  # type: ignore
    except Exception as e:
        return f"❌ emergentintegrations unavailable: {e}"
    try:
        chat = LlmChat(
            api_key=api_key,
            session_id=f"chip-{uuid.uuid4().hex[:10]}",
            system_message=(
                "You are ORA, AUREM's content + strategy brain. Output ONLY the "
                "requested markdown — no preamble, no greeting, no 'here is'. "
                "Specific numbers over generic claims. Canadian voice. Clear, "
                "useful, ship-able outputs only."
            ),
        ).with_model("anthropic", "claude-sonnet-4-5-20250929") \
         .with_params(max_tokens=max_tokens)
        out = await asyncio.wait_for(chat.send_message(UserMessage(text=prompt)),
                                      timeout=timeout)
        return (out or "").strip()
    except Exception as e:
        logger.exception(f"[chip] ora_call failed: {e}")
        return f"❌ ORA call failed: {type(e).__name__}: {str(e)[:160]}"


async def fire_chip(chip_id: str, inputs: Optional[Dict[str, Any]],
                     db) -> Dict[str, Any]:
    spec = CHIP_TEMPLATES.get(chip_id)
    if not spec:
        return {"ok": False, "error": f"unknown_chip: {chip_id}"}
    inp = inputs or {}
    if spec.get("needs_form"):
        for f in spec.get("form_fields") or []:
            if f.get("required") and not (inp.get(f["name"]) or "").strip():
                return {"ok": False, "error": f"missing_field: {f['name']}"}

    started = datetime.now(timezone.utc)
    prompt = spec["build_prompt"](inp)
    out = await _ora_call(prompt)
    duration = round((datetime.now(timezone.utc) - started).total_seconds(), 2)

    record_id = uuid.uuid4().hex[:14]
    try:
        if db is not None:
            await db.console_chip_runs.insert_one({
                "chip_run_id": record_id, "chip_id": chip_id,
                "label": spec["label"], "inputs": inp,
                "output_markdown": out, "duration_s": duration,
                "ts": started.isoformat(),
            })
            # Stage 6 alignment: also write to ora_learnings
            from services.founders_pipeline import record_learning
            await record_learning(db, {
                "task_title": f"Quick chip: {spec['label']}",
                "raw_input": str(inp)[:300],
                "optimized_prompt": prompt,
                "council_verdict": "BYPASSED",
                "risk_score": 0,
                "outcome": "success" if not out.startswith("❌") else "failed",
                "files_changed": [],
                "duration_seconds": duration,
                "build_path": "quick_chip",
                "build_summary": {"chip_id": chip_id, "label": spec["label"]},
            })
    except Exception as e:
        logger.warning(f"[chip] persist failed: {e}")

    return {
        "ok": not out.startswith("❌"),
        "chip_run_id": record_id, "chip_id": chip_id, "label": spec["label"],
        "output_markdown": out, "duration_s": duration,
        "ts": started.isoformat(),
    }
