"""
gate_test_router.py — End-to-end test endpoints proving the service_gate
stack works (plan check → quota check → success usage log → admin ORA telemetry).

Used by E2E tests + admin smoke verification. Founder lifetime_free hits
should always return 200; trial accounts hit 402 for non-trial services.
"""
from __future__ import annotations

import logging
from fastapi import APIRouter, HTTPException, Request

from middleware.bin_context import get_bin_ctx
from utils.service_gate import require_service

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/api/gate-test/me")
async def gate_test_me(request: Request):
    """Returns the resolved BinCtx for the current caller. No service gate
    — useful for verifying middleware decoded the JWT correctly."""
    ctx = get_bin_ctx(request, required=True)
    return {
        "ok": True,
        "user_id": ctx.user_id,
        "email": ctx.email,
        "business_id": ctx.business_id,
        "plan": ctx.plan,
        "services_unlocked": ctx.services_unlocked,
        "is_admin": ctx.is_admin,
    }


@router.post("/api/gate-test/probe/voice")
@require_service("voice_agent_ai", quota_kind="voice_limit")
async def probe_voice(request: Request):
    """Should: 200 if voice_agent_ai unlocked, 402 if not, 429 if over quota."""
    ctx = get_bin_ctx(request, required=True)
    return {"ok": True, "service": "voice_agent_ai", "business_id": ctx.business_id}


@router.post("/api/gate-test/probe/email")
@require_service("email_campaigns", quota_kind="email_limit")
async def probe_email(request: Request):
    ctx = get_bin_ctx(request, required=True)
    return {"ok": True, "service": "email_campaigns", "business_id": ctx.business_id}


@router.post("/api/gate-test/probe/crm")
@require_service("crm_starter", quota_kind="leads_limit")
async def probe_crm(request: Request):
    ctx = get_bin_ctx(request, required=True)
    return {"ok": True, "service": "crm_starter", "business_id": ctx.business_id}
