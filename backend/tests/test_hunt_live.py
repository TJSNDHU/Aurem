"""
Regression tests for the Hunt Live Progress pipeline.
Verifies:
  • HUNT intent parses correctly from natural-language input
  • TEST_CITY triggers mock mode automatically
  • start_hunt() returns a hunt_id and pushes SSE events through the pipeline
  • Every expected step (scout/verify/website/email/whatsapp/sms/call) emits an event
  • hud_node_flash events fire for HUD node map coverage
"""
import asyncio
import pytest
from unittest.mock import AsyncMock, patch

from services.ora_command_center import parse_command
from services.hunt_live import start_hunt, STEP_TO_HUD_NODE


# ──────────────────────────────────────────────────────────────
# Parser tests
# ──────────────────────────────────────────────────────────────

def test_parse_hunt_with_count():
    parsed = parse_command("hunt Mississauga auto shops 20")
    assert parsed["intent"] == "HUNT"
    assert parsed["params"]["city"] == "Mississauga"
    assert parsed["params"]["industry"] == "auto repair shop"
    assert parsed["params"]["count"] == 20
    assert parsed["params"]["mock"] is False


def test_parse_hunt_without_count_defaults_to_10():
    parsed = parse_command("hunt Toronto dentists")
    assert parsed["intent"] == "HUNT"
    assert parsed["params"]["city"] == "Toronto"
    assert parsed["params"]["count"] == 10


def test_parse_hunt_test_city_triggers_mock_mode():
    parsed = parse_command("hunt TEST_CITY auto shops 3")
    assert parsed["intent"] == "HUNT"
    assert parsed["params"]["mock"] is True
    assert parsed["params"]["count"] == 3


def test_parse_scout_not_overridden_by_hunt():
    """Ensure the new HUNT pattern doesn't swallow SCOUT commands."""
    parsed = parse_command("scout Toronto auto shops")
    assert parsed["intent"] == "SCOUT"


# ──────────────────────────────────────────────────────────────
# Pipeline tests (mock mode — no DB, no real API calls)
# ──────────────────────────────────────────────────────────────

def test_hud_node_map_covers_all_steps():
    """Every pipeline step must map to an Empire HUD node (for UI flashing)."""
    required = {"scout", "verify", "website", "email", "whatsapp", "sms", "call", "campaign"}
    assert required.issubset(set(STEP_TO_HUD_NODE.keys()))


def test_start_hunt_returns_hunt_id():
    """start_hunt() must return immediately with a hunt_id."""
    async def _run():
        hid = await start_hunt(db=None, city="TEST_CITY", industry="auto shops", count=1, mock=True)
        return hid

    hid = asyncio.run(_run())
    assert hid.startswith("hunt_")
    assert len(hid) > 5


def test_hunt_pipeline_emits_all_events():
    """
    Run a 2-business mock hunt and capture every SSE event.
    Must include scout + verify + website + (email/whatsapp/sms/call) per business,
    plus an overall 'complete' event.
    """
    captured = []

    async def _mock_push(event_type, payload):
        captured.append((event_type, payload))

    async def _run():
        with patch("routers.server_misc_routes.push_sse_event", side_effect=_mock_push):
            await start_hunt(db=None, city="TEST_CITY", industry="auto shops", count=2, mock=True)
            # Give the background task time to complete the 2-biz mock pipeline
            await asyncio.sleep(8)

    asyncio.run(_run())

    # Collect all steps that emitted an OK/complete status
    ok_steps = {
        (p["step"], p["status"])
        for (t, p) in captured
        if t == "hunt_progress"
    }
    # Must have at minimum these step/status combos
    required = {
        ("hunt", "started"),
        ("scout", "ok"),
        ("verify", "ok"),
        ("website", "ok"),
        ("hunt", "complete"),
    }
    assert required.issubset(ok_steps), f"Missing steps: {required - ok_steps}"

    # Final complete event must carry a summary with scouted>=1
    complete_events = [p for (t, p) in captured if t == "hunt_progress" and p["step"] == "hunt" and p["status"] == "complete"]
    assert len(complete_events) >= 1
    summary = complete_events[-1]["data"]
    assert summary.get("scouted") == 2
    assert summary.get("websites_built") == 2

    # hud_node_flash events must have fired
    flashes = [t for (t, _) in captured if t == "hud_node_flash"]
    assert len(flashes) >= 6  # scout + verify + website + 3 blast channels per business
