"""
AUREM Outreach Templates
========================
Central rendering for all 4 outreach channels (WhatsApp, SMS, Email, Voice).
Variables auto-fill from `campaign_leads` documents.

Tagline: "World's First AI Business Intelligence from AUREM"
Used across every template for consistent brand recall.
"""
from __future__ import annotations

import re
from typing import Any, Dict


TAGLINE_WA = "_World's First AI Business Intelligence_ from *AUREM*"
TAGLINE_PLAIN = "World's First AI Business Intelligence from AUREM"


# ─────────────────────── VARIABLE EXTRACTION ───────────────────────
# Approximate monthly search volume by (city, category) — conservative estimates.
_CITY_CATEGORY_SEARCHES = {
    ("brampton", "auto"): 8500,
    ("brampton", "hair"): 6200,
    ("brampton", "restaurant"): 14000,
    ("mississauga", "auto"): 12000,
    ("mississauga", "hair"): 9800,
    ("toronto", "auto"): 34000,
    ("toronto", "hair"): 28000,
    ("toronto", "restaurant"): 65000,
    ("oakville", "auto"): 4200,
    ("markham", "auto"): 6800,
}


def _slugify(text: str) -> str:
    text = (text or "").lower().strip()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-")[:60] or "business"


def _extract_city(location: str) -> str:
    if not location:
        return "your area"
    # "41 Geranium Cres, Brampton, ON L6Y 1N8" → Brampton (never the
    # province code). iter 315j: skip 2-letter tokens and ZIP/postal codes.
    parts = [p.strip() for p in location.split(",") if p.strip()]
    if not parts:
        return "your area"
    _prov_re = re.compile(
        r"^(on|bc|ab|qc|nb|nl|pe|ns|mb|sk|yt|nt|nu"
        r"|al|ak|az|ar|ca|co|ct|de|fl|ga|hi|id|il|in|ia|ks|ky|la|me|md"
        r"|ma|mi|mn|ms|mo|mt|ne|nv|nh|nj|nm|ny|nc|nd|oh|ok|or|pa|ri|sc"
        r"|sd|tn|tx|ut|vt|va|wa|wv|wi|wy)$", re.IGNORECASE)
    _zip_re = re.compile(r"\b\d{5}\b|\b[A-Z]\d[A-Z]\s*\d[A-Z]\d\b",
                            re.IGNORECASE)

    def _is_province_or_zip(tok: str) -> bool:
        base = tok.split()[0] if tok else ""
        return bool(_prov_re.match(base) or _zip_re.search(tok))

    for p in parts:
        if len(p) > 30:
            continue
        if _is_province_or_zip(p):
            continue
        if len(p.strip()) < 2:
            continue
        # Skip tokens that are pure numbers (street numbers)
        if re.match(r"^\d+[a-z]?$", p, re.IGNORECASE):
            continue
        # Skip street segments (start with number, e.g. "41 Geranium Cres")
        if re.match(r"^\d+\s+", p):
            continue
        return p.title()
    return parts[0].title()


def _extract_review_count(lead: Dict[str, Any]) -> int:
    """Pull review count from lead.reviews_count if present, else parse notes."""
    if isinstance(lead.get("reviews_count"), int):
        return lead["reviews_count"]
    notes = str(lead.get("notes", ""))
    m = re.search(r"(\d+)\s+(?:google\s+)?reviews?", notes, re.I)
    if m:
        return int(m.group(1))
    return 3  # conservative default for unreviewed businesses


def _extract_rating(lead: Dict[str, Any]) -> str:
    if isinstance(lead.get("rating"), (int, float)):
        return f"{lead['rating']:.1f}"
    m = re.search(r"(\d\.\d)\s*star", str(lead.get("notes", "")), re.I)
    if m:
        return m.group(1)
    return "4.5"


def _category_keyword(category: str) -> str:
    """Normalize a Google category to a keyword for search-volume lookup."""
    c = (category or "").lower()
    if "auto" in c or "mechanic" in c or "body shop" in c:
        return "auto"
    if "hair" in c or "salon" in c or "beauty" in c:
        return "hair"
    if "restaurant" in c or "food" in c or "cafe" in c:
        return "restaurant"
    return "auto"  # safe default


def _estimate_searches(city: str, category: str) -> int:
    key = (city.lower().strip(), _category_keyword(category))
    return _CITY_CATEGORY_SEARCHES.get(key, 5000)


def _business_type_singular(category: str) -> str:
    c = (category or "local business").lower()
    c = c.replace("auto body shop", "auto shop")
    c = c.replace("hair salon", "salon")
    c = c.replace("restaurant", "restaurant")
    # Drop brand words
    return c.split(",")[0].strip() or "local business"


def _opportunities(lead: Dict[str, Any]) -> int:
    """Count real growth gaps visible from the scout data."""
    count = 0
    if not lead.get("website_url"):
        count += 1  # no website
    if _extract_review_count(lead) < 25:
        count += 1  # low reviews
    if not (lead.get("social_media") or {}).get("instagram"):
        count += 1  # no social
    count += 2  # always: no automated follow-up + no CRM tracking
    return max(3, min(count, 7))


def build_variables(lead: Dict[str, Any]) -> Dict[str, Any]:
    """Extract the full variable set for any template, from a lead document."""
    name = lead.get("business_name", "there")
    category = lead.get("category", "local business")
    # iter 324q — Prefer the explicit `city` field (OSM admin-hunt sets it
    # directly: "Brampton", "Toronto, ON" etc). Fall back to legacy
    # `location` (Google Places set this) only when city is missing.
    raw_city = (lead.get("city") or "").strip()
    if raw_city:
        city = _extract_city(raw_city) if "," in raw_city else raw_city
    else:
        city = _extract_city(lead.get("location", "") or "")
    review_count = _extract_review_count(lead)
    return {
        "business_name": name,
        "business_slug": lead.get("lead_id") or _slugify(name),
        "business_type": _business_type_singular(category),
        "category": category,
        "city": city,
        "review_count": review_count,
        "monthly_searches": _estimate_searches(city, category),
        "opportunities_count": _opportunities(lead),
        "rating": _extract_rating(lead),
    }


# ─────────────────────── TEMPLATE 1: WHATSAPP ───────────────────────
# iter 315j — Twilio carrier-compliance rewrite.
# Removed: "FREE", "7-day trial", "No credit card. No risk", "💥🎉🚀",
# exclamation stacks ("!"), promotional checkmark ladders. Kept concrete,
# useful, minimally emoji. Tone = specific consultant, not pitch.
def render_whatsapp(lead: Dict[str, Any]) -> str:
    v = build_variables(lead)
    return (
        f"Hi {v['business_name']}, I'm ORA from AUREM.\n\n"
        f"I analyzed your Google presence and found "
        f"{v['opportunities_count']} gaps costing you customers monthly:\n\n"
        f"• Only {v['review_count']} reviews — most {v['business_type']}s "
        f"your size have 50 or more\n"
        f"• {v['monthly_searches']}+ monthly searches in {v['city']} "
        f"that aren't reaching you\n\n"
        f"Your full analysis:\n"
        f"aurem.live/report/{v['business_slug']}\n\n"
        f"Reply YES to see the full report. Reply STOP to opt out."
    )


# ─────────────────────── TEMPLATE 2: SMS ───────────────────────
def render_sms(lead: Dict[str, Any]) -> str:
    v = build_variables(lead)
    return (
        f"Hi {v['business_name']}, I'm ORA from AUREM.\n\n"
        f"I analyzed your Google presence and found "
        f"{v['opportunities_count']} gaps costing you customers monthly.\n\n"
        f"Your report: aurem.live/report/{v['business_slug']}\n\n"
        f"Reply YES to see the full analysis. Reply STOP to opt out."
    )


# ─────────────────────── TEMPLATE 3: EMAIL ───────────────────────
# iter 324q — Subject-line redesign + A/B variants.
#
# Why: the previous subject template
#   "{BusinessName} — N gaps found in your Google presence"
# was specific but stiff. Every lead got the same shape, no A/B
# data ever collected, no curiosity gap. Industry data on cold-
# email subject lines: open rate is dominated by (a) recipient
# name in subject, (b) one specific number, (c) open loop.
#
# Two new variants follow that template. They're paired deliberately
# so we A/B-test two _different psychological hooks_ (forensic
# finding vs loss frame), not two paraphrases of the same hook.
#
# Variant A — "Forensic finding" (matches user spec example):
#     "Found {N} gaps hurting {BusinessName}'s Google ranking"
#   Open-loop ("what gaps?") + names target + specific number.
#
# Variant B — "Loss frame, location-specific":
#     "{BusinessName} — {K}+ {City} searches missing you"
#   Loss aversion + concrete number + city = local relevance.
#
# Both stay under ~70 chars (Gmail truncation). Business names
# longer than 30 chars are abbreviated to preserve the hook.
#
# Bucketing: deterministic by `lead_id` so the SAME lead always
# receives the SAME variant on repeat sends (clean A/B data).


def _short_business_name(name: str, max_len: int = 28) -> str:
    """Truncate long business names mid-subject so the hook still fits."""
    n = (name or "").strip()
    if len(n) <= max_len:
        return n
    # Drop common suffixes that pad length without identity loss.
    for suffix in (
        " inc.", " inc", " ltd.", " ltd", " llc", " corp.", " corp",
        " co.", " company", " group", " services", " service",
    ):
        if n.lower().endswith(suffix):
            n = n[: -len(suffix)].rstrip(",. ")
            if len(n) <= max_len:
                return n
    return n[: max_len - 1].rstrip() + "…"


def _format_search_volume(n: int) -> str:
    """8500 → '8.5K', 34000 → '34K', 500 → '500'."""
    if n >= 10000:
        return f"{n // 1000}K"
    if n >= 1000:
        return f"{n / 1000:.1f}".rstrip("0").rstrip(".") + "K"
    return str(n)


def pick_subject_variant(lead_id: str) -> str:
    """Deterministic A/B bucketing by lead_id. Returns 'A' or 'B'.

    Uses md5 over the full lead_id (not a sliced prefix) so uuid-style
    ids with a fixed common prefix still split ~50/50.
    """
    if not lead_id:
        return "A"
    import hashlib
    h = hashlib.md5(str(lead_id).encode("utf-8")).digest()
    return "A" if (h[0] & 1) == 0 else "B"


def render_email_subject_variant_a(lead: Dict[str, Any]) -> str:
    """Forensic finding hook.
    "Found 3 gaps hurting AtlasCare's Google ranking"
    """
    v = build_variables(lead)
    name = _short_business_name(v["business_name"])
    return f"Found {v['opportunities_count']} gaps hurting {name}'s Google ranking"


def render_email_subject_variant_b(lead: Dict[str, Any]) -> str:
    """Loss-framed, location-specific hook.
    "AtlasCare — 8.5K+ Brampton searches missing you"
    """
    v = build_variables(lead)
    name = _short_business_name(v["business_name"], max_len=24)
    return (
        f"{name} — {_format_search_volume(v['monthly_searches'])}+ "
        f"{v['city']} searches missing you"
    )


def render_email_subject(lead: Dict[str, Any], variant: str | None = None) -> str:
    """Render the email subject for a lead.

    `variant` accepts 'A', 'B', or None. When None, falls back to the
    deterministic bucket from `pick_subject_variant(lead_id)` so the
    same lead always sees the same variant on repeat sends.
    """
    if not variant:
        variant = pick_subject_variant(lead.get("lead_id", ""))
    if variant.upper() == "B":
        return render_email_subject_variant_b(lead)
    return render_email_subject_variant_a(lead)


def render_email_html(lead: Dict[str, Any]) -> str:
    v = build_variables(lead)
    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>AUREM — Growth Report for {v['business_name']}</title></head>
<body style="margin:0;padding:0;background:#f4f4f4;font-family:-apple-system,Segoe UI,Roboto,Arial,sans-serif;">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="padding:32px 0;background:#f4f4f4;">
  <tr><td align="center">
    <table role="presentation" width="640" cellpadding="0" cellspacing="0" style="background:#ffffff;border-radius:12px;overflow:hidden;box-shadow:0 4px 20px rgba(0,0,0,0.08);">

      <!-- Header -->
      <tr><td style="background:#000000;padding:36px 40px 28px;text-align:left;">
        <div style="font-family:'Cinzel',Georgia,serif;font-size:32px;font-weight:700;letter-spacing:4px;color:#C9A227;">AUREM</div>
        <div style="margin-top:6px;font-size:12px;letter-spacing:3px;text-transform:uppercase;color:#C9A227;font-weight:600;">AI Business Intelligence</div>
      </td></tr>

      <!-- Body -->
      <tr><td style="padding:36px 40px 8px;color:#111827;">
        <h1 style="margin:0 0 14px;font-size:22px;line-height:1.3;color:#0b0b0f;">Hi {v['business_name']},</h1>
        <p style="margin:0 0 16px;font-size:15px;line-height:1.65;color:#374151;">
          I'm <strong>ORA</strong> from <strong>AUREM</strong>.
        </p>
        <p style="margin:0 0 24px;font-size:15px;line-height:1.65;color:#374151;">
          I analyzed your Google presence and found <strong style="color:#C9A227;">{v['opportunities_count']} gaps</strong> costing you customers monthly.
        </p>
      </td></tr>

      <!-- Findings -->
      <tr><td style="padding:0 40px 24px;">
        <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#f9fafb;border-left:4px solid #C9A227;border-radius:8px;">
          <tr><td style="padding:18px 22px;">
            <div style="font-size:11px;letter-spacing:2px;font-weight:700;color:#92400e;text-transform:uppercase;margin-bottom:10px;">What we found</div>
            <ul style="margin:0;padding:0 0 0 18px;color:#1f2937;font-size:14px;line-height:1.7;">
              <li>{v['review_count']} Google reviews (competitors your size typically have 50 or more)</li>
              <li>{v['monthly_searches']}+ monthly searches in {v['city']} that aren't reaching you</li>
              <li>No automated follow-up when customers reach out</li>
            </ul>
          </td></tr>
        </table>
      </td></tr>

      <!-- CTA Button -->
      <tr><td align="center" style="padding:8px 40px 30px;">
        <a href="https://aurem.live/report/{v['business_slug']}"
           style="display:inline-block;background:#C9A227;color:#000000;font-weight:700;font-size:15px;padding:16px 34px;border-radius:10px;text-decoration:none;letter-spacing:1px;box-shadow:0 4px 12px rgba(201,162,39,0.35);">
          See the full analysis
        </a>
        <div style="margin-top:12px;font-size:12px;color:#4b5563;">aurem.live/report/{v['business_slug']}</div>
      </td></tr>

      <tr><td style="padding:0 40px 28px;font-size:14px;line-height:1.65;color:#374151;">
        <p style="margin:0 0 14px;">Reply to this email with YES and I'll walk you through the report personally.</p>
        <p style="margin:0 0 4px;">— ORA</p>
        <p style="margin:0;font-size:12px;color:#4b5563;">AUREM</p>
      </td></tr>

      <!-- Footer -->
      <tr><td style="background:#0b0b0f;padding:18px 40px;text-align:center;font-size:11px;color:#9ca3af;line-height:1.6;">
        AUREM · Toronto, ON · <a href="https://aurem.live" style="color:#C9A227;text-decoration:none;">aurem.live</a>
        &nbsp; · &nbsp;
        <a href="mailto:ora@aurem.live" style="color:#C9A227;text-decoration:none;">ora@aurem.live</a><br>
        <span style="color:#6b7280;">Reply STOP to unsubscribe.</span>
      </td></tr>

    </table>
  </td></tr>
</table>
</body></html>"""


# ─────────────────────── TEMPLATE 4: VOICE SCRIPT ───────────────────────
def render_voice_script(lead: Dict[str, Any]) -> str:
    v = build_variables(lead)
    # iter 315j — carrier-compliance rewrite (no "FREE", no "trial",
    # no stacked exclamations). Natural consultant tone.
    return (
        f"Hello, may I speak with someone at {v['business_name']}? "
        f"Hi, I'm ORA, calling from AUREM. "
        f"I did a quick analysis of {v['business_name']} on Google "
        f"and found {v['opportunities_count']} gaps that are costing you "
        f"customers every month. "
        f"For example, {v['city']} has over {v['monthly_searches']} "
        f"monthly searches for {v['business_type']} services, "
        f"and right now most of them aren't reaching you. "
        f"To see your full analysis, please visit "
        f"aurem dot live slash report slash {v['business_slug']}. "
        f"Or reply YES to this message and I'll walk you through it. "
        f"Thank you, and have a good day."
    )


def render_all(lead: Dict[str, Any]) -> Dict[str, Any]:
    """Returns all 4 rendered templates + the variable set used.

    iter 324q — Email block now exposes both subject variants under
    `email.subject_variants` (A/B map) and pre-picks one based on the
    deterministic `lead_id` bucket in `email.subject_variant`. The
    blast service should log `email.subject_variant` alongside each
    send so we can correlate opens/replies per variant.
    """
    variant = pick_subject_variant(lead.get("lead_id", ""))
    subj_a = render_email_subject_variant_a(lead)
    subj_b = render_email_subject_variant_b(lead)
    return {
        "variables": build_variables(lead),
        "whatsapp": render_whatsapp(lead),
        "sms": render_sms(lead),
        "email": {
            "subject": subj_a if variant == "A" else subj_b,
            "subject_variant": variant,
            "subject_variants": {"A": subj_a, "B": subj_b},
            "html": render_email_html(lead),
        },
        "voice_script": render_voice_script(lead),
    }
