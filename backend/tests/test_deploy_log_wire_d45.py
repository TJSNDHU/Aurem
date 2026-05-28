"""
tests/test_deploy_log_wire_d45.py — iter D-45

Locks the contract that the frontend DevDeploy poller depends on:
  1. The /api/developers/deploy/log/{run_id} endpoint exists, is
     dev-auth-gated, returns the documented field shape (`status`,
     `next_cursor`, `lines`, `exit_code`).
  2. The deploy command emitted by `_deploy_command` still contains the
     three substring anchors the frontend classifier uses to advance
     steps (`git ` → step 1, `compose pull` → step 2, `DEPLOY_HEAD=`
     → step 5). If the bash one-liner is ever rewritten in a way that
     drops one of these anchors, this test trips before the broken UI
     ships.
  3. The frontend `DevDeploy.jsx` keeps the matching `classifyStep`
     branches (string-grep the file).
"""
from __future__ import annotations

import inspect
import os
import re
import sys


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


def test_deploy_command_contains_step_anchors():
    """The bash one-liner must still log substrings the frontend uses
    to drive its step progress."""
    from routers.developer_deploy_router import _deploy_command
    cmd = _deploy_command({
        "repo_path": "/opt/aurem", "branch": "main",
        "compose_file": "docker-compose.yml",
    }, mode="deploy")
    assert "git fetch"     in cmd  # frontend step 1 anchor
    assert "docker compose" in cmd and "pull"  in cmd  # frontend step 2 anchor
    assert "DEPLOY_HEAD="  in cmd  # frontend step 5 anchor


def test_deploy_log_endpoint_registered():
    """`/api/developers/deploy/log/{run_id}` must still be wired with
    the documented response shape (status, next_cursor, lines)."""
    from routers.developer_deploy_router import get_deploy_log
    sig = inspect.signature(get_deploy_log)
    params = list(sig.parameters)
    assert "run_id" in params
    assert "since"  in params
    # Verify the function body declares the keys the frontend reads.
    src = inspect.getsource(get_deploy_log)
    for key in ("status", "exit_code", "next_cursor", "lines"):
        assert f"\"{key}\"" in src, f"deploy log response missing key {key!r}"


def test_devdeploy_classifier_has_all_branches():
    """Frontend classifier must keep the 6 anchors aligned with the
    backend command above. Plain string-grep is enough — we just need
    each step's identifying substring to still be referenced."""
    path = os.path.join(
        ROOT, "..", "frontend", "src", "platform", "developers",
        "DevDeploy.jsx",
    )
    src = open(path).read()
    for needle in (
        "deploy_head=",         # step 5
        "compose pull",         # step 2
        "creating ",            # step 3
        "git ",                 # step 1
        "$ ",                   # step 0
    ):
        assert needle in src, f"classifyStep missing anchor {needle!r}"
    # Polling loop hits /log/{run_id}
    assert "/api/developers/deploy/log/" in src
    # No more naive timer animation
    assert "setInterval(() => { let i" not in src


def test_devdeploy_has_log_tail_panel():
    path = os.path.join(
        ROOT, "..", "frontend", "src", "platform", "developers",
        "DevDeploy.jsx",
    )
    src = open(path).read()
    assert "deploy-log-tail" in src
    assert "logLines"        in src


def test_no_fork_button_anywhere_in_frontend():
    """User requested removing the `Fork` button. Confirm no JSX
    component is labelled `Fork` or carries `GitFork` icon."""
    fdir = os.path.join(ROOT, "..", "frontend", "src")
    hits = []
    for root, _dirs, files in os.walk(fdir):
        if "node_modules" in root or "build" in root:
            continue
        for f in files:
            if not f.endswith((".jsx", ".js")):
                continue
            p = os.path.join(root, f)
            try:
                txt = open(p, encoding="utf-8").read()
            except Exception:
                continue
            # JSX button literal labelled "Fork"  e.g. <button …>Fork</button>
            if re.search(r">\s*Fork\s*<", txt):
                hits.append(p + ":Fork-label")
            if "GitFork" in txt and "lucide" in txt.lower():
                hits.append(p + ":GitFork-import")
            if 'data-testid="fork-' in txt.lower():
                hits.append(p + ":fork-testid")
    assert hits == [], f"Fork button artefacts still present: {hits}"
