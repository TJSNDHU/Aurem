"""
Campaign Router Splitter — iter 262 (Big Split).
================================================
Reads the monolithic /app/backend/routers/campaign_router.py and splits
it into 5 focused modules under pillars/sales/routes/:

  _shared.py         — helpers, templates, constants (~240 LOC)
  render_templates.py — /competitor-templates, /seed-aurem, /templates/preview
  lead_crud.py       — /overview, /stats, /leads*, /do-not-contact, /unsubscribe
  blast_service.py   — per-lead dispatch, /test-*, /voice-*, /whatsapp-webhook
  auto_blast.py      — /ops-status, /auto-blast/*, /scrape, /pause, /resume,
                       run_daily_scrape + sister sequence fns (registry hooks)

The original campaign_router.py is reduced to a thin shim that re-exports
the combined router + the 4 sequence fns so registry.py and server.py
imports keep working unchanged.
"""
from __future__ import annotations
from pathlib import Path

SRC = Path("/app/backend/routers/campaign_router.py")
DST = Path("/app/backend/pillars/sales/routes")
lines = SRC.read_text(encoding="utf-8").splitlines(keepends=True)

def slice_ranges(ranges):
    """ranges = [(start,end), …] — both 1-indexed inclusive."""
    out = []
    for s, e in ranges:
        out.extend(lines[s-1:e])
    return "".join(out)

# ── Line-range map (all 1-indexed inclusive, validated against file) ──
SHARED_RANGES = [
    (1, 15),       # docstring + imports
    (20, 52),      # _db, set_db, _get_db, _verify_admin
    (55, 239),     # WHATSAPP_TEMPLATES, EMAIL_SUBJECTS, TARGET_CATEGORIES, COMPETITOR_TEMPLATES
    (461, 469),    # _get_today_schedule
]

RENDER_RANGES = [
    (242, 259),    # /competitor-templates
    (257, 423),    # /seed-aurem (includes header comment + full body)
    (891, 905),    # /leads/{lead_id}/templates/preview
]
# Note: line 257-259 is a comment banner — safe to include twice? No, dedupe.
# Actually 242-254 = /competitor-templates body, 257-259 = banner comment, 260-423 = /seed-aurem.
# Cleaner:
RENDER_RANGES = [
    (242, 254),    # /competitor-templates
    (257, 423),    # banner + /seed-aurem
    (891, 905),    # /leads/{lead_id}/templates/preview
]

LEAD_CRUD_RANGES = [
    (426, 458),    # banner + /overview
    (623, 758),    # /stats, GET /leads, GET /leads/{id}, LeadUpdate, PUT /leads/{id}, POST /leads/add
    (1574, 1651),  # DNCEntry + POST/GET /do-not-contact, GET /unsubscribe
]

BLAST_RANGES = [
    (760, 890),    # /leads/{id}/send-email, /send-whatsapp, /send-sms, /call
    (906, 1098),   # execute_blast_for_lead helper + /leads/{id}/blast-all
    (1306, 1572),  # TestXxxRequest + /test-sms/-email/-whatsapp/-call + /voice-call/{id} + /voice/keypress/{id}
    (1681, 1717),  # /whatsapp-webhook
]

AUTO_BLAST_RANGES = [
    (471, 622),    # /ops-status
    (1099, 1211),  # /auto-blast/status, /toggle, /run-now
    (1212, 1305),  # ScrapeRequest + /scrape
    (1652, 1680),  # /pause, /resume
    (1718, 2069),  # run_daily_scrape, run_website_scans, run_email_sequence, run_whatsapp_sequence, run_sms_sequence, run_voice_sequence
]

# ── Build _shared.py ───────────────────────────────────────────────────
shared_body = slice_ranges(SHARED_RANGES)
shared_out = '''"""Shared helpers, templates, and constants for the Sales/Campaign routes.

Split from the former monolithic routers/campaign_router.py (2,068 LOC) as
part of Pillar 1 (Sales) logic modularization — iter 262.
"""
''' + shared_body

# Replace the original APIRouter line with a no-op (we emit APIRouters per sub-module)
shared_out = shared_out.replace(
    'router = APIRouter(prefix="/api/campaign", tags=["AUREM Campaign"])\n',
    '# Each sub-module owns its own APIRouter; see routes/__init__.py for the combined router.\n',
)
(DST / "_shared.py").write_text(shared_out, encoding="utf-8")
print(f"✓ _shared.py         — {shared_out.count(chr(10))} lines")

# ── Helper to build a sub-module with its own APIRouter ────────────────
HEADER = '''"""{title}

Split from the former monolithic routers/campaign_router.py (2,068 LOC) as
part of Pillar 1 (Sales) logic modularization — iter 262.
"""
import logging
import os
import uuid
import asyncio
from datetime import datetime, timezone, timedelta
from typing import Optional, Any, Dict
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from pillars.sales.routes._shared import (
    _get_db, _verify_admin, _get_today_schedule,
    WHATSAPP_TEMPLATES, EMAIL_SUBJECTS, TARGET_CATEGORIES, COMPETITOR_TEMPLATES,
)

router = APIRouter(prefix="/api/campaign", tags=["AUREM Campaign"])
logger = logging.getLogger(__name__)
'''

def build_submodule(title, ranges, filename):
    body = slice_ranges(ranges)
    content = HEADER.format(title=title) + "\n\n" + body
    (DST / filename).write_text(content, encoding="utf-8")
    print(f"✓ {filename:<22} — {content.count(chr(10))} lines")

build_submodule(
    "Sales/Campaign — Template & Public-Facing Renderers.",
    RENDER_RANGES,
    "render_templates.py",
)
build_submodule(
    "Sales/Campaign — Lead CRUD + DNC + Unsubscribe.",
    LEAD_CRUD_RANGES,
    "lead_crud.py",
)
build_submodule(
    "Sales/Campaign — Per-Lead Blast Dispatch + Test Endpoints.",
    BLAST_RANGES,
    "blast_service.py",
)
build_submodule(
    "Sales/Campaign — Auto-Blast Controls + Sequence Runners.",
    AUTO_BLAST_RANGES,
    "auto_blast.py",
)

# ── __init__.py — combined router so registry.py keeps working ────────
init_out = '''"""Combined Sales/Campaign router (iter 262 Big Split).

The old monolith was 2,068 LOC in a single file. This package splits it
into 4 focused sub-routers while exposing a single combined APIRouter so
that registry.py and the old `from routers.campaign_router import router`
imports continue to work without touching any callers.
"""
from fastapi import APIRouter

from pillars.sales.routes._shared import set_db  # re-exported for server.py
from pillars.sales.routes import lead_crud, render_templates, blast_service, auto_blast

# Combined router — preserves the /api/campaign prefix of the old monolith.
router = APIRouter()
router.include_router(lead_crud.router)
router.include_router(render_templates.router)
router.include_router(blast_service.router)
router.include_router(auto_blast.router)

# Re-export the scheduler sequence fns so registry.py\\'s APScheduler wiring
# keeps working unchanged:  from routers.campaign_router import run_daily_scrape, …
run_daily_scrape = auto_blast.run_daily_scrape
run_website_scans = auto_blast.run_website_scans
run_email_sequence = auto_blast.run_email_sequence
run_whatsapp_sequence = auto_blast.run_whatsapp_sequence
run_sms_sequence = auto_blast.run_sms_sequence
run_voice_sequence = auto_blast.run_voice_sequence

__all__ = [
    "router", "set_db",
    "run_daily_scrape", "run_website_scans",
    "run_email_sequence", "run_whatsapp_sequence",
    "run_sms_sequence", "run_voice_sequence",
]
'''
(DST / "__init__.py").write_text(init_out, encoding="utf-8")
print(f"✓ __init__.py          — {init_out.count(chr(10))} lines")

print("\nDone. Total files written to", DST)
