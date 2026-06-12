"""
ORA Command Center
==================
Universal natural-language command parser + executor for AUREM.

Works across 3 channels:
  1. ORA chat (aurem.live)
  2. Telegram bot
  3. WhatsApp (WHAPI inbound)

Supported commands (case-insensitive, flexible word order):
  SCOUT:
    - "Scout {city} {industry}"                e.g. "Scout Toronto auto shops"
  CAMPAIGN:
    - "Blast {business name}"                  e.g. "Blast Damons Landscaping"
    - "Blast all {city} leads"                 e.g. "Blast all Toronto leads"
  REPORT:
    - "Show campaign stats"
    - "How many leads today"
    - "Who replied"
  WEBSITE:
    - "Build website for {slug}"
    - "Send website to {business}"
  SYSTEM:
    - "Pause campaigns"
    - "Resume campaigns"
    - "Show pipeline"
    - "Help" / "Commands"

All executors return a dict:
    {"ok": bool, "reply": str, "data": {...}}
The `reply` is a channel-agnostic plain/markdown string suitable for chat UI,
Telegram (Markdown), or WhatsApp (simple formatting).
"""
from __future__ import annotations

import logging
import os
import re
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Tuple

from shared.tenant import FOUNDER_BIN

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────
# PARSER
# ─────────────────────────────────────────────────────────────
INDUSTRY_SYNONYMS = {
    "auto shops": "auto repair shop",
    "auto shop": "auto repair shop",
    "mechanic": "auto repair shop",
    "mechanics": "auto repair shop",
    "salons": "hair salon",
    "salon": "hair salon",
    "dentists": "dentist",
    "dentist": "dentist",
    "restaurants": "restaurant",
    "restaurant": "restaurant",
    "landscapers": "landscaping",
    "landscaping": "landscaping",
    "plumbers": "plumber",
    "plumber": "plumber",
    "lawyers": "law firm",
    "attorneys": "law firm",
    "gyms": "gym",
    "cafes": "cafe",
    "coffee shops": "cafe",
}


def _normalize_industry(term: str) -> str:
    t = term.strip().lower()
    return INDUSTRY_SYNONYMS.get(t, t)


def parse_command(text: str) -> Dict[str, Any]:
    """
    Parse a free-form command string into {intent, params}.
    Returns {"intent": "UNKNOWN"} if no pattern matches.
    """
    if not text:
        return {"intent": "UNKNOWN", "params": {}, "raw": ""}

    # Strip leading bot mentions / slashes and whitespace
    t = re.sub(r"^[/@]\S+\s+", "", text.strip())
    low = t.lower()

    # HELP
    if low in ("help", "commands", "/help", "/start", "what can you do", "?"):
        return {"intent": "HELP", "params": {}, "raw": text}

    # AUTO-HUNT controls
    if re.match(r"^\s*pause\s+auto.?hunt\s*$", low):
        return {"intent": "AUTOHUNT_PAUSE", "params": {}, "raw": text}
    if re.match(r"^\s*resume\s+auto.?hunt\s*$", low):
        return {"intent": "AUTOHUNT_RESUME", "params": {}, "raw": text}
    if re.match(r"^\s*(show|view|list)\s+(hunt\s+)?queue\s*$", low):
        return {"intent": "AUTOHUNT_QUEUE", "params": {}, "raw": text}
    m_limit = re.match(r"^\s*set\s+daily\s+limit\s+(\d+)\s*$", low)
    if m_limit:
        return {"intent": "AUTOHUNT_SET_LIMIT", "params": {"limit": int(m_limit.group(1))}, "raw": text}

    # AGENT controls — "pause hunter", "resume closer"
    m_agent = re.match(r"^\s*(pause|resume)\s+(hunter|follow.?up|closer|referral)(?:\s+ora)?\s*$", low)
    if m_agent:
        action = m_agent.group(1)
        agent_raw = m_agent.group(2).replace("-", "").replace(" ", "")
        agent_map = {"hunter": "hunter_ora", "followup": "followup_ora", "closer": "closer_ora", "referral": "referral_ora"}
        agent_id = agent_map.get(agent_raw, agent_raw + "_ora")
        intent = "AGENT_PAUSE" if action == "pause" else "AGENT_RESUME"
        return {"intent": intent, "params": {"agent_id": agent_id}, "raw": text}

    # HUNT — "hunt {city} {industry} {count}"  (full Scout→Verify→Website→Blast pipeline)
    # Examples: "hunt mississauga auto shops 20", "hunt toronto dentists", "hunt TEST_CITY"
    m = re.match(r"^\s*hunt\s+(.+?)(?:\s+(\d+))?\s*$", low)
    if m:
        rest = m.group(1).strip()
        count = int(m.group(2)) if m.group(2) else 10
        # Try to split into city + industry (last known industry pattern or last word)
        ind_match = re.search(r"(auto\s*shops?|mechanics?|salons?|dentists?|restaurants?|landscap\w+|plumbers?|lawyers?|attorneys|gyms?|cafes?|coffee\s*shops?|[a-z]+ists?|[a-z]+ers?)\s*$", rest)
        if ind_match:
            industry = _normalize_industry(ind_match.group(1))
            city = rest[: ind_match.start()].strip()
        else:
            # No industry keyword — treat whole string as city, default industry
            city = rest
            industry = "businesses"
        # Special: TEST_CITY triggers mock mode automatically
        mock = city.strip().upper() == "TEST_CITY"
        return {
            "intent": "HUNT",
            "params": {"city": city.title(), "industry": industry, "count": count, "mock": mock},
            "raw": text,
        }

    # LOOKUP_BIN fast-path: "lookup BIN XXXX-XXXX" / "show RERO-DMYE" / "BIN PREV-HX5U"
    m = re.match(r"^\s*(?:lookup|show|details?|find|details for|info about)?\s*(?:bin|business[- ]?id)?\s*([A-Za-z]{2,5}-[A-Za-z0-9]{2,8})\b", text.strip(), re.IGNORECASE)
    if m:
        return {"intent": "LOOKUP_BIN", "params": {"bin_code": m.group(1).upper()}, "raw": text}
    if re.match(r"^\s*(list|show|all)\s+bins?\b|^\s*saare\s+(bin|business)", low):
        return {"intent": "LIST_BINS", "params": {}, "raw": text}
    if re.match(r"^\s*(list|show|all)\s+websites?\b|^\s*saari\s+website|linked\s+websites?\b", low):
        return {"intent": "LIST_WEBSITES", "params": {}, "raw": text}
    if re.match(r"^\s*(full\s+)?tenants?\s+(list|report|full)\b|tenant\s+intelligence", low):
        return {"intent": "LIST_TENANTS_FULL", "params": {}, "raw": text}

    # AGENT_ROI shortcut: "<agent> roi", "<agent> P&L", "<agent> ka hisaab"
    m = re.match(r"^\s*(scout|hunter|closer|envoy|follow.?up|referral)(?:\s+ora)?\s+(roi|p&?l|hisaab|ledger)\b", low)
    if m:
        agent_raw = m.group(1).replace("-", "").replace(" ", "")
        agent_map = {"scout": "scout_ora", "hunter": "hunter_ora", "closer": "closer_ora",
                     "envoy": "envoy_ora", "followup": "followup_ora", "referral": "referral_ora"}
        return {"intent": "AGENT_ROI", "params": {"agent_id": agent_map.get(agent_raw, agent_raw + "_ora")},
                "raw": text}

    # AGENT_SOUL shortcut: "<agent> soul" / "<agent> reflection"
    m = re.match(r"^\s*(scout|hunter|closer|envoy|follow.?up|referral)(?:\s+ora)?\s+(soul|reflection)\b", low)
    if m:
        agent_raw = m.group(1).replace("-", "").replace(" ", "")
        agent_map = {"scout": "scout_ora", "hunter": "hunter_ora", "closer": "closer_ora",
                     "envoy": "envoy_ora", "followup": "followup_ora", "referral": "referral_ora"}
        return {"intent": "AGENT_SOUL", "params": {"agent_id": agent_map.get(agent_raw, agent_raw + "_ora")},
                "raw": text}

    # SCOUT — "scout {city} {industry}"
    m = re.match(r"^\s*scout\s+(.+?)\s+(auto\s*shops?|mechanics?|salons?|dentists?|restaurants?|landscap\w+|plumbers?|lawyers?|attorneys|gyms?|cafes?|coffee\s*shops?|[a-z ]+shops?|[a-z]+ists?|[a-z]+ers?)\s*$", low)
    if m:
        return {
            "intent": "SCOUT",
            "params": {"city": m.group(1).strip().title(), "industry": _normalize_industry(m.group(2))},
            "raw": text,
        }
    # Fallback: "scout {query}" (freeform)
    m = re.match(r"^\s*scout\s+(.+)\s*$", low)
    if m:
        return {"intent": "SCOUT", "params": {"query": m.group(1).strip()}, "raw": text}

    # BLAST_BULK — "blast all {city} leads"
    m = re.match(r"^\s*blast\s+all\s+(.+?)\s+leads?\s*$", low)
    if m:
        return {"intent": "BLAST_BULK", "params": {"city": m.group(1).strip().title()}, "raw": text}

    # BLAST_ONE — "blast {business name}"
    m = re.match(r"^\s*blast\s+(.+?)\s*$", low)
    if m:
        return {"intent": "BLAST_ONE", "params": {"business_name": t[len("blast "):].strip()}, "raw": text}

    # STATS
    if re.search(r"\b(campaign\s+stats?|show\s+stats?|current\s+stats?)\b", low):
        return {"intent": "STATS", "params": {}, "raw": text}

    if re.search(r"\b(how\s+many\s+leads?|leads?\s+today|lead\s+count)\b", low):
        return {"intent": "LEAD_COUNT", "params": {}, "raw": text}

    if re.search(r"\bwho\s+replied\b|\breplies\s+today\b|\bshow\s+replies\b", low):
        return {"intent": "REPLIES", "params": {}, "raw": text}

    # PIPELINE
    if re.search(r"\bshow\s+pipeline\b|\bfull\s+status\b|\bwhere\s+do\s+we\s+stand\b", low):
        return {"intent": "PIPELINE", "params": {}, "raw": text}

    # WEBSITE
    m = re.match(r"^\s*build\s+website\s+for\s+(.+?)\s*$", low)
    if m:
        return {"intent": "WEBSITE_BUILD", "params": {"slug": m.group(1).strip().lower().replace(" ", "-")}, "raw": text}

    m = re.match(r"^\s*send\s+website\s+to\s+(.+?)\s*$", low)
    if m:
        return {"intent": "WEBSITE_SEND", "params": {"business_name": t[len("send website to "):].strip()}, "raw": text}

    # PAUSE / RESUME
    if re.search(r"\bpause\s+campaigns?\b|\bstop\s+all\s+outreach\b", low):
        return {"intent": "PAUSE", "params": {}, "raw": text}
    if re.search(r"\bresume\s+campaigns?\b|\brestart\s+outreach\b|\bstart\s+campaigns?\b", low):
        return {"intent": "RESUME", "params": {}, "raw": text}

    # VERIFY — multi-source accuracy check before outreach
    # "Verify {business}" or "Verify {business} in {city}"
    m = re.match(r"^\s*verify\s+(.+?)(?:\s+in\s+(.+?))?\s*$", low)
    if m:
        biz = t[len("verify "):].strip()
        city = ""
        if " in " in biz.lower():
            parts = biz.rsplit(" in ", 1)
            biz, city = parts[0].strip(), parts[1].strip()
        return {"intent": "VERIFY", "params": {"business_name": biz, "city": city}, "raw": text}

    # BUILD — "build <feature description>"   → AUREM self-builder
    m = re.match(r"^\s*build\s+(.+)$", low, re.DOTALL)
    if m and not low.startswith("build website"):
        return {"intent": "BUILD", "params": {"description": t[len("build "):].strip()}, "raw": text}

    # FIX — "fix <bug description>"   → routed through the builder for a patch
    m = re.match(r"^\s*fix\s+(.+)$", low, re.DOTALL)
    if m:
        return {"intent": "FIX", "params": {"description": t[len("fix "):].strip()}, "raw": text}

    # TEST_ENDPOINT — "test <endpoint>"   → quick GET/POST smoke call
    m = re.match(r"^\s*test\s+(\S+)\s*$", low)
    if m:
        return {"intent": "TEST_ENDPOINT", "params": {"endpoint": m.group(1).strip()}, "raw": text}

    # ─── iter 315h — Founder self-service platform intelligence ─────────
    # RUN_OUTREACH — arm a blast (fires when Twilio approves, no manual step)
    if re.search(
        r"(start\s+(blast|outreach|campaign)|"
        r"outreach\s+shuru|leads?\s+blast\s+karo|"
        r"go\s+(blast|live|outreach)?|"
        r"arm\s+(blast|campaign)|"
        r"run\s+(blast|outreach))",
        low
    ) or low.strip() in {"go", "ship it", "fire", "blast karo", "chalao"}:
        # Optional count / pitch / city
        m_count = re.search(r"\b(\d{2,3})\s+leads?", low)
        m_saas = re.search(r"(saas|subscription|\$97|97/mo)", low)
        m_city = re.search(r"(?:in|for|to)\s+([a-z\s]+?)(?:\s+(?:leads?|\$|auto|pitch|blast|$))", low)
        params = {}
        if m_count:
            params["count"] = int(m_count.group(1))
        if m_saas:
            params["pitch"] = "saas_97"
        if m_city:
            city_name = m_city.group(1).strip()
            if len(city_name) < 30:
                params["city"] = city_name.title()
        return {"intent": "RUN_OUTREACH", "params": params, "raw": text}

    # CANCEL — kill the most-recent armed campaign
    if re.search(
        r"^\s*(cancel|stop|abort|rok)\s+(blast|campaign|outreach)?\s*$",
        low
    ) or low.strip() in {"cancel", "stop", "abort"}:
        return {"intent": "CANCEL_OUTREACH", "params": {}, "raw": text}

    # PLATFORM_STATUS — one-shot health & activity snapshot
    if re.search(
        r"(platform\s+status|status\s+report|full\s+snapshot|"
        r"platform\s+(brief|summary|pulse|health|overview)|"
        r"what.?s\s+going\s+on|kya\s+chal\s+raha|aaj\s+ka\s+(brief|report|snapshot))",
        low
    ):
        return {"intent": "PLATFORM_STATUS", "params": {}, "raw": text}

    # SIGNUPS — real platform_users (excludes dogfood/test/admin)
    if re.search(
        r"(real\s+(signups?|users?|customers?)|"
        r"kitne\s+real\s+signup|"
        r"how\s+many\s+(new\s+)?(signups?|paying\s+customers?|platform\s+users?)|"
        r"signups?\s+today|signups?\s+count|user\s+count)",
        low
    ):
        return {"intent": "SIGNUPS", "params": {}, "raw": text}

    # VISITORS / PIXEL — aurem.live traffic
    if re.search(
        r"(visitors?|traffic|pixel\s+(data|hits|events?)|"
        r"koi\s+visitor|aurem\.live\s+pe\s+koi|"
        r"aurem\.live\s+(traffic|visitors?))",
        low
    ):
        return {"intent": "VISITORS", "params": {}, "raw": text}

    return {"intent": "UNKNOWN", "params": {}, "raw": text}


# ─────────────────────────────────────────────────────────────
# EXECUTORS — each returns {"ok": bool, "reply": str, "data": {...}}
# ─────────────────────────────────────────────────────────────
HELP_TEXT = (
    "*ORA Command Center*\n\n"
    "_Scout:_\n"
    "• `Scout Toronto auto shops`\n"
    "• `Scout Mississauga salons`\n\n"
    "_Verify (multi-source accuracy check):_\n"
    "• `Verify Damons Landscaping`\n"
    "• `Verify Tim Hortons in Toronto`\n\n"
    "_Campaign:_\n"
    "• `Blast Damons Landscaping`\n"
    "• `Blast all Toronto leads`\n\n"
    "_Reports:_\n"
    "• `Show campaign stats`\n"
    "• `How many leads today`\n"
    "• `Who replied`\n"
    "• `Show pipeline`\n\n"
    "_Platform intelligence (iter 315h):_\n"
    "• `Platform status report` — full 24h snapshot\n"
    "• `How many real signups` — platform_users (dogfood excluded)\n"
    "• `Any visitors on aurem.live` — pixel traffic\n\n"
    "_Websites:_\n"
    "• `Build website for damons-landscaping`\n"
    "• `Send website to Damons Landscaping`\n\n"
    "_System:_\n"
    "• `Pause campaigns` / `Resume campaigns`\n\n"
    "_Builder (admin):_\n"
    "• `Build endpoint /api/builder-test returning build status`\n"
    "• `Fix the /api/leads endpoint returning 500`\n"
    "• `Test /api/telegram/status`"
)


async def _exec_scout(db, params: Dict[str, Any]) -> Dict[str, Any]:
    city = params.get("city") or ""
    industry = params.get("industry") or ""
    query = params.get("query") or f"{industry} in {city}".strip()
    if not query:
        return {"ok": False, "reply": "Tell me *what* and *where* — e.g. `Scout Toronto auto shops`.", "data": {}}

    try:
        from services.business_scout import scout_business_full
        result = await scout_business_full(query, "")
    except Exception as e:
        return {"ok": False, "reply": f"Scout failed: {e}", "data": {}}

    found_any = False
    lines: List[str] = []
    gp = result.get("sources", {}).get("google_places") or {}
    if gp:
        found_any = True
        lines.append(f"*{gp.get('business_name','')}* — {gp.get('rating','—')}⭐ ({gp.get('review_count',0)} reviews)")
        if gp.get("phone"):
            lines.append(f"📞 {gp['phone']}")
        if gp.get("address"):
            lines.append(f"📍 {gp['address']}")
        others = gp.get("other_results", [])
        if others:
            lines.append("\n_More in area:_")
            for o in others[:5]:
                lines.append(f"• {o.get('name','')} — {o.get('address','')[:60]}")

    ddg = result.get("sources", {}).get("duckduckgo") or {}
    if not found_any and ddg.get("results"):
        for r in ddg["results"][:5]:
            lines.append(f"• {r.get('title','')} — {r.get('url','')}")
        found_any = True

    if not found_any:
        return {
            "ok": False,
            "reply": f"No results for *{query}*. Try a different city or industry.",
            "data": result,
        }

    # Auto-persist the top hit as a campaign_lead (admins can blast it later)
    lead_doc = None
    if gp and gp.get("business_name"):
        slug = re.sub(r"[^a-z0-9]+", "-", gp["business_name"].lower()).strip("-")[:60]
        lead_doc = {
            "lead_id": slug,
            "business_name": gp["business_name"],
            "phone": gp.get("phone", ""),
            "website_url": gp.get("website", ""),
            "category": gp.get("primary_type", ""),
            "city": city,
            "rating": gp.get("rating"),
            "issues_count": 0,
            "score": int(float(gp.get("rating") or 4) * 20),
            "source": "ora_scout_command",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        if db is not None:
            try:
                await db.campaign_leads.update_one(
                    {"lead_id": slug, "business_id": FOUNDER_BIN},
                    {"$setOnInsert": lead_doc, "$set": {"last_scouted_at": lead_doc["created_at"]}},
                    upsert=True,
                )
                # AUTO-GENERATE sample website for prospects without an existing site
                if not lead_doc.get("website_url"):
                    try:
                        from routers.website_builder_router import auto_generate_if_missing
                        await auto_generate_if_missing(db, lead_doc)
                    except Exception as ge:
                        logger.warning(f"[ORA-CC] Website auto-generate failed for {slug}: {ge}")
            except Exception as e:
                logger.warning(f"[ORA-CC] Failed to persist scouted lead: {e}")

    header = f"🔍 *Scout* — {query}\n"
    reply = header + "\n".join(lines)
    if lead_doc:
        reply += f"\n\n_Saved as lead `{lead_doc['lead_id']}` — blast with_ `Blast {lead_doc['business_name']}`"
    return {"ok": True, "reply": reply, "data": {"lead": lead_doc, "scout": result}}


async def _find_lead_by_name(db, name: str) -> Optional[Dict[str, Any]]:
    if db is None or not name:
        return None
    # Try exact lead_id (slug) first, then case-insensitive business_name
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    lead = await db.campaign_leads.find_one(
        {"lead_id": slug, "business_id": FOUNDER_BIN}, {"_id": 0})
    if lead:
        return lead
    return await db.campaign_leads.find_one(
        {"business_name": {"$regex": f"^{re.escape(name)}$", "$options": "i"},
         "business_id": FOUNDER_BIN}, {"_id": 0}
    )


async def _exec_blast_one(db, params: Dict[str, Any]) -> Dict[str, Any]:
    name = params.get("business_name", "").strip()
    if not name:
        return {"ok": False, "reply": "Which business? e.g. `Blast Damons Landscaping`", "data": {}}
    if db is None:
        return {"ok": False, "reply": "Database unavailable.", "data": {}}

    lead = await _find_lead_by_name(db, name)
    if not lead:
        return {"ok": False, "reply": f"No lead found for *{name}*. Run `Scout` first.", "data": {}}

    # Ensure a sample website exists before blasting (prospects without websites get one)
    if not lead.get("website_url"):
        try:
            from routers.website_builder_router import auto_generate_if_missing
            await auto_generate_if_missing(db, lead)
        except Exception as e:
            logger.warning(f"[ORA-CC] Pre-blast website auto-generate failed: {e}")

    try:
        from routers.campaign_router import blast_all_channels  # type: ignore
        # Build a minimal Request-like object — reuse the FastAPI function by calling its core directly
        # The endpoint depends on _verify_admin + request; we bypass by calling internal pipeline.
        from services.aurem_outreach_templates import (
            render_whatsapp, render_sms, render_email_subject, render_email_html,
        )
        from services.email_engine import resend  # iter 326x defensive
        import httpx
        results: Dict[str, Any] = {}

        email = (lead.get("email") or "").strip()
        phone = (lead.get("phone") or "").strip()

        # EMAIL
        if email:
            try:
                resend.api_key = os.environ.get("RESEND_API_KEY", "")
                r = resend.Emails.send({
                    "from": "ORA <ora@aurem.live>",
                    "to": [email],
                    "subject": render_email_subject(lead),
                    "html": render_email_html(lead),
                })
                results["email"] = {"ok": True, "id": r.get("id")}
            except Exception as e:
                results["email"] = {"ok": False, "error": str(e)[:120]}
        else:
            results["email"] = {"ok": False, "error": "no email"}

        # WHATSAPP
        if phone:
            try:
                whapi_token = os.environ.get("WHAPI_API_TOKEN", "")
                whapi_url = os.environ.get("WHAPI_API_URL", "")
                if whapi_token and whapi_url:
                    clean = phone.replace("+", "").replace("-", "").replace(" ", "")
                    async with httpx.AsyncClient(timeout=15) as client:
                        resp = await client.post(
                            f"{whapi_url}/messages/text",
                            headers={"authorization": f"Bearer {whapi_token}", "content-type": "application/json"},
                            json={"to": f"{clean}@s.whatsapp.net", "body": render_whatsapp(lead)},
                        )
                    results["whatsapp"] = {"ok": resp.status_code == 200, "status": resp.status_code}
                else:
                    results["whatsapp"] = {"ok": False, "error": "whapi not configured"}
            except Exception as e:
                results["whatsapp"] = {"ok": False, "error": str(e)[:120]}
        else:
            results["whatsapp"] = {"ok": False, "error": "no phone"}

        # SMS
        if phone:
            try:
                sid = os.environ.get("TWILIO_ACCOUNT_SID", "")
                token = os.environ.get("TWILIO_AUTH_TOKEN", "")
                from_num = os.environ.get("TWILIO_PHONE_NUMBER", "")
                if sid and token and from_num:
                    async with httpx.AsyncClient(timeout=15) as client:
                        resp = await client.post(
                            f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json",
                            auth=(sid, token),
                            data={"From": from_num, "To": phone, "Body": render_sms(lead)},
                        )
                    results["sms"] = {"ok": resp.status_code in (200, 201), "status": resp.status_code}
                else:
                    results["sms"] = {"ok": False, "error": "twilio not configured"}
            except Exception as e:
                results["sms"] = {"ok": False, "error": str(e)[:120]}
        else:
            results["sms"] = {"ok": False, "error": "no phone"}

        sent = [k for k, v in results.items() if v.get("ok")]
        failed = [k for k, v in results.items() if not v.get("ok")]
        reply = (
            f"📣 *Blast to {lead.get('business_name')}*\n"
            f"✅ Sent: {', '.join(sent) or 'none'}\n"
            f"❌ Skipped/Failed: {', '.join(failed) or 'none'}"
        )
        # Persist history
        try:
            await db.campaign_leads.update_one(
                {"lead_id": lead["lead_id"], "business_id": FOUNDER_BIN},
                {"$set": {"last_blasted_at": datetime.now(timezone.utc).isoformat()},
                 "$inc": {"blast_count": 1}},
            )
        except Exception:
            pass
        return {"ok": True, "reply": reply, "data": results}
    except Exception as e:
        logger.exception("blast failed")
        return {"ok": False, "reply": f"Blast failed: {e}", "data": {}}


async def _exec_blast_bulk(db, params: Dict[str, Any]) -> Dict[str, Any]:
    city = params.get("city", "").strip()
    if not city:
        return {"ok": False, "reply": "Which city? e.g. `Blast all Toronto leads`", "data": {}}
    if db is None:
        return {"ok": False, "reply": "Database unavailable.", "data": {}}

    cursor = db.campaign_leads.find(
        {"city": {"$regex": f"^{re.escape(city)}$", "$options": "i"}, "status": {"$ne": "do_not_contact"},
         "business_id": FOUNDER_BIN},
        {"_id": 0, "lead_id": 1, "business_name": 1},
    ).limit(25)
    leads = await cursor.to_list(25)
    if not leads:
        return {"ok": False, "reply": f"No leads in *{city}*. Run `Scout {city} <industry>` first.", "data": {}}

    summary = {"total": len(leads), "succeeded": 0, "failed": 0}
    for lead in leads:
        res = await _exec_blast_one(db, {"business_name": lead["business_name"]})
        if res.get("ok"):
            summary["succeeded"] += 1
        else:
            summary["failed"] += 1

    reply = (
        f"📣 *Bulk blast to {city}* — {summary['total']} leads\n"
        f"✅ {summary['succeeded']} sent\n"
        f"❌ {summary['failed']} failed"
    )
    return {"ok": True, "reply": reply, "data": summary}


async def _exec_stats(db, _params: Dict[str, Any]) -> Dict[str, Any]:
    if db is None:
        return {"ok": False, "reply": "Database unavailable.", "data": {}}
    campaign = await db.campaigns.find_one(
        {"campaign_id": "aurem-acquisition-001"}, {"_id": 0, "stats": 1, "status": 1}
    )
    stats = (campaign or {}).get("stats", {}) or {}
    total_leads = await db.campaign_leads.count_documents({"business_id": FOUNDER_BIN})
    today = datetime.now(timezone.utc).date().isoformat()
    leads_today = await db.campaign_leads.count_documents(
        {"business_id": FOUNDER_BIN, "created_at": {"$gte": today}})
    reply = (
        f"📊 *Campaign Stats*\n"
        f"Status: `{(campaign or {}).get('status','inactive')}`\n"
        f"Total leads: *{total_leads}*  (today: *{leads_today}*)\n"
        f"Emails sent: {stats.get('emails_sent', 0)}\n"
        f"SMS sent: {stats.get('sms_sent', 0)}\n"
        f"WhatsApp sent: {stats.get('whatsapp_sent', 0)}\n"
        f"Replies: {stats.get('replies', 0)}"
    )
    return {"ok": True, "reply": reply, "data": {"stats": stats, "total_leads": total_leads, "leads_today": leads_today}}


async def _exec_lead_count(db, _params: Dict[str, Any]) -> Dict[str, Any]:
    if db is None:
        return {"ok": False, "reply": "Database unavailable.", "data": {}}
    today = datetime.now(timezone.utc).date().isoformat()
    total = await db.campaign_leads.count_documents({"business_id": FOUNDER_BIN})
    today_count = await db.campaign_leads.count_documents(
        {"business_id": FOUNDER_BIN, "created_at": {"$gte": today}})
    return {
        "ok": True,
        "reply": f"📈 *{today_count}* leads captured today.\n_All-time:_ {total}",
        "data": {"today": today_count, "total": total},
    }


async def _exec_replies(db, _params: Dict[str, Any]) -> Dict[str, Any]:
    if db is None:
        return {"ok": False, "reply": "Database unavailable.", "data": {}}
    since = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
    cursor = db.campaign_leads.find(
        {"status": {"$in": ["replied", "interested", "hot"]}, "last_reply_at": {"$gte": since},
         "business_id": FOUNDER_BIN},
        {"_id": 0, "business_name": 1, "status": 1, "last_reply_at": 1, "last_reply_text": 1},
    ).sort("last_reply_at", -1).limit(10)
    items = await cursor.to_list(10)
    if not items:
        return {"ok": True, "reply": "No replies in the last 7 days.", "data": []}
    lines = ["💬 *Recent Replies*"]
    for it in items:
        lines.append(f"• *{it.get('business_name')}* — `{it.get('status','replied')}`")
        if it.get("last_reply_text"):
            lines.append(f"  _{it['last_reply_text'][:110]}_")
    return {"ok": True, "reply": "\n".join(lines), "data": items}


async def _exec_pipeline(db, _params: Dict[str, Any]) -> Dict[str, Any]:
    if db is None:
        return {"ok": False, "reply": "Database unavailable.", "data": {}}
    statuses = ["new", "contacted", "replied", "interested", "hot", "closed_won", "closed_lost"]
    counts: Dict[str, int] = {}
    for s in statuses:
        counts[s] = await db.campaign_leads.count_documents(
            {"status": s, "business_id": FOUNDER_BIN})
    unstatused = await db.campaign_leads.count_documents(
        {"status": {"$exists": False}, "business_id": FOUNDER_BIN})
    total = sum(counts.values()) + unstatused
    lines = [f"📊 *Pipeline* (total {total})"]
    for s in statuses:
        if counts[s]:
            lines.append(f"• {s.replace('_',' ').title()}: *{counts[s]}*")
    if unstatused:
        lines.append(f"• Unclassified: {unstatused}")
    return {"ok": True, "reply": "\n".join(lines), "data": counts}


async def _exec_website_build(db, params: Dict[str, Any]) -> Dict[str, Any]:
    slug = params.get("slug", "").strip()
    if not slug:
        return {"ok": False, "reply": "Usage: `Build website for damons-landscaping`", "data": {}}
    try:
        from services.website_builder import generate_website_for_slug
        result = await generate_website_for_slug(db, slug)
        url = f"https://aurem.live/sample/{slug}"
        return {
            "ok": True,
            "reply": f"🌐 Website ready: {url}\n\n_Send to prospect with_ `Send website to {slug}`",
            "data": result if isinstance(result, dict) else {"slug": slug},
        }
    except ImportError:
        return {"ok": False, "reply": "Website builder service not available on this server.", "data": {}}
    except Exception as e:
        return {"ok": False, "reply": f"Build failed: {e}", "data": {}}


async def _exec_website_send(db, params: Dict[str, Any]) -> Dict[str, Any]:
    name = params.get("business_name", "").strip()
    if not name or db is None:
        return {"ok": False, "reply": "Usage: `Send website to <business name>`", "data": {}}
    lead = await _find_lead_by_name(db, name)
    if not lead:
        return {"ok": False, "reply": f"No lead for *{name}*. Run `Scout` first.", "data": {}}
    # Stamp lead with sample URL and trigger blast
    slug = lead["lead_id"]
    await db.campaign_leads.update_one(
        {"lead_id": slug, "business_id": FOUNDER_BIN},
        {"$set": {"sample_website_url": f"https://aurem.live/sample/{slug}"}},
    )
    return await _exec_blast_one(db, {"business_name": lead["business_name"]})


async def _exec_pause_resume(db, pause: bool) -> Dict[str, Any]:
    if db is None:
        return {"ok": False, "reply": "Database unavailable.", "data": {}}
    new_status = "paused" if pause else "active"
    await db.campaigns.update_one(
        {"campaign_id": "aurem-acquisition-001"},
        {"$set": {"status": new_status, "status_changed_at": datetime.now(timezone.utc).isoformat()}},
        upsert=True,
    )
    verb = "paused" if pause else "resumed"
    return {"ok": True, "reply": f"⏸️ Campaigns *{verb}*.\nAll scheduled outreach {'halted' if pause else 'restarted'}.", "data": {"status": new_status}}


# ─────────────────────────────────────────────────────────────
# iter 315h — Founder self-service platform intelligence
# ─────────────────────────────────────────────────────────────
_TEST_EMAIL_RE = re.compile(
    r"(dogfood|\+test|test@|seed|example\.com|admin@|demo@|fake|"
    r"polarisbuilt|teji\.ss1986@gmail|healthcheck@)",
    re.IGNORECASE,
)


async def _exec_signups(db, _params: Dict[str, Any]) -> Dict[str, Any]:
    """Real platform user count excluding dogfood/test/admin/healthcheck."""
    if db is None:
        return {"ok": False, "reply": "DB unavailable", "data": {}}
    try:
        total = await db.platform_users.count_documents({})
        real_filter = {"email": {"$not": {"$regex": _TEST_EMAIL_RE.pattern,
                                              "$options": "i"}}}
        real = await db.platform_users.count_documents(real_filter)
        t24 = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
        t7 = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
        new24_real = await db.platform_users.count_documents(
            {**real_filter, "created_at": {"$gte": t24}})
        new7_real = await db.platform_users.count_documents(
            {**real_filter, "created_at": {"$gte": t7}})
        # Latest 3 real users (for context)
        latest = []
        async for u in db.platform_users.find(
            real_filter,
            {"_id": 0, "email": 1, "created_at": 1, "business_id": 1}
        ).sort("created_at", -1).limit(3):
            latest.append(u)
        lines = [
            "*🧑 Real signups (dogfood/test excluded)*",
            f"• Total: *{real}*  (raw: {total})",
            f"• Last 24h: *{new24_real}*",
            f"• Last 7d: *{new7_real}*",
        ]
        if latest:
            lines.append("")
            lines.append("_Recent:_")
            for u in latest:
                lines.append(
                    f"• `{u.get('business_id','?')}` "
                    f"{u.get('email','?')} "
                    f"({(u.get('created_at','?') or '')[:10]})"
                )
        if real == 0:
            lines.append("")
            lines.append("_No real signups yet — Twilio 10DLC approval will "
                            "unlock outbound → first awareness wave._")
        return {"ok": True, "reply": "\n".join(lines),
                "data": {"real": real, "total": total,
                          "new24_real": new24_real, "new7_real": new7_real,
                          "latest": latest}}
    except Exception as e:
        return {"ok": False, "reply": f"Query failed: {e}", "data": {}}


async def _exec_visitors(db, _params: Dict[str, Any]) -> Dict[str, Any]:
    """aurem.live pixel traffic snapshot."""
    if db is None:
        return {"ok": False, "reply": "DB unavailable", "data": {}}
    try:
        t24 = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
        t1 = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        total = await db.pixel_events.count_documents({})
        last24 = await db.pixel_events.count_documents(
            {"timestamp": {"$gte": t24}})
        last1 = await db.pixel_events.count_documents(
            {"timestamp": {"$gte": t1}})
        sessions = await db.pixel_events.distinct("session_id") or []
        sessions = [s for s in sessions if s]
        # Dogfood tenant specifically
        rugc = await db.pixel_events.count_documents(
            {"business_id": "AURE-RUGC"})
        lines = [
            "*📡 aurem.live visitor pulse (pixel)*",
            f"• Events all-time: *{total}*",
            f"• Last 24h: *{last24}*",
            f"• Last 1h: *{last1}*",
            f"• Distinct sessions: *{len(sessions)}*",
            f"• AURE-RUGC (dogfood tag): {rugc}",
        ]
        if last24 == 0:
            lines.append("")
            lines.append("_Zero traffic in 24h — pixel may not be deployed to "
                            "prod yet (check `/app/frontend/public/index.html` "
                            "embed + redeploy)._")
        return {"ok": True, "reply": "\n".join(lines),
                "data": {"total": total, "last24": last24, "last1": last1,
                          "distinct_sessions": len(sessions),
                          "aure_rugc": rugc}}
    except Exception as e:
        return {"ok": False, "reply": f"Pixel query failed: {e}", "data": {}}


async def _exec_platform_status(db, _params: Dict[str, Any]) -> Dict[str, Any]:
    """One-shot founder dashboard — signups + leads + scans + sites + outreach
    + real revenue, 24h window. Written to be copy-pasteable into WhatsApp."""
    if db is None:
        return {"ok": False, "reply": "DB unavailable", "data": {}}
    try:
        t24 = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
        real_filter = {"email": {"$not": {"$regex": _TEST_EMAIL_RE.pattern,
                                              "$options": "i"}}}
        # Signups
        users_real = await db.platform_users.count_documents(real_filter)
        users_24 = await db.platform_users.count_documents(
            {**real_filter, "created_at": {"$gte": t24}})
        # Leads
        leads_24 = await db.campaign_leads.count_documents(
            {"business_id": FOUNDER_BIN, "created_at": {"$gte": t24}})
        leads_total = await db.campaign_leads.count_documents(
            {"business_id": FOUNDER_BIN})
        # Scans
        scans_24 = await db.customer_scans.count_documents(
            {"created_at": {"$gte": t24}})
        # Sites
        sites_built_24 = await db.auto_built_sites.count_documents(
            {"created_at": {"$gte": t24}})
        sites_pub_total = await db.auto_built_sites.count_documents(
            {"status": {"$in": ["published", "deployed", "rendered"]}})
        # Outreach enqueued
        welcome_24 = await db.auto_built_sites.count_documents(
            {"post_publish.welcome_sent_at": {"$gte": t24}})
        upsell_24 = await db.auto_built_sites.count_documents(
            {"post_publish.upsell_sent_at": {"$gte": t24}})
        # Real revenue
        paid_24 = await db.repair_orders.count_documents(
            {"paid_at": {"$gte": t24}})
        pay_succeeded_24 = await db.payment_transactions.count_documents(
            {"$or": [{"created_at": {"$gte": t24}},
                      {"paid_at": {"$gte": t24}}],
              "status": {"$in": ["paid", "succeeded", "complete",
                                    "completed"]}})
        # NPS
        nps_24 = await db.nps_responses.count_documents(
            {"created_at": {"$gte": t24}})
        # Pixel
        try:
            pixel_24 = await db.pixel_events.count_documents(
                {"timestamp": {"$gte": t24}})
        except Exception:
            pixel_24 = 0
        # Errors
        try:
            anomaly_24 = await db.anomaly_detections.count_documents(
                {"$or": [{"created_at": {"$gte": t24}},
                          {"timestamp": {"$gte": t24}}]})
        except Exception:
            anomaly_24 = 0

        real_rev = bool(paid_24 or pay_succeeded_24)
        lines = [
            "*📊 AUREM · Platform Status (24h)*",
            "",
            "*🧑 Signups*",
            f"• Real users total: *{users_real}*  · 24h: *{users_24}*",
            "",
            "*🎯 Acquisition*",
            f"• Leads captured: *{leads_24}*  (all-time {leads_total})",
            f"• Sites scanned: *{scans_24}*",
            f"• aurem.live visitors: *{pixel_24}*",
            "",
            "*🏗 Build*",
            f"• Sites built: *{sites_built_24}*  · published all-time: {sites_pub_total}",
            "",
            "*📣 Outreach (enqueued)*",
            f"• Welcome messages: *{welcome_24}*",
            f"• Domain upsell: *{upsell_24}*",
            "",
            "*💰 Real revenue*",
            f"• Paid repair orders: *{paid_24}*",
            f"• Stripe txns succeeded: *{pay_succeeded_24}*",
            f"• NPS responses: *{nps_24}*",
            "",
            "*🚨 Errors*",
            f"• Anomaly detections: *{anomaly_24}*",
            "",
            ("_🟢 Revenue landed — check Boardroom._"
              if real_rev
              else "_🔴 Zero real revenue — Twilio 10DLC approval is the single "
                    "unblocker for outbound → first customer._"),
        ]
        return {"ok": True, "reply": "\n".join(lines),
                "data": {
                    "users_real": users_real, "users_24": users_24,
                    "leads_24": leads_24, "leads_total": leads_total,
                    "scans_24": scans_24,
                    "sites_built_24": sites_built_24,
                    "sites_pub_total": sites_pub_total,
                    "welcome_24": welcome_24, "upsell_24": upsell_24,
                    "paid_24": paid_24,
                    "pay_succeeded_24": pay_succeeded_24,
                    "nps_24": nps_24, "pixel_24": pixel_24,
                    "anomaly_24": anomaly_24,
                }}
    except Exception as e:
        logger.exception("[ORA-CC] platform status failed")
        return {"ok": False, "reply": f"Status query failed: {e}", "data": {}}


# ─────────────────────────────────────────────────────────────
# MAIN ENTRY POINT
# ─────────────────────────────────────────────────────────────
EXECUTORS = {
    "SCOUT": _exec_scout,
    "BLAST_ONE": _exec_blast_one,
    "BLAST_BULK": _exec_blast_bulk,
    "STATS": _exec_stats,
    "LEAD_COUNT": _exec_lead_count,
    "REPLIES": _exec_replies,
    "PIPELINE": _exec_pipeline,
    "WEBSITE_BUILD": _exec_website_build,
    "WEBSITE_SEND": _exec_website_send,
    "PAUSE": lambda db, p: _exec_pause_resume(db, True),
    "RESUME": lambda db, p: _exec_pause_resume(db, False),
    "VERIFY": None,  # bound below after _exec_verify is defined
    "HUNT": None,    # bound below after _exec_hunt is defined
    # iter 315h — founder self-service platform intelligence
    "PLATFORM_STATUS": _exec_platform_status,
    "SIGNUPS": _exec_signups,
    "VISITORS": _exec_visitors,
    # iter 315i — founder outreach armament (bound below)
    "RUN_OUTREACH": None,
    "CANCEL_OUTREACH": None,
}


async def _exec_run_outreach(db, params: Dict[str, Any]) -> Dict[str, Any]:
    """Arm a blast campaign. No actual send until Twilio approves +
    scheduled_at. Params: count, pitch ('repair_149'|'saas_97'), city,
    schedule ('monday_9am'|'now')."""
    if db is None:
        return {"ok": False, "reply": "DB unavailable", "data": {}}
    try:
        from services.armed_outreach import arm_outreach
        out = await arm_outreach(
            db,
            count=int(params.get("count") or 50),
            pitch=params.get("pitch") or "repair_149",
            city=params.get("city"),
            schedule=params.get("schedule") or "monday_9am",
        )
        if not out.get("ok"):
            err = out.get("error") or "failed"
            if err == "no_eligible_leads":
                return {"ok": False,
                        "reply": "No unblasted leads available. "
                                   "Run `Scout <city> <industry>` first.",
                        "data": out}
            return {"ok": False, "reply": f"Arm failed: {err}", "data": out}
        if out.get("skipped") == "already_armed":
            reply = (
                f"⚠️ Campaign already armed — *{out['campaign_id']}*\n"
                f"{out['lead_count']} leads queued.\n"
                f"Fires: `{out['scheduled_at']}`\n"
                f"Pitch: {out['pitch_label']}\n\n"
                f"_Reply_ `cancel` _to release, then try again._")
            return {"ok": True, "reply": reply, "data": out}
        reply = (
            f"✅ *{out['lead_count']} leads armed.*\n"
            f"Blast: *{out.get('scheduled_local') or out['scheduled_at']}*\n"
            f"Pitch: *{out['pitch_label']}*\n"
            f"Campaign: `{out['campaign_id']}`\n\n"
            f"_Fires automatically when Twilio approves + scheduled time hits "
            f"— no manual step._\n"
            f"_Reply_ `cancel` _to stop._")
        return {"ok": True, "reply": reply, "data": out}
    except Exception as e:
        logger.exception("[ORA-CC] run_outreach failed")
        return {"ok": False, "reply": f"Arm failed: {e}", "data": {}}


async def _exec_cancel_outreach(db, _params: Dict[str, Any]) -> Dict[str, Any]:
    if db is None:
        return {"ok": False, "reply": "DB unavailable", "data": {}}
    try:
        from services.armed_outreach import cancel_latest_armed
        out = await cancel_latest_armed(db)
        if not out.get("ok"):
            if out.get("error") == "no_armed_campaign":
                return {"ok": False,
                        "reply": "No armed campaign to cancel.",
                        "data": out}
            return {"ok": False, "reply": f"Cancel failed: {out.get('error')}",
                    "data": out}
        reply = (
            f"🛑 *Campaign cancelled* — `{out['cancelled']}`\n"
            f"Released {out['released_leads']} leads back to the pool.")
        return {"ok": True, "reply": reply, "data": out}
    except Exception as e:
        return {"ok": False, "reply": f"Cancel failed: {e}", "data": {}}


# Bind forward-refs so EXECUTORS keys resolve correctly on import.
EXECUTORS["RUN_OUTREACH"] = _exec_run_outreach
EXECUTORS["CANCEL_OUTREACH"] = _exec_cancel_outreach


async def _exec_hunt(db, params: Dict[str, Any]) -> Dict[str, Any]:
    """
    Kick off a Hunt pipeline (Scout → Verify → Website → Blast) for `count` businesses.
    Runs in background; returns immediately with a hunt_id so the UI can subscribe to SSE.
    """
    city = (params.get("city") or "").strip()
    industry = (params.get("industry") or "businesses").strip()
    count = int(params.get("count") or 10)
    mock = bool(params.get("mock") or (city.upper() == "TEST_CITY"))

    if not city:
        return {
            "ok": False,
            "reply": "Usage: `Hunt {city} {industry} {count}`\nExample: `Hunt Mississauga auto shops 20`\nTip: use `Hunt TEST_CITY` for a safe mock run.",
            "data": {},
        }

    try:
        from services.hunt_live import start_hunt
        hunt_id = await start_hunt(db, city=city, industry=industry, count=count, mock=mock)
    except Exception as e:
        logger.exception("[ORA-CC] Hunt start failed")
        return {"ok": False, "reply": f"Hunt failed to start: {e}", "data": {}}

    mode_tag = "🧪 MOCK" if mock else "🔥 LIVE"
    reply = (
        f"{mode_tag} *Hunt started* — {industry} in {city} (target: {count})\n\n"
        "Watch live progress above in ORA chat, in *Campaign HQ* → Active Hunts, "
        "or in the *Empire HUD* (nodes will flash as each step runs).\n\n"
        f"_hunt_id: `{hunt_id}`_"
    )
    return {
        "ok": True,
        "reply": reply,
        "data": {"hunt_id": hunt_id, "city": city, "industry": industry, "count": count, "mock": mock},
    }


async def _exec_verify(db, params: Dict[str, Any]) -> Dict[str, Any]:
    """Run full multi-source verification on a business and return a channel-gating report."""
    name = (params.get("business_name") or "").strip()
    city = (params.get("city") or "").strip()
    if not name:
        return {"ok": False, "reply": "Usage: `Verify {business name}` or `Verify {business} in {city}`", "data": {}}
    # Try to infer city from stored lead if not provided
    if not city and db is not None:
        try:
            lead = await _find_lead_by_name(db, name)
            if lead:
                city = (lead.get("city") or "").strip()
        except Exception:
            pass
    try:
        from services.accurate_scout import full_business_verify
        result = await full_business_verify(name, city or "Toronto", country="ca")
    except Exception as e:
        return {"ok": False, "reply": f"Verification failed: {e}", "data": {}}

    c = result.get("consolidated", {}) or {}
    phone = c.get("phone", {}) or {}
    email = c.get("email", {}) or {}
    gating = result.get("channel_gating", {}) or {}

    def _badge(conf):
        return {"HIGH": "🟢", "MEDIUM": "🟡", "LOW": "🔴", "NONE": "⚪"}.get(conf, "⚪")

    lines = [
        f"🔎 *Verified {result.get('business_name')}*",
        f"⏱ {result.get('elapsed_ms', 0)} ms · {len(result.get('sources_used', []))} sources",
        "",
        f"📞 {phone.get('value', '—') or '—'}  {_badge(phone.get('confidence','NONE'))} {phone.get('confidence','NONE')} "
        f"({phone.get('source_count', 0)} sources)",
        f"📧 {email.get('value', '—') or '—'}  {_badge(email.get('confidence','NONE'))} {email.get('confidence','NONE')} "
        f"({email.get('source_count', 0)} sources)",
        "",
        "*Channel Gating:*",
        f"  Call {'✅' if gating.get('call') else '🛑'}   SMS {'✅' if gating.get('sms') else '🛑'}   "
        f"WhatsApp {'✅' if gating.get('whatsapp') else '🛑'}   Email {'✅' if gating.get('email') else '🛑'}",
    ]
    if result.get("government_verified"):
        lines.append(f"🏛 Government Verified ✅ (#{result.get('registration_number') or '—'})")
    if result.get("bbb_rating"):
        lines.append(f"🏅 BBB Rating: {result['bbb_rating']}")

    return {"ok": True, "reply": "\n".join(lines), "data": result}


EXECUTORS["VERIFY"] = _exec_verify
EXECUTORS["HUNT"] = _exec_hunt


async def _exec_autohunt_pause(db, params: Dict[str, Any]) -> Dict[str, Any]:
    if db is None:
        return {"ok": False, "reply": "DB unavailable.", "data": {}}
    await db.auto_hunt_settings.update_one(
        {"_id": "singleton"},
        {"$set": {"enabled": False, "paused_via_ora_at": datetime.now(timezone.utc).isoformat()}},
        upsert=True,
    )
    return {"ok": True, "reply": "⏸ Auto-Hunt paused. All 4 agents will stop after current cycle.", "data": {"enabled": False}}


async def _exec_autohunt_resume(db, params: Dict[str, Any]) -> Dict[str, Any]:
    if db is None:
        return {"ok": False, "reply": "DB unavailable.", "data": {}}
    doc = await db.auto_hunt_settings.find_one({"_id": "singleton"}, {"_id": 0}) or {}
    update = {"enabled": True, "resumed_via_ora_at": datetime.now(timezone.utc).isoformat()}
    if not doc.get("activated_at"):
        update["activated_at"] = datetime.now(timezone.utc).isoformat()
    await db.auto_hunt_settings.update_one({"_id": "singleton"}, {"$set": update}, upsert=True)
    from services.agents.hunter_ora import HunterORA
    hunter = HunterORA(db)
    limit = await hunter.get_daily_limit()
    ramp = doc.get("ramp_mode", "safe")
    emoji = "🚀" if ramp == "aggressive" else "🐢"
    return {
        "ok": True,
        "reply": f"▶️ Auto-Hunt resumed.\nMode: {emoji} {ramp.title()} — Today limit: {limit}/day",
        "data": {"enabled": True, "daily_limit": limit, "ramp_mode": ramp},
    }


async def _exec_autohunt_queue(db, params: Dict[str, Any]) -> Dict[str, Any]:
    from services.agents.hunter_ora import WEEKLY_ROTATION
    from datetime import timedelta as _td
    today = datetime.now(timezone.utc)
    lines = ["📅 *Hunt Queue — Next 7 Days*\n"]
    for i in range(7):
        d = today + _td(days=i)
        targets = WEEKLY_ROTATION.get(d.weekday(), [])
        slots = " + ".join(f"{t} {ind}" for (t, ind) in targets) or "—"
        lines.append(f"• {d.strftime('%a %b %d')}: {slots}")
    return {"ok": True, "reply": "\n".join(lines), "data": {}}


async def _exec_autohunt_set_limit(db, params: Dict[str, Any]) -> Dict[str, Any]:
    limit = int(params.get("limit") or 50)
    if limit < 1 or limit > 1000:
        return {"ok": False, "reply": "Limit must be between 1 and 1000.", "data": {}}
    if db is None:
        return {"ok": False, "reply": "DB unavailable.", "data": {}}
    await db.auto_hunt_settings.update_one(
        {"_id": "singleton"},
        {"$set": {"daily_limit_override": limit, "override_at": datetime.now(timezone.utc).isoformat()}},
        upsert=True,
    )
    return {"ok": True, "reply": f"✅ Daily limit set to {limit}/day (override active — takes precedence over ramp).", "data": {"limit": limit}}


async def _exec_agent_pause(db, params: Dict[str, Any]) -> Dict[str, Any]:
    agent_id = params.get("agent_id") or ""
    from services.agents import get_agent
    agent = get_agent(agent_id)
    if not agent:
        return {"ok": False, "reply": f"Unknown agent: `{agent_id}`. Try `pause hunter`, `pause follow-up`, `pause closer`, `pause referral`.", "data": {}}
    await agent.pause()
    return {"ok": True, "reply": f"⏸ {agent.AGENT_EMOJI} {agent.AGENT_NAME} paused.", "data": {"agent_id": agent_id}}


async def _exec_agent_resume(db, params: Dict[str, Any]) -> Dict[str, Any]:
    agent_id = params.get("agent_id") or ""
    from services.agents import get_agent
    agent = get_agent(agent_id)
    if not agent:
        return {"ok": False, "reply": f"Unknown agent: `{agent_id}`.", "data": {}}
    await agent.resume()
    return {"ok": True, "reply": f"▶️ {agent.AGENT_EMOJI} {agent.AGENT_NAME} resumed.", "data": {"agent_id": agent_id}}


EXECUTORS["AUTOHUNT_PAUSE"] = _exec_autohunt_pause
EXECUTORS["AUTOHUNT_RESUME"] = _exec_autohunt_resume
EXECUTORS["AUTOHUNT_QUEUE"] = _exec_autohunt_queue
EXECUTORS["AUTOHUNT_SET_LIMIT"] = _exec_autohunt_set_limit
EXECUTORS["AGENT_PAUSE"] = _exec_agent_pause
EXECUTORS["AGENT_RESUME"] = _exec_agent_resume


# ─────────────────────────────────────────────────────────────
# BUILDER — delegate to services.aurem_builder
# ─────────────────────────────────────────────────────────────
async def _exec_build(db, params: Dict[str, Any]) -> Dict[str, Any]:
    desc = (params.get("description") or "").strip()
    if not desc:
        return {"ok": False, "reply": "Tell me *what* to build — e.g. `Build endpoint /api/builder-test returning build status`.", "data": {}}
    try:
        from services.aurem_builder import build_feature
        res = await build_feature(db, description=desc, admin="ora_command")
    except Exception as e:
        return {"ok": False, "reply": f"Builder crashed: {e}", "data": {}}

    files_ok = sum(1 for f in res.get("files", []) if f.get("ok"))
    files_total = len(res.get("files", []))
    status = res.get("status", "failed")
    reply_lines = [
        f"🛠 *AUREM Builder* — {status.upper()}",
        f"• Files written: {files_ok}/{files_total}",
        f"• Duration: {res.get('duration_s', 0)}s · Cost ≈ ${res.get('cost_estimate_usd', 0)}",
    ]
    if res.get("test_command"):
        reply_lines.append(f"• Test: `{res['test_command'][:120]}`")
    if res.get("notes"):
        reply_lines.append("• Manual: " + "; ".join(res["notes"][:2]))
    return {"ok": status == "success", "reply": "\n".join(reply_lines), "data": res}


async def _exec_fix(db, params: Dict[str, Any]) -> Dict[str, Any]:
    desc = (params.get("description") or "").strip()
    if not desc:
        return {"ok": False, "reply": "Describe the bug — e.g. `Fix the ORA status endpoint returning 500`.", "data": {}}
    # Route through the builder with an explicit 'fix' prefix so Claude behaves accordingly.
    return await _exec_build(db, {"description": f"Patch the existing code to fix this bug: {desc}"})


async def _exec_test_endpoint(db, params: Dict[str, Any]) -> Dict[str, Any]:
    import os as _os
    import httpx
    endpoint = (params.get("endpoint") or "").strip()
    if not endpoint:
        return {"ok": False, "reply": "Usage: `test /api/some/path`", "data": {}}
    if not endpoint.startswith("/"):
        endpoint = "/" + endpoint
    base = _os.environ.get("AUREM_PUBLIC_URL") or "http://localhost:8001"
    url = base.rstrip("/") + endpoint
    try:
        async with httpx.AsyncClient(timeout=8) as client:
            r = await client.get(url)
        preview = (r.text or "")[:180].replace("\n", " ")
        return {
            "ok": r.status_code < 400,
            "reply": f"📡 `GET {endpoint}` → *{r.status_code}*\n`{preview}`",
            "data": {"status": r.status_code, "url": url, "body_preview": preview},
        }
    except Exception as e:
        return {"ok": False, "reply": f"Request failed: {e}", "data": {"url": url}}


EXECUTORS["BUILD"] = _exec_build
EXECUTORS["FIX"] = _exec_fix
EXECUTORS["TEST_ENDPOINT"] = _exec_test_endpoint


# ─────────────────────────────────────────────────────────────
# FOUNDER-ONLY EXECUTORS (gated by is_founder flag)
# ─────────────────────────────────────────────────────────────
FOUNDER_INTENTS = {
    "SYSTEM_HEALTH", "AUTOPILOT_STATUS", "AGENTS_STATUS", "DEPLOY_TRIGGER",
    "TENANTS_LIST", "REVENUE_TODAY", "MORNING_BRIEF_NOW", "EVENING_WRAP_NOW",
    "KILL_SWITCH", "RESURRECT", "INTEGRATIONS_PING",
    # Iter 288.0 — Revenue-Reflector / Sovereign Boardroom
    "BOARD_MEETING", "AGENT_LEDGER", "AGENT_ROI", "AGENT_KILL_SWITCH",
    "AGENT_SOUL", "BURN_RATE",
    # Iter 288.1 — Sovereign DB Oracle
    "LOOKUP_BIN", "LOOKUP_USER", "LIST_BINS", "LIST_WEBSITES",
    "LIST_TENANTS_FULL", "DB_QUERY",
}


async def _exec_system_health(db, params: Dict[str, Any]) -> Dict[str, Any]:
    import httpx as _httpx
    base = os.environ.get("AUREM_PUBLIC_URL") or "http://localhost:8001"
    lines = ["🩺 *System Health*"]
    try:
        async with _httpx.AsyncClient(timeout=5) as c:
            r = await c.get(f"{base}/api/health")
            lines.append(f"• Backend: *{r.status_code}* ({r.elapsed.total_seconds():.2f}s)")
    except Exception as e:
        lines.append(f"• Backend: ❌ {e}")
    if db is not None:
        try:
            leads = await db.campaign_leads.count_documents(
                {"business_id": FOUNDER_BIN})
            logs = await db.truth_logs.count_documents({})
            lines.append(f"• DB: ✅ leads={leads} truth_logs={logs}")
        except Exception as e:
            lines.append(f"• DB: ❌ {e}")
    else:
        lines.append("• DB: ⚠️ unavailable")
    return {"ok": True, "reply": "\n".join(lines), "data": {}}


async def _exec_autopilot_status(db, params: Dict[str, Any]) -> Dict[str, Any]:
    if db is None:
        return {"ok": False, "reply": "DB unavailable.", "data": {}}
    try:
        doc = await db.autopilot_runs.find_one({}, sort=[("started_at", -1)], projection={"_id": 0})
    except Exception as e:
        return {"ok": False, "reply": f"Autopilot status fetch failed: {e}", "data": {}}
    if not doc:
        return {"ok": True, "reply": "🤖 Autopilot: no runs yet. Daily trigger at 08:00 AM Toronto.", "data": {}}
    return {
        "ok": True,
        "reply": (
            f"🤖 *Autopilot* — last run `{doc.get('started_at','?')}`\n"
            f"• Status: *{doc.get('status','?')}*\n"
            f"• Scouted: {doc.get('scouted',0)} · Hunted: {doc.get('hunted',0)} · Blasted: {doc.get('blasted',0)}\n"
            f"• Next: daily 08:00 AM Toronto"
        ),
        "data": doc,
    }


async def _exec_agents_status(db, params: Dict[str, Any]) -> Dict[str, Any]:
    if db is None:
        return {"ok": False, "reply": "DB unavailable.", "data": {}}
    try:
        docs = await db.agent_state.find({}, {"_id": 0}).to_list(length=20)
    except Exception as e:
        return {"ok": False, "reply": f"Agents fetch failed: {e}", "data": {}}
    if not docs:
        return {"ok": True, "reply": "🤖 No agent state recorded yet.", "data": {}}
    lines = ["🤖 *Agent Swarm*"]
    for d in docs:
        emoji = "⏸" if d.get("paused") else "▶️"
        lines.append(f"• {emoji} {d.get('agent_id','?')} — runs: {d.get('run_count',0)}")
    return {"ok": True, "reply": "\n".join(lines), "data": {"agents": docs}}


async def _exec_deploy_trigger(db, params: Dict[str, Any]) -> Dict[str, Any]:
    import httpx as _httpx
    base = os.environ.get("AUREM_PUBLIC_URL") or "http://localhost:8001"
    admin_key = os.environ.get("ADMIN_KEY", "")
    try:
        async with _httpx.AsyncClient(timeout=10) as c:
            r = await c.post(
                f"{base}/api/admin/deploy/trigger",
                headers={"X-Admin-Key": admin_key} if admin_key else {},
            )
        return {
            "ok": r.status_code < 400,
            "reply": f"🚀 Deploy trigger → *{r.status_code}*\n`{(r.text or '')[:160]}`",
            "data": {"status": r.status_code},
        }
    except Exception as e:
        return {"ok": False, "reply": f"Deploy trigger failed: {e}", "data": {}}


async def _exec_tenants_list(db, params: Dict[str, Any]) -> Dict[str, Any]:
    if db is None:
        return {"ok": False, "reply": "DB unavailable.", "data": {}}
    try:
        tenants = await db.users.find(
            {}, {"_id": 0, "email": 1, "plan": 1, "last_login": 1, "is_admin": 1}
        ).limit(25).to_list(length=25)
    except Exception as e:
        return {"ok": False, "reply": f"Tenants fetch failed: {e}", "data": {}}
    if not tenants:
        return {"ok": True, "reply": "👥 No tenants yet.", "data": {}}
    lines = [f"👥 *Tenants* (top {len(tenants)})"]
    for t in tenants:
        tag = "👑" if t.get("is_admin") else "•"
        lines.append(f"{tag} {t.get('email','?')} — {t.get('plan','free')}")
    return {"ok": True, "reply": "\n".join(lines), "data": {"tenants": tenants}}


async def _exec_revenue_today(db, params: Dict[str, Any]) -> Dict[str, Any]:
    if db is None:
        return {"ok": False, "reply": "DB unavailable.", "data": {}}
    try:
        from datetime import datetime as _dt
        start = _dt.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        count = await db.stripe_charges.count_documents({"created_at": {"$gte": start}})
        total_doc = await db.stripe_charges.aggregate([
            {"$match": {"created_at": {"$gte": start}}},
            {"$group": {"_id": None, "total": {"$sum": "$amount"}}},
        ]).to_list(length=1)
        total_cents = (total_doc[0]["total"] if total_doc else 0) or 0
    except Exception as e:
        return {"ok": False, "reply": f"Revenue fetch failed: {e}", "data": {}}
    return {
        "ok": True,
        "reply": f"💰 *Today* — {count} charges · *${total_cents/100:,.2f}*",
        "data": {"count": count, "total_usd": total_cents / 100},
    }


async def _exec_morning_brief_now(db, params: Dict[str, Any]) -> Dict[str, Any]:
    if db is None:
        return {"ok": False, "reply": "DB unavailable.", "data": {}}
    try:
        from services.autopilot_brief_notifier import dispatch_brief
        # Use latest autopilot run or synthesize a zero-run brief
        run = await db.autopilot_runs.find_one({}, sort=[("started_at", -1)], projection={"_id": 0}) or {
            "run_id": f"manual-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M')}",
            "scouted": 0, "hunted": 0, "blasted": 0, "status": "manual_fire",
            "started_at": datetime.now(timezone.utc).isoformat(),
        }
        res = await dispatch_brief(db, run)
        return {"ok": True, "reply": "📨 Morning brief fired. Check Telegram/Email.", "data": res or {}}
    except Exception as e:
        return {"ok": False, "reply": f"Morning brief failed: {e}", "data": {}}


async def _exec_evening_wrap_now(db, params: Dict[str, Any]) -> Dict[str, Any]:
    if db is None:
        return {"ok": False, "reply": "DB unavailable.", "data": {}}
    try:
        from services.autopilot_brief_notifier import dispatch_brief
        run = await db.autopilot_runs.find_one({}, sort=[("started_at", -1)], projection={"_id": 0}) or {
            "run_id": f"manual-wrap-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M')}",
            "scouted": 0, "hunted": 0, "blasted": 0, "status": "evening_wrap",
            "started_at": datetime.now(timezone.utc).isoformat(),
        }
        res = await dispatch_brief(db, run)
        return {"ok": True, "reply": "📨 Evening wrap fired. Check Telegram/Email.", "data": res or {}}
    except Exception as e:
        return {"ok": False, "reply": f"Evening wrap failed: {e}", "data": {}}


async def _exec_kill_switch(db, params: Dict[str, Any]) -> Dict[str, Any]:
    if db is None:
        return {"ok": False, "reply": "DB unavailable.", "data": {}}
    try:
        await db.system_kill_switch.update_one(
            {"_id": "singleton"},
            {"$set": {"killed": True, "killed_at": datetime.now(timezone.utc).isoformat()}},
            upsert=True,
        )
        # Pause all agents + autohunt
        try:
            await db.auto_hunt_settings.update_one(
                {"_id": "singleton"}, {"$set": {"enabled": False}}, upsert=True
            )
            await db.agent_state.update_many({}, {"$set": {"paused": True}})
        except Exception:
            pass
    except Exception as e:
        return {"ok": False, "reply": f"Kill-switch failed: {e}", "data": {}}
    return {"ok": True, "reply": "🛑 *KILL SWITCH engaged.* All outbound paused. Say `resurrect` to restart.", "data": {}}


async def _exec_resurrect(db, params: Dict[str, Any]) -> Dict[str, Any]:
    if db is None:
        return {"ok": False, "reply": "DB unavailable.", "data": {}}
    try:
        await db.system_kill_switch.update_one(
            {"_id": "singleton"},
            {"$set": {"killed": False, "resurrected_at": datetime.now(timezone.utc).isoformat()}},
            upsert=True,
        )
        await db.auto_hunt_settings.update_one(
            {"_id": "singleton"}, {"$set": {"enabled": True}}, upsert=True
        )
        await db.agent_state.update_many({}, {"$set": {"paused": False}})
    except Exception as e:
        return {"ok": False, "reply": f"Resurrect failed: {e}", "data": {}}
    return {"ok": True, "reply": "▶️ *Resurrected.* All systems back online.", "data": {}}


async def _exec_integrations_ping(db, params: Dict[str, Any]) -> Dict[str, Any]:
    checks = []
    checks.append(("Resend", bool(os.environ.get("RESEND_API_KEY"))))
    checks.append(("Twilio", bool(os.environ.get("TWILIO_AUTH_TOKEN")) and bool(os.environ.get("TWILIO_ACCOUNT_SID"))))
    checks.append(("Telegram", bool(os.environ.get("TELEGRAM_BOT_TOKEN"))))
    checks.append(("Apollo", bool(os.environ.get("APOLLO_API_KEY"))))
    checks.append(("Stripe", bool(os.environ.get("STRIPE_SECRET_KEY"))))
    checks.append(("Emergent LLM", bool(os.environ.get("EMERGENT_LLM_KEY"))))
    lines = ["🔌 *Integrations*"]
    for name, ok in checks:
        lines.append(f"• {'✅' if ok else '❌'} {name}")
    return {"ok": True, "reply": "\n".join(lines), "data": {"checks": dict(checks)}}


EXECUTORS["SYSTEM_HEALTH"] = _exec_system_health
EXECUTORS["AUTOPILOT_STATUS"] = _exec_autopilot_status
EXECUTORS["AGENTS_STATUS"] = _exec_agents_status
EXECUTORS["DEPLOY_TRIGGER"] = _exec_deploy_trigger
EXECUTORS["TENANTS_LIST"] = _exec_tenants_list
EXECUTORS["REVENUE_TODAY"] = _exec_revenue_today
EXECUTORS["MORNING_BRIEF_NOW"] = _exec_morning_brief_now
EXECUTORS["EVENING_WRAP_NOW"] = _exec_evening_wrap_now
EXECUTORS["KILL_SWITCH"] = _exec_kill_switch
EXECUTORS["RESURRECT"] = _exec_resurrect
EXECUTORS["INTEGRATIONS_PING"] = _exec_integrations_ping


# ─────────────────────────────────────────────────────────────
# Iter 288.0 — Sovereign Boardroom / Revenue-Reflector executors
# ─────────────────────────────────────────────────────────────
async def _exec_board_meeting(db, params: Dict[str, Any]) -> Dict[str, Any]:
    if db is None:
        return {"ok": False, "reply": "DB unavailable.", "data": {}}
    try:
        from services.agent_soul import board_meeting
        days = int(params.get("days") or 7)
        out = await board_meeting(db, days=max(1, min(days, 90)))
    except Exception as e:
        return {"ok": False, "reply": f"Board meeting failed: {e}", "data": {}}
    return {"ok": True, "reply": out.get("summary", ""), "data": out}


async def _exec_agent_ledger(db, params: Dict[str, Any]) -> Dict[str, Any]:
    if db is None:
        return {"ok": False, "reply": "DB unavailable.", "data": {}}
    try:
        from services.agent_ledger import get_board
        days = int(params.get("days") or 7)
        rows = await get_board(db, days=max(1, min(days, 90)))
    except Exception as e:
        return {"ok": False, "reply": f"Ledger fetch failed: {e}", "data": {}}
    lines = [f"📒 *Agent Ledger — last {days}d*"]
    for r in rows:
        lines.append(
            f"• {r['agent_id']}: ${r['cost_usd']:.2f} spent → "
            f"${r['revenue_potential_usd']:.2f} pipeline · "
            f"${r['revenue_realized_usd']:.2f} realized · ROI {r['roi_potential']}x"
        )
    return {"ok": True, "reply": "\n".join(lines), "data": {"rows": rows, "days": days}}


async def _exec_agent_roi(db, params: Dict[str, Any]) -> Dict[str, Any]:
    if db is None:
        return {"ok": False, "reply": "DB unavailable.", "data": {}}
    agent_id = (params.get("agent_id") or "").strip().lower()
    if not agent_id:
        return {"ok": False, "reply": "Which agent? e.g. `scout roi`, `hunter P&L`.", "data": {}}
    try:
        from services.agent_ledger import get_roi
        days = int(params.get("days") or 7)
        r = await get_roi(db, agent_id, days=max(1, min(days, 90)))
    except Exception as e:
        return {"ok": False, "reply": f"ROI fetch failed: {e}", "data": {}}
    reply = (
        f"📊 *{agent_id}* — last {r['days']}d\n"
        f"• Cost: ${r['cost_usd']:.2f}\n"
        f"• Pipeline: ${r['revenue_potential_usd']:.2f}\n"
        f"• Realized: ${r['revenue_realized_usd']:.2f}\n"
        f"• ROI (potential): *{r['roi_potential']}x*"
    )
    return {"ok": True, "reply": reply, "data": r}


async def _exec_agent_kill_switch(db, params: Dict[str, Any]) -> Dict[str, Any]:
    if db is None:
        return {"ok": False, "reply": "DB unavailable.", "data": {}}
    try:
        from services.agent_ledger import kill_switch_check
        days = int(params.get("days") or 7)
        losers = await kill_switch_check(db, days=days)
    except Exception as e:
        return {"ok": False, "reply": f"Check failed: {e}", "data": {}}
    if not losers:
        return {"ok": True, "reply": "✅ No money-losing agents. Fleet is profitable.", "data": {"losers": []}}
    lines = [f"🔴 *Firing Line — last {days}d*"]
    for loser in losers:
        lines.append(
            f"• {loser['agent_id']}: burned ${loser['cost_usd']:.2f}, "
            f"pipeline ${loser['revenue_potential_usd']:.2f}, ROI {loser['roi_potential']}x"
        )
    return {"ok": True, "reply": "\n".join(lines), "data": {"losers": losers}}


async def _exec_agent_soul(db, params: Dict[str, Any]) -> Dict[str, Any]:
    agent_id = (params.get("agent_id") or "").strip().lower()
    if not agent_id:
        return {"ok": False, "reply": "Which agent? e.g. `scout soul`, `hunter reflection`.", "data": {}}
    try:
        from services.agent_soul import get_soul
        s = get_soul(agent_id)
    except Exception as e:
        return {"ok": False, "reply": f"Soul read failed: {e}", "data": {}}
    if not s["exists"]:
        return {"ok": True, "reply": f"🧠 {agent_id} has no soul yet. Say `board meeting` to birth one.", "data": s}
    content = s["content"]
    # Send only the status header (first ~900 chars) for chat — full file is in /api/agents/board/soul/{id}
    preview = content[:900] + ("\n… _(truncated — full SOUL.md in Boardroom UI)_" if len(content) > 900 else "")
    return {"ok": True, "reply": preview, "data": s}


async def _exec_burn_rate(db, params: Dict[str, Any]) -> Dict[str, Any]:
    if db is None:
        return {"ok": False, "reply": "DB unavailable.", "data": {}}
    try:
        from services.agent_ledger import get_top_rollup
        days = int(params.get("days") or 1)
        r = await get_top_rollup(db, days=max(1, min(days, 90)))
    except Exception as e:
        return {"ok": False, "reply": f"Burn rate failed: {e}", "data": {}}
    reply = (
        f"🔥 *Live Ledger — last {r['days']}d*\n"
        f"• Gross burn: *${r['gross_burn_usd']:.2f}*\n"
        f"• Pipeline: *${r['potential_pipeline_usd']:.2f}*\n"
        f"• Realized: *${r['realized_revenue_usd']:.2f}*\n"
        f"• Net margin: *${r['net_margin_usd']:.2f}*"
    )
    if r.get("firing_line"):
        reply += "\n• 🔴 Firing line: " + ", ".join(r["firing_line"])
    return {"ok": True, "reply": reply, "data": r}


EXECUTORS["BOARD_MEETING"] = _exec_board_meeting
EXECUTORS["AGENT_LEDGER"] = _exec_agent_ledger
EXECUTORS["AGENT_ROI"] = _exec_agent_roi
EXECUTORS["AGENT_KILL_SWITCH"] = _exec_agent_kill_switch
EXECUTORS["AGENT_SOUL"] = _exec_agent_soul
EXECUTORS["BURN_RATE"] = _exec_burn_rate


# ─────────────────────────────────────────────────────────────
# Iter 288.1 — Sovereign DB Oracle executors
# ─────────────────────────────────────────────────────────────
async def _exec_lookup_bin(db, params: Dict[str, Any]) -> Dict[str, Any]:
    from services.ora_db_oracle import lookup_bin
    code = (params.get("bin_code") or params.get("code") or params.get("business_id") or "").strip()
    if not code:
        return {"ok": False, "reply": "Which BIN? e.g. `lookup BIN RERO-DMYE`.", "data": {}}
    res = await lookup_bin(db, code)
    return {"ok": res.get("ok", False), "reply": res.get("reply", ""),
            "data": res.get("data") or res.get("candidates") or {}}


async def _exec_lookup_user(db, params: Dict[str, Any]) -> Dict[str, Any]:
    from services.ora_db_oracle import lookup_user
    ident = (params.get("identifier") or params.get("query") or params.get("email") or "").strip()
    if not ident:
        return {"ok": False, "reply": "Who? Pass email / name / phone / company.", "data": {}}
    res = await lookup_user(db, ident)
    return {"ok": res.get("ok", False), "reply": res.get("reply", ""),
            "data": res.get("matches", [])}


async def _exec_list_bins(db, params: Dict[str, Any]) -> Dict[str, Any]:
    from services.ora_db_oracle import list_bins
    res = await list_bins(db)
    return {"ok": res.get("ok", False), "reply": res.get("reply", ""),
            "data": {"bins": res.get("bins", []), "count": res.get("count", 0)}}


async def _exec_list_websites(db, params: Dict[str, Any]) -> Dict[str, Any]:
    from services.ora_db_oracle import list_websites
    res = await list_websites(db)
    return {"ok": res.get("ok", False), "reply": res.get("reply", ""),
            "data": {"sites": res.get("sites", []), "count": res.get("count", 0)}}


async def _exec_list_tenants_full(db, params: Dict[str, Any]) -> Dict[str, Any]:
    from services.ora_db_oracle import list_tenants_full
    res = await list_tenants_full(db)
    return {"ok": res.get("ok", False), "reply": res.get("reply", ""),
            "data": {"tenants": res.get("tenants", []), "count": res.get("count", 0)}}


async def _exec_db_query(db, params: Dict[str, Any]) -> Dict[str, Any]:
    from services.ora_db_oracle import db_query
    q = (params.get("question") or params.get("q") or params.get("query") or "").strip()
    if not q:
        return {"ok": False, "reply": "What do you want to query? Ask in plain language.", "data": {}}
    res = await db_query(db, q)
    return {"ok": res.get("ok", False), "reply": res.get("reply", ""),
            "data": {"plan": res.get("plan"), "results": res.get("results", []),
                     "count": res.get("count", 0)}}


EXECUTORS["LOOKUP_BIN"] = _exec_lookup_bin
EXECUTORS["LOOKUP_USER"] = _exec_lookup_user
EXECUTORS["LIST_BINS"] = _exec_list_bins
EXECUTORS["LIST_WEBSITES"] = _exec_list_websites
EXECUTORS["LIST_TENANTS_FULL"] = _exec_list_tenants_full
EXECUTORS["DB_QUERY"] = _exec_db_query


# ─────────────────────────────────────────────────────────────
# LLM FALLBACK — when regex parser returns UNKNOWN
# Uses Emergent LLM Key (Claude Sonnet 4.5) to classify natural-language /
# Hinglish input into a known intent, or reply conversationally.
# ─────────────────────────────────────────────────────────────
_BASE_INTENTS_SPEC = """Standard intents (available to everyone):
- SCOUT           {"city": str, "industry": str}           // discover businesses
- HUNT            {"city": str, "industry": str, "count": int}  // full Scout→Verify→Website→Blast
- VERIFY          {"business_name": str, "city": str}       // multi-source accuracy check
- BLAST_ONE       {"business_name": str}                    // single outreach
- BLAST_BULK      {"city": str}                             // mass outreach
- STATS           {}                                        // campaign metrics
- LEAD_COUNT      {}                                        // today's lead count
- REPLIES         {}                                        // who replied
- PIPELINE        {}                                        // full funnel status
- WEBSITE_BUILD   {"slug": str}
- WEBSITE_SEND    {"business_name": str}
- PAUSE           {}                                        // pause all campaigns
- RESUME          {}                                        // resume all campaigns
- AUTOHUNT_PAUSE  {}
- AUTOHUNT_RESUME {}
- AUTOHUNT_QUEUE  {}                                        // show next 7 days
- HELP            {}                                        // show help text
- CHAT            {}                                        // no command — conversational reply"""

_FOUNDER_INTENTS_SPEC = """Founder-only intents (admin superpowers):
- SYSTEM_HEALTH      {}          // backend + services + DB + integrations health
- AUTOPILOT_STATUS   {}          // Master Autopilot last run, next run, ramp mode
- AGENTS_STATUS      {}          // Scout/Hunter/Closer/Envoy/Follow-up/Referral state
- DEPLOY_TRIGGER     {}          // Fire GitHub-actions deploy webhook fallback
- TENANTS_LIST       {}          // All customer tenants + plan + last active
- REVENUE_TODAY      {}          // MRR, today's revenue, Stripe charges
- MORNING_BRIEF_NOW  {}          // Fire Morning Brief notifier immediately
- EVENING_WRAP_NOW   {}          // Fire Evening Wrap notifier immediately
- KILL_SWITCH        {}          // Stop ALL outbound (campaigns + agents + autopilot)
- RESURRECT          {}          // Undo KILL_SWITCH — restart everything
- INTEGRATIONS_PING  {}          // Ping Resend/Twilio/Telegram/Apollo status
- BOARD_MEETING      {"days": 7} // Summon all agents → P&L + self-reflections
- AGENT_LEDGER       {"days": 7} // Full per-agent cost + revenue table
- AGENT_ROI          {"agent_id": str, "days": 7}  // Single-agent P&L deep dive
- AGENT_KILL_SWITCH  {"days": 7} // List money-losing agents to fire
- AGENT_SOUL         {"agent_id": str}  // Read an agent's SOUL.md reflection
- BURN_RATE          {"days": 1} // Gross burn + pipeline rollup (Live Ledger)
- LOOKUP_BIN         {"bin_code": str}        // Show full details for a Business ID (RERO-DMYE)
- LOOKUP_USER        {"identifier": str}       // Find user by email/name/phone/company
- LIST_BINS          {}                        // Show every BIN in the database
- LIST_WEBSITES      {}                        // Every website linked to AUREM
- LIST_TENANTS_FULL  {}                        // Aggregated tenant intelligence
- DB_QUERY           {"question": str}         // Natural-language → safe Mongo query

Founder routing hints (be AGGRESSIVE — prefer these over CHAT when user is clearly asking about ops data):
- "system health", "health check", "status of servers", "how is backend" → SYSTEM_HEALTH
- "integrations status", "check integrations", "vérifier intégrations", "integration theek hai" → INTEGRATIONS_PING
- "tenants list", "all customers", "kitne tenants", "list clients", "cuántos clientes" → TENANTS_LIST
- "revenue today", "aaj ka revenue", "cuánto hemos ganado hoy", "paisa kitna" → REVENUE_TODAY
- "autopilot status", "autopilot kya kar raha", "what is autopilot doing" → AUTOPILOT_STATUS
- "agents status", "agent swarm", "agents kya kar rahe" → AGENTS_STATUS
- "deploy now", "push to prod", "deploy trigger", "deploy daal" → DEPLOY_TRIGGER
- "send morning brief", "morning brief abhi bhej", "fire morning brief" → MORNING_BRIEF_NOW
- "evening wrap", "wrap up abhi bhej" → EVENING_WRAP_NOW
- "kill switch", "stop everything", "sab band kar" → KILL_SWITCH
- "resurrect", "restart everything", "sab chalu kar" → RESURRECT
- "board meeting", "agents ki meeting bulao", "summon the agents", "agents ka class lo" → BOARD_MEETING
- "agent ledger", "agent P&L", "agent ROI report", "sab agents ka khaata dikhao" → AGENT_LEDGER
- "kaun paisa barbaad kar raha", "who is losing money", "firing line", "agents to fire" → AGENT_KILL_SWITCH
- "scout soul", "hunter soul", "read hunter reflection" → AGENT_SOUL (with agent_id)
- "scout roi", "closer ka hisaab", "hunter P&L" → AGENT_ROI (with agent_id)
- "burn rate", "kitna jala", "live ledger", "aaj ka burn" → BURN_RATE
- "lookup BIN <CODE>", "show RERO-DMYE", "details for SAND-KGRR", "BIN PREV-HX5U kya hai" → LOOKUP_BIN (extract bin_code as XXXX-XXXX or alphanumeric)
- "find user <email/name>", "kaun hai pawandeep", "search for teji.ss1986" → LOOKUP_USER
- "all BINs", "show me every BIN", "saare business IDs", "list all business codes" → LIST_BINS
- "all websites", "linked websites", "saari websites jo connected hain", "domains in system" → LIST_WEBSITES
- "all tenants full", "tenant report", "har tenant ki info" → LIST_TENANTS_FULL
- ANY ad-hoc question about data ("how many enterprise users", "kitne leads enrolled this week", "show me Stripe charges over $500", "campaign_leads where city is toronto") → DB_QUERY (pass the FULL original question as the "question" param)"""


def _build_llm_system_prompt(is_founder: bool = False) -> str:
    scope = "FOUNDER" if is_founder else "STANDARD"
    intents = _BASE_INTENTS_SPEC + ("\n\n" + _FOUNDER_INTENTS_SPEC if is_founder else "")
    return f"""You are ORA, the AUREM Command Center assistant. Current scope: {scope}.
The user typed a message that did NOT match any strict command regex.
Your job: map it to ONE supported intent, or reply conversationally.

{intents}

Language rules (CRITICAL):
- The user may write in ANY language: English, Hindi (Devanagari), Hinglish, Punjabi, Spanish, French, German, Portuguese, Italian, Dutch, Arabic, Mandarin, Japanese, Korean, Russian, Turkish, Vietnamese, Tagalog, Bengali, Urdu, Tamil, etc.
- Auto-detect the language. Your "reply" field MUST be in the SAME language/script the user used.
- Understand idioms and casual slang in every language ("sab theek", "qué tal", "comment ça va", "wie geht's", "你好吗").

Routing rules:
1. Return STRICT JSON only. No markdown, no prose wrapper, no fences.
2. Shape: {{"intent": "<INTENT>", "params": {{...}}, "reply": "<short reply in user's language>"}}
3. Casual status queries ("all good", "status", "kya haal", "qué hay") → intent=PIPELINE.
4. Greetings → intent=CHAT with a warm 1-line reply in user's language.
5. Thanks/ack → intent=CHAT with a brief ack.
6. If unsure → intent=CHAT with a helpful reply steering toward a command.
7. Keep replies ≤ 2 sentences, punchy, matching user's tone.
{"8. FOUNDER SCOPE: User is the platform founder — confidently trigger admin intents (DEPLOY, KILL_SWITCH, REVENUE_TODAY, TENANTS_LIST) without hesitation." if is_founder else "8. STANDARD SCOPE: Do NOT invent admin intents — those are founder-only."}
"""


async def _llm_intent_fallback(text: str, is_founder: bool = False, db=None) -> Optional[Dict[str, Any]]:
    """Map free-form / any-language input to a known intent via Emergent LLM Key.
    Returns {"intent", "params", "reply"} or None on failure."""
    api_key = os.environ.get("EMERGENT_LLM_KEY", "").strip()
    if not api_key:
        return None
    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage
        import json as _json
        import uuid as _uuid

        chat = LlmChat(
            api_key=api_key,
            session_id=f"ora_fallback_{_uuid.uuid4().hex[:8]}",
            system_message=_build_llm_system_prompt(is_founder=is_founder),
        )
        # gpt-4o-mini — fast, cheap, reliable intent classification
        chat.with_model("openai", "gpt-4o-mini")

        resp = await chat.send_message(UserMessage(text=text))
        raw = (resp or "").strip()
        # Iter 288.8 — Boardroom Ledger: estimate tokens (~4 chars/token) and record
        try:
            from services.agent_ledger import record_cost
            est_tokens = max(1, (len(text) + len(raw)) // 4)
            if db is not None:
                await record_cost(db, "ora_brain", "llm_openai_gpt4o_mini",
                                  est_tokens, meta={"channel": "command_fallback",
                                                    "founder": is_founder})
        except Exception:
            pass
        # Strip ```json fences if any
        if raw.startswith("```"):
            raw = re.sub(r"^```(?:json)?\s*", "", raw)
            raw = re.sub(r"\s*```\s*$", "", raw)
        # Extract first JSON object
        m = re.search(r"\{.*\}", raw, re.DOTALL)
        if not m:
            return None
        data = _json.loads(m.group(0))
        intent = (data.get("intent") or "CHAT").upper()
        params = data.get("params") or {}
        reply = data.get("reply") or ""
        return {"intent": intent, "params": params, "reply": reply}
    except Exception as e:
        logger.warning(f"[ORA-CC] LLM fallback failed: {e}")
        return None


async def execute_command(db, text: str, channel: str = "chat", user: str = "admin", is_founder: bool = False) -> Dict[str, Any]:
    """
    Parse and execute a command. Logs every command for audit.
    Returns: {"ok", "reply", "intent", "params", "data"}

    If is_founder=True, founder-only admin intents (KILL_SWITCH, DEPLOY_TRIGGER,
    TENANTS_LIST, REVENUE_TODAY, etc.) become available via LLM fallback.
    """
    parsed = parse_command(text)
    intent = parsed["intent"]
    llm_used = False

    # LLM fallback for free-form / any-language input
    if intent == "UNKNOWN":
        fb = await _llm_intent_fallback(text, is_founder=is_founder, db=db)
        if fb:
            llm_used = True
            intent = fb["intent"]
            parsed = {"intent": intent, "params": fb["params"], "raw": text, "llm_reply": fb["reply"]}

    # Gate founder-only intents
    if intent in FOUNDER_INTENTS and not is_founder:
        return {
            "ok": False,
            "intent": "FORBIDDEN",
            "params": {},
            "reply": "🔒 That's a founder-only command.",
            "data": {},
        }

    if intent == "UNKNOWN":
        return {
            "ok": False,
            "intent": "UNKNOWN",
            "params": {},
            "reply": "I didn't catch that. Type `help` to see what I can do.",
            "data": {},
        }

    if intent == "CHAT":
        reply = parsed.get("llm_reply") or "Noted. Type `help` to see what I can do."
        return {"ok": True, "intent": "CHAT", "params": {}, "reply": reply, "data": {"llm": llm_used}}
    if intent == "HELP":
        return {"ok": True, "intent": "HELP", "params": {}, "reply": HELP_TEXT, "data": {}}

    executor = EXECUTORS.get(intent)
    if not executor:
        return {
            "ok": False,
            "intent": intent,
            "params": parsed["params"],
            "reply": f"Unknown intent: {intent}",
            "data": {},
        }

    try:
        res = await executor(db, parsed["params"])
    except Exception as e:
        logger.exception(f"[ORA-CC] Executor failed for {intent}")
        res = {"ok": False, "reply": f"Command failed: {e}", "data": {}}

    # Audit log (best-effort)
    try:
        if db is not None:
            await db.ora_command_log.insert_one({
                "channel": channel,
                "user": user,
                "raw": text,
                "intent": intent,
                "params": parsed["params"],
                "ok": res.get("ok", False),
                "reply_preview": (res.get("reply") or "")[:200],
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "ttl_at": datetime.now(timezone.utc),  # Iter 206: 60-day TTL
            })
    except Exception:
        pass

    return {"ok": res.get("ok", False), "intent": intent, "params": parsed["params"],
            "reply": res.get("reply", ""), "data": res.get("data", {})}
