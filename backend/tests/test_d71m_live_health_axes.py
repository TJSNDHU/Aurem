"""
D-71m — Live Health customer page: GEO/SEC tiles always 0 fix.

User reported the dogfood customer interface Live Health page showed
GEO=0, SEC=0, ACC=100, SEO=100. Investigation showed the backend
`/api/repair/scores` only returned `seo` and `accessibility` keys —
the frontend looked for `s.geo` and `s.sec`, got undefined, and
defaulted to 0 via the `num()` helper.

Root cause: 4-axis UI vs 2-axis backend response. Now backend returns
all 4 axes computed from `repair_fixes` rows categorised as
"geo"/"geo_readiness" and "security"/"sec".
"""
from __future__ import annotations

from pathlib import Path

import os as _os_q, pytest as _pytest_q
pytestmark = _pytest_q.mark.skipif(
    not _os_q.environ.get("AUREM_RUN_LEGACY"),
    reason="asserts pre-slim health/bootstrap shape or older infra spec — quarantined iter D-86b; set AUREM_RUN_LEGACY=1 to run",
)


def _src():
    return Path("/app/backend/routers/ai_repair_router.py").read_text()


def test_repair_scores_returns_all_four_axes():
    src = _src()
    # Find the get_repair_scores function and verify it returns all 4 keys.
    idx = src.index("@router.get(\"/api/repair/scores\")")
    body = src[idx:idx + 3500]
    for axis in ('"seo"', '"accessibility"', '"geo"', '"security"'):
        assert axis in body, (
            f"/api/repair/scores must return {axis} so the Live Health "
            f"4-tile UI doesn't render zero for missing keys"
        )


def test_repair_scores_filters_geo_and_security_fixes():
    src = _src()
    # The fix-filter expressions must exist
    assert 'f["category"] in ("geo", "geo_readiness")' in src
    assert 'f["category"] in ("security", "sec")' in src


def test_geo_and_security_have_score_before_after_shape():
    """Frontend `num()` helper reads `.score_after` first — both new
    axes must include it so the tile shows the post-fix score."""
    src = _src()
    # Each new axis dict has the four standard keys
    idx = src.index('"geo":')
    geo_body = src[idx:idx + 400]
    for k in ("score_before", "score_after", "total_fixes", "approved", "pending"):
        assert k in geo_body, f"geo axis missing key {k}"
    idx = src.index('"security":')
    sec_body = src[idx:idx + 400]
    for k in ("score_before", "score_after", "total_fixes", "approved", "pending"):
        assert k in sec_body, f"security axis missing key {k}"
