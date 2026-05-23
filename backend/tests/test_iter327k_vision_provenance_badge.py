"""
iter 327k — Vision provenance badge on ORA chat replies.

Founder request (2026-02-23):
  "Yes — add 'saw image via GPT-4o' badge. Helps confirm vision
   actually fired."

When the immediately-preceding user turn carried an image attachment
whose `vision_description` is non-empty (cached at upload time in
ora_attachments_router.attach_file from iter 327j), the assistant
bubble in OraChat.jsx renders a small green pill:
   "🔍 SAW IMAGE VIA GPT-4O"
with data-testid="vision-description-source".

If the user uploaded an image but vision failed → no badge (we don't
lie about firing).
If the user sent a pure text turn → no badge.
"""
from __future__ import annotations
from pathlib import Path

FRONTEND = Path("/app/frontend/src/platform/admin/OraChat.jsx")


def test_badge_component_present_and_testid_correct():
    src = FRONTEND.read_text()
    assert 'data-testid="vision-description-source"' in src
    # Green color family for "this is real, not a guess"
    assert "#7DD3A0" in src
    # Uses lucide Eye icon
    assert "<Eye size={10}" in src
    # Pill copy
    assert "Saw image via GPT-4o" in src


def test_badge_only_fires_when_prev_user_image_has_vision_description():
    """Source-level check that the badge gate is gated on
    prev.role==user AND attachments has an image with non-empty
    vision_description — not just any prior user turn."""
    src = FRONTEND.read_text()
    # The exact gate must check all three conditions.
    needles = [
        "prev.role === \"user\"",
        "Array.isArray(prev.attachments)",
        'a.kind === "image"',
        "vision_description",
    ]
    for n in needles:
        assert n in src, f"badge gate missing condition: {n!r}"


def test_message_component_now_receives_prev_prop():
    src = FRONTEND.read_text()
    # The map call must pass the previous message for the badge logic
    assert "prev={i > 0 ? history[i - 1] : null}" in src
    assert "function Message({ m, i, prev," in src


def test_iter_327k_marker_present():
    src = FRONTEND.read_text()
    assert "iter 327k" in src
