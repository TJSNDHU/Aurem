"""
iter 332b D-14 — Chat timeout budget + safe HTML-response handling.

Bug seen in production: OpenRouter free-tier `:free` model variants
queue behind paid traffic and routinely take 90-120 seconds to start
emitting. Cloudflare's edge gives us ~100s upstream timeout; once that
elapses Cloudflare returns an HTML 524 error page. The frontend then
tries JSON.parse() on `<!DOCTYPE html>` and crashes the chat panel
with "Unexpected token '<'".

Fix:
  • Backend caps each model attempt at 28s — ladder of 3 = 84s max,
    safely under Cloudflare's 100s ceiling.
  • Dropped the `:free` suffixes from rungs 2+3 — paid variants are
    pennies per million tokens and don't queue.
  • Frontend safely parses non-JSON responses and shows a friendly
    message ("The free-tier model took too long…") instead of
    surfacing the raw JSON.parse exception.
"""
from __future__ import annotations


def test_openrouter_timeout_under_cloudflare_ceiling():
    """3 × per-call timeout must stay strictly under 100s so Cloudflare
    never gets to cut us off with an HTML 524."""
    from services.dev_cto_chat import _OPENROUTER_TIMEOUT_S, FREE_TIER_MODELS
    assert _OPENROUTER_TIMEOUT_S <= 30, (
        f"Per-call timeout {_OPENROUTER_TIMEOUT_S}s is too generous — "
        "ladder will exceed Cloudflare's 100s budget."
    )
    worst_case = _OPENROUTER_TIMEOUT_S * len(FREE_TIER_MODELS)
    assert worst_case < 100, (
        f"Worst-case ladder traversal {worst_case}s ≥ 100s. "
        "Cloudflare 524 will fire before our last rung returns."
    )


def test_no_free_variants_in_ladder():
    """Free OpenRouter variants queue behind paid traffic and break
    Cloudflare's 100s budget. Test guards against re-introduction."""
    from services.dev_cto_chat import FREE_TIER_MODELS
    for model, _label in FREE_TIER_MODELS:
        assert ":free" not in model, (
            f"Free variant {model!r} queues past Cloudflare timeout."
        )


def test_frontend_safely_parses_html_response():
    """DevCtoChatPanel.jsx must wrap the JSON.parse in try/catch so
    Cloudflare HTML pages produce a friendly error, not a raw
    `Unexpected token <` crash."""
    src = open(
        "/app/frontend/src/platform/developers/DevCtoChatPanel.jsx"
    ).read()
    # Safe parse wrapper
    assert "JSON.parse(raw)" in src, (
        "Frontend still uses `await r.json()` blindly. Must wrap in "
        "try/catch so HTML 524 doesn't crash the panel."
    )
    # Friendly copy for 524
    assert "free-tier model took too long" in src.lower(), (
        "Friendly error message for Cloudflare 524 missing."
    )
    # History budget — iter 332b D-19 bumped to 12 turns / 3000 chars to
    # carry more context across persistent sessions. Still well under the
    # 28s per-model Cloudflare ceiling because OpenRouter streams.
    assert "slice(-12)" in src, "History should cap at 12 turns."
    assert ".slice(0, 3000)" in src, (
        "Each message should be clipped to 3000 chars to keep payloads sane."
    )
