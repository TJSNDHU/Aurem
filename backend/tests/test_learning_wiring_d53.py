"""
tests/test_learning_wiring_d53.py — iter D-53

Frontend wiring assertions for the D-53 self-learning UI:
  • ConfidenceBadge exists and calls /api/developers/cto/learning/confidence
  • DeployProgressDialog records SUCCESS + FAILURE outcomes via the
    verified-only learning endpoint
  • SaveToGithubDialog records github_push outcomes
  • Chat panel mounts ConfidenceBadge
"""
from __future__ import annotations

import os

FRONTEND = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)),
                  "..", "..", "frontend", "src", "platform", "developers")
)

BADGE  = os.path.join(FRONTEND, "ConfidenceBadge.jsx")
DEPLOY = os.path.join(FRONTEND, "DeployProgressDialog.jsx")
SAVE   = os.path.join(FRONTEND, "SaveToGithubDialog.jsx")
PANEL  = os.path.join(FRONTEND, "DevCtoChatPanel.jsx")


def _read(p):
    with open(p, "r", encoding="utf-8") as f:
        return f.read()


def test_confidence_badge_file_exists():
    assert os.path.exists(BADGE)
    src = _read(BADGE)
    assert "/api/developers/cto/learning/confidence" in src
    assert "taskType" in src


def test_deploy_dialog_records_success_and_failure():
    src = _read(DEPLOY)
    assert "/api/developers/cto/learning/record" in src
    assert 'result: "success"' in src or '"success"' in src
    assert 'result: "failure"' in src or '"failure"' in src
    assert '"deploy_green"' in src   # only system-verified verified_by


def test_save_dialog_records_github_push():
    src = _read(SAVE)
    assert "/api/developers/cto/learning/record" in src
    assert '"github_push"' in src
    assert '"github_green"' in src


def test_chat_panel_mounts_confidence_badge():
    src = _read(PANEL)
    assert "import ConfidenceBadge" in src
    assert "<ConfidenceBadge" in src
    assert 'taskType="github_push"' in src
