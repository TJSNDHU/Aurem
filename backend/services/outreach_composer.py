"""
ORA Outreach Composer — iter 282ai (Prompt 6).

LLM-composed per-lead per-channel outreach message. Wraps `tone_tuner` +
`emergentintegrations` (Claude Sonnet 4.5) into a single async call the
`followup_ora` drip dispatcher consumes instead of its old hardcoded bodies.

Public surface:
  • compose_outreach(lead, channel, step, *, site_change_context, scan_content)
  • compose_outreach_sync(...)    — pytest helper
  • composer_health()             — pillar chip probe

Never raises. On LLM failure the hardcoded fallback table below fires and
`fallback_used=True` is returned. Callers can log to `composer_fallbacks`.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import uuid
from datetime import datetime, timedelta, timezone

logger = logging.getLogger(__name__)

MODEL_PROVIDER = "anthropic"
MODEL_NAME = "claude-sonnet-4-5-20250929"
MAX_TOKENS = 400

CHANNEL_LIMITS = {
    "email":     {"word_cap": 150, "char_cap": None, "needs_subject": True},
    "sms":       {"word_cap":  30, "char_cap":  160, "needs_subject": False},
    "whatsapp":  {"word_cap": 200, "char_cap": None, "needs_subject": False},
    "linkedin":  {"word_cap": 100, "char_cap": None, "needs_subject": False},
}

SYSTEM_PROMPT = (
    "You are ORA, AUREM's AI outreach agent. AUREM is a Canadian-owned "
    "platform built in Mississauga, Ontario.\n\n"
    "GOLDEN RULE — VALUE FIRST:\n"
    "Every message must follow this sequence:\n"
    "  1. OBSERVE — show you know their situation (use their real "
    "business name, city, industry terms, specific pain point)\n"
    "  2. OFFER VALUE — give something useful BEFORE asking for anything "
    "(free website audit, free scan report, specific insight about their "
    "business, something they didn't know)\n"
    "  3. SOFT CTA — make it easy to say yes (preview link, not a sales "
    "pitch). Never: 'Buy now', 'Sign up today'. Always: 'Take a look', "
    "'Here's what we found', 'Worth 30 seconds?'\n"
    "  4. OPT-OUT — always present, never buried. CASL requirement. "
    "Non-negotiable.\n\n"
    "CANADIAN CONTEXT:\n"
    "  - Reference Canadian seasons/events when relevant (spring cleanup "
    "season, winter furnace checks, ICBC claims).\n"
    "  - Use Canadian spelling (colour, neighbour, centre).\n"
    "  - Reference Canadian trust signals (TSSA, ESA, RCDSO, ICBC, OHIP).\n"
    "  - Never mention US pricing, US laws, or US references.\n"
    "  - Distance in km, not miles. Temperature in Celsius.\n\n"
    "TONE BY STEP:\n"
    "  Step 1 (first touch): Helpful stranger — you noticed something, "
    "sharing it.\n"
    "  Step 2 (follow-up): Familiar neighbour — following up like a "
    "local would.\n"
    "  Step 3 (final): Respectful close — last message, no pressure, "
    "door open.\n\n"
    "HARD RULES:\n"
    "  - Always in English with Canadian spelling.\n"
    "  - Never sound robotic or templated.\n"
    "  - Reference specific details about the business.\n"
    "  - CASL compliant: always include opt-out in email/SMS.\n"
    "  - Max length: email 150 words, sms 160 CHARACTERS (hard limit), "
    "whatsapp 200 words, linkedin 100 words.\n"
    "  - For LinkedIn posts: include 2-3 hashtags at the end. Use "
    "specific location + category only. Examples: #MississaugaPlumbers "
    "#TorontoHVAC #OntarioAutoBody #CanadianContractors. Base on lead "
    "city + category. No generic tags.\n"
    "  - Never use deceptive subjects (no 'Re:', 'Fwd:', 'urgent', "
    "'final warning', 'last chance').\n"
    "  - Never use hard sales CTAs ('buy now', 'sign up today', "
    "'subscribe', 'pay now').\n"
    "  - Return JSON ONLY. No preamble, no markdown, no code fences."
)


# EMAIL_FOOTER is imported from value_first_hooks — re-exported here so
# tests / other services can `from services.outreach_composer import EMAIL_FOOTER`.
from services.value_first_hooks import EMAIL_FOOTER, SMS_FOOTER  # noqa: E402

# CASL-compliant fallback messages (public so tests can assert compliance).
# Iter 282al-7 — rewritten value-first + Canadian + physical address.
FALLBACK_MESSAGES = {
    "email": {
        "subject": "Found something about your business",
        "body": (
            "Hi, we ran a quick free audit on your online presence and "
            "found a few things that might be costing you customers. "
            "Putting the report together — no charge, no pitch.\n\n"
            "Worth a 30-second look?\n\n"
            "🍁 AUREM — Canadian-owned, Mississauga ON\n"
            + EMAIL_FOOTER
        ),
    },
    "sms": {
        "subject": None,
        "body": (
            "AUREM here — free website report ready: aurem.live/r/x. "
            + SMS_FOOTER
        ),
    },
    "whatsapp": {
        "subject": None,
        "body": (
            "AUREM ORA here — Canadian team, Mississauga-built. "
            "We pulled a free audit on your business. Worth a 30-second "
            "look? Reply STOP to opt out."
        ),
    },
    "linkedin": {
        "subject": None,
        "body": ("Hi, I work with Canadian trades on their web "
                  "presence — thought this might be useful. "
                  "#CanadianContractors #LocalBusiness"),
    },
}


# ─────────────────────────────────────────────────────────────────────
# Fallback table
# ─────────────────────────────────────────────────────────────────────
def _fallback(lead: dict, channel: str) -> dict:
    biz = lead.get("business_name") or "your business"
    lead_id = lead.get("lead_id") or "x"
    tpl = FALLBACK_MESSAGES.get(channel) or FALLBACK_MESSAGES["email"]
    if channel == "email":
        body = tpl["body"].replace("your business", biz) if "your business" in tpl["body"] else tpl["body"]
        # Personalize subject with business name.
        subject = tpl["subject"]
        if "your business" in subject:
            subject = subject.replace("your business", biz)
        else:
            subject = f"Found something about {biz}"
        return {"subject": subject, "body": body}
    if channel == "sms":
        body = (f"{biz}: free website report ready — aurem.live/r/{lead_id}. "
                 f"AUREM.ca — Canadian-built. Reply STOP to opt out.")
        return {"subject": None, "body": body[:160]}
    if channel == "whatsapp":
        body = tpl["body"].replace("local service businesses",
                                    f"{biz} and similar local businesses")
        return {"subject": None, "body": body}
    if channel == "linkedin":
        body = (f"Hi, I work with local service businesses on their web "
                 f"presence. Thought {biz} might find this useful. "
                 f"#CanadianContractors #LocalBusiness")
        return {"subject": None, "body": body}
    return {"subject": None, "body": tpl["body"]}


# ─────────────────────────────────────────────────────────────────────
# User prompt builder (deterministic per-input so tests can compare)
# ─────────────────────────────────────────────────────────────────────
def _build_user_prompt(lead: dict, channel: str, step: int,
                       site_change_context: str | None,
                       scan_content: str | None) -> str:
    from services.tone_tuner import get_outreach_tone
    # iter 282al-6 — industry slang injection.
    import random
    try:
        from services.industry_slang import get_industry_context
        industry = get_industry_context(lead.get("category") or "general")
    except Exception:
        industry = {}
    parts = [
        f"Business: {lead.get('business_name') or 'this business'}",
        f"Location: {(lead.get('city') or '').strip()} {(lead.get('province') or '').strip()}".strip(),
        f"Category: {lead.get('category') or ''}",
        f"Rating: {lead.get('yelp_rating', 'N/A')} "
        f"({lead.get('review_count', 0)} reviews)",
        f"Website status: {lead.get('has_website', False)}",
        f"Tone instruction: {get_outreach_tone(lead)}",
        f"Channel: {channel}",
        f"Drip step: {step}",
    ]
    if scan_content:
        parts.append(f"Site scan excerpt: {scan_content[:300]}")
    if site_change_context:
        parts.append(f"PRIORITY — site recently changed: {site_change_context}")

    if industry:
        pain_points = industry.get("pain_points") or []
        services    = industry.get("services") or []
        trust_sigs  = industry.get("trust_signals") or []
        searches    = industry.get("search_terms") or []
        urgency     = industry.get("urgency_hook") or ""
        cred_note   = industry.get("credibility_note") or ""
        pain   = random.choice(pain_points) if pain_points else ""
        trust  = random.choice(trust_sigs) if trust_sigs else ""
        search = (searches[0] if searches else "")
        svc    = ", ".join(services[:3])
        parts.append("INDUSTRY CONTEXT — weave these in naturally,")
        parts.append("DO NOT copy verbatim:")
        if pain:
            parts.append(f"  · Pain point: {pain}")
        if svc:
            parts.append(f"  · Their actual services: {svc}")
        if urgency:
            parts.append(f"  · Urgency angle: {urgency}")
        if trust:
            parts.append(f"  · Trust signal: {trust}")
        if search:
            parts.append(f"  · Customer search term: \"{search}\"")
        if cred_note:
            parts.append(f"  · Insider credibility: {cred_note}")
        parts.append("Sound like an industry insider — not a generic agency.")

    # iter 282al-7 — value-first hook injection (Canadian Moat).
    try:
        from services.value_first_hooks import get_value_hook
        hook = get_value_hook(lead, channel, step)
    except Exception:
        hook = {}
    if hook:
        parts.append("")
        parts.append("VALUE-FIRST STRUCTURE — adapt these naturally")
        parts.append("using the lead's real data. DO NOT copy verbatim:")
        if hook.get("value_offer"):
            parts.append(f"  · Value offer: {hook['value_offer']}")
        if hook.get("cta"):
            parts.append(f"  · Soft CTA style: {hook['cta']}")
        if hook.get("ps"):
            parts.append(f"  · Optional P.S.: {hook['ps']}")
        parts.append("Open with what you OBSERVED about them. Then the "
                     "value. Then the soft CTA. Always include opt-out.")

    instruction = (
        f"\nWrite the {channel} message now. "
        + ("For email also write a subject line. " if channel == "email" else "")
        + 'Return JSON only: {"subject": "...", "body": "..."} '
        "No preamble. No markdown. JSON only."
    )
    return "\n".join(parts) + instruction


# ─────────────────────────────────────────────────────────────────────
# Core composer
# ─────────────────────────────────────────────────────────────────────
def _clamp_limits(channel: str, body: str) -> str:
    limits = CHANNEL_LIMITS.get(channel) or {}
    cap = limits.get("char_cap")
    if cap and len(body) > cap:
        # iter 282al-7 — guarantee STOP survives truncation on SMS.
        # Reserve room for the opt-out tail and rebuild as
        # "<truncated body> Reply STOP" within cap.
        tail = " Reply STOP"
        head_room = max(0, cap - len(tail))
        body = body[:head_room].rstrip(" ,.;:") + tail
        return body[:cap].rstrip()
    word_cap = limits.get("word_cap")
    if word_cap:
        words = body.split()
        if len(words) > word_cap:
            return " ".join(words[:word_cap]).rstrip()
    return body


def _parse_llm_response(resp: str) -> dict | None:
    if not resp:
        return None
    # Strip markdown code fences if the model ignored the instruction.
    cleaned = resp.strip()
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", cleaned, flags=re.IGNORECASE | re.MULTILINE)
    try:
        return json.loads(cleaned)
    except Exception:
        m = re.search(r"\{.*\}", cleaned, re.S)
        if not m:
            return None
        try:
            return json.loads(m.group(0))
        except Exception:
            return None


async def compose_outreach(
    lead: dict,
    channel: str,
    step: int,
    db=None,
    *,
    site_change_context: str | None = None,
    scan_content: str | None = None,
) -> dict:
    """Compose one outreach message. Never raises.

    `db` is optional — when supplied, a 24h composed_outreach_cache layer is
    consulted before the LLM call (keyed by {lead_id}:{channel}:{step}) and
    successful LLM responses are written back. Pass `db=None` to bypass the
    cache (e.g. in `composer_health` probes).
    """
    channel = (channel or "").lower()
    if channel not in CHANNEL_LIMITS:
        channel = "email"
    lead = lead or {}
    step = int(step or 1)

    composed_at = datetime.now(timezone.utc)
    result_shell = {
        "channel":       channel,
        "subject":       None,
        "body":          "",
        "tone_used":     "",
        "model":         f"{MODEL_PROVIDER}:{MODEL_NAME}",
        "composed_at":   composed_at,
        "fallback_used": False,
        "cache_hit":     False,
    }
    try:
        from services.tone_tuner import get_outreach_tone
        result_shell["tone_used"] = get_outreach_tone(lead)
    except Exception:
        result_shell["tone_used"] = ""

    # ── Cache lookup ────────────────────────────────────────────────
    cache_key = None
    if db is not None:
        lead_id = lead.get("lead_id") or str(lead.get("_id") or "")
        if lead_id:
            cache_key = f"{lead_id}:{channel}:{step}"
            try:
                cutoff = composed_at - timedelta(hours=24)
                hit = await db.composed_outreach_cache.find_one(
                    {"key": cache_key, "ts": {"$gt": cutoff}},
                    projection={"_id": 0, "result": 1},
                )
                if hit and isinstance(hit.get("result"), dict):
                    cached = dict(hit["result"])
                    cached["cache_hit"] = True
                    # Preserve the original `composed_at` from cache
                    return cached
            except Exception as e:
                logger.debug(f"[composer] cache lookup failed: {e}")

    api_key = os.environ.get("EMERGENT_LLM_KEY", "").strip()
    if not api_key:
        fb = _fallback(lead, channel)
        result_shell.update({
            "subject":       fb.get("subject"),
            "body":          _clamp_limits(channel, fb.get("body") or ""),
            "fallback_used": True,
        })
        try:
            audit = casl_check_message(
                channel, result_shell.get("subject"), result_shell.get("body"),
            )
            result_shell["casl_passed"] = audit["passed"]
            result_shell["casl_fail_reason"] = audit["fail_reason"]
            if db is not None:
                await log_casl_score(
                    db,
                    message_id=str(uuid.uuid4()),
                    channel=channel,
                    passed=audit["passed"],
                    fail_reason=audit["fail_reason"],
                    lead_id=str(lead.get("lead_id") or ""),
                )
        except Exception as e:
            logger.debug(f"[composer] casl audit (no-key) failed: {e}")
        return result_shell

    try:
        # iter 282al-5 — route through unified LLM gateway: Sovereign
        # (Legion) → OpenRouter → Emergent → hard fallback. This gives
        # us zero-cost Legion first, cloud second, Emergent key last.
        from services.llm_gateway import call_llm_with_meta

        prompt = _build_user_prompt(
            lead, channel, step,
            site_change_context=site_change_context,
            scan_content=scan_content,
        )
        gw = await call_llm_with_meta(
            SYSTEM_PROMPT, prompt, max_tokens=MAX_TOKENS,
        )
        if not gw.get("ok"):
            raise ValueError(f"llm gateway exhausted: {gw.get('provider')}")
        resp = gw["content"]
        parsed = _parse_llm_response(resp)
        if not parsed or not (parsed.get("body") or "").strip():
            raise ValueError("LLM returned unparseable body")

        body = _clamp_limits(channel, str(parsed.get("body") or "").strip())
        subject = parsed.get("subject") if channel == "email" else None
        if channel == "email" and not subject:
            subject = f"Quick note for {lead.get('business_name') or 'your business'}"

        result_shell.update({
            "subject":       subject,
            "body":          body,
            "fallback_used": False,
            "llm_provider":  gw.get("provider"),
        })

        # iter 282al-7 — CASL value-first audit (LLM path).
        try:
            audit = casl_check_message(channel, subject, body)
            result_shell["casl_passed"] = audit["passed"]
            result_shell["casl_fail_reason"] = audit["fail_reason"]
            if db is not None:
                await log_casl_score(
                    db,
                    message_id=str(uuid.uuid4()),
                    channel=channel,
                    passed=audit["passed"],
                    fail_reason=audit["fail_reason"],
                    lead_id=str(lead.get("lead_id") or ""),
                )
        except Exception as e:
            logger.debug(f"[composer] casl audit failed: {e}")

        # ── Cache write-back (LLM path only; fallbacks not cached) ──
        if db is not None and cache_key:
            try:
                await db.composed_outreach_cache.update_one(
                    {"key": cache_key},
                    {"$set": {
                        "key":     cache_key,
                        "channel": channel,
                        "step":    step,
                        "result":  dict(result_shell),
                        "ts":      composed_at,
                    }},
                    upsert=True,
                )
            except Exception as e:
                logger.debug(f"[composer] cache write failed: {e}")

        return result_shell
    except Exception as e:
        logger.warning(f"[composer] LLM path failed ({type(e).__name__}): {str(e)[:160]}")
        fb = _fallback(lead, channel)
        result_shell.update({
            "subject":       fb.get("subject"),
            "body":          _clamp_limits(channel, fb.get("body") or ""),
            "fallback_used": True,
        })
        # iter 282al-7 — CASL audit on fallback path too.
        try:
            audit = casl_check_message(
                channel, result_shell.get("subject"), result_shell.get("body"),
            )
            result_shell["casl_passed"] = audit["passed"]
            result_shell["casl_fail_reason"] = audit["fail_reason"]
            if db is not None:
                await log_casl_score(
                    db,
                    message_id=str(uuid.uuid4()),
                    channel=channel,
                    passed=audit["passed"],
                    fail_reason=audit["fail_reason"],
                    lead_id=str(lead.get("lead_id") or ""),
                )
        except Exception as e2:
            logger.debug(f"[composer] casl audit (fallback) failed: {e2}")
        return result_shell


async def ensure_cache_indexes(db) -> None:
    """TTL 24h on composed_outreach_cache.ts. Idempotent."""
    if db is None:
        return
    try:
        await db.composed_outreach_cache.create_index(
            [("ts", 1)], expireAfterSeconds=86400, name="ts_ttl_24h",
        )
        await db.composed_outreach_cache.create_index(
            [("key", 1)], unique=True, name="key_uniq",
        )
    except Exception as e:
        logger.debug(f"[composer] cache index skipped: {e}")


def compose_outreach_sync(lead: dict, channel: str, step: int, db=None, **kw) -> dict:
    """Sync wrapper for pytest."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
                return ex.submit(
                    lambda: asyncio.run(compose_outreach(lead, channel, step, db, **kw))
                ).result()
    except RuntimeError:
        pass
    return asyncio.run(compose_outreach(lead, channel, step, db, **kw))


# ─────────────────────────────────────────────────────────────────────
# Pillar-map health chip
# ─────────────────────────────────────────────────────────────────────
async def composer_health() -> dict:
    """Pillar-chip probe.

    iter 282al-12 — fast config-only probe. The previous version did a
    real `compose_outreach` call which routed through the LLM gateway and
    blew past the chip's 2.5s budget on a cold Sovereign tunnel, painting
    the chip red. Now we just verify (a) the LLM key/cascade is configured
    and (b) the value-first hooks module loads. Behaviour-correctness is
    covered by `test_canadian_moat`."""
    try:
        # Verify hooks/footer are importable (used by every compose call)
        from services.value_first_hooks import (  # noqa: F401
            EMAIL_FOOTER, get_value_hook,
        )
    except Exception as e:
        return {"ok": False, "status": "red",
                "detail": f"value_first_hooks import: {e}"}

    has_emergent = bool(os.environ.get("EMERGENT_LLM_KEY", "").strip())
    has_sov = bool(os.environ.get("SOVEREIGN_NODE_URL", "").strip())
    has_or = bool(os.environ.get("OPENROUTER_API_KEY", "").strip())
    if not (has_emergent or has_sov or has_or):
        return {"ok": True, "status": "yellow",
                "fallback_used": True,
                "detail": "no LLM cascade configured — fallback only"}

    parts = []
    if has_sov: parts.append("Sovereign")
    if has_or: parts.append("OpenRouter")
    if has_emergent: parts.append("Emergent")
    return {"ok": True, "status": "green",
            "fallback_used": False,
            "detail": f"cascade ready: {' → '.join(parts)}"}


# ─────────────────────────────────────────────────────────────────────
# iter 282al-7 — CASL Value-First scorer
# ─────────────────────────────────────────────────────────────────────
DECEPTIVE_SUBJECTS = (
    "re:", "fwd:", "you won", "urgent", "final warning", "last chance",
    "act now",
)
HARD_SALES_CTAS = (
    "buy now", "sign up today", "subscribe now", "purchase",
    "pay now", "order today",
)
VALUE_WORDS = (
    "free", "found", "noticed", "built", "report", "scan",
    "discovered", "preview", "audit",
)


def casl_check_message(channel: str, subject: str | None, body: str) -> dict:
    """Run a CASL + value-first audit on a composed message.

    Returns {"passed": bool, "fail_reason": str|None, "checks": {...}}.
    """
    body_l = (body or "").lower()
    subj_l = (subject or "").lower()
    checks = {
        "has_optout": ("stop" in body_l) or ("unsubscribe" in body_l),
        "has_sender_id": "aurem" in body_l,
        "has_address": (
            "mississauga" in body_l or "sigsbee" in body_l
            or "ontario" in body_l or " on " in body_l or " on," in body_l
            or "ON L4T" in (body or "")
        ),
        "has_value_word": any(w in body_l for w in VALUE_WORDS),
        "no_hard_cta": not any(c in body_l for c in HARD_SALES_CTAS),
        "no_deceptive_subject": not any(d in subj_l for d in DECEPTIVE_SUBJECTS),
    }
    # Email is the strictest channel — must satisfy ALL.
    # SMS / WhatsApp / LinkedIn skip the address check (length budget).
    if channel == "email":
        required = ("has_optout", "has_sender_id", "has_address",
                     "has_value_word", "no_hard_cta", "no_deceptive_subject")
    else:
        required = ("has_optout", "has_sender_id", "has_value_word",
                     "no_hard_cta")
    fail = [k for k in required if not checks.get(k)]
    return {
        "passed": len(fail) == 0,
        "fail_reason": ",".join(fail) if fail else None,
        "checks": checks,
    }


async def log_casl_score(db, *, message_id: str, channel: str,
                          passed: bool, fail_reason: str | None,
                          lead_id: str = "") -> None:
    if db is None:
        return
    try:
        await db.casl_scores.insert_one({
            "message_id": message_id or str(uuid.uuid4()),
            "lead_id":    lead_id,
            "channel":    channel,
            "passed":     bool(passed),
            "fail_reason": fail_reason,
            "ts":         datetime.now(timezone.utc),
        })
    except Exception as e:
        logger.debug(f"[composer] casl log failed: {e}")


async def ensure_casl_indexes(db) -> None:
    """TTL 90d on casl_scores + ts/channel index. Idempotent."""
    if db is None:
        return
    try:
        await db.casl_scores.create_index(
            [("ts", 1)], expireAfterSeconds=90 * 24 * 3600,
            name="ts_ttl_90d",
        )
        await db.casl_scores.create_index(
            [("channel", 1), ("ts", -1)], name="channel_ts",
        )
    except Exception as e:
        logger.debug(f"[composer] casl index skipped: {e}")


__all__ = [
    "compose_outreach",
    "compose_outreach_sync",
    "composer_health",
    "ensure_cache_indexes",
    "casl_check_message",
    "log_casl_score",
    "ensure_casl_indexes",
    "CHANNEL_LIMITS",
    "MODEL_NAME",
    "FALLBACK_MESSAGES",
    "EMAIL_FOOTER",
    "SMS_FOOTER",
]
