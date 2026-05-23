"""
tests/test_iter330d_api_key_health_watcher.py — iter 330d
"""
import sys
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def test_module_present():
    from services import api_key_health_watcher as w
    assert callable(w.record_api_failure)
    assert callable(w.health_summary)


def test_bucket_classification():
    from services.api_key_health_watcher import _bucket, _is_credential_error
    assert _bucket(401) == "unauthorized"
    assert _bucket(403) == "forbidden"
    assert _bucket(429) == "rate_limit"
    assert _bucket(500) == "other"
    # Body-token credential detection.
    assert _is_credential_error(400, "API_INACCESSIBLE: not available") is True
    assert _is_credential_error(400, "Consumer api_key has been suspended.") is True
    # Plain 500 → not classified as cred error.
    assert _is_credential_error(500, "internal server error") is False


@pytest.mark.asyncio
async def test_record_failure_persists_and_alerts(monkeypatch):
    from services import api_key_health_watcher as w

    class LogColl:
        def __init__(self): self.rows = []
        async def insert_one(self, d): self.rows.append(d)

    class DB:
        api_key_health_log = LogColl()

    w.set_db(DB())

    sent = []
    async def fake_tg(msg, fingerprint=None): sent.append((msg, fingerprint))
    import services.silent_failure_alerts as sfa
    monkeypatch.setattr(sfa, "_send", fake_tg)

    out = await w.record_api_failure(
        provider="google_places", status_code=403,
        body="Consumer api_key has been suspended.",
        key_hint="abc123",
    )
    assert out["ok"] is True
    assert out["alerted"] is True
    assert "google_places" in sent[0][0].lower()
    assert sent[0][1].startswith("apikey_google_places_forbidden_")


def test_callers_wired_into_3_providers():
    for path in (
        "/app/backend/services/hunt_live.py",
        "/app/backend/services/yelp_scout.py",
        "/app/backend/services/apollo_scout.py",
    ):
        src = Path(path).read_text()
        assert "record_api_failure" in src, f"missing watcher hook in {path}"
