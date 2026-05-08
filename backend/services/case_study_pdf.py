"""
AUREM Case Study — PDF Generator (WeasyPrint)
═══════════════════════════════════════════════════════════════════════════════
Renders the aggregated report payload to a cinematic AUREM-branded PDF using
Jinja2 templates + WeasyPrint. Also attaches a Claude 4.5 "AI Outlook" block
for forward-looking advisory.
"""
from __future__ import annotations

import os
import json
import logging
import uuid
from pathlib import Path
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

TEMPLATE_DIR = Path(__file__).parent.parent / "templates" / "case_study"
OUTPUT_DIR = Path("/app/generated_reports")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


async def generate_ai_outlook(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Ask Claude 4.5 for 3 predictive suggestions + a bottom-line statement."""
    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage
        key = os.environ.get("EMERGENT_LLM_KEY", "")
        if not key:
            return _outlook_fallback(payload)

        compact = {
            "customer": payload.get("customer_name"),
            "period": payload.get("report_period_label"),
            "uptime_pct": payload["exec"]["uptime_pct"],
            "incidents_resolved": payload["exec"]["incidents_resolved"],
            "errors_captured": payload["exec"]["errors_captured"],
            "auto_healed": payload["sentinel"]["auto_healed"],
            "leads_handled": payload["exec"]["leads_handled"],
            "voice_calls": payload["ora"]["voice_calls"],
            "hours_saved": payload["exec"]["hours_saved"],
            "dollars_saved": payload["exec"]["dollars_saved"],
            "roi_multiplier": payload["exec"]["roi_multiplier"],
            "top_error_types": payload["sentinel"]["top_types"][:3],
            "top_incidents": payload["uptime"]["top_incidents"][:3],
        }

        chat = LlmChat(
            api_key=key,
            session_id=f"case-study-{uuid.uuid4().hex[:8]}",
            system_message=(
                "You are AUREM's Chief Intelligence Officer preparing a "
                "quarterly business review for a C-suite audience. Given a "
                "telemetry summary, produce STRICT JSON with forward-looking "
                "predictions. Tone: calm, authoritative, specific, no hype.\n\n"
                "Schema (no markdown, no code fences):\n"
                '{\n'
                '  "horizon_label": "next 30 days / next quarter / etc.",\n'
                '  "predictions": [\n'
                '    {"title": "short headline (6-10 words)", "body": "2-3 sentence specific recommendation rooted in the data"},\n'
                '    ... exactly 3 items ...\n'
                '  ],\n'
                '  "bottom_line": "one 2-sentence strategic takeaway"\n'
                "}\n"
                "Rules: cite actual numbers from the telemetry. Never invent data. "
                "If data is sparse, say so and recommend what to measure next."
            ),
        ).with_model("anthropic", "claude-sonnet-4-5")

        reply = await chat.send_message(
            UserMessage(text=f"Telemetry summary:\n{json.dumps(compact, indent=2)}")
        )
        raw = str(reply).strip()
        start = raw.find("{")
        end = raw.rfind("}")
        if start == -1 or end == -1:
            return _outlook_fallback(payload)
        parsed = json.loads(raw[start:end + 1])
        preds = parsed.get("predictions") or []
        # Normalize
        return {
            "horizon_label": (parsed.get("horizon_label") or "next period")[:80],
            "predictions": [
                {"title": (p.get("title") or "")[:120], "body": (p.get("body") or "")[:480]}
                for p in preds[:3]
            ],
            "bottom_line": (parsed.get("bottom_line") or "")[:600],
        }
    except Exception as e:
        logger.warning(f"[case-study] AI outlook fallback: {e}")
        return _outlook_fallback(payload)


def _outlook_fallback(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Data-driven fallback when Claude is unavailable."""
    up = payload["exec"]["uptime_pct"]
    inc = payload["exec"]["incidents_resolved"]
    hours = payload["exec"]["hours_saved"]
    predictions = []
    if up < 99.5:
        predictions.append({
            "title": "Prioritize reliability capacity upgrades",
            "body": f"Uptime of {up}% is below the 99.5% SLA bar — projected next-period risk is elevated. Recommend capacity headroom review on the two weakest endpoints."
        })
    if inc > 3:
        predictions.append({
            "title": "Formalize incident postmortem cadence",
            "body": f"{inc} incidents resolved this window. Introduce a weekly 15-minute postmortem standup to prevent repeat categories and build institutional memory."
        })
    predictions.append({
        "title": "Scale AI workforce where ROI is strongest",
        "body": f"AUREM saved {hours} hours of human labor this period. Redirect that recovered capacity toward strategic work (product, partnerships) rather than reactive ops."
    })
    return {
        "horizon_label": "next period",
        "predictions": predictions[:3],
        "bottom_line": "Maintain the current AUREM posture; the telemetry indicates steady returns with room to push reliability one tier higher."
    }


def render_html(payload: Dict[str, Any]) -> str:
    """Render Jinja2 HTML from the payload (with outlook already attached)."""
    from jinja2 import Environment, FileSystemLoader, select_autoescape
    env = Environment(
        loader=FileSystemLoader(str(TEMPLATE_DIR)),
        autoescape=select_autoescape(["html", "xml"]),
    )
    tmpl = env.get_template("case_study.html")
    return tmpl.render(**payload)


def render_pdf(html: str, output_name: Optional[str] = None) -> Path:
    """Render HTML → PDF via WeasyPrint. Returns absolute path to the file."""
    from weasyprint import HTML
    name = output_name or f"aurem_report_{uuid.uuid4().hex[:10]}.pdf"
    out = OUTPUT_DIR / name
    HTML(string=html, base_url=str(TEMPLATE_DIR)).write_pdf(str(out))
    return out


async def build_and_write_pdf(db, payload: Dict[str, Any]) -> Dict[str, Any]:
    """Convenience: attach AI outlook, render HTML, render PDF, persist record."""
    outlook = await generate_ai_outlook(payload)
    payload["outlook"] = outlook

    html = render_html(payload)
    pdf_name = f"{payload['report_id']}.pdf"
    path = render_pdf(html, output_name=pdf_name)

    record = {
        "report_id": payload["report_id"],
        "customer_email": payload.get("customer_email"),
        "customer_bin": payload.get("customer_bin"),
        "customer_name": payload.get("customer_name"),
        "report_type": payload.get("report_type"),
        "period_start": payload.get("period_start_human"),
        "period_end": payload.get("period_end_human"),
        "issued_at": payload.get("issued_at_iso"),
        "pdf_filename": pdf_name,
        "pdf_size_bytes": path.stat().st_size,
        "outlook_preview": outlook.get("bottom_line", "")[:280],
        "metadata": {
            "uptime_pct": payload["exec"]["uptime_pct"],
            "hours_saved": payload["exec"]["hours_saved"],
            "dollars_saved": payload["exec"]["dollars_saved"],
            "errors_captured": payload["exec"]["errors_captured"],
            "leads": payload["exec"]["leads_handled"],
        },
    }
    try:
        await db.case_study_reports.insert_one(dict(record))
    except Exception as e:
        logger.warning(f"[case-study] record insert skipped: {e}")

    record.pop("_id", None)
    record["pdf_path"] = str(path)
    return record
