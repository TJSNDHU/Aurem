"""
test_iter326y_playwright_browser_tool.py — iter 326y regression.
══════════════════════════════════════════════════════════════════════════════
Phase 2, P1 capability jump: ORA-CTO gets real browser control via Playwright.

Founder ask:
  "Aaj ORA sirf static HTML padh sakta hai. Click nahi kar sakta, dynamic
   content nahi dekh sakta. Yeh ORA ka sabse bada capability jump hoga."

THE FIX
───────
1. `services/ora_tools.py` exposes two new wrappers:
     - `browser_get_text(url, selector=None, multiple=False, wait_ms=800)`
     - `browser_screenshot(url, full_page=True, wait_ms=1500)`
   Both delegate to `services/browser_agent_service` (Chromium).
2. Both are TIER_2_APPROVE — external URLs get the 30 s cancel window
   from iter 326w. ORA's tier gate IS the founder approval, so the
   inner approval queue in browser_agent_service is bypassed with
   `requires_approval=False`.
3. Both registered in TOOL_REGISTRY so they appear in the LLM tool list.
4. System prompt lists the new tools in the TIER 2 section.

WHAT THIS TEST LOCKS IN
───────────────────────
  • Both wrappers are exported and registered.
  • Both refuse non-http(s) URLs without launching a browser.
  • Both pass `requires_approval=False` to the inner service so the
    inner queue doesn't double-gate.
  • Both classified as tier2_approve (NOT tier1_auto, NOT tier3).
  • Browser failure surfaces as `{"ok": False, "error": "..."}` — never
    raises.

Run:  cd /app/backend && python3 -m pytest \
        tests/test_iter326y_playwright_browser_tool.py -v
"""
from __future__ import annotations

import pytest


# ─────────────────────────────────────────────────────────────────────────────
# 1) Exports + registry surface
# ─────────────────────────────────────────────────────────────────────────────
def test_browser_tools_exported():
    from services import ora_tools
    for name in ("browser_get_text", "browser_screenshot"):
        assert hasattr(ora_tools, name), f"ora_tools must export {name}"
        assert callable(getattr(ora_tools, name))


def test_browser_tools_registered_in_TOOL_REGISTRY():
    from services.ora_tools import TOOL_REGISTRY
    for name in ("browser_get_text", "browser_screenshot"):
        assert name in TOOL_REGISTRY, f"{name} missing from TOOL_REGISTRY"
        meta = TOOL_REGISTRY[name]
        assert callable(meta["fn"])
        assert "description" in meta and "iter 326y" in meta["description"]


def test_browser_tools_visible_in_list_tools():
    """The LLM-facing catalog must surface the new tools so the model
    actually uses them."""
    from services.ora_tools import list_tools
    names = {t["name"] for t in list_tools()}
    assert "browser_get_text" in names
    assert "browser_screenshot" in names


# ─────────────────────────────────────────────────────────────────────────────
# 2) Tier classification — both must be TIER_2 (30 s cancel window)
# ─────────────────────────────────────────────────────────────────────────────
def test_browser_tools_classified_tier2():
    from services.ora_agent import (
        TIER_1_AUTO, TIER_2_APPROVE, TIER_3_HIGH_RISK, tier_of,
    )
    for name in ("browser_get_text", "browser_screenshot"):
        assert name not in TIER_1_AUTO, (
            f"{name} must NOT be tier1 — external URLs are expensive and need "
            f"founder visibility (30s cancel window)."
        )
        assert name not in TIER_3_HIGH_RISK, (
            f"{name} is not destructive — should be tier2, not tier3."
        )
        assert name in TIER_2_APPROVE
        assert tier_of(name) == "tier2_approve"


# ─────────────────────────────────────────────────────────────────────────────
# 3) URL validation — refuses non-http(s) without launching browser
# ─────────────────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
@pytest.mark.parametrize("bad_url", [
    "", "ftp://example.com", "javascript:alert(1)", "file:///etc/passwd",
    123, None, "example.com",  # no scheme
])
async def test_browser_get_text_refuses_non_http(bad_url):
    from services.ora_tools import browser_get_text
    res = await browser_get_text(bad_url)
    assert res["ok"] is False
    assert "http" in res["error"].lower()


@pytest.mark.asyncio
@pytest.mark.parametrize("bad_url", [
    "", "ftp://example.com", "javascript:alert(1)", "file:///etc/passwd",
    None, "example.com",
])
async def test_browser_screenshot_refuses_non_http(bad_url):
    from services.ora_tools import browser_screenshot
    res = await browser_screenshot(bad_url)
    assert res["ok"] is False
    assert "http" in res["error"].lower()


# ─────────────────────────────────────────────────────────────────────────────
# 4) Delegation — bypasses inner approval queue (ORA tier gate is enough)
# ─────────────────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_browser_get_text_bypasses_inner_approval_queue(monkeypatch):
    """We must pass requires_approval=False so the inner browser_agent
    queue doesn't double-gate ORA's own tier gate."""
    captured: dict = {}

    async def _fake_extract(url, **kw):
        captured.update(kw)
        captured["url"] = url
        return {"ok": True, "data": "stub", "final_url": url,
                "title": "stub", "pending": False}

    import services.browser_agent_service as bas
    monkeypatch.setattr(bas, "extract_url", _fake_extract)

    from services.ora_tools import browser_get_text
    res = await browser_get_text(
        "https://example.com", selector="h1", multiple=False, wait_ms=500,
    )
    assert res["ok"] is True
    assert captured["requires_approval"] is False, (
        "Must bypass inner approval queue — ORA's tier2 gate is the approval."
    )
    assert captured["url"] == "https://example.com"
    assert captured["selector"] == "h1"
    assert captured["multiple"] is False


@pytest.mark.asyncio
async def test_browser_screenshot_bypasses_inner_approval_queue(monkeypatch):
    captured: dict = {}

    async def _fake_shot(url, **kw):
        captured.update(kw)
        captured["url"] = url
        return {"ok": True, "image_url": "https://r2/x.png",
                "title": "stub", "final_url": url, "pending": False,
                "size_bytes": 42}

    import services.browser_agent_service as bas
    monkeypatch.setattr(bas, "screenshot_url", _fake_shot)

    from services.ora_tools import browser_screenshot
    res = await browser_screenshot(
        "https://example.com", full_page=False, wait_ms=2000,
    )
    assert res["ok"] is True
    assert captured["requires_approval"] is False
    assert captured["full_page"] is False
    assert captured["wait_ms"] == 2000


# ─────────────────────────────────────────────────────────────────────────────
# 5) Failure surfacing — must never raise
# ─────────────────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_browser_tools_surface_inner_failure_cleanly(monkeypatch):
    async def _boom(*_a, **_kw):
        raise RuntimeError("chromium boom")

    import services.browser_agent_service as bas
    monkeypatch.setattr(bas, "extract_url", _boom)
    monkeypatch.setattr(bas, "screenshot_url", _boom)

    from services.ora_tools import browser_get_text, browser_screenshot
    # browser_get_text / browser_screenshot delegate without their own
    # try/except — but invoke_tool wraps everything. Direct call may raise,
    # so we route through invoke_tool to mirror the production path.
    from services.ora_tools import invoke_tool
    r1 = await invoke_tool("browser_get_text", {"url": "https://example.com"})
    r2 = await invoke_tool("browser_screenshot", {"url": "https://example.com"})
    for r in (r1, r2):
        assert r["ok"] is False
        assert "chromium" in r["error"].lower() or "RuntimeError" in r["error"]


# ─────────────────────────────────────────────────────────────────────────────
# 6) System prompt mentions the new capability so the LLM uses it
# ─────────────────────────────────────────────────────────────────────────────
def test_system_prompt_advertises_browser_tools():
    from services.ora_agent import SYSTEM_PROMPT
    assert "browser_get_text" in SYSTEM_PROMPT
    assert "browser_screenshot" in SYSTEM_PROMPT
