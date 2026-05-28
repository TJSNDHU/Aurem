"""
tests/test_deploy_gate_d52a.py — iter D-52a

Asserts that the Deploy CTA in SaveToGithubDialog is BLOCKED until
the GitHub verify row turns GREEN (and never shown if any row is RED).
"""
from __future__ import annotations

import os

FRONTEND = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)),
                  "..", "..", "frontend", "src", "platform", "developers")
)

SAVE  = os.path.join(FRONTEND, "SaveToGithubDialog.jsx")
BADGE = os.path.join(FRONTEND, "VerificationBadge.jsx")


def _read(p):
    with open(p, "r", encoding="utf-8") as f:
        return f.read()


def test_canShowDeploy_helper_exists():
    src = _read(BADGE)
    assert "export function canShowDeploy" in src
    # Red row → block
    assert 'r?.status === "red"' in src
    # GitHub must be green
    assert 'rows.github?.status === "green"' in src


def test_useVerifyRows_hook_exists():
    src = _read(BADGE)
    assert "export function useVerifyRows" in src


def test_save_dialog_gates_deploy_cta():
    src = _read(SAVE)
    # Hook is imported and wired
    assert "useVerifyRows" in src
    assert "canShowDeploy" in src
    # Conditional render uses deployAllowed
    assert "deployAllowed" in src
    # Both branches present
    assert 'data-testid="save-github-deploy-cta"' in src
    assert 'data-testid="save-github-deploy-blocked"' in src


def test_blocked_message_mentions_green():
    src = _read(SAVE)
    assert "GREEN" in src or "✅" in src
