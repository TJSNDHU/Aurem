"""
Yelp Fusion Scout regression — iter 282z

Run:
    cd /app/backend && python -m pytest tests/test_yelp_scout.py -v
"""

import os
from unittest.mock import patch, MagicMock

import pytest


@pytest.fixture(autouse=True)
def _set_keys(monkeypatch):
    monkeypatch.setenv("YELP_API_KEY", "test_key")


@pytest.mark.asyncio
async def test_yelp_returns_validated_leads():
    """Yelp results pass through is_valid_lead + de-duplicated phones."""
    from services import yelp_scout
    fake_response = MagicMock(status_code=200)
    fake_response.json = MagicMock(return_value={
        "businesses": [
            {
                "id": "biz1",
                "name": "Acme Roofing",
                "phone": "+14165550100",
                "display_phone": "(416) 555-0100",
                "url": "https://www.yelp.com/biz/acme-roofing",
                "location": {"display_address": ["123 Main St", "Mississauga, ON"], "city": "Mississauga"},
                "categories": [{"title": "Roofing"}],
                "rating": 4.7, "review_count": 25,
            },
            {
                "id": "biz2",
                "name": "",  # invalid — empty name
                "phone": "+14165550101",
                "url": "https://www.yelp.com/biz/empty",
            },
            {
                "id": "biz3",
                "name": "Phone-less Co",  # invalid — no phone
                "phone": "",
                "url": "https://www.yelp.com/biz/no-phone",
            },
        ]
    })

    class _FakeClient:
        def __init__(self, *a, **k): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *a, **k): return False
        async def get(self, *a, **k): return fake_response

    with patch.object(yelp_scout.httpx, "AsyncClient", _FakeClient):
        res = await yelp_scout.yelp_leads("roofing", "Mississauga, ON", limit=10)
    assert res["success"] is True
    assert res["total"] == 1
    assert res["leads"][0]["business_name"] == "Acme Roofing"
    assert res["leads"][0]["phone"] == "+14165550100"
    assert res["leads"][0]["source"] == "yelp_fusion"


@pytest.mark.asyncio
async def test_yelp_no_key_returns_empty():
    """Missing key → graceful empty result, no crash."""
    import importlib
    from services import yelp_scout as ys
    os.environ.pop("YELP_API_KEY", None)
    importlib.reload(ys)
    res = await ys.yelp_leads("roofing", "Mississauga, ON")
    assert res["success"] is False
    assert res["total"] == 0
    assert res["error"] == "no_key"


def test_yelp_category_alias_mapping():
    from services.yelp_scout import _yelp_alias
    assert _yelp_alias("roofing") == "roofing"
    assert _yelp_alias("Plumbing") == "plumbing"
    assert _yelp_alias("auto repair") == "autorepair"
    assert _yelp_alias("hair salon") == "hair"
    # Unknown → empty (free-text term search)
    assert _yelp_alias("xyzzy123") == ""
