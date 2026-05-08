"""
Auto Website Builder (iter 297 — P1 #4) — Scaffold
==================================================
Pipeline: Scout (no-website filter) → Gemini draft → Claude refine → React template render.
DNS / Cloudflare wiring is intentionally out of scope here (queued via A2A tasks).

Pipeline emits:
  • Council deliberation (action_kind = "site_deploy", high-stakes → LLM voters auto)
  • A2A chain  scout → architect → envoy
  • ORA Learning log_action
  • Persists draft + refined HTML to `auto_built_sites`

Public API:
  await build_site_for_lead(db, lead_id) -> {site_id, status, ...}
  await build_batch(db, limit=5)         -> {built: [...], skipped: [...]}
  await list_sites(db, limit=50)         -> [{site_id, lead_id, status, preview_url, ...}]

Persistence: `auto_built_sites`
  {site_id, lead_id, business_name, niche, status:
    drafted|refined|rendered|deployed|failed|vetoed,
   gemini_draft, claude_refined, rendered_html, council_decision_id,
   chain_id, task_ids, created_at, updated_at, error}
"""
from __future__ import annotations

# iter 282al-6 — Safe normalization helpers for dedupe keys.
# Imported lazily so the heavy lead_dedup module isn't loaded just for
# these three pure functions on hot insert paths.
def _norm_phone_safe(p):
    try:
        from services.lead_dedup import _norm_phone
        return _norm_phone(p) or None
    except Exception:
        return None


def _domain_safe(u):
    try:
        from services.lead_dedup import extract_domain
        return extract_domain(u) or None
    except Exception:
        return None


def _norm_name_safe(n):
    try:
        from services.lead_dedup import _norm_name
        return _norm_name(n) or None
    except Exception:
        return None

import asyncio
import logging
import os
import re
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

NICHE_FALLBACK_TEMPLATE = "service-business"
MAX_DRAFT_TOKENS = 1400


# ─── LLM helpers ────────────────────────────────────────────────────────────
async def _gemini_draft(lead: Dict[str, Any],
                         repair_context: Optional[Dict[str, Any]] = None,
                         design_tokens: Optional[Dict[str, Any]] = None) -> Optional[str]:
    api_key = os.environ.get("EMERGENT_LLM_KEY", "")
    if not api_key:
        return None
    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage  # type: ignore
    except Exception:
        return None
    biz = lead.get("business_name") or "the business"
    niche = lead.get("niche") or NICHE_FALLBACK_TEMPLATE
    city = lead.get("city") or ""
    phone = (((lead.get("verification") or {}).get("phone") or {}).get("value")) \
            or lead.get("phone") or ""
    email = (((lead.get("verification") or {}).get("email") or {}).get("value")) \
            or lead.get("email") or ""

    # iter 282al-8 — auto-filled PRD for grounding (Prompt 11).
    prd_block = ""
    try:
        from services.prd_auto_fill import auto_fill_prd, prd_summary_for_llm
        prd = auto_fill_prd(lead)
        prd_block = prd_summary_for_llm(prd)
    except Exception as e:
        logger.debug(f"[awb] prd_auto_fill skipped: {e}")
    try:
        chat = LlmChat(
            api_key=api_key, session_id=f"awb-draft-{uuid.uuid4().hex[:8]}",
            system_message=(
                "You are a senior conversion copywriter for AUREM auto-built sites. "
                "Output a STRICT JSON object with these keys: "
                "headline, sub_headline, hero_cta, services[3 items: {name, description}], "
                "about (≤80 words), trust_bullets[3 items], contact_block. "
                "No markdown, no prose outside the JSON."
            ),
        ).with_model("gemini", "gemini-2.5-flash").with_max_tokens(MAX_DRAFT_TOKENS)
        prompt = (
            f"Business: {biz}\nNiche: {niche}\nCity: {city}\n"
            f"Phone: {phone}\nEmail: {email}\n"
            "Write conversion-focused English copy. Canadian audience tone. "
            "Avoid superlatives banned by CASL/FTC ('best','#1','guaranteed')."
        )
        if prd_block:
            prompt += "\n\n" + prd_block
        if repair_context:
            issues = repair_context.get("issues") or []
            issues_str = "; ".join(f"{i.get('title','')} ({i.get('kind','')})"
                                    for i in issues[:6]) or "various issues"
            prompt += (
                f"\n\nMODE: REPAIR (not full rebuild)."
                f"\nOriginal site: {repair_context.get('original_url') or 'n/a'}"
                f"\nScore before: {repair_context.get('audit_score_before')}/100"
                f"\nIssues detected: {issues_str}"
                f"\nKeep ORIGINAL brand colors and content tone if you can infer them. "
                f"Fix copy gaps that hurt conversions (no contact form / weak CTA / "
                f"stale year / missing trust bullets). Do NOT invent services."
            )
        if design_tokens and design_tokens.get("ok"):
            try:
                from services.design_extractor import design_prompt_snippet
                snippet = design_prompt_snippet(design_tokens)
                if snippet:
                    prompt += "\n\n" + snippet
            except Exception:
                pass
        out = await asyncio.wait_for(chat.send_message(UserMessage(text=prompt)), timeout=15.0)
        return (out or "").strip() or None
    except Exception as e:
        logger.debug(f"[awb] gemini draft failed: {e}")
        return None


async def _claude_refine(draft_json_str: str, lead: Dict[str, Any]) -> Optional[str]:
    api_key = os.environ.get("EMERGENT_LLM_KEY", "")
    if not api_key:
        return None
    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage  # type: ignore
    except Exception:
        return None
    try:
        chat = LlmChat(
            api_key=api_key, session_id=f"awb-refine-{uuid.uuid4().hex[:8]}",
            system_message=(
                "You are AUREM's content quality + legal reviewer. "
                "INPUT: a JSON copy draft. OUTPUT: refined JSON (same schema). "
                "Strip CASL-violating claims, banned superlatives, vague benefits. "
                "Tighten. Keep all keys: headline, sub_headline, hero_cta, services, "
                "about, trust_bullets, contact_block. Reply with JSON only."
            ),
        ).with_model("anthropic", "claude-sonnet-4.5").with_max_tokens(MAX_DRAFT_TOKENS)
        prompt = (
            f"Business: {lead.get('business_name','')}\n"
            f"Draft JSON:\n{draft_json_str[:6000]}"
        )
        out = await asyncio.wait_for(chat.send_message(UserMessage(text=prompt)), timeout=15.0)
        return (out or "").strip() or None
    except Exception as e:
        logger.debug(f"[awb] claude refine failed: {e}")
        return None


# ─── Renderer ───────────────────────────────────────────────────────────────
def _extract_json_block(s: str) -> Dict[str, Any]:
    if not s:
        return {}
    m = re.search(r"\{.*\}", s, re.S)
    if not m:
        return {}
    try:
        import json
        return json.loads(m.group(0))
    except Exception:
        return {}


def _default_services_for(biz_name: str, category: str = "") -> List[Dict[str, str]]:
    """Curated fallbacks when LLM didn't fill services. Keyword-based
    matching against business name + category."""
    text = f"{biz_name} {category}".lower()
    lib = [
        (["auto", "mechanic", "garage", "collision", "tire", "brake"],
         [("Collision Repair", "Frame-straightening, panel work, factory-spec finish."),
          ("Paint & Bodywork", "Colour-matched refinishing that looks factory fresh."),
          ("Dent Removal", "Paintless and traditional dent repair."),
          ("Mechanical Service", "Brakes, suspension, diagnostics, tune-ups."),
          ("Insurance Work", "We handle the paperwork so you don't have to."),
          ("Free Estimates", "No-cost walk-in inspection and written quote.")]),
        (["salon", "spa", "hair", "beauty", "nail", "lash"],
         [("Precision Cuts", "Classic, modern, and trend cuts for every face shape."),
          ("Colour & Highlights", "Balayage, foil, gloss, grey blend."),
          ("Treatments", "Keratin, bond-repair, deep conditioning."),
          ("Bridal Styling", "Trial-day booking, full wedding party packages."),
          ("Blow-dry Bar", "30-minute wash and style — walk-ins welcome."),
          ("Gift Cards", "Any amount, e-delivered or printed in store.")]),
        (["plumb", "drain", "hvac", "heating", "cooling", "electric"],
         [("Emergency Service", "Same-day response, 7 days a week."),
          ("Installation", "Fixture, furnace, and panel installs done right."),
          ("Repair & Maintenance", "Diagnostics, tune-ups, and fast repairs."),
          ("Inspection", "Permit-ready reports for real-estate transactions."),
          ("Upfront Pricing", "Flat-rate quotes — no surprises on the invoice."),
          ("Warranty-Backed", "Labour warranty on every job we complete.")]),
        (["cafe", "coffee", "restaurant", "bistro", "bakery", "eatery", "diner"],
         [("Fresh Daily", "Baked, brewed, and plated in-house every morning."),
          ("Catering", "Office, birthday, wedding — boxed or platter service."),
          ("Takeout & Delivery", "Order ahead from our site or app partners."),
          ("Seasonal Menu", "Quarterly rotation featuring local ingredients."),
          ("Private Events", "Host intimate dinners or product launches."),
          ("Gift Cards", "Treat someone to their next favourite bite.")]),
        (["clinic", "dental", "medical", "chiro", "therap", "wellness"],
         [("New-Patient Welcome", "Same-week appointments with no waiting list."),
          ("Preventive Care", "Cleanings, exams, and early-issue detection."),
          ("Restorative Work", "Crowns, fillings, and custom treatment plans."),
          ("Insurance Direct", "We bill your provider — you only pay the copay."),
          ("Emergency Slots", "Daily reserved slots for urgent patient needs."),
          ("Family Friendly", "Kids, teens, adults — all under one roof.")]),
        (["law", "accounting", "tax", "real estate", "realtor", "consulting"],
         [("Consultation", "Free 30-minute discovery call, no obligation."),
          ("Full-Service", "End-to-end handling, from intake to closing."),
          ("Transparent Fees", "Flat-fee pricing disclosed before we engage."),
          ("Local Expertise", "Decades of experience in this exact market."),
          ("Fast Response", "24-hour turnaround on all inbound inquiries."),
          ("Privacy First", "Confidentiality is our default, not an add-on.")]),
    ]
    for keywords, svc in lib:
        if any(k in text for k in keywords):
            return [{"name": n, "description": d} for n, d in svc]
    # Generic fallback
    return [
        {"name": "Quality Service", "description": "Craftsmanship and attention to detail on every job."},
        {"name": "Local Expertise", "description": "Family-owned and operated in the community we serve."},
        {"name": "Transparent Pricing", "description": "Upfront quotes — no surprises, no hidden fees."},
        {"name": "Satisfaction Guaranteed", "description": "We stand behind our work with a written warranty."},
        {"name": "Fast Response", "description": "Same-day or next-day service for most requests."},
        {"name": "Free Estimates", "description": "Bring us your project — we'll price it for free."},
    ]


def _render_html(copy: Dict[str, Any], lead: Dict[str, Any],
                 style: Optional[Dict[str, Any]] = None) -> str:
    """iter 282i — premium AUREM site template.

    Sections: Hero (glow + grid) · Services grid · Why Us 3-card · About ·
    Contact (click-to-call/email + optional map) · Footer.
    Default palette: #080808 bg, #F97316 orange accent, Cinzel + Jost.
    """
    biz = lead.get("business_name") or "Business"
    category = lead.get("category") or lead.get("business_category") or ""
    headline = copy.get("headline") or biz
    sub = (copy.get("sub_headline")
            or f"{category + ' for ' if category else ''}"
              f"{lead.get('city') or 'your neighbourhood'}. Licensed. Insured. Local.")
    cta = copy.get("hero_cta") or "Get a Free Quote"
    about = (copy.get("about")
              or f"{biz} is a proudly local, family-run {category or 'business'} serving "
                 f"the community with craftsmanship, honest pricing, and the kind of service "
                 f"that keeps customers coming back. Whether it's your first visit or your "
                 f"fifteenth, we treat every job like our reputation depends on it — "
                 f"because it does.")
    services = copy.get("services") or _default_services_for(biz, category)
    bullets = copy.get("trust_bullets") or [
        "Fully Licensed & Insured",
        "Locally Owned & Operated",
        "Satisfaction Guaranteed",
    ]
    phone = (((lead.get("verification") or {}).get("phone") or {}).get("value")) \
            or lead.get("phone") or ""
    email = (((lead.get("verification") or {}).get("email") or {}).get("value")) \
            or lead.get("email") or ""
    address = lead.get("address") or lead.get("full_address") or ""
    city = lead.get("city") or ""

    # Theme palette — iter 282i defaults align with AUREM brand (orange).
    # Callers can still override via `style` hint (e.g. tenant-branded sites).
    s = style or {}
    bg = s.get("primary_bg", "#080808")
    ink = s.get("primary_text", "#F2EDE4")
    accent = s.get("accent", "#F97316")
    accent2 = s.get("accent_secondary", "#EA580C")
    heading_color = s.get("heading_color", "#FFFFFF")
    body_font = s.get("body_font", "Jost")
    heading_font = s.get("heading_font", "Cinzel")
    muted = "#7A7066"

    def esc(x: Any) -> str:
        return (str(x or "")
                .replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))

    phone_href = "tel:" + "".join(c for c in str(phone) if c.isdigit() or c == "+")
    email_href = f"mailto:{email}" if email else ""

    # iter 282j Task 1 — Lead-uploaded logo (img.aurem.live CDN)
    # iter 282ah — onerror hide + strict size caps so broken logo urls never
    # render a broken-image icon to the prospect.
    logo_url = (lead.get("logo_url") or "").strip()
    logo_block = ""
    if logo_url and logo_url.startswith(("http://", "https://")):
        logo_block = (
            f'<div class="hero-logo">'
            f'<img src="{esc(logo_url)}" alt="{esc(biz)} logo" loading="eager" '
            f'style="max-height:60px;max-width:200px;object-fit:contain;" '
            f'onerror="this.style.display=\'none\'" />'
            f'</div>'
        )

    # Services with compact icon glyphs
    svc_icons = ["◆", "◇", "●", "▲", "■", "▼", "★", "◈"]
    svc_cards = "".join(
        f'<article class="svc" data-i="{i}">'
        f'<span class="svc-ic">{svc_icons[i % len(svc_icons)]}</span>'
        f'<h3>{esc(svc.get("name"))}</h3>'
        f'<p>{esc(svc.get("description"))}</p>'
        f'</article>'
        for i, svc in enumerate(services[:6]) if isinstance(svc, dict)
    )

    trust_items = "".join(
        f'<div class="trust-card"><span class="trust-dot"></span>{esc(b)}</div>'
        for b in bullets[:3]
    )

    contact_items = []
    if phone:
        contact_items.append(
            f'<a class="ct-link" href="{phone_href}"><span>Call</span><strong>{esc(phone)}</strong></a>'
        )
    if email:
        contact_items.append(
            f'<a class="ct-link" href="{email_href}"><span>Email</span><strong>{esc(email)}</strong></a>'
        )
    if address:
        from urllib.parse import quote_plus as _qp
        map_q = _qp(address + (f", {city}" if city else ""))
        contact_items.append(
            f'<a class="ct-link" href="https://www.google.com/maps/search/?api=1&query={map_q}" target="_blank" rel="noopener">'
            f'<span>Visit</span><strong>{esc(address)}</strong></a>'
        )
    contact_html = "".join(contact_items) or '<p class="muted">Contact details coming soon.</p>'

    return f"""<!doctype html>
<html lang="en"><head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width,initial-scale=1" />
<meta name="description" content="{esc(sub)}" />
<title>{esc(biz)}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Cinzel:wght@500;700&family=Jost:wght@300;400;500;600&display=swap" rel="stylesheet">
<style>
:root{{--bg:{bg};--ink:{ink};--accent:{accent};--accent2:{accent2};--head:{heading_color};--muted:{muted}}}
*{{box-sizing:border-box;-webkit-font-smoothing:antialiased}}
html,body{{margin:0;padding:0}}
body{{font:400 16px/1.65 '{body_font}','Helvetica Neue',system-ui,sans-serif;background:var(--bg);color:var(--ink);overflow-x:hidden}}
h1,h2,h3{{font-family:'{heading_font}','Trajan Pro',serif;font-weight:500;letter-spacing:.02em;color:var(--head)}}
a{{color:var(--accent);text-decoration:none}}
.wrap{{max-width:1120px;margin:0 auto;padding:0 24px}}
section{{padding:88px 0;position:relative}}

/* HERO */
.hero{{position:relative;padding:120px 0 100px;overflow:hidden;background:
  radial-gradient(ellipse at top,rgba(249,115,22,.18),transparent 55%),
  linear-gradient(180deg,var(--bg) 0%,#050505 100%);
  background-image:radial-gradient(ellipse at top,rgba(249,115,22,.18),transparent 55%),
    linear-gradient(rgba(249,115,22,.04) 1px,transparent 1px),
    linear-gradient(90deg,rgba(249,115,22,.04) 1px,transparent 1px),
    linear-gradient(180deg,var(--bg),#050505);
  background-size:auto,44px 44px,44px 44px,auto;}}
.hero::after{{content:"";position:absolute;bottom:0;left:0;right:0;height:120px;background:linear-gradient(0deg,var(--bg),transparent);pointer-events:none}}
.hero-inner{{position:relative;z-index:2;max-width:780px}}
.hero-logo{{margin:0 0 28px}}
.hero-logo img{{max-height:64px;max-width:240px;display:block;
  filter:drop-shadow(0 4px 16px rgba(249,115,22,.25))}}
.eyebrow{{display:inline-block;padding:6px 16px;border:1px solid rgba(249,115,22,.35);border-radius:40px;
  font-size:11px;letter-spacing:.22em;color:var(--accent);text-transform:uppercase;margin-bottom:28px}}
.hero h1{{font-size:clamp(38px,6vw,64px);line-height:1.05;margin:0 0 18px;letter-spacing:.01em}}
.hero h1 span{{background:linear-gradient(90deg,var(--accent),var(--accent2));-webkit-background-clip:text;background-clip:text;color:transparent}}
.hero p.sub{{font-size:clamp(16px,1.8vw,20px);color:#BFB8AA;max-width:640px;line-height:1.55;margin:0 0 32px}}
.hero-actions{{display:flex;gap:14px;flex-wrap:wrap;align-items:center}}
.cta{{display:inline-flex;align-items:center;gap:10px;padding:16px 34px;border-radius:8px;
  background:var(--accent);color:#0A0A00;font-weight:600;font-size:14px;letter-spacing:.08em;
  text-transform:uppercase;box-shadow:0 8px 32px rgba(249,115,22,.35);transition:transform .18s ease,box-shadow .18s ease}}
.cta:hover{{transform:translateY(-2px);box-shadow:0 14px 44px rgba(249,115,22,.55)}}
.cta-ghost{{display:inline-flex;align-items:center;gap:10px;padding:16px 28px;border-radius:8px;
  background:transparent;border:1px solid rgba(249,115,22,.4);color:var(--accent);
  font-weight:500;font-size:13px;letter-spacing:.1em;text-transform:uppercase}}
.cta-ghost:hover{{background:rgba(249,115,22,.08);border-color:var(--accent)}}
.phone-pill{{margin-top:20px;font-family:'{heading_font}',serif;font-size:22px;color:var(--head);letter-spacing:.08em}}
.phone-pill a{{color:inherit}}

/* SERVICES */
.services{{background:#060606;border-top:1px solid rgba(249,115,22,.08)}}
.sec-eyebrow{{font-size:11px;letter-spacing:.22em;color:var(--accent);text-transform:uppercase;margin-bottom:12px}}
.sec-title{{font-size:clamp(28px,4vw,42px);margin:0 0 14px}}
.sec-lead{{color:#9A9284;max-width:520px;margin:0 0 48px;font-size:16px;line-height:1.6}}
.svc-grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:18px}}
.svc{{position:relative;padding:28px 24px;background:linear-gradient(180deg,#0D0D0D,#060606);
  border:1px solid rgba(249,115,22,.14);border-radius:12px;transition:all .25s ease;overflow:hidden}}
.svc::before{{content:"";position:absolute;top:0;left:0;right:0;height:1px;
  background:linear-gradient(90deg,transparent,rgba(249,115,22,.6),transparent);opacity:0;transition:opacity .25s}}
.svc:hover{{border-color:rgba(249,115,22,.45);transform:translateY(-3px);box-shadow:0 20px 40px rgba(0,0,0,.5)}}
.svc:hover::before{{opacity:1}}
.svc-ic{{display:inline-block;font-size:20px;color:var(--accent);margin-bottom:14px;line-height:1}}
.svc h3{{margin:0 0 10px;font-size:19px;color:var(--head)}}
.svc p{{margin:0;color:#8F8878;font-size:14px;line-height:1.6}}

/* WHY US */
.why{{background:var(--bg)}}
.why-grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:20px;margin-top:40px}}
.trust-card{{display:flex;align-items:center;gap:14px;padding:24px;background:#0A0A0A;
  border:1px solid rgba(249,115,22,.18);border-radius:10px;font-size:15px;color:var(--head);
  font-weight:500;letter-spacing:.02em}}
.trust-dot{{width:10px;height:10px;border-radius:50%;background:var(--accent);
  box-shadow:0 0 16px rgba(249,115,22,.6);flex-shrink:0}}

/* ABOUT */
.about{{background:#060606}}
.about-text{{font-size:17px;line-height:1.75;color:#BFB8AA;max-width:720px}}

/* CONTACT */
.contact{{background:var(--bg);border-top:1px solid rgba(249,115,22,.08)}}
.ct-grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:14px;margin-top:36px}}
.ct-link{{display:flex;flex-direction:column;gap:6px;padding:22px;background:#0A0A0A;
  border:1px solid rgba(249,115,22,.18);border-radius:10px;transition:all .2s ease}}
.ct-link:hover{{border-color:rgba(249,115,22,.5);background:#0E0E0E}}
.ct-link span{{font-size:10px;letter-spacing:.25em;color:var(--accent);text-transform:uppercase}}
.ct-link strong{{font-family:'{heading_font}',serif;font-weight:500;font-size:18px;color:var(--head);letter-spacing:.02em}}

/* FOOTER */
footer.site{{padding:48px 0 32px;background:#030303;border-top:1px solid rgba(249,115,22,.12);color:#5A5248;font-size:13px;text-align:center}}
footer.site .biz{{font-family:'{heading_font}',serif;letter-spacing:.14em;color:var(--head);margin-bottom:10px;text-transform:uppercase;font-size:14px}}
.aurem-bar{{padding:18px 20px;background:linear-gradient(180deg,#050505,#000);
  border-top:1px solid rgba(249,115,22,.18);text-align:center;font-size:12px;letter-spacing:.1em;color:#7A7066}}
.aurem-bar a{{color:var(--accent);font-weight:600;text-decoration:none}}
.aurem-bar a:hover{{text-decoration:underline}}

@media(max-width:700px){{
  section{{padding:64px 0}}
  .hero{{padding:88px 0 72px}}
  .hero h1{{font-size:40px}}
}}
</style></head>
<body>

<section class="hero">
  <div class="wrap">
    <div class="hero-inner">
      {logo_block}
      <span class="eyebrow">{esc(city) or "Local"} · {esc(category) or "Trusted Service"}</span>
      <h1>{esc(headline.split(' ')[0] if ' ' in headline else headline)} <span>{esc(' '.join(headline.split(' ')[1:]) if ' ' in headline else '')}</span></h1>
      <p class="sub">{esc(sub)}</p>
      <div class="hero-actions">
        <a href="#contact" class="cta">{esc(cta)} <span>→</span></a>
        {f'<a href="{phone_href}" class="cta-ghost">Call Now</a>' if phone else ''}
      </div>
      {f'<div class="phone-pill"><a href="{phone_href}">{esc(phone)}</a></div>' if phone else ''}
    </div>
  </div>
</section>

<section class="services" id="services">
  <div class="wrap">
    <div class="sec-eyebrow">What we do</div>
    <h2 class="sec-title">Services built for people who need it done right.</h2>
    <p class="sec-lead">Every job is handled by skilled pros who treat your time, your property, and your budget with respect.</p>
    <div class="svc-grid">{svc_cards}</div>
  </div>
</section>

<section class="why">
  <div class="wrap">
    <div class="sec-eyebrow">Why us</div>
    <h2 class="sec-title">The trust we've built, backed by paper.</h2>
    <div class="why-grid">{trust_items}</div>
  </div>
</section>

<section class="about" id="about">
  <div class="wrap">
    <div class="sec-eyebrow">About</div>
    <h2 class="sec-title">Local roots, real standards.</h2>
    <p class="about-text">{esc(about)}</p>
  </div>
</section>

<section class="contact" id="contact">
  <div class="wrap">
    <div class="sec-eyebrow">Get in touch</div>
    <h2 class="sec-title">One call. One text. One email. You choose.</h2>
    <p class="sec-lead">We reply during business hours — emergencies get a faster response.</p>
    <div class="ct-grid">{contact_html}</div>
  </div>
</section>

<footer class="site">
  <div class="wrap">
    <div class="biz">{esc(biz)}</div>
    © {datetime.now(timezone.utc).year} {esc(biz)}. All rights reserved.
  </div>
</footer>

<div class="aurem-bar">
  Powered by <a href="https://aurem.live?utm_source=awb_site&amp;utm_medium=footer" target="_blank" rel="noopener">AUREM</a>
  · <a href="https://aurem.live?utm_source=awb_site&amp;utm_medium=footer_cta" target="_blank" rel="noopener">Get your free site →</a>
</div>

</body></html>"""


# ─── Lead selection ────────────────────────────────────────────────────────
async def _select_no_website_leads(db, limit: int = 5) -> List[Dict[str, Any]]:
    """Pick leads that need a free preview site built.

    iter 282 fix: exclude leads that ALREADY have a successfully-built
    site in `auto_built_sites` (status in {rendered, published, deployed})
    OR a lead-level `awb_built_at` marker. Prevents the runaway loop where
    autopilot kept rebuilding sites for the same leads every 30 min,
    spamming customers with hundreds of duplicate "your site is live" emails.
    """
    if db is None:
        return []
    # 1. Pre-fetch lead_ids that already have a successful site build.
    built_lead_ids = await db.auto_built_sites.distinct(
        "lead_id",
        {"status": {"$in": ["rendered", "published", "deployed"]}},
    )
    q = {
        "$and": [
            {"$or": [
                {"website": {"$in": [None, ""]}},
                {"verification.has_website": False},
                {"website_quality": {"$in": ["poor", "broken", None]}},
            ]},
            {"$or": [
                {"verification.channel_gating.email": True},
                {"verification.channel_gating.call": True},
            ]},
            # Exclude leads we've already built for (lead-level marker)
            {"awb_built_at": {"$in": [None, ""]}},
        ],
    }
    if built_lead_ids:
        q["$and"].append({"lead_id": {"$nin": built_lead_ids}})
    return await db.campaign_leads.find(q, {"_id": 0}).limit(int(limit)).to_list(int(limit))


# ─── Main pipeline ─────────────────────────────────────────────────────────
async def build_site_for_lead(db, lead_id: str,
                               style_hint: Optional[Dict[str, Any]] = None,
                               mode: str = "build",
                               original_url: Optional[str] = None,
                               audit_id: Optional[str] = None) -> Dict[str, Any]:
    if db is None:
        return {"ok": False, "error": "db unavailable"}
    lead = await db.campaign_leads.find_one({"lead_id": lead_id}, {"_id": 0})
    if not lead:
        return {"ok": False, "error": f"lead {lead_id} not found"}

    site_id = uuid.uuid4().hex[:14]
    now = datetime.now(timezone.utc).isoformat()

    # iter 282al-6 — Cross-business dedupe. If we already built a site
    # for this same business (matching phone, domain, or name+city),
    # return the existing one instead of rebuilding. Saves LLM tokens
    # and prevents the "Mike got 3 websites" anti-pattern.
    try:
        from services.lead_dedup import find_existing_site
        existing = await find_existing_site(db, lead)
        if existing:
            logger.info(
                f"[AWB] reusing existing site for lead_id={lead_id} "
                f"→ site_id={existing.get('site_id')} "
                f"slug={existing.get('slug')}"
            )
            # Mark this lead as built (point at the existing site) so
            # future selector queries skip it.
            try:
                await db.campaign_leads.update_one(
                    {"lead_id": lead_id},
                    {"$set": {
                        "awb_built_at":  datetime.now(timezone.utc).isoformat(),
                        "awb_site_id":   existing.get("site_id"),
                        "awb_slug":      existing.get("slug"),
                        "awb_reused":    True,
                    }},
                )
            except Exception:
                pass
            return {
                "ok":              True,
                "already_existed": True,
                "site_id":         existing.get("site_id"),
                "slug":            existing.get("slug"),
                "preview_url":     existing.get("preview_url"),
                "lead_id":         lead_id,
                "reused_from":     existing.get("lead_id"),
            }
    except Exception as _e:
        logger.debug(f"[AWB] find_existing_site skipped: {_e}")

    # Iter 304 — repair-mode context (audit-driven Gemini hint)
    # Iter 307 — design-token extraction for visual continuity
    repair_context: Dict[str, Any] = {}
    design_tokens: Optional[Dict[str, Any]] = None
    if mode == "repair":
        if not audit_id:
            audit_id = lead.get("audit_id")
        if audit_id:
            audit_doc = await db.customer_scans.find_one(
                {"scan_id": audit_id}, {"_id": 0}
            ) or {}
            repair_context = {
                "audit_id": audit_id,
                "audit_score_before": audit_doc.get("overall_score"),
                "issues": (audit_doc.get("issues") or [])[:8],
                "original_url": original_url or audit_doc.get("website")
                                 or lead.get("website_url"),
            }
        # Reuse cached design tokens from lead if recent (≤7 days)
        cached = lead.get("design_tokens") or {}
        if cached.get("extraction_success"):
            design_tokens = cached.get("data")
        else:
            url_for_design = repair_context.get("original_url") \
                              or lead.get("website_url")
            if url_for_design:
                try:
                    from services.design_extractor import extract_design
                    design_tokens = await extract_design(url_for_design, db=db)
                    # Cache on lead for next time
                    if design_tokens.get("ok"):
                        await db.campaign_leads.update_one(
                            {"lead_id": lead_id},
                            {"$set": {"design_tokens": {
                                "extraction_success": True,
                                "extracted_at": design_tokens["extracted_at"],
                                "source_url": design_tokens["source_url"],
                                "data": {k: v for k, v in design_tokens.items()
                                          if k != "raw_files"},
                            }}},
                        )
                except Exception as e:
                    logger.warning(f"[awb] design extract failed: {e}")

    base = {
        "site_id": site_id, "lead_id": lead_id,
        "business_name": lead.get("business_name"),
        "niche": lead.get("niche") or NICHE_FALLBACK_TEMPLATE,
        "status": "drafting", "created_at": now, "updated_at": now,
        "task_ids": [], "chain_id": None,
        "repair_mode": mode == "repair",
        "build_mode": mode,
        "original_url": repair_context.get("original_url"),
        "audit_score_before": repair_context.get("audit_score_before"),
        "audit_id": repair_context.get("audit_id"),
        "design_extracted": bool(design_tokens and design_tokens.get("ok")),
        # iter 282al-6 — dedupe keys for find_existing_site()
        "phone_normalized":         _norm_phone_safe(lead.get("phone")),
        "website_domain":           _domain_safe(lead.get("website")
                                                 or lead.get("website_url")),
        "business_name_normalized": _norm_name_safe(lead.get("business_name")),
    }
    await db.auto_built_sites.insert_one(base)

    # Council pre-approval
    from services.council import council
    decision = await council.deliberate(
        action_kind="site_deploy",
        payload={
            "lead_id": lead_id, "domain": lead.get("domain") or "",
            "niche": lead.get("niche") or NICHE_FALLBACK_TEMPLATE,
        },
        cost_usd=0.02,
    )
    base["council_decision_id"] = decision["decision_id"]

    if decision["decision"] == "veto":
        await db.auto_built_sites.update_one(
            {"site_id": site_id},
            {"$set": {"status": "vetoed", "council_decision_id": decision["decision_id"],
                      "error": decision.get("reason"), "updated_at": _now()}},
        )
        return {"ok": False, "site_id": site_id, "status": "vetoed",
                "reason": decision.get("reason")}

    # Emit A2A chain
    from services.a2a_task_queue import tq
    t1 = await tq.submit("scout", "architect", "build_site",
                         {"lead_id": lead_id, "site_id": site_id,
                          "niche": lead.get("niche")},
                         council_decision_id=decision["decision_id"])
    chain = await tq.chain(t1)
    chain_id = chain[0]["chain_id"] if chain else t1
    t2 = await tq.submit("architect", "envoy", "deliver_site_link",
                         {"lead_id": lead_id, "site_id": site_id},
                         parent_task_id=t1, council_decision_id=decision["decision_id"])
    base["chain_id"] = chain_id
    base["task_ids"] = [t1, t2]

    # Gemini draft
    draft_raw = await _gemini_draft(lead,
                                     repair_context=repair_context or None,
                                     design_tokens=design_tokens) or "{}"
    draft_json = _extract_json_block(draft_raw)
    await db.auto_built_sites.update_one(
        {"site_id": site_id},
        {"$set": {"gemini_draft": draft_raw[:6000],
                  "status": "drafted", "updated_at": _now(),
                  "chain_id": chain_id, "task_ids": [t1, t2]}},
    )

    # Claude refine
    refined_raw = await _claude_refine(draft_raw, lead) or draft_raw
    refined_json = _extract_json_block(refined_raw) or draft_json
    await db.auto_built_sites.update_one(
        {"site_id": site_id},
        {"$set": {"claude_refined": refined_raw[:6000],
                  "status": "refined", "updated_at": _now()}},
    )

    # Render — merge style_hint with extracted design tokens (design tokens win)
    final_style = dict(style_hint or {})
    if design_tokens and design_tokens.get("ok"):
        c = design_tokens.get("colors") or {}
        f = design_tokens.get("fonts") or {}
        if c.get("bg"):
            final_style["primary_bg"] = c["bg"]
        if c.get("text"):
            final_style["primary_text"] = c["text"]
            final_style["heading_color"] = c["text"]
        # Use original primary as accent for CTA buttons (high visibility)
        if c.get("primary"):
            final_style["accent"] = c["primary"]
        if f.get("heading"):
            final_style["heading_font"] = f["heading"]
        if f.get("body"):
            final_style["body_font"] = f["body"]

    # iter 282ae — webclaw brand overlay. Fills in anything design_tokens missed
    # so even leads without structured design tokens get their real accent + font
    # on the generated site. webclaw is only called when WEBCLAW_API_KEY is set
    # (otherwise scan_website falls back to the legacy httpx path which has no
    # brand data and this block is a no-op).
    try:
        from services.webclaw_client import is_configured as _wc_on
        if _wc_on():
            url_for_brand = (repair_context.get("original_url") if repair_context else None) \
                             or lead.get("website_url")
            if url_for_brand:
                from services.website_scraper import scan_website as _scan
                from services.brand_injection import brand_style_overrides
                scan_res = await _scan(url_for_brand)
                overrides = brand_style_overrides(scan_res)
                for k in ("accent", "body_font"):
                    if overrides.get(k) and not final_style.get(k):
                        final_style[k] = overrides[k]
                if overrides.get("_logo_url") and not lead.get("logo_url"):
                    lead["logo_url"] = overrides["_logo_url"]
    except Exception as _e:
        logger.debug(f"[awb] webclaw brand overlay skipped: {_e}")

    html = _render_html(refined_json or draft_json, lead, style=final_style)
    from services.cloudflare_dns import safe_slug
    slug_base = safe_slug(lead.get("business_name") or lead_id)
    slug = f"{slug_base}-{site_id[:6]}"
    # Public-facing URL the customer can actually open. iter 280.9 fix:
    # previously this stored the admin endpoint path
    # (`/api/admin/platform/website-builder/preview/{site_id}`) which
    # required super_admin auth and rendered "Link Expired" when emailed
    # to customers. Use the public `/api/sites/{slug}` route which has no
    # auth and is what the welcome/upsell emails should link to.
    # iter 282 fix: prefer PUBLIC_APP_URL when AUREM_PUBLIC_URL not set so
    # preview-env builds don't email aurem.live URLs that 404.
    _public_base = (
        os.environ.get("AUREM_PUBLIC_URL")
        or os.environ.get("PUBLIC_APP_URL")
        or "https://aurem.live"
    ).rstrip("/")
    preview_url = f"{_public_base}/api/sites/{slug}"
    public_path = f"/api/sites/{slug}"

    # iter 282al-36 — post-process: inject theme CSS vars from style_hint so
    # accent/bg/font actually land in the final rendered HTML. LLM prompts
    # alone don't honour hex codes reliably, so we overlay a deterministic
    # CSS block. Safe no-op if style_hint is empty.
    try:
        from services.awb_theme_catalog import inject_theme_css
        html = inject_theme_css(html, style_hint)
    except Exception as _inj_e:
        logger.debug(f"[awb] theme CSS injection skipped: {_inj_e}")
    # iter 305g — inject gold-particles hero canvas on EVERY generated site.
    # Idempotent (sentinel-gated) and never mutates existing content.
    try:
        from services.awb_particles_injector import inject_particles
        html = inject_particles(html)
    except Exception as _p_inj_e:
        logger.debug(f"[awb] particles injection skipped: {_p_inj_e}")
    # iter 282b: Partial unique index `unique_lead_active_site` on
    # auto_built_sites(lead_id, status) for status in {rendered, published,
    # deployed}. If a previous active site exists for this lead (which
    # *should* have been excluded by _select_no_website_leads but in case
    # the code-level filter regresses or this was called directly), the
    # status flip below will raise DuplicateKeyError. Catch it, mark this
    # build as a no-op, and bail — preventing duplicate-site spam.
    from pymongo.errors import DuplicateKeyError
    try:
        await db.auto_built_sites.update_one(
            {"site_id": site_id},
            {"$set": {"rendered_html": html, "status": "rendered",
                      "slug": slug, "preview_url": preview_url,
                      "public_url": public_path,
                      "updated_at": _now()}},
        )
    except DuplicateKeyError as dup_err:
        logger.warning(
            f"[awb] DUPLICATE blocked by unique_lead_active_site for "
            f"lead={lead_id}: {dup_err}"
        )
        # Flip our half-built doc to a terminal non-active status so it
        # doesn't pollute reporting and so the index never re-fires.
        await db.auto_built_sites.update_one(
            {"site_id": site_id},
            {"$set": {"status": "skipped_duplicate",
                      "skipped_reason": "active site already exists for lead",
                      "updated_at": _now()}},
        )
        existing = await db.auto_built_sites.find_one(
            {"lead_id": lead_id,
             "status": {"$in": ["rendered", "published", "deployed"]}},
            {"_id": 0, "site_id": 1, "slug": 1, "preview_url": 1},
        ) or {}
        return {
            "ok": False,
            "site_id": site_id,
            "status": "skipped_duplicate",
            "reason": "active site already exists",
            "existing_site_id": existing.get("site_id"),
            "existing_slug": existing.get("slug"),
            "existing_preview_url": existing.get("preview_url"),
        }

    # Publish: upload to R2 + create {slug}.aurem.live CNAME (when configured).
    # Path URL `/api/sites/{slug}` is always live as a fallback.
    publish_info = await _publish_pipeline(db, site_id, slug, html)

    # Mark final status
    final_status = "deployed" if publish_info.get("ok") else "published"
    await db.auto_built_sites.update_one(
        {"site_id": site_id},
        {"$set": {"status": final_status, "updated_at": _now()}},
    )

    # iter 282: stamp the lead so autopilot won't re-pick it on next cycle.
    # Only set when we actually rendered something useful (skip on style_hint
    # re-renders so the original mark stays intact).
    if not style_hint:
        try:
            await db.campaign_leads.update_one(
                {"lead_id": lead_id},
                {"$set": {
                    "awb_built_at": _now(),
                    "awb_site_id": site_id,
                    "awb_slug": slug,
                }},
            )
        except Exception as _e:
            logger.debug(f"[awb] lead awb_built_at stamp failed: {_e}")

    # Mark A2A tasks complete
    try:
        await tq.complete(t1, {"site_id": site_id, "status": "rendered"})
        await tq.complete(t2, {"site_id": site_id, "preview_url": preview_url})
    except Exception:
        pass

    # iter 282e — auto-screenshot the fresh site (same-host = auto-approved,
    # no admin gate needed). Runs in background so AWB response latency is
    # unaffected. Screenshot URL is then attached to the site doc and
    # included in any subsequent outreach emails.
    if not style_hint:
        async def _shoot_and_save():
            try:
                from services.browser_agent_service import screenshot_url
                shot = await screenshot_url(
                    preview_url,
                    full_page=True,
                    wait_ms=2000,
                    requires_approval=False,   # same-host
                    slug_hint=slug,
                    reason=f"AWB auto-screenshot for {slug}",
                    triggered_by=f"awb:build_site_for_lead:{site_id}",
                )
                if shot.get("ok") and shot.get("image_url"):
                    await db.auto_built_sites.update_one(
                        {"site_id": site_id},
                        {"$set": {
                            "screenshot_url": shot["image_url"],
                            "screenshot_captured_at": _now(),
                        }},
                    )
                    logger.info(
                        f"[awb] screenshot captured for {slug} -> {shot['image_url']}"
                    )
            except Exception as e:
                logger.debug(f"[awb] screenshot task failed (non-fatal): {e}")
        try:
            import asyncio as _asyncio
            _asyncio.create_task(_shoot_and_save())
        except Exception:
            pass

    # ORA log
    try:
        from services.ora_learning import ora
        aid = await ora.log_action(
            agent="architect", action="auto_build_site",
            input_data={"lead_id": lead_id, "niche": lead.get("niche")},
            output_data={"site_id": site_id, "status": "rendered"},
            cost_usd=0.02, chain_id=chain_id, task_id=t1,
        )
        await ora.update_outcome(aid, "success")
    except Exception:
        pass

    return {
        "ok": True, "site_id": site_id,
        "status": final_status,
        "preview_url": preview_url,
        "public_url": f"/api/sites/{slug}",
        "live_url": publish_info.get("url"),
        "slug": slug,
        "chain_id": chain_id,
        "task_ids": [t1, t2],
        "council_decision_id": decision["decision_id"],
        "publish": publish_info,
        "style_hint_used": bool(style_hint),
        "outreach": await _trigger_lead_outreach(db, site_id, slug, lead) if not style_hint else None,
    }


async def build_batch(db, limit: int = 5) -> Dict[str, Any]:
    leads = await _select_no_website_leads(db, limit=limit)
    built: List[Dict[str, Any]] = []
    skipped: List[Dict[str, Any]] = []
    for ld in leads:
        try:
            r = await build_site_for_lead(db, ld["lead_id"])
            (built if r.get("ok") else skipped).append(r)
        except Exception as e:
            skipped.append({"lead_id": ld.get("lead_id"), "error": str(e)[:200]})
    return {"selected": len(leads), "built": built, "skipped": skipped}


async def list_sites(db, limit: int = 50) -> List[Dict[str, Any]]:
    if db is None:
        return []
    return await db.auto_built_sites.find(
        {}, {"_id": 0, "rendered_html": 0, "gemini_draft": 0, "claude_refined": 0},
    ).sort("created_at", -1).limit(int(limit)).to_list(int(limit))


async def get_site_html(db, site_id: str) -> Optional[str]:
    if db is None:
        return None
    row = await db.auto_built_sites.find_one(
        {"site_id": site_id}, {"_id": 0, "rendered_html": 1},
    )
    return row and row.get("rendered_html")


# ─── helpers ────────────────────────────────────────────────────────────────
def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


async def _trigger_lead_outreach(db, site_id: str, slug: str,
                                 lead: Dict[str, Any]) -> Dict[str, Any]:
    """
    On site build completion, send the customer a preview link via the
    open channels in their `verification.channel_gating`.
    Goes through Council deliberation (action_kind='lead_outreach_preview').
    Returns {sent: [...], skipped: [...]}.
    """
    from services.council import council
    out: Dict[str, Any] = {"sent": [], "skipped": []}
    try:
        # iter 305 — PRE-FLIGHT: never dispatch an outreach link if the
        # site isn't actually renderable. Without this guard customers
        # receive links that resolve to the public 404 page, which has
        # cost us real deals. Refuse to send if rendered_html is empty
        # or status isn't in a live state.
        try:
            preflight = await db.auto_built_sites.find_one(
                {"site_id": site_id},
                projection={"_id": 0, "rendered_html": 1, "status": 1, "slug": 1},
            ) or {}
        except Exception as _pf_e:
            logger.warning(f"[awb] outreach preflight DB error: {_pf_e}")
            preflight = {}
        pf_status = (preflight.get("status") or "").strip()
        pf_html = preflight.get("rendered_html") or ""
        pf_slug = preflight.get("slug") or slug
        if (not pf_html) or pf_status not in ("rendered", "published", "deployed"):
            reason = (
                f"preflight_failed: status={pf_status!r}, "
                f"has_html={bool(pf_html)}, slug_match={pf_slug == slug}"
            )
            logger.warning(
                f"[awb] outreach BLOCKED for site_id={site_id} slug={slug} — {reason}"
            )
            return {"sent": [], "skipped": [{"reason": reason}]}

        gates = (((lead.get("verification") or {}).get("channel_gating")) or {})
        if not any(gates.values()):
            return {"skipped": [{"reason": "no open channels"}]}

        biz = lead.get("business_name") or "Your business"
        preview_url = f"https://aurem.live/preview/{slug}"

        # iter 282al-9 hotfix — only advertise the subdomain URL if the
        # CNAME actually got created (publish_status == "live"). Wildcard
        # `*.aurem.live` DNS is not yet configured in production, so
        # blindly sending `{slug}.aurem.live` to customers produced
        # `DNS_PROBE_FINISHED_NXDOMAIN`. The path-based `/api/sites/{slug}`
        # endpoint is always served by the apex and always reachable.
        path_url = f"https://aurem.live/api/sites/{slug}"
        try:
            site_doc = await db.auto_built_sites.find_one(
                {"site_id": site_id},
                projection={"_id": 0, "live_url": 1, "publish_status": 1},
            )
        except Exception:
            site_doc = None
        if (site_doc and site_doc.get("publish_status") == "live"
                and site_doc.get("live_url")):
            live_url = site_doc["live_url"]
        else:
            live_url = path_url

        decision = await council.deliberate(
            action_kind="lead_outreach_preview",
            payload={
                "lead_id": lead.get("lead_id"), "site_id": site_id,
                "channels": [k for k, v in gates.items() if v],
                "preview_url": preview_url,
            },
            cost_usd=0.001,
        )
        if decision["decision"] == "veto":
            return {"skipped": [{"reason": f"council veto: {decision.get('reason','')[:120]}"}]}

        msg_short = (
            f"Hi — I built a free preview website for {biz}. "
            f"Pick your style here: {preview_url} "
            f"(live now: {live_url}). Powered by AUREM."
        )
        msg_email_html = f"""
        <p>Hi {biz},</p>
        <p>I built you a <strong>free preview website</strong>. It's already live —
        you can also pick a different style or colour theme in 30 seconds.</p>
        <p>👉 <a href="{preview_url}"><strong>Pick your style</strong></a><br>
           👉 Live now: <a href="{live_url}">{live_url}</a></p>
        <p>Reply if you want me to add anything (services, photos, hours).</p>
        <p>— TJ at AUREM</p>
        """.strip()

        # EMAIL via Resend
        if gates.get("email"):
            email_addr = (((lead.get("verification") or {}).get("email") or {}).get("value")) \
                         or lead.get("email")
            if email_addr:
                try:
                    import os
                    import resend
                    resend.api_key = os.environ.get("RESEND_API_KEY", "")
                    if resend.api_key:
                        from_email = os.environ.get("RESEND_FROM_EMAIL", "tj@aurem.live")
                        resp = resend.Emails.send({
                            "from": from_email, "to": email_addr,
                            "subject": f"{biz} — your free site is live",
                            "html": msg_email_html,
                        })
                        out["sent"].append({"channel": "email", "to": email_addr,
                                            "id": (resp or {}).get("id")})
                    else:
                        out["skipped"].append({"channel": "email", "reason": "no RESEND_API_KEY"})
                except Exception as e:
                    out["skipped"].append({"channel": "email", "reason": str(e)[:120]})

        # WHATSAPP via Twilio
        if gates.get("whatsapp"):
            phone_val = (((lead.get("verification") or {}).get("phone") or {}).get("value")) \
                        or lead.get("phone")
            if phone_val:
                try:
                    from shared.providers.twilio import send_whatsapp_message
                    r = await send_whatsapp_message(phone_val, msg_short)
                    out["sent"].append({"channel": "whatsapp", "to": phone_val,
                                        "ok": r.get("ok") if isinstance(r, dict) else True})
                except Exception as e:
                    out["skipped"].append({"channel": "whatsapp", "reason": str(e)[:120]})

        # Persist outreach event
        try:
            await db.outreach_history.insert_one({
                "lead_id": lead.get("lead_id"), "site_id": site_id, "slug": slug,
                "type": "awb_preview", "channels_attempted": list(gates.keys()),
                "result": out, "ts": _now(),
            })
        except Exception:
            pass
        return out
    except Exception as e:
        logger.warning(f"[awb] outreach trigger failed: {e}")
        return {"skipped": [{"reason": str(e)[:120]}]}


async def _publish_pipeline(db, site_id: str, slug: str, html: str) -> Dict[str, Any]:
    """
    Best-effort publish: R2 upload + CNAME create.
    Returns {ok, url?, r2?, dns?, error?}. Updates auto_built_sites with publish state.
    Path URL `/api/sites/{slug}` is always live as a fallback.
    """
    out: Dict[str, Any] = {"ok": False, "url": None, "r2": None, "dns": None}

    # 1. R2 upload (if configured)
    try:
        from services.cloudflare_r2 import upload_site_html, is_configured as r2_ok
        if r2_ok():
            r2 = await upload_site_html(slug, html)
            out["r2"] = r2
            if not r2.get("ok"):
                out["error"] = f"r2: {r2.get('error', 'failed')}"
    except Exception as e:
        out["error"] = f"r2_exc: {str(e)[:120]}"
        out["r2"] = {"ok": False, "error": str(e)[:120]}

    # 2. CNAME (always, if CF is wired) — Worker handles host-routing
    try:
        from services.cloudflare_dns import cf_create_cname, is_configured as cf_ok
        if cf_ok():
            dns = await cf_create_cname(slug, proxied=True)
            out["dns"] = dns
            if dns.get("ok"):
                out["url"] = dns.get("url")
                out["ok"] = bool(out["r2"] and out["r2"].get("ok"))
    except Exception as e:
        out["error"] = (out.get("error") or "") + f" dns_exc: {str(e)[:120]}"

    # Persist
    try:
        await db.auto_built_sites.update_one(
            {"site_id": site_id},
            {"$set": {
                "publish_status": "live" if out["ok"] else "partial",
                "live_url": out.get("url"),
                "r2_key": (out.get("r2") or {}).get("key"),
                "r2_etag": (out.get("r2") or {}).get("etag"),
                "cf_record_id": (out.get("dns") or {}).get("record_id"),
                "publish_error": out.get("error", "")[:300] if out.get("error") else None,
                "deployed_at": _now() if out["ok"] else None,
                "updated_at": _now(),
            }},
        )
    except Exception:
        pass

    return out


async def _publish_to_cloudflare(db, site_id: str, slug: str) -> Dict[str, Any]:
    """
    Create a {slug}.aurem.live CNAME → aurem.live (same-origin, proxied).
    Returns {ok, url, record_id, error?}. Updates auto_built_sites with deployed status.
    """
    try:
        from services.cloudflare_dns import cf_create_cname, is_configured
        if not is_configured():
            await db.auto_built_sites.update_one(
                {"site_id": site_id},
                {"$set": {"publish_status": "skipped_unconfigured", "updated_at": _now()}},
            )
            return {"ok": False, "error": "cloudflare not configured"}
        result = await cf_create_cname(slug, proxied=True)
        if result.get("ok"):
            await db.auto_built_sites.update_one(
                {"site_id": site_id},
                {"$set": {
                    "status": "deployed",
                    "live_url": result.get("url"),
                    "cf_record_id": result.get("record_id"),
                    "publish_status": "live",
                    "deployed_at": _now(),
                    "updated_at": _now(),
                }},
            )
        else:
            await db.auto_built_sites.update_one(
                {"site_id": site_id},
                {"$set": {"publish_status": "failed",
                          "publish_error": (result.get("error") or "")[:200],
                          "updated_at": _now()}},
            )
        return result
    except Exception as e:
        logger.warning(f"[awb] publish failed: {e}")
        return {"ok": False, "error": str(e)[:200]}


def ensure_indexes(db):
    try:
        import asyncio as _a
        async def _ix():
            try:
                await db.auto_built_sites.create_index([("site_id", 1)], unique=True, background=True)
                await db.auto_built_sites.create_index([("lead_id", 1), ("created_at", -1)], background=True)
                await db.auto_built_sites.create_index([("status", 1), ("created_at", -1)], background=True)
            except Exception:
                pass
        _a.create_task(_ix())
    except Exception:
        pass
