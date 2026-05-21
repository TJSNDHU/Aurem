"""seo_static_router.py — iter 325t

Tiny router that serves the SEO / crawler-discovery files every modern
search bot + LLM crawler probes:

  GET /sitemap.xml      — main sitemap (canonical pages)
  GET /robots.txt       — crawler policy
  GET /llms.txt         — concise LLM-crawler index (Anthropic spec)
  GET /llms-full.txt    — full LLM-crawler context (Anthropic spec)

Production log-noise reason for adding these: aurem.live was returning
404 for all four endpoints on every crawl, which both hurts SEO ranking
and pollutes the runtime log feed (drowns out real errors). Each file
is generated dynamically so it always reflects current pages — no build
step required, no static asset to forget to bundle.
"""
from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import PlainTextResponse, Response

router = APIRouter()


# ─────────────────────────────────────────────────────────────────
# Canonical paths
# ─────────────────────────────────────────────────────────────────

_HOST = "https://aurem.live"

_PAGES = [
    "/",
    "/my",
    "/pricing",
    "/free-seo-audit",
    "/login",
    "/signup",
    "/ora",
]


@router.get("/sitemap.xml", include_in_schema=False)
async def sitemap_xml():
    urls = "\n".join(
        f"  <url><loc>{_HOST}{p}</loc><changefreq>daily</changefreq></url>"
        for p in _PAGES
    )
    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        f"{urls}\n"
        '</urlset>\n'
    )
    return Response(content=xml, media_type="application/xml")


@router.get("/robots.txt", include_in_schema=False)
async def robots_txt():
    body = (
        "User-agent: *\n"
        "Allow: /\n"
        "Disallow: /api/\n"
        "Disallow: /admin/\n"
        f"Sitemap: {_HOST}/sitemap.xml\n"
    )
    return PlainTextResponse(body)


# ─────────────────────────────────────────────────────────────────
# llms.txt — Anthropic / OpenAI crawler discovery spec
# https://llmstxt.org/
# ─────────────────────────────────────────────────────────────────

_LLMS_TXT = """\
# AUREM

AUREM is an autonomous orchestration platform: outbound sales,
website auto-repair, real-time customer dashboards, and a multi-agent
ORA CTO that handles its own bug fixes.

## Public surfaces
- [Homepage](https://aurem.live/) — product overview + pricing
- [Free SEO Audit](https://aurem.live/free-seo-audit) — instant site scan
- [Customer Portal](https://aurem.live/my) — auth-gated dashboard
- [ORA Voice PWA](https://aurem.live/ora) — voice chat with ORA

## API
- Public chat: POST /api/public/ora/chat — accepts {text|message, session_id}
- Catalog: GET /api/catalog/services
- Health: GET /api/ora/health
"""


@router.get("/llms.txt", include_in_schema=False)
async def llms_txt():
    return PlainTextResponse(_LLMS_TXT)


_LLMS_FULL_TXT = _LLMS_TXT + """

## Architecture
- Backend: FastAPI + Motor (async MongoDB) + APScheduler
- Frontend: React 19 + Tailwind + lucide icons + sonner toasts
- LLM Gateway: DeepSeek V3.1 (OpenRouter) for logic, Claude Sonnet
  (Emergent Universal Key) for sensitive auth/billing operations
- Voice: Retell AI for outbound calls
- Payments: Stripe
- Email: Resend

## Autonomous Repair Stack
Scanners (qa_guardian, shannon_security, react_doctor) write to
incident_bus → triage_brain classifies → ora_cto_repair_agent uses
DeepSeek to generate code patches → Tier-1 fixes auto-apply, Tier-2
fixes require Telegram founder approval.

## Customer Dashboard V2
6 merged pages: Home / Live Health / CRM / Campaign / ORA / Profile /
Settings. Edge-to-edge responsive (desktop 1024+ / tablet 768-1023 /
mobile <768 with bottom tab bar). Auto dark/light theme that follows
the OS preference + manual override. All save/edit buttons trigger
real PATCH/POST/DELETE — no mocks.
"""


@router.get("/llms-full.txt", include_in_schema=False)
async def llms_full_txt():
    return PlainTextResponse(_LLMS_FULL_TXT)
