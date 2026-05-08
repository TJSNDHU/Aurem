"""
Sunday Founder's Forecast (iter 313)
=====================================
Every Sunday 8 PM Toronto, pull last-7-day metrics across the platform:
  · MEGA scans (db.intelligence_scans)
  · Monday Brief outcomes (db.monday_briefs)
  · Stripe revenue (db.repair_orders)
  · New domains registered (db.customer_domains)
  · Customer edits (db.auto_built_sites.edit_count delta)
  · AWB sites built (db.auto_built_sites)

ORA synthesizes a single forecast and ships it via Email + WhatsApp.

Public:
  await maybe_send_forecast(db) -> dict      (hourly tick — fires Sun 8 PM TO)
  await send_forecast_now(db) -> dict        (admin trigger / manual test)
"""
from __future__ import annotations

import logging
import os
import uuid
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List

import httpx

logger = logging.getLogger(__name__)

FOUNDER_WHATSAPP = os.environ.get("FOUNDER_WHATSAPP", "+16134000000")
FOUNDER_EMAIL = os.environ.get("FOUNDER_EMAIL", "teji.ss1986@gmail.com")
TZ_OFFSET_HOURS = -4  # Toronto


def _toronto_now() -> datetime:
    return datetime.now(timezone.utc) + timedelta(hours=TZ_OFFSET_HOURS)


def _is_sunday_8pm_window() -> bool:
    n = _toronto_now()
    return n.weekday() == 6 and n.hour == 20


async def _gather_metrics(db) -> Dict[str, Any]:
    week_ago = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()

    # MEGA scans
    scans = await db.intelligence_scans.find(
        {"status": "done", "ts": {"$gte": week_ago}},
        {"_id": 0, "lenses": 0},
    ).sort("ts", -1).limit(20).to_list(20)

    # Monday brief
    monday = await db.monday_briefs.find_one(
        {"ts": {"$gte": week_ago}}, {"_id": 0},
        sort=[("ts", -1)],
    )

    # Stripe revenue (paid orders only)
    revenue_orders = await db.repair_orders.find(
        {"status": {"$in": ["paid", "completed"]},
         "created_at": {"$gte": week_ago}},
        {"_id": 0, "amount_cad": 1, "tier": 1, "domain_addon": 1, "slug": 1},
    ).to_list(200)
    revenue_total = sum(int(o.get("amount_cad", 0)) for o in revenue_orders) / 100

    # New domains
    new_domains = await db.customer_domains.find(
        {"registered_at": {"$gte": week_ago}}, {"_id": 0},
    ).to_list(100)

    # Customer edits — count of sites whose last_edited is in the window
    edits_pipeline = [
        {"$match": {"last_edited": {"$gte": week_ago}}},
        {"$group": {"_id": None,
                     "edits_total": {"$sum": "$edit_count"},
                     "sites_edited": {"$sum": 1}}},
    ]
    edits_doc = await db.auto_built_sites.aggregate(edits_pipeline).to_list(1)
    edits_total = (edits_doc[0]["edits_total"] if edits_doc else 0)
    sites_edited = (edits_doc[0]["sites_edited"] if edits_doc else 0)

    # AWB sites built this week
    sites_built = await db.auto_built_sites.count_documents(
        {"created_at": {"$gte": week_ago},
         "status": {"$in": ["rendered", "published", "deployed"]}})

    # Iter 315 — top-performing bets (rolling 30 days)
    proven: List[Dict[str, Any]] = []
    try:
        from services.attribution import top_performing_bets
        proven = await top_performing_bets(db, days=30, limit=3)
    except Exception as e:
        logger.warning(f"[forecast] proven bets fetch failed: {e}")

    return {
        "scans": scans, "monday_brief": monday,
        "revenue_orders": revenue_orders, "revenue_total_cad": revenue_total,
        "new_domains": new_domains, "edits_total": edits_total,
        "sites_edited": sites_edited, "sites_built": sites_built,
        "proven_bets": proven,
        "week_start": week_ago,
    }


async def _ora_synthesize(metrics: Dict[str, Any]) -> Dict[str, Any]:
    """7th call — ask ORA to write the forecast."""
    api_key = os.environ.get("EMERGENT_LLM_KEY", "")
    if not api_key:
        return {"verdict": "MODIFY", "raw_markdown": ""}

    # Compress scans for prompt
    scan_lines: List[str] = []
    for s in metrics["scans"][:10]:
        c = s.get("council", {}) or {}
        topic = (s.get("inputs", {}) or {}).get("topic", "")[:60]
        scan_lines.append(
            f"- {topic} · verdict={c.get('verdict')} · risk={c.get('risk')}/10 · conf={c.get('confidence')}%"
        )
    scans_block = "\n".join(scan_lines) or "(no scans this week)"

    # Iter 315 — proven converters bias
    proven = metrics.get("proven_bets") or []
    proven_block = "\n".join(
        f"- {b['bet_topic']} · ${b['revenue_per_100']:.0f}/100 leads · "
        f"paid={b['paid']} · booked={b['booked']} · responded={b['responded']}"
        for b in proven[:3]
    ) or "(no proven converters yet)"

    prompt = (
        f"Week ended: {datetime.now(timezone.utc).date().isoformat()}\n"
        f"Sites built: {metrics['sites_built']} · "
        f"Domains registered: {len(metrics['new_domains'])} · "
        f"Customer edits: {metrics['edits_total']} (across {metrics['sites_edited']} sites) · "
        f"Revenue: ${metrics['revenue_total_cad']:.2f} CAD\n\n"
        f"PROVEN CONVERTERS (rolling 30d):\n{proven_block}\n\n"
        f"MEGA scans this week:\n{scans_block}\n\n"
        f"Synthesize a 1-page founder forecast for next week. "
        f"Bias BUILD verdicts toward proven-converter patterns above. "
        f"Output ONLY this markdown (max 320 tokens):\n\n"
        f"**THIS WEEK BUILT:** {metrics['sites_built']} sites · "
        f"{len(metrics['new_domains'])} domains · "
        f"${metrics['revenue_total_cad']:.0f} CAD\n"
        f"**MOMENTUM:** [📈 / 📉 / →] one short reason\n"
        f"**🏆 BEST PERFORMING BETS:** [3 lines, one per top bet, in the form\n"
        f"  `bet_topic — $X/100 leads — Yp/Zb/Wr`]\n"
        f"**BUILD THIS WEEK:** [pick 1 highest-leverage BUILD verdict from "
        f"the scans, biased toward proven patterns. Name the topic + first move.]\n"
        f"**SKIP THIS WEEK:** [pick 1 SKIP-or-MODIFY verdict, why drop it]\n"
        f"**NEXT BIG BET:** [pick 1 long-horizon move; specific, "
        f"shippable]\n"
        f"**THIS WEEK BIASED TOWARD:** [name the proven pattern this week's BUILD copies]\n"
        f"**RISK TO WATCH:** [one sentence]"
    )

    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage  # type: ignore
        import asyncio
        import uuid
        chat = LlmChat(
            api_key=api_key,
            session_id=f"forecast-{uuid.uuid4().hex[:10]}",
            system_message=("You are ORA writing TJ Sandhu's Sunday "
                             "founder forecast. Output ONLY the requested "
                             "markdown. Specific, ship-able, Canadian voice. "
                             "Numbers over claims."),
        ).with_model("anthropic", "claude-sonnet-4-5-20250929") \
         .with_params(max_tokens=480)
        out = await asyncio.wait_for(
            chat.send_message(UserMessage(text=prompt)), timeout=45.0,
        )
        return {"raw_markdown": (out or "").strip()}
    except Exception as e:
        logger.warning(f"[forecast] ORA synth failed: {e}")
        return {"raw_markdown": "", "error": str(e)[:200]}


def _format_text(metrics: Dict[str, Any], synth: Dict[str, Any]) -> str:
    today = _toronto_now().strftime("%Y-%m-%d")
    raw = synth.get("raw_markdown", "")
    if raw:
        return f"📊 *AUREM WEEKLY FORECAST*\nWeek of {today}\n\n{raw}"
    # Fallback if LLM unavailable
    return (
        f"📊 *AUREM WEEKLY FORECAST*\n"
        f"Week of {today}\n\n"
        f"*This week built:* {metrics['sites_built']} sites · "
        f"{len(metrics['new_domains'])} domains\n"
        f"*Revenue:* ${metrics['revenue_total_cad']:.0f} CAD\n"
        f"*Customer edits:* {metrics['edits_total']} (across "
        f"{metrics['sites_edited']} sites)\n"
        f"*MEGA scans completed:* {len(metrics['scans'])}\n"
    )


async def _send_email(subject: str, html: str) -> bool:
    api_key = os.environ.get("RESEND_API_KEY", "")
    from_addr = os.environ.get("RESEND_FROM_EMAIL", "ORA <ora@aurem.live>")
    if not api_key:
        return False
    try:
        async with httpx.AsyncClient(timeout=15) as c:
            r = await c.post(
                "https://api.resend.com/emails",
                headers={"authorization": f"Bearer {api_key}",
                          "content-type": "application/json"},
                json={"from": from_addr, "to": [FOUNDER_EMAIL],
                       "subject": subject, "html": html},
            )
            return r.status_code < 300
    except Exception as e:
        logger.warning(f"[forecast] email failed: {e}")
        return False


async def _send_whatsapp(text: str) -> bool:
    try:
        from routers.whatsapp_alerts import send_whatsapp
        out = await send_whatsapp(FOUNDER_WHATSAPP, text)
        return bool(out and out.get("ok"))
    except Exception as e:
        logger.warning(f"[forecast] wa failed: {e}")
        return False


async def send_forecast_now(db) -> Dict[str, Any]:
    metrics = await _gather_metrics(db)
    synth = await _ora_synthesize(metrics)
    text = _format_text(metrics, synth)

    proven_html = ""
    if metrics.get("proven_bets"):
        rows = "".join(
            f"<li><strong>{b['bet_topic'][:80]}</strong> — "
            f"${b['revenue_per_100']:.0f}/100 leads · "
            f"{b['paid']}p / {b['booked']}b / {b['responded']}r</li>"
            for b in metrics["proven_bets"]
        )
        proven_html = (
            "<h3 style='color:#8a6d1c;margin-top:18px'>🏆 Best Performing Bets</h3>"
            f"<ul style='font-size:13px;line-height:1.6'>{rows}</ul>"
        )

    html = (
        "<div style='font-family:Georgia,serif;max-width:640px'>"
        "<h2 style='color:#8a6d1c;margin:0 0 4px'>AUREM Weekly Forecast</h2>"
        f"<p style='color:#555;font-size:12px;margin:0 0 14px'>"
        f"Week ending {_toronto_now().strftime('%Y-%m-%d')}</p>"
        "<pre style='white-space:pre-wrap;background:#faf6e8;padding:18px;"
        "border-left:3px solid #C9A227;font-family:Georgia,serif;"
        f"font-size:14px;line-height:1.55'>{text}</pre>"
        f"{proven_html}"
        "<table style='font-size:12px;color:#666;margin-top:18px;width:100%'>"
        f"<tr><td>Sites built</td><td>{metrics['sites_built']}</td></tr>"
        f"<tr><td>New domains</td><td>{len(metrics['new_domains'])}</td></tr>"
        f"<tr><td>Revenue (paid)</td><td>${metrics['revenue_total_cad']:.2f} CAD</td></tr>"
        f"<tr><td>Customer edits</td><td>{metrics['edits_total']}</td></tr>"
        f"<tr><td>MEGA scans</td><td>{len(metrics['scans'])}</td></tr>"
        "</table>"
        "<p style='font-size:11px;color:#888;margin-top:18px'>"
        "Generated by ORA · Sunday 8 PM Toronto · "
        "<a href='https://aurem.live/admin/console'>Founders Console</a>"
        "</p></div>"
    )

    email_ok = await _send_email(
        f"AUREM Weekly Forecast — {_toronto_now().strftime('%b %d')}", html)
    wa_ok = await _send_whatsapp(text)

    record = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "metrics": {
            "sites_built": metrics["sites_built"],
            "domains": len(metrics["new_domains"]),
            "revenue_total_cad": metrics["revenue_total_cad"],
            "edits_total": metrics["edits_total"],
            "scans_count": len(metrics["scans"]),
        },
        "raw_markdown": synth.get("raw_markdown", "")[:2000],
        "email_ok": email_ok, "whatsapp_ok": wa_ok,
        "preview": text[:500],
    }
    forecast_id = uuid.uuid4().hex[:14]
    record["forecast_id"] = forecast_id
    try:
        await db.founder_forecasts.insert_one(dict(record))
    except Exception:
        pass

    # Iter 315 — record proven bets as ora_learning so Council reads it
    try:
        from services.attribution import record_proven_bets_learning
        if metrics.get("proven_bets"):
            await record_proven_bets_learning(db, metrics["proven_bets"])
    except Exception as e:
        logger.debug(f"[forecast] proven-bets learning persist failed: {e}")

    # Iter 314 — auto-arm Monday outbound campaign from NEXT BIG BET
    campaign_arm = None
    try:
        from services.forecast_campaigns import arm_campaign_from_forecast
        campaign_arm = await arm_campaign_from_forecast(
            db, forecast_id, synth.get("raw_markdown", ""),
        )
    except Exception as e:
        logger.warning(f"[forecast] campaign auto-arm failed: {e}")
        campaign_arm = {"ok": False, "error": str(e)[:200]}

    record.pop("_id", None)
    record["campaign_arm"] = (
        {"ok": campaign_arm.get("ok"),
          "skipped": campaign_arm.get("skipped"),
          "campaign_id": campaign_arm.get("campaign_id"),
          "lead_count": campaign_arm.get("lead_count"),
          "bet_topic": campaign_arm.get("bet_topic")}
        if campaign_arm else None
    )
    return record


async def maybe_send_forecast(db) -> Dict[str, Any]:
    """Hourly tick — fires only Sun 8-9 PM Toronto, idempotent within 22 h."""
    if not _is_sunday_8pm_window():
        return {"ok": True, "skipped": "not_sunday_8pm_window"}
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=22)).isoformat()
    existing = await db.founder_forecasts.find_one(
        {"ts": {"$gte": cutoff}}, {"_id": 0, "ts": 1},
    )
    if existing:
        return {"ok": True, "skipped": "already_sent_today",
                "last_ts": existing.get("ts")}
    return await send_forecast_now(db)
