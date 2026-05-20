"""
Smoke test for react-doctor frontend gate.

Ensures:
1. The react-doctor.config.json is valid JSON with public/** excluded.
2. The CI workflow exists at .github/workflows/react-doctor.yml.
3. The react-doctor npm script is wired in package.json.

The actual score gate runs in CI (Node side); this is just a static check.
"""
import json
from pathlib import Path

ROOT = Path("/app")


def test_react_doctor_config_excludes_public():
    cfg = ROOT / "frontend" / "react-doctor.config.json"
    assert cfg.exists(), "react-doctor.config.json must exist at frontend/ root"
    data = json.loads(cfg.read_text())
    files = data.get("ignore", {}).get("files", [])
    assert "public/**" in files, "public/** must be excluded (third-party partytown)"
    assert "build/**" in files
    assert "node_modules/**" in files


def test_react_doctor_workflow_exists():
    wf = ROOT / ".github" / "workflows" / "react-doctor.yml"
    assert wf.exists(), "CI workflow must exist"
    body = wf.read_text()
    assert "react-doctor" in body
    assert "THRESHOLD" in body and "70" in body, "Score gate must enforce >= 70"
    assert "--score" in body


def test_react_doctor_npm_script_wired():
    pkg = json.loads((ROOT / "frontend" / "package.json").read_text())
    assert "react-doctor" in pkg.get("scripts", {}), "yarn react-doctor must be runnable"


def test_unused_heavy_deps_removed():
    """rrweb / rrweb-player / face-api.js were dead deps — must NOT appear in deps."""
    pkg = json.loads((ROOT / "frontend" / "package.json").read_text())
    deps = pkg.get("dependencies", {})
    for ghost in ("rrweb", "rrweb-player", "face-api.js"):
        assert ghost not in deps, f"{ghost} is unused — should be removed from package.json"


def test_robotviewport_dead_code_removed():
    """RobotViewport.jsx was dead — LiveCampaignPipeline replaced it."""
    assert not (ROOT / "frontend" / "src" / "platform" / "RobotViewport.jsx").exists()


def test_forensic_helix_lazy_loaded():
    body = (ROOT / "frontend" / "src" / "platform" / "ShopifyAppManager.jsx").read_text()
    assert "lazy(() => import('./ForensicMinerHelix'))" in body, \
        "ForensicMinerHelix (Three.js) must be lazy-loaded"
    assert "Suspense" in body
