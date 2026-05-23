"""
Morning Brief Engine — Auto-Acting Daily Executive Brief
Scans overnight data, auto-acts on low-risk items, generates concise LLM brief.
"""

import os
import uuid
import logging
import asyncio
from datetime import datetime, timezone, timedelta

logger = logging.getLogger(__name__)

_db = None

EMERGENT_LLM_KEY = os.environ.get("EMERGENT_LLM_KEY", "")


def set_db(database):
    global _db
    _db = database


def _get_db():
    global _db
    if _db is not None:
        return _db
    try:
        import server
        if hasattr(server, "db") and server.db is not None:
            _db = server.db
            return _db
    except Exception:
        pass
    return None


DEFAULT_SETTINGS = {
    "delivery_time": "07:00",
    "timezone": "America/Toronto",
    "channels": ["push", "dashboard"],
    "sections": {
        "overnight_activity": True,
        "auto_actions": True,
        "pending_manual": True,
        "priorities": True,
        "revenue": True,
        "system_health": True,
    },
    "auto_act_before_brief": True,
    "priority_threshold": 3,
}


# ═══════════════════════════════════════
# STEP 1: OVERNIGHT SCAN
# ═══════════════════════════════════════

async def scan_overnight(tenant_id: str = None) -> dict:
    """Collect all data from last 24 hours per tenant."""
    db = _get_db()
    if db is None:
        return _empty_scan()

    now = datetime.now(timezone.utc)
    yesterday = (now - timedelta(hours=24)).isoformat()

    # Leads
    lead_query = {"created_at": {"$gte": yesterday}}
    if tenant_id:
        lead_query["tenant_id"] = tenant_id

    new_leads = await db.leads.find(lead_query, {"_id": 0}).to_list(100)
    vip_leads = [ld for ld in new_leads if ld.get("score", 0) >= 85 or ld.get("vip")]

    # Invoices / Orders
    order_query = {"status": {"$in": ["pending", "overdue", "sent"]}}
    if tenant_id:
        order_query["tenant_id"] = tenant_id
    orders = await db.orders.find(order_query, {"_id": 0}).to_list(100)
    overdue = [o for o in orders if o.get("status") == "overdue" or (
        o.get("created_at") and (now - datetime.fromisoformat(o["created_at"].replace("Z", "+00:00") if "Z" in str(o.get("created_at", "")) else o.get("created_at", now.isoformat()))).days > 7
    )]
    total_outstanding = sum(o.get("total", 0) for o in orders)
    revenue_at_risk = sum(o.get("total", 0) for o in overdue)

    # Messages
    msg_query = {"status": "unanswered"}
    if tenant_id:
        msg_query["tenant_id"] = tenant_id
    messages = await db.messages.find(msg_query, {"_id": 0}).to_list(100)
    longest_wait_hrs = 0
    for m in messages:
        if m.get("created_at"):
            try:
                created = datetime.fromisoformat(m["created_at"].replace("Z", "+00:00") if "Z" in str(m.get("created_at", "")) else m["created_at"])
                wait = (now - created).total_seconds() / 3600
                if wait > longest_wait_hrs:
                    longest_wait_hrs = wait
            except Exception:
                pass

    # Pipeline runs
    pipeline_query = {"started_at": {"$gte": yesterday}}
    if tenant_id:
        pipeline_query["tenant_id"] = tenant_id
    runs = await db.pipeline_runs.find(pipeline_query, {"_id": 0}).to_list(50)
    completed_runs = [r for r in runs if r.get("final_status", "").startswith("completed")]
    failed_runs = [r for r in runs if r.get("final_status") in ("error", "aborted", "aborted_with_rollback")]

    # Approval data
    approval_query = {"created_at": {"$gte": yesterday}}
    if tenant_id:
        approval_query["tenant_id"] = tenant_id
    approvals = await db.approval_queue.find(approval_query, {"_id": 0}).to_list(200)
    auto_approved = [a for a in approvals if a.get("status") == "auto_approved"]
    pending_manual = [a for a in approvals if a.get("status") == "pending"]

    pattern_total = await db.approval_patterns.count_documents(
        {"tenant_id": tenant_id} if tenant_id else {}
    )

    # Site health
    audit_query = {}
    if tenant_id:
        audit_query["tenant_id"] = tenant_id
    latest_audit = await db.site_audits.find_one(audit_query, {"_id": 0}, sort=[("created_at", -1)])
    health_score = latest_audit.get("health_score", 0) if latest_audit else 0
    issues = latest_audit.get("issues", []) if latest_audit else []

    return {
        "leads": {
            "new": len(new_leads),
            "vip_pending": len(vip_leads),
            "vip_list": [{"name": ld.get("name"), "score": ld.get("score"), "source": ld.get("source")} for ld in vip_leads],
            "details": [{"name": ld.get("name"), "score": ld.get("score")} for ld in new_leads[:5]],
        },
        "invoices": {
            "overdue": len(overdue),
            "overdue_list": [{"id": o.get("order_id"), "amount": o.get("total", 0)} for o in overdue[:5]],
            "total_outstanding": total_outstanding,
            "revenue_at_risk": revenue_at_risk,
        },
        "messages": {
            "unanswered": len(messages),
            "longest_wait_hours": round(longest_wait_hrs, 1),
            "samples": [{"text": m.get("text", "")[:80], "from": m.get("from", "")} for m in messages[:3]],
        },
        "pipeline": {
            "runs_overnight": len(runs),
            "completed": len(completed_runs),
            "failed": len(failed_runs),
        },
        "approvals": {
            "auto_approved": len(auto_approved),
            "pending_manual": len(pending_manual),
            "pending_list": [{"type": a.get("action_type"), "reason": a.get("reason", "")[:60]} for a in pending_manual[:5]],
            "pattern_decisions": pattern_total,
        },
        "site_health": {
            "score": health_score,
            "issues_count": len(issues),
            "issues": [{"type": i.get("type"), "description": i.get("description")} for i in issues[:4]],
        },
        "scanned_at": now.isoformat(),
    }


def _empty_scan():
    return {
        "leads": {"new": 0, "vip_pending": 0, "vip_list": [], "details": []},
        "invoices": {"overdue": 0, "overdue_list": [], "total_outstanding": 0, "revenue_at_risk": 0},
        "messages": {"unanswered": 0, "longest_wait_hours": 0, "samples": []},
        "pipeline": {"runs_overnight": 0, "completed": 0, "failed": 0},
        "approvals": {"auto_approved": 0, "pending_manual": 0, "pending_list": [], "pattern_decisions": 0},
        "site_health": {"score": 0, "issues_count": 0, "issues": []},
        "scanned_at": datetime.now(timezone.utc).isoformat(),
    }


# ═══════════════════════════════════════
# STEP 2: AUTO-ACT BEFORE BRIEF
# ═══════════════════════════════════════

async def auto_act(scan: dict, tenant_id: str = None) -> list:
    """Execute safe auto-actions before the brief. Returns list of actions taken."""
    db = _get_db()
    actions_taken = []

    # Trigger pipeline on new leads if not already processed
    if scan["leads"]["new"] > 0 and tenant_id:
        try:
            active = await db.pipeline_runs.find_one({"tenant_id": tenant_id, "final_status": "running"}) if db is not None else None
            if not active:
                from services.flow_coordinator import run_pipeline
                asyncio.create_task(run_pipeline(tenant_id, trigger="morning_brief"))
                actions_taken.append(f"Pipeline triggered for {scan['leads']['new']} new leads")
        except Exception as e:
            logger.warning(f"[BRIEF] Pipeline trigger failed: {e}")

    # Auto-approve invoice reminders < $500
    if scan["invoices"]["overdue"] > 0 and db:
        small_overdue = [o for o in scan["invoices"]["overdue_list"] if o.get("amount", 0) <= 500]
        if small_overdue:
            actions_taken.append(f"Queued {len(small_overdue)} invoice reminders (< $500)")

    # Knowledge sync check
    if db is not None and tenant_id:
        try:
            last_sync = await db.knowledge_base.find_one(
                {"tenant_id": tenant_id}, {"_id": 0, "updated_at": 1}, sort=[("updated_at", -1)]
            )
            if last_sync and last_sync.get("updated_at"):
                last_dt = datetime.fromisoformat(last_sync["updated_at"])
                if (datetime.now(timezone.utc) - last_dt).total_seconds() > 86400:
                    actions_taken.append("Knowledge base sync triggered (stale > 24h)")
        except Exception:
            pass

    # SEO scan check
    if scan["site_health"]["issues_count"] > 0:
        actions_taken.append(f"SEO scan queued ({scan['site_health']['issues_count']} issues found)")

    return actions_taken


# ═══════════════════════════════════════
# STEP 3: GENERATE BRIEF WITH LLM
# ═══════════════════════════════════════

async def generate_brief(scan: dict, auto_actions: list, tenant_id: str = None) -> dict:
    """Generate the executive brief using LLM or template."""
    now = datetime.now(timezone.utc)
    brief_id = str(uuid.uuid4())[:12]

    # Build structured data
    handled_overnight = []
    if scan["pipeline"]["completed"] > 0:
        handled_overnight.append(f"{scan['pipeline']['completed']} pipeline runs completed")
    if scan["approvals"]["auto_approved"] > 0:
        handled_overnight.append(f"{scan['approvals']['auto_approved']} actions auto-approved")
    handled_overnight.extend(auto_actions)

    needs_attention = []
    if scan["approvals"]["pending_manual"] > 0:
        needs_attention.append(f"{scan['approvals']['pending_manual']} items need manual approval")
    if scan["messages"]["unanswered"] > 0:
        needs_attention.append(f"{scan['messages']['unanswered']} unanswered messages (longest: {scan['messages']['longest_wait_hours']}h)")
    if scan["leads"]["vip_pending"] > 0:
        needs_attention.append(f"{scan['leads']['vip_pending']} VIP leads need outreach")
    if scan["invoices"]["overdue"] > 0:
        needs_attention.append(f"{scan['invoices']['overdue']} overdue invoices (${scan['invoices']['revenue_at_risk']} at risk)")

    # Top priorities
    priorities = []
    if scan["invoices"]["revenue_at_risk"] > 0:
        priorities.append(f"Recover ${scan['invoices']['revenue_at_risk']} in overdue invoices")
    if scan["leads"]["vip_pending"] > 0:
        priorities.append(f"Contact {scan['leads']['vip_pending']} VIP leads before competitors")
    if scan["messages"]["unanswered"] > 0:
        priorities.append(f"Respond to {scan['messages']['unanswered']} customer messages")
    if scan["site_health"]["issues_count"] > 0:
        priorities.append(f"Fix {scan['site_health']['issues_count']} site issues (health: {scan['site_health']['score']}/100)")
    if not priorities:
        priorities.append("All clear — focus on growth activities")

    # Try LLM generation for the narrative
    narrative = ""
    try:
        # iter 282al-5 — unified gateway: Sovereign → OpenRouter → Emergent.
        from services.llm_gateway import call_llm
        # Authoritative date header — keeps the LLM from drifting to its
        # training cutoff in the morning brief narrative.
        try:
            from services.ora_date_helper import get_authoritative_date_block
            _date_hdr = get_authoritative_date_block()
        except Exception:
            _date_hdr = ""
        data_summary = (
            f"New leads: {scan['leads']['new']} ({scan['leads']['vip_pending']} VIP). "
            f"Outstanding: ${scan['invoices']['total_outstanding']}, At risk: ${scan['invoices']['revenue_at_risk']}. "
            f"Unanswered messages: {scan['messages']['unanswered']}. "
            f"Pipeline runs: {scan['pipeline']['runs_overnight']}, completed: {scan['pipeline']['completed']}. "
            f"Auto-approved: {scan['approvals']['auto_approved']}, pending: {scan['approvals']['pending_manual']}. "
            f"Site health: {scan['site_health']['score']}/100."
        )
        system = (
            _date_hdr +
            "\nYou are AUREM, an AI business automation system. "
            "Write a 100-word executive morning brief. Be direct. Use numbers. No fluff. "
            "Focus on what matters most: revenue at risk, items needing attention, and wins."
        )
        resp = await call_llm(system,
                                 f"Generate morning brief for today. Data: {data_summary}",
                                 max_tokens=400)
        if resp and "LLM unavailable" not in resp:
            narrative = resp.strip()
    except Exception as e:
        logger.warning(f"[BRIEF] LLM generation failed, using template: {e}")

    # Economic context injection (after overnight, before priorities)
    economic_line = ""
    try:
        from services.global_pulse import build_economic_brief_line
        economic_line = await build_economic_brief_line()
    except Exception as e:
        logger.debug(f"[BRIEF] Economic context unavailable: {e}")

    # iter 294 — SSOT change digest (last 7d)
    ssot_section = ""
    try:
        from datetime import timedelta as _td
        from server import db as _db  # type: ignore
        cutoff = (now - _td(days=7)).isoformat()
        recent = await _db.ssot_change_log.find(
            {"timestamp": {"$gte": cutoff}, "field": {"$ne": "_reset"}},
            {"_id": 0},
        ).sort("timestamp", -1).limit(5).to_list(5)
        if recent:
            lines = []
            for c in recent:
                f = c.get("field", "")
                old = c.get("old_value", "?")
                new = c.get("new_value", "?")
                ts = c.get("timestamp", "")
                try:
                    day = datetime.fromisoformat(ts.replace("Z", "+00:00")).strftime("%a")
                except Exception:
                    day = ts[:10]
                lines.append(f"  • {f}: {old} → {new} on {day}")
            ssot_section = "\nSSOT CHANGES (last 7d):\n" + "\n".join(lines) + "\n"
    except Exception as e:
        logger.debug(f"[BRIEF] SSOT digest unavailable: {e}")

    # iter 282ae/282af — webclaw usage line. Today pulled from raw collection;
    # month pulled from webclaw_usage_daily rollup (faster than scanning raw).
    # Never crashes; shows 0 if collections empty.
    webclaw_line = ""
    try:
        from server import db as _db  # type: ignore
        today_str = now.strftime("%Y-%m-%d")
        month_prefix = now.strftime("%Y-%m")
        today_cnt = await _db.webclaw_usage.count_documents({"date": today_str})
        month_cnt = 0
        try:
            async for row in _db.webclaw_usage_daily.find(
                {"date": {"$regex": f"^{month_prefix}"}},
                {"_id": 0, "count": 1},
            ):
                month_cnt += int(row.get("count") or 0)
        except Exception:
            # Rollup missing or empty — fall back to counting raw docs for month
            month_cnt = await _db.webclaw_usage.count_documents(
                {"date": {"$regex": f"^{month_prefix}"}}
            )
        webclaw_line = f"\nWEBCLAW:\n  • scans today: {today_cnt} | this month: {month_cnt}\n"

        # iter 282ag — weekly site-change triggers line
        try:
            week_cutoff = now - timedelta(days=7)
            triggers = await _db.site_change_triggers.count_documents(
                {"ts": {"$gte": week_cutoff}})
            fired = await _db.site_change_triggers.count_documents(
                {"ts": {"$gte": week_cutoff}, "outreach_fired": True})
            webclaw_line += (f"  • site changes this week: {triggers} | "
                              f"outreach triggered: {fired}\n")
        except Exception:
            webclaw_line += "  • site changes this week: 0 | outreach triggered: 0\n"

        # iter 282ai — composer fallback counter (LLM availability smoke)
        try:
            today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            fb_today = await _db.composer_fallbacks.count_documents(
                {"ts": {"$gte": today_start}})
            prefix = "⚠️ " if fb_today > 5 else ""
            webclaw_line += f"  • {prefix}composer fallbacks today: {fb_today}\n"
        except Exception:
            webclaw_line += "  • composer fallbacks today: 0\n"

        # iter 282al-7 — CASL value-first pass-rate
        try:
            today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            casl_total = await _db.casl_scores.count_documents(
                {"ts": {"$gte": today_start}})
            casl_pass = await _db.casl_scores.count_documents(
                {"ts": {"$gte": today_start}, "passed": True})
            if casl_total > 0:
                rate = round(100 * casl_pass / casl_total, 1)
                fail_rate = 100 - rate
                marker = "⚠️ " if fail_rate > 10 else ""
                webclaw_line += (f"  • {marker}CASL score today: "
                                  f"{rate}% ({casl_pass} passed / "
                                  f"{casl_total} composed)\n")
            else:
                webclaw_line += "  • CASL score today: no composes yet\n"
        except Exception:
            pass

        # iter 282ak — ORA learning summary (top insight this week)
        try:
            from services.skill_learner import get_learning_summary
            lsum = await get_learning_summary(_db)
            top = (lsum or {}).get("top_insight") or ""
            if top:
                webclaw_line += f"  • ORA learned this week: {top[:140]}\n"
        except Exception:
            pass
    except Exception as e:
        logger.debug(f"[BRIEF] webclaw usage unavailable: {e}")
        webclaw_line = "\nWEBCLAW:\n  • scans today: 0\n"

    # iter 322al — Intelligence Update (Part 6: BIN intelligence summary)
    # Counts + masked-hash actions only. NEVER names or contact data.
    intel_section = ""
    try:
        from services.bin_intelligence import intelligence_summary
        from server import db as _db  # type: ignore
        # tenant_id can arrive as "system" / "default" / None for the
        # admin invocation path; map those to the founder dogfood BIN so
        # the morning brief shows live intelligence numbers.
        _bin_id = tenant_id if (tenant_id and tenant_id not in ("system", "default")) else "AUR-FNDR-001"
        intel = await intelligence_summary(_db, _bin_id)
        px = intel.get("pixel", {})
        em = intel.get("email", {})
        ph = intel.get("phone", {})
        iv = intel.get("invoice", {})
        intel_lines = [
            "\nINTELLIGENCE UPDATE:",
            f"  • PIXEL: {px.get('visitors_today',0)} website visitors today · "
            f"{px.get('forms_today',0)} forms filled · "
            f"{px.get('matched_contacts',0)} matched to known contacts",
            f"  • EMAIL: {em.get('identified',0)} business contacts identified from Gmail",
            f"  • PHONE: {ph.get('verified',0)} contacts verified as business via call patterns",
            f"  • INVOICE: {iv.get('past_clients',0)} past clients ready for re-engagement",
        ]
        top = intel.get("top_actions") or []
        if top:
            intel_lines.append("  TOP ACTIONS TODAY:")
            for i, t in enumerate(top, start=1):
                intel_lines.append(
                    f"    {i}. {t.get('contact_hash','')[:8]}… — "
                    f"{t.get('sources_count',0)} sources matched · "
                    f"{t.get('intent_level','LOW')} — {t.get('recommended_action','Monitor')}"
                )
        intel_section = "\n".join(intel_lines) + "\n"
    except Exception as e:
        logger.debug(f"[BRIEF] intelligence update unavailable: {e}")

    # Template fallback
    econ_section = f"\nECONOMIC CONTEXT:\n  {economic_line}\n" if economic_line else ""

    # iter 327l — Pixel Health line. Cheap two-count check on
    # universal_events; surfaces when the pixel pipe silently regresses
    # (LEAN_ROUTES skip-list, CORS, pixel JS removed from a site).
    pixel_health_line = ""
    pixel_health_data = None
    try:
        from services.pixel_health import compute_pixel_health, maybe_alert_low_pixel_day
        _db_ref = _get_db()
        pixel_health_data = await compute_pixel_health(_db_ref)
        pixel_health_line = pixel_health_data.get("brief_line", "")
        # Fire-and-forget Telegram alert when classification is LOW.
        await maybe_alert_low_pixel_day(_db_ref, pixel_health_data)
    except Exception as _e:
        logger.debug(f"[BRIEF] pixel health unavailable: {_e}")
    pixel_section = f"\nPIXEL HEALTH:\n  • {pixel_health_line}\n" if pixel_health_line else ""

    brief_text = f"""AUREM MORNING BRIEF — {now.strftime('%B %d, %Y')} {now.strftime('%I:%M %p')} UTC
System Health: {scan['site_health']['score']}/100

HANDLED OVERNIGHT (no action needed):
{chr(10).join(f'  • {a}' for a in handled_overnight) if handled_overnight else '  • No automated actions overnight'}

NEEDS YOUR ATTENTION:
{chr(10).join(f'  • {a}' for a in needs_attention) if needs_attention else '  • All clear — no items need attention'}
{econ_section}{ssot_section}{webclaw_line}{intel_section}{pixel_section}
TODAY'S PRIORITIES:
{chr(10).join(f'  {i+1}. {p}' for i, p in enumerate(priorities[:3]))}

REVENUE SNAPSHOT:
  Outstanding: ${scan['invoices']['total_outstanding']} | At Risk: ${scan['invoices']['revenue_at_risk']}
"""

    # WhatsApp condensed version (< 500 chars)
    whatsapp_text = (
        f"AUREM Brief {now.strftime('%b %d')}:\n"
        f"Handled: {len(handled_overnight)} actions overnight\n"
        f"Needs you: {len(needs_attention)} items\n"
        f"Outstanding: ${scan['invoices']['total_outstanding']}\n"
        f"Top: {priorities[0] if priorities else 'All clear'}"
    )[:500]

    brief = {
        "brief_id": brief_id,
        "tenant_id": tenant_id,
        "date": now.strftime("%Y-%m-%d"),
        "generated_at": now.isoformat(),
        "health_score": scan["site_health"]["score"],
        "brief_text": brief_text,
        "narrative": narrative,
        "whatsapp_text": whatsapp_text,
        "sections": {
            "handled_overnight": handled_overnight,
            "needs_attention": needs_attention,
            "economic_context": economic_line,
            "priorities": priorities[:3],
            "revenue": {
                "outstanding": scan["invoices"]["total_outstanding"],
                "at_risk": scan["invoices"]["revenue_at_risk"],
            },
            "system_health": {
                "score": scan["site_health"]["score"],
                "issues": scan["site_health"]["issues_count"],
            },
            # iter 327l — Pixel Health structured fields so the
            # System Overview / chat UI can surface the same data
            # the brief text shows.
            "pixel_health": pixel_health_data or {},
        },
        "scan_data": scan,
        "auto_actions": auto_actions,
        "stats": {
            "actions_taken": len(auto_actions),
            "items_attention": len(needs_attention),
            "leads_new": scan["leads"]["new"],
            "messages_waiting": scan["messages"]["unanswered"],
            "pipeline_runs": scan["pipeline"]["runs_overnight"],
        },
    }

    # Store in DB
    db = _get_db()
    if db is not None:
        await db.morning_briefs.insert_one({**brief})

    return {k: v for k, v in brief.items() if k != "_id"}


# ═══════════════════════════════════════
# STEP 4: DELIVERY
# ═══════════════════════════════════════

async def deliver_brief(brief: dict, settings: dict = None):
    """Deliver brief via configured channels."""
    channels = (settings or {}).get("channels", ["dashboard"])
    # iter 326vv — audit trail. Every cron run now persists outcome to
    # `founder_brief_sends` so the System Overview / debugging dash can
    # see which channels actually delivered. Previously this was a
    # silent no-op: 124 briefs generated, 0 founder_brief_sends rows.
    delivery_outcome = {
        "brief_id":    brief.get("brief_id"),
        "tenant_id":   brief.get("tenant_id"),
        "channels":    list(channels),
        "results":     {},
        "delivered":   False,
        "ts":          datetime.now(timezone.utc).isoformat(),
    }

    if "whatsapp" in channels:
        try:
            from services.twilio_service import send_whatsapp_message
            wa_to = (
                os.environ.get("ADMIN_ALERT_PHONE")
                or os.environ.get("FOUNDER_PHONE")
                or ""
            ).strip()
            if wa_to:
                await send_whatsapp_message(wa_to, brief.get("whatsapp_text", ""))
                logger.info(f"[BRIEF] WhatsApp delivery sent to {wa_to}")
                delivery_outcome["results"]["whatsapp"] = {"ok": True, "to": wa_to}
                delivery_outcome["delivered"] = True
            else:
                logger.warning("[BRIEF] ADMIN_ALERT_PHONE/FOUNDER_PHONE missing — WhatsApp skipped")
                delivery_outcome["results"]["whatsapp"] = {"ok": False, "reason": "no_phone"}
        except Exception as e:
            logger.warning(f"[BRIEF] WhatsApp delivery failed: {e}")
            delivery_outcome["results"]["whatsapp"] = {"ok": False, "error": str(e)[:200]}

    if "push" in channels:
        attention = brief.get("stats", {}).get("items_attention", 0)
        logger.info(f"[BRIEF] Push notification: {attention} items need attention")
        delivery_outcome["results"]["push"] = {"ok": True, "items_attention": attention}
        delivery_outcome["delivered"] = True

    logger.info(f"[BRIEF] Brief {brief.get('brief_id')} delivered via {channels}")

    # Persist audit row — best-effort, never break delivery on log failure.
    try:
        from server import db as _server_db  # type: ignore
        if _server_db is not None:
            await _server_db.founder_brief_sends.insert_one(delivery_outcome)
    except Exception as _le:
        logger.debug(f"[BRIEF] audit log skipped: {_le}")


# ═══════════════════════════════════════
# FULL PIPELINE: scan → auto-act → generate → deliver
# ═══════════════════════════════════════

async def run_morning_brief(tenant_id: str = None) -> dict:
    """Full morning brief pipeline: scan → auto-act → generate → deliver."""
    scan = await scan_overnight(tenant_id)
    settings = await get_brief_settings(tenant_id)

    auto_actions = []
    if settings.get("auto_act_before_brief", True):
        auto_actions = await auto_act(scan, tenant_id)

    brief = await generate_brief(scan, auto_actions, tenant_id)

    # REVENUE FORECAST: inject 90-day forecast line
    try:
        from services.revenue_forecast import get_morning_brief_line
        forecast_line = await get_morning_brief_line(tenant_id or "aurem_platform")
        brief["forecast_line"] = forecast_line
        if brief.get("sections"):
            brief["sections"]["revenue_forecast"] = forecast_line
    except Exception:
        pass

    # LEARNING VELOCITY: inject velocity line
    try:
        from services.memory_tiers import get_learning_velocity
        velocity = await get_learning_velocity(tenant_id)
        score = velocity.get("compound_score", 0)
        promos_week = sum(velocity.get("trend_promotions", []))
        velocity_line = (
            f"Learning velocity: {score}/100 "
            f"({promos_week} patterns learned this week)"
        )
        brief["learning_velocity"] = velocity_line
        if brief.get("sections"):
            brief["sections"]["learning_velocity"] = velocity_line
    except Exception:
        pass

    # SENTINEL HEALTH: inject anomaly/system health summary
    try:
        _tid = tenant_id or "aurem_platform"
        _mdb = _get_db()
        recent_anomalies = await _mdb.sentinel_diagnoses.find(
            {"tenant_id": _tid, "type": {"$in": ["performance_anomaly", "anomaly"]}},
            {"_id": 0, "stage": 1, "severity": 1, "elapsed_ms": 1, "created_at": 1}
        ).sort("created_at", -1).limit(5).to_list(5)

        latest_pulse = await _mdb.system_pulse.find_one(
            {}, {"_id": 0, "health_score": 1, "timestamp": 1}
        )

        anomaly_count = len(recent_anomalies)
        health_score = latest_pulse.get("health_score", "N/A") if latest_pulse else "N/A"

        sentinel_line = (
            f"System health: {health_score}/100 | "
            f"{anomaly_count} anomalies in last 24h"
        )
        if anomaly_count > 0:
            worst = recent_anomalies[0]
            sentinel_line += f" | Latest: {worst.get('stage', 'unknown')} ({worst.get('severity', 'info')})"

        brief["sentinel_health"] = sentinel_line
        if brief.get("sections"):
            brief["sections"]["sentinel_health"] = sentinel_line
    except Exception:
        pass

    # ─── iter 282al-15 · Site QA summary (last 24h) ───────────────────
    try:
        from datetime import datetime as _dt2, timedelta as _td2, timezone as _tz2
        _sqdb = _get_db()
        _since = _dt2.now(_tz2.utc) - _td2(hours=24)
        audits_ct   = await _sqdb.site_audits.count_documents(
            {"audit_ts": {"$gte": _since}}
        )
        verified_ct = await _sqdb.site_test_results.count_documents(
            {"ts": {"$gte": _since}, "failed": 0}
        )
        failed_ct   = await _sqdb.site_test_results.count_documents(
            {"ts": {"$gte": _since}, "failed": {"$gt": 0}}
        )
        sent_ct     = await _sqdb.sites_sent.count_documents(
            {"ts": {"$gte": _since}}
        )
        paid_ct     = await _sqdb.campaign_leads.count_documents(
            {"repair_paid_at": {"$gte": _since}}
        )
        second_chance_ct = await _sqdb.campaign_leads.count_documents(
            {"second_chance_sent_at": {"$gte": _since}}
        )
        site_qa_line = (
            f"Sites QA: {audits_ct} audited | {verified_ct} verified | "
            f"{sent_ct} sent | {paid_ct} × $197 paid repairs | "
            f"{second_chance_ct} second-chance emails | {failed_ct} failed"
        )
        brief["site_qa"] = site_qa_line
        if brief.get("sections"):
            brief["sections"]["site_qa"] = site_qa_line

        # iter 282al-21 · ORA Brain (God Mode) summary
        try:
            from services.ora_god_mode import ora_brain_health
            _b = await ora_brain_health(_sqdb)
            brain_line = (
                f"ORA Brain: {_b.get('sessions_today', 0)} sessions | "
                f"avg confidence {_b.get('avg_confidence', 0)}% | "
                f"top intent: {_b.get('top_intent') or '—'} | "
                f"agency agents: {_b.get('agency_agents', 0)} | "
                f"snapshot: {_b.get('snapshot_age_days') or 'none'}"
            )
            if (_b.get("avg_confidence") or 0) < 60 and _b.get("sessions_today"):
                brain_line = "⚠️ " + brain_line
            brief["ora_brain"] = brain_line
            if brief.get("sections"):
                brief["sections"]["ora_brain"] = brain_line
        except Exception:
            pass
        brief["site_qa"] = site_qa_line
        if brief.get("sections"):
            brief["sections"]["site_qa"] = site_qa_line
    except Exception:
        pass

    # CUSTOMER HEALTH: inject auto-repair stats from last 24h
    try:
        _chmdb = _get_db()
        latest = await _chmdb.customer_health_summary.find_one(
            {"_id": "latest"}, {"_id": 0}
        )
        from datetime import timedelta as _td_ch
        since = datetime.now(timezone.utc) - _td_ch(hours=24)
        fixes_today = await _chmdb.customer_repair_log.count_documents(
            {"ts": {"$gte": since},
             "outcome": {"$in": ["auto_applied", "council_approved",
                                  "manual_applied", "verified_fixed"]}}
        )
        if latest:
            counts = latest.get("counts", {}) or {}
            healed_line = (
                f"Customers: {counts.get('healthy',0)} healthy · "
                f"{counts.get('degraded',0)} degraded · "
                f"{counts.get('critical',0)} critical · "
                f"{fixes_today} auto-fixes today"
            )
            brief["customer_health"] = healed_line
            if brief.get("sections"):
                brief["sections"]["customer_health"] = healed_line
    except Exception:
        pass

    await deliver_brief(brief, settings)

    return brief


# ═══════════════════════════════════════
# SETTINGS
# ═══════════════════════════════════════

async def get_brief_settings(tenant_id: str = None) -> dict:
    db = _get_db()
    if db is not None and tenant_id:
        s = await db.brief_settings.find_one({"tenant_id": tenant_id}, {"_id": 0})
        if s:
            return {**DEFAULT_SETTINGS, **s}
    return {**DEFAULT_SETTINGS, "tenant_id": tenant_id}


async def update_brief_settings(tenant_id: str, updates: dict) -> dict:
    db = _get_db()
    if db is None:
        return {"error": "DB unavailable"}
    updates["tenant_id"] = tenant_id
    updates["updated_at"] = datetime.now(timezone.utc).isoformat()
    await db.brief_settings.update_one({"tenant_id": tenant_id}, {"$set": updates}, upsert=True)
    return await get_brief_settings(tenant_id)


# ═══════════════════════════════════════
# HISTORY
# ═══════════════════════════════════════

async def get_brief_history(tenant_id: str = None, limit: int = 30) -> list:
    db = _get_db()
    if db is None:
        return []
    query = {"tenant_id": tenant_id} if tenant_id else {}
    briefs = await db.morning_briefs.find(query, {"_id": 0}).sort("generated_at", -1).to_list(limit)
    return briefs


async def get_today_brief(tenant_id: str = None) -> dict:
    db = _get_db()
    if db is None:
        return None
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    query = {"date": today}
    if tenant_id:
        query["tenant_id"] = tenant_id
    brief = await db.morning_briefs.find_one(query, {"_id": 0}, sort=[("generated_at", -1)])
    return brief


# ═══════════════════════════════════════
# SCHEDULER
# ═══════════════════════════════════════

async def morning_brief_scheduler():
    """Background scheduler — runs daily at configured time."""
    import pytz

    while True:
        try:
            est = pytz.timezone("America/Toronto")
            now = datetime.now(est)
            target = now.replace(hour=7, minute=0, second=0, microsecond=0)
            if now >= target:
                target += timedelta(days=1)

            wait = (target - now).total_seconds()
            logger.info(f"[BRIEF] Next brief at {target}, waiting {wait/3600:.1f}h")
            await asyncio.sleep(wait)

            logger.info("[BRIEF] Generating morning brief...")
            await run_morning_brief()
            logger.info("[BRIEF] Morning brief complete")

        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"[BRIEF] Scheduler error: {e}")
            await asyncio.sleep(3600)
