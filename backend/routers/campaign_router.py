"""
Campaign Router — thin shim (iter 262 Big Split).

The former 2,068 LOC monolith was split into 4 focused sub-modules under
`pillars/sales/routes/`:
  - lead_crud.py       (CRUD / overview / stats / DNC / unsubscribe)
  - blast_service.py   (per-lead dispatch, test endpoints, voice, webhook)
  - auto_blast.py      (auto-blast controls + daily sequence runners)
  - render_templates.py (competitor templates, seed-aurem, template preview)

This file remains for backward compatibility — registry.py, server.py, and
a handful of other services still import from `routers.campaign_router`.
Everything is re-exported from `pillars.sales.routes`.
"""
from pillars.sales.routes import (  # noqa: F401
    router,
    set_db,
    run_daily_scrape,
    run_website_scans,
    run_email_sequence,
    run_whatsapp_sequence,
    run_sms_sequence,
    run_voice_sequence,
)

# External callers of these endpoint fns (website_builder_router,
# ora_command_center, auto_blast_engine). Re-exported so existing imports
# `from routers.campaign_router import blast_all_channels` keep working.
from pillars.sales.routes.blast_service import (  # noqa: F401
    blast_all_channels,
    execute_blast_for_lead,
)

__all__ = [
    "router",
    "set_db",
    "run_daily_scrape",
    "run_website_scans",
    "run_email_sequence",
    "run_whatsapp_sequence",
    "run_sms_sequence",
    "run_voice_sequence",
    "blast_all_channels",
    "execute_blast_for_lead",
]
