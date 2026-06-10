"""
test_d75_route_dedupe.py — iter D-75 Part 2 #2 regression guard.

After D-71p audit + D-75 detector found 314 silent duplicate
(verb, path) registrations because registry.py had multiple
registration lists including the same routers 2-3 times each, an
idempotent include_router guard was added that no-ops 2nd+
registrations of the same router object.

These tests:
  1. Assert the guard exists.
  2. Assert the boot-time `_detect_duplicate_routes` and
     `_detect_unwired_set_db_modules` functions exist and emit
     observable signals.
  3. Lock the duplicate count to ≤ 20 (was 314 pre-guard, 17
     post-guard). If a future PR re-introduces broad double-
     registration, this test catches it before merge.

Run: PYTHONPATH=/app/backend python3 -m pytest tests/test_d75_route_dedupe.py -v
"""
from __future__ import annotations

import inspect
import sys

import pytest

sys.path.insert(0, "/app/backend")


def test_idempotent_include_router_guard_exists():
    """The wrapper that no-ops 2nd+ registrations of the same router
    must be present in `register_all_routers`."""
    from routers import registry
    src = inspect.getsource(registry.register_all_routers)
    assert "_included_router_ids" in src, (
        "idempotent include_router guard missing — D-75 regression. "
        "Without it, registry.py multi-list registration silently "
        "double-counts routes."
    )
    assert "_dedup_include_router" in src
    assert "app.include_router = _dedup_include_router" in src


def test_duplicate_route_detector_exists():
    """`_detect_duplicate_routes` must be defined as a top-level
    function in the registry module (not nested) so future PRs can
    import + test it directly."""
    from routers import registry
    assert hasattr(registry, "_detect_duplicate_routes"), (
        "registry._detect_duplicate_routes missing — D-75 regression"
    )
    sig = inspect.signature(registry._detect_duplicate_routes)
    assert "app" in sig.parameters


def test_set_db_wiring_audit_exists():
    """`_detect_unwired_set_db_modules` audit must exist + emit a
    warning when there are unwired modules."""
    from routers import registry
    assert hasattr(registry, "_detect_unwired_set_db_modules")


def test_detect_duplicate_routes_emits_signal(caplog):
    """Build a tiny synthetic FastAPI app with one deliberately
    duplicated route, run the detector against it, assert the
    warning surface fires."""
    from fastapi import FastAPI, APIRouter
    from routers import registry
    import logging

    test_app = FastAPI()
    r1 = APIRouter()
    @r1.get("/dupe-test")
    async def h1():
        return "a"
    r2 = APIRouter()
    @r2.get("/dupe-test")
    async def h2():
        return "b"
    test_app.include_router(r1)
    test_app.include_router(r2)

    with caplog.at_level(logging.WARNING, logger="routers.registry"):
        registry._detect_duplicate_routes(test_app)

    msgs = [rec.getMessage() for rec in caplog.records
            if rec.name == "routers.registry"]
    joined = "\n".join(msgs)
    assert "DUPE" in joined and "/dupe-test" in joined, (
        f"detector failed to log the synthetic dupe. Logged: {joined!r}"
    )


def test_live_route_table_dupe_count_under_threshold():
    """Live regression cap: after the idempotent guard, the route
    table has ≤ 20 genuine cross-handler duplicates (was 314 pre-
    guard, 17 right after). If this number creeps up, someone
    re-introduced broad double-registration OR added a new conflict
    without resolving the old ones."""
    from server import app as live_app
    from collections import defaultdict
    by_route: dict[tuple, set] = defaultdict(set)
    for r in getattr(live_app, "routes", []):
        path = getattr(r, "path", None)
        methods = getattr(r, "methods", None)
        if not path or not methods:
            continue
        if path.startswith("/openapi") or path.startswith("/docs") \
                or path.startswith("/redoc"):
            continue
        endpoint = getattr(r, "endpoint", None)
        endpoint_id = (
            f"{endpoint.__module__}.{endpoint.__qualname__}"
            if endpoint else "unknown"
        )
        for verb in methods:
            by_route[(verb, path)].add(endpoint_id)

    cross_handler_dupes = {k: v for k, v in by_route.items() if len(v) > 1}
    assert len(cross_handler_dupes) <= 20, (
        f"{len(cross_handler_dupes)} cross-handler route duplicates — "
        "broad double-registration regression. Was 17 immediately "
        "post-D-75 #2."
    )
