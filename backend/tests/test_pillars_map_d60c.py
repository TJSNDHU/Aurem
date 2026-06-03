"""
tests/test_pillars_map_d60c.py — iter D-60c

Lock in the fix for the racey pillar-map probe that was painting
production red even when all 4 pillars were green.

Two bugs fixed in this iter:
  1. FE route probe was hitting the EXTERNAL preview URL from inside
     the pod, which couldn't egress back through its own ingress →
     `route failed: ` (empty exception) → flows red.
     Fix: probe the IN-CLUSTER frontend at http://localhost:3000.
  2. `_BOOT_GRACE_EXCLUDE` middleware was short-circuiting the new
     `/api/pillars/*` and `/api/admin/pillars-map/*` endpoints with
     204 No Content during pod warmup → UI showed empty payload.
     Fix: add both prefixes to the exclude tuple.
"""
from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


def _read(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


# ── BOOT-GRACE EXCLUSIONS ────────────────────────────────────────

def test_boot_grace_excludes_pillar_endpoints():
    src = _read(os.path.join(ROOT, "middleware", "health_probe.py"))
    assert "/api/admin/pillars-map" in src, (
        "pillars-map should be excluded from boot-grace short-circuit"
    )
    assert "/api/pillars/" in src, (
        "top-level pillars endpoint should be excluded from boot-grace"
    )


# ── PILLAR-MAP FE PROBE FIX ──────────────────────────────────────

def test_pillar_map_uses_local_frontend_url():
    src = _read(os.path.join(ROOT, "routers", "pillars_map_router.py"))
    assert "_LOCAL_FRONTEND_URL" in src, (
        "_LOCAL_FRONTEND_URL constant must be defined"
    )
    assert 'http://localhost:3000' in src, (
        "FE probe must point at in-cluster frontend"
    )


def test_pillar_map_route_probe_surfaces_exception_class():
    """Old code reported `route failed: ` with empty message when the
    exception had no string repr. New code prefixes with the exception
    class name (`ConnectError`, `TimeoutException` etc.) and never
    returns an empty reason string."""
    src = _read(os.path.join(ROOT, "routers", "pillars_map_router.py"))
    assert 'type(route_res).__name__' in src
    # Exception path must downgrade to yellow (not red blocking)
    assert "fe_side = \"yellow\"" in src


def test_pillar_map_timeout_at_least_4s():
    """2.5s was too tight for cluster-internal probes during scheduler
    sweeps. Must be >= 4 seconds to give httpx room to complete."""
    src = _read(os.path.join(ROOT, "routers", "pillars_map_router.py"))
    import re
    m = re.search(r"AsyncClient\(timeout=([\d.]+)\s*,\s*follow_redirects=False\)", src)
    assert m, "AsyncClient probe timeout pattern not found"
    assert float(m.group(1)) >= 4.0, (
        f"FE probe timeout {m.group(1)}s too short — cluster sweeps race"
    )


# ── PILLAR HEALTH RESPONSE SHAPE ─────────────────────────────────

def test_top_level_pillar_health_router_exposes_all_four():
    src = _read(os.path.join(ROOT, "routers", "pillars_health_router.py"))
    # All 4 pillars must be reported
    for p in ("P1", "P2", "P3", "P4"):
        assert f'"{p}"' in src or f"'{p}'" in src, (
            f"pillars_health_router must report {p}"
        )
