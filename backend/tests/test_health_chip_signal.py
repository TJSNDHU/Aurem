"""
test_health_chip_signal.py — guard against the SystemStatusChip "loading · 0m"
regression (iter D-61).

Background
----------
SystemStatusChip + BuildBadge poll `/api/health` and expect:
  - "v"              (build SHA or version string)
  - "uptime_seconds" (int)

If either field is missing, the top-right chip sticks on
"loading · 0m" forever which makes the whole admin shell look broken.

This test pins the contract so any future refactor of
`middleware/health_probe.py` or `server.py`'s liveness routes that
silently drops these fields will fail in CI.
"""

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="module")
def client():
    from server import app
    return TestClient(app)


def _assert_chip_contract(payload: dict) -> None:
    assert payload.get("status") in ("ok", "healthy"), payload
    assert "v" in payload, f"missing 'v' (build sha) → chip sticks on 'loading' · {payload}"
    assert isinstance(payload["v"], str) and payload["v"], payload
    assert "uptime_seconds" in payload, f"missing 'uptime_seconds' → chip sticks on '· 0m' · {payload}"
    assert isinstance(payload["uptime_seconds"], int), payload
    assert payload["uptime_seconds"] >= 0, payload


def test_api_health_returns_chip_fields(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    _assert_chip_contract(r.json())


def test_health_returns_chip_fields(client):
    r = client.get("/health")
    assert r.status_code == 200
    _assert_chip_contract(r.json())


def test_api_platform_health_returns_chip_fields(client):
    r = client.get("/api/platform/health")
    assert r.status_code == 200
    _assert_chip_contract(r.json())
