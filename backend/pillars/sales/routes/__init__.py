"""Combined Sales/Campaign router (iter 262 Big Split).

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

# Re-export the scheduler sequence fns so registry.py\'s APScheduler wiring
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
