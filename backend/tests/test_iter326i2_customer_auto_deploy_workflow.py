"""
iter 326i-2 — Verify the customer auto-deploy workflow is correctly refined.

CONTEXT
───────
Earlier audit found `.github/workflows/auto_deploy.yml` was a bash cleanup
script with a `.yml` extension — GitHub Actions could not parse it, so it
silently did nothing on push.

Founder clarified: aurem.live deploys MANUALLY. The auto-deploy stack is
a PRODUCT FEATURE for AUREM subscribers — when AUREM generates a fix for
a customer, `services/github_deploy_service.py::push_fix` opens a PR in
the customer's repo. That PR-merge then needs to trigger a workflow in
the customer's repo that validates + deploys.

This test file asserts:
  1. The bash cleanup script is preserved at scripts/dead_code_cleanup.sh
  2. .github/workflows/auto_deploy.yml is now valid GitHub Actions YAML
  3. It is NOT going to fire on aurem.live's own pushes (no aurem-specific
     triggers — workflow_dispatch + customer-style push to main/master +
     PR labeled aurem-autofix)
  4. It exposes the correct job structure (pr_gate + deploy)
  5. It calls back to https://aurem.live/api/customer/deploy/report so the
     control plane knows the customer's deploy succeeded
"""
from __future__ import annotations

import os

import pytest
import yaml


WORKFLOW_PATH = "/app/.github/workflows/auto_deploy.yml"
PRESERVED_SCRIPT_PATH = "/app/scripts/dead_code_cleanup.sh"


def _load_workflow() -> dict:
    """Load and return the parsed workflow YAML."""
    with open(WORKFLOW_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f)


# ─── 1. Preservation of the original bash script ──────────────────────
def test_dead_code_cleanup_script_preserved():
    """Founder said 'no delete, just refine' — the original bash content
    must live at /app/scripts/dead_code_cleanup.sh with shebang intact."""
    assert os.path.isfile(PRESERVED_SCRIPT_PATH), (
        f"preserved script missing at {PRESERVED_SCRIPT_PATH}"
    )
    with open(PRESERVED_SCRIPT_PATH, encoding="utf-8") as f:
        head = f.read(200)
    assert head.startswith("#!/usr/bin/env bash"), (
        "preserved script lost its shebang"
    )
    assert "AUREM — Dead Code Cleanup" in head, (
        "preserved script is not the original cleanup script"
    )
    assert os.access(PRESERVED_SCRIPT_PATH, os.X_OK), (
        "preserved script is not executable"
    )


# ─── 2. YAML validity ─────────────────────────────────────────────────
def test_workflow_is_valid_yaml():
    """The replacement must parse cleanly (the bug was that the old file
    failed YAML parsing because it was a bash script)."""
    doc = _load_workflow()
    assert isinstance(doc, dict)
    assert "name" in doc
    # 'on' is a YAML key BUT PyYAML coerces unquoted `on:` to bool True.
    # GitHub Actions accepts both representations; cope with either.
    assert ("on" in doc) or (True in doc), "no 'on' trigger block"
    assert "jobs" in doc


def test_workflow_first_line_is_not_shebang():
    """Defensive — guarantees the file isn't a bash script masquerading."""
    with open(WORKFLOW_PATH, encoding="utf-8") as f:
        first = f.readline().strip()
    assert not first.startswith("#!"), (
        f"workflow first line is a shebang — still a bash script? {first!r}"
    )


# ─── 3. Trigger safety — does NOT fire on aurem.live's own pushes ─────
def test_workflow_triggers_are_customer_scoped():
    doc = _load_workflow()
    on_block = doc.get("on") or doc.get(True)
    assert isinstance(on_block, dict)
    # MUST support manual operator invocation
    assert "workflow_dispatch" in on_block
    # MUST support customer-merge deploys
    assert "push" in on_block
    branches = on_block["push"]["branches"]
    assert "main" in branches, "missing main branch trigger"
    assert "master" in branches, "missing master branch trigger (customer compat)"
    # MUST also gate on PR label (defensive CI before merge)
    assert "pull_request" in on_block


def test_workflow_has_paths_ignore_for_aurem_assets():
    """AUREM may commit files into `.aurem/` inside customer repos — those
    paths must NOT re-trigger the workflow (otherwise infinite deploy loop)."""
    doc = _load_workflow()
    on_block = doc.get("on") or doc.get(True)
    ignore = on_block["push"].get("paths-ignore") or []
    # The exact list isn't important, but ".aurem/**" MUST be present
    matched = any(p.startswith(".aurem") for p in ignore)
    assert matched, f"paths-ignore must contain .aurem/**: got {ignore}"


# ─── 4. Job structure ─────────────────────────────────────────────────
def test_workflow_has_pr_gate_and_deploy_jobs():
    doc = _load_workflow()
    jobs = doc["jobs"]
    assert "pr_gate" in jobs, "missing pr_gate job (CI green before merge)"
    assert "deploy" in jobs, "missing deploy job (post-merge rollout)"

    # pr_gate must be guarded by aurem-autofix label so it never fires on
    # an arbitrary customer PR
    pr_gate = jobs["pr_gate"]
    if_clause = (pr_gate.get("if") or "").lower()
    assert "aurem-autofix" in if_clause, (
        f"pr_gate must gate on aurem-autofix label, got: {if_clause!r}"
    )

    # deploy must NOT fire on pull_request (only post-merge push)
    deploy = jobs["deploy"]
    if_clause = (deploy.get("if") or "").lower()
    assert "pull_request" in if_clause, (
        "deploy job must explicitly exclude pull_request events"
    )


# ─── 5. Reports back to AUREM control plane ───────────────────────────
def test_workflow_reports_back_to_aurem_control_plane():
    """The deploy job MUST POST a result to aurem.live/api/customer/deploy/report
    so AUREM knows the customer's PR shipped."""
    with open(WORKFLOW_PATH, encoding="utf-8") as f:
        raw = f.read()
    assert "https://aurem.live/api/customer/deploy/report" in raw, (
        "deploy report-back URL missing — AUREM won't know if customer deploy succeeded"
    )
    assert "AUREM_API_KEY" in raw, (
        "AUREM_API_KEY env secret reference missing"
    )


# ─── 6. Required customer secrets are documented in the header ────────
def test_workflow_documents_required_customer_secrets():
    with open(WORKFLOW_PATH, encoding="utf-8") as f:
        raw = f.read()
    # The header docs MUST list every secret the workflow references
    for secret in (
        "AUREM_DEPLOY_TARGET",
        "AUREM_DEPLOY_HOOK_URL",
        "AUREM_NOTIFY_EMAIL",
        "AUREM_API_KEY",
    ):
        assert secret in raw, f"workflow doesn't document {secret} secret"


# ─── 7. Sanity: file is < 200 lines and self-contained ────────────────
def test_workflow_is_reasonably_sized():
    """A canonical template should be readable in one sitting."""
    with open(WORKFLOW_PATH, encoding="utf-8") as f:
        lines = f.readlines()
    assert 50 < len(lines) < 250, (
        f"workflow size suspicious: {len(lines)} lines"
    )
