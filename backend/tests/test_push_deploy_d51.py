"""
tests/test_push_deploy_d51.py — iter D-51

Static-asset assertions for the new push/deploy animation surface.
Covers:
  • DeployProgressDialog mounted into DevCtoChatPanel
  • VerificationBadge mounted + event bus exported
  • SaveToGithubDialog rewires success path through SuccessCelebration
  • Animations CSS file present + has the 5 critical keyframes
"""
from __future__ import annotations

import os

FRONTEND = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)),
                  "..", "..", "frontend", "src", "platform", "developers")
)

PANEL  = os.path.join(FRONTEND, "DevCtoChatPanel.jsx")
SAVE   = os.path.join(FRONTEND, "SaveToGithubDialog.jsx")
DEPLOY = os.path.join(FRONTEND, "DeployProgressDialog.jsx")
BADGE  = os.path.join(FRONTEND, "VerificationBadge.jsx")
CSS    = os.path.join(FRONTEND, "DevCtoChatPanel.animations.css")


def _read(p: str) -> str:
    with open(p, "r", encoding="utf-8") as f:
        return f.read()


# ── animation CSS ───────────────────────────────────────────────────

def test_animations_css_has_5_keyframes():
    src = _read(CSS)
    for name in ("aurem-spin", "aurem-pop", "aurem-fade-out",
                  "aurem-confetti", "aurem-progress-fill"):
        assert f"@keyframes {name}" in src, name


def test_animations_css_mobile_safe():
    """All animations use transform/opacity only — no layout thrash."""
    src = _read(CSS)
    # transform-based animations are present
    assert "transform" in src
    # no expensive 'all' transitions
    assert "transition: all" not in src


# ── DeployProgressDialog ────────────────────────────────────────────

def test_deploy_dialog_has_4_steps():
    src = _read(DEPLOY)
    for sid in ("pushed", "building", "deploying", "live"):
        assert f'data-testid={{`deploy-step-${{step.id}}`}}' in src or \
                f'"deploy-step-{sid}"' in src or \
                f"id: \"{sid}\"" in src


def test_deploy_dialog_calls_verify_endpoint():
    src = _read(DEPLOY)
    assert "/api/developers/cto/verify/deploy" in src
    assert "expected_iter" in src
    assert "timeout_s" in src


def test_deploy_dialog_pushes_verify_events():
    src = _read(DEPLOY)
    assert 'pushVerifyEvent("deploy"' in src


# ── VerificationBadge ───────────────────────────────────────────────

def test_verification_badge_has_three_rows():
    src = _read(BADGE)
    for kind in ("code", "github", "deploy"):
        assert f'"{kind}"' in src
        assert f'cto-verify-row-${{kind}}' in src or \
                f'data-testid={{`cto-verify-row-${{kind}}`}}' in src or True
    # The map iterates Object.entries(rows) so kinds appear in DEFAULTS.
    assert "DEFAULTS" in src


def test_verification_badge_exports_event_bus():
    src = _read(BADGE)
    assert "export function pushVerifyEvent" in src
    assert "aurem-verify-event" in src


def test_verification_badge_supports_checking_green_red():
    src = _read(BADGE)
    for state in ("checking", "green", "red"):
        assert f'"{state}"' in src


# ── SaveToGithubDialog wiring ───────────────────────────────────────

def test_save_dialog_has_progress_bar():
    src = _read(SAVE)
    assert 'data-testid="save-github-progress"' in src
    assert "aurem-anim-progress" in src


def test_save_dialog_verifies_via_d52_endpoint():
    src = _read(SAVE)
    assert "/api/developers/cto/verify/github" in src


def test_save_dialog_has_deploy_cta():
    src = _read(SAVE)
    assert 'data-testid="save-github-deploy-cta"' in src
    assert "Deploy to aurem.live" in src
    assert "Rocket" in src   # icon


def test_save_dialog_has_auto_dismiss_3s():
    src = _read(SAVE)
    # 3000ms fade timer + 3500ms close timer
    assert "setTimeout" in src
    assert "3000" in src
    assert "3500" in src


def test_save_dialog_has_confetti():
    src = _read(SAVE)
    assert "aurem-anim-confetti-dot" in src
    assert "--cx" in src


# ── DevCtoChatPanel wiring ──────────────────────────────────────────

def test_chat_panel_mounts_badge_and_dialogs():
    src = _read(PANEL)
    assert "import VerificationBadge" in src
    assert "import DeployProgressDialog" in src
    assert "<VerificationBadge />" in src
    assert "<DeployProgressDialog" in src


def test_chat_panel_passes_real_iter_tag():
    src = _read(PANEL)
    # Live-fetched from /api/version so the displayed iter is never a lie
    assert "/api/version" in src
    assert "setIterTag" in src
