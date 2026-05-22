"""
test_iter326r_cors_hardening.py — Regression for iter 326r.
══════════════════════════════════════════════════════════════════════════════
Founder asked: "fix wherever you saw issue which cause a CORS error in
future". This file locks in the proactive sweep that landed in
`backend/server.py` ~line 750 (the CORSMiddleware setup).

What was fragile before, and what changed:

(1)  `aurem.live` was listed TWICE — cosmetic, but the duplicate hid
     the fact that `www.aurem.live` was MISSING. When the host config
     redirected aurem.live → www.aurem.live, every API call from the
     www page CORS-failed. → www.aurem.live now in the allowlist; the
     duplicate is gone.

(2)  Emergent rotates preview subdomains (`ai-platform-preview-3` →
     `ai-platform-preview-4`, etc). The static allowlist broke each
     time. → Added `allow_origin_regex` matching any subdomain of
     `preview.emergentagent.com`.

(3)  Future white-label customer subdomains (admin.aurem.live,
     app.aurem.live, tenant.aurem.live) had no path to authorisation
     without a deploy. → Regex matches any subdomain of `aurem.live`.

(4)  PUBLIC_APP_URL env var (operator-set canonical URL) wasn't being
     appended to the allowlist. → It is now, alongside REACT_APP_BACKEND_URL
     and APP_URL.

(5)  CORS misfires were hard to diagnose because the final allowlist
     was never logged at startup. → Added a single info line on the
     `aurem.cors` logger.

(6)  Anchoring — `^...$` on the regex — must reject hostile origins
     that try to spoof aurem.live (e.g. `https://aurem.live.evil.com`).

Run:  cd /app/backend && python3 -m pytest tests/test_iter326r_cors_hardening.py -v
"""
from __future__ import annotations

import re
from pathlib import Path

SERVER_PY = Path("/app/backend/server.py")


def _server_src() -> str:
    return SERVER_PY.read_text()


# ─────────────────────────────────────────────────────────────────────────────
# (1)  Static allowlist defaults
# ─────────────────────────────────────────────────────────────────────────────
def test_default_allowlist_includes_www_aurem_live():
    """Most users type `aurem.live` in the address bar; the host
    redirects to www.aurem.live; every API call CORS-failed without
    this entry."""
    src = _server_src()
    # The literal must appear inside the fallback allowlist block.
    assert '"https://www.aurem.live"' in src, (
        "www.aurem.live is NOT in the default CORS allowlist — "
        "the previous bug will recur."
    )


def test_default_allowlist_includes_aurem_live():
    src = _server_src()
    assert '"https://aurem.live"' in src


def test_default_allowlist_no_longer_duplicates_aurem_live():
    """Before the fix, `aurem.live` was listed twice in the default
    allowlist. Lock the dedupe in."""
    src = _server_src()
    # Slice out just the default-list block to avoid false positives
    # from comments / docstrings elsewhere in the file.
    block_start = src.index("elif not _cors_raw_stripped:")
    block_end = src.index("else:", block_start)
    block = src[block_start:block_end]
    occurrences = block.count('"https://aurem.live"')
    assert occurrences == 1, (
        f"aurem.live appears {occurrences} times in default allowlist "
        f"— must appear exactly once (was 2 before iter 326r)."
    )


def test_default_allowlist_includes_localhost_dev():
    src = _server_src()
    assert "http://localhost:3000" in src


# ─────────────────────────────────────────────────────────────────────────────
# (2)  PUBLIC_APP_URL env support
# ─────────────────────────────────────────────────────────────────────────────
def test_public_app_url_is_appended_to_allowlist():
    """Operators sometimes set PUBLIC_APP_URL as the canonical URL for
    the deploy (separate from REACT_APP_BACKEND_URL). The CORS block
    must consume it just like the other two URL envs."""
    src = _server_src()
    assert "PUBLIC_APP_URL" in src
    # And the append idiom must reference _cors_origins (not just the env)
    block = src[src.index("PUBLIC_APP_URL"):]
    block = block[:1200]
    assert "_cors_origins.append(_public_app_url)" in block


def test_react_app_backend_url_still_appended():
    """Pre-existing behaviour we must NOT lose during the refactor."""
    src = _server_src()
    assert "_cors_origins.append(_react_url)" in src


def test_app_url_still_appended():
    src = _server_src()
    assert "_cors_origins.append(_app_url)" in src


# ─────────────────────────────────────────────────────────────────────────────
# (3, 4) allow_origin_regex matches every shape that must work
# ─────────────────────────────────────────────────────────────────────────────
def _extract_cors_regex_pattern() -> str:
    """Pull the regex literal that the server hands to CORSMiddleware.
    The regex spans multiple `r"..."` lines inside a parenthesised
    expression, so we hand-parse line-by-line instead of trying to
    write a regex that matches regex literals."""
    src = _server_src()
    start_marker = "_cors_origin_regex = ("
    end_marker = ")\n\n# CORS spec"
    i = src.index(start_marker)
    j = src.index(end_marker, i)
    block = src[i + len(start_marker):j]
    # Every line inside the block is `    r"..."` plus optional `# comment`.
    pieces = []
    for line in block.splitlines():
        m = re.search(r'r"([^"]*)"', line)
        if m:
            pieces.append(m.group(1))
    assert pieces, "no r-string literals found in _cors_origin_regex block"
    return "".join(pieces)


def test_regex_matches_apex_aurem_live():
    """The apex domain `https://aurem.live` must still match the regex
    (belt-and-braces with the static allowlist entry)."""
    pat = _extract_cors_regex_pattern()
    assert re.match(pat, "https://aurem.live")


def test_regex_matches_www_aurem_live():
    pat = _extract_cors_regex_pattern()
    assert re.match(pat, "https://www.aurem.live")


def test_regex_matches_white_label_subdomain():
    """Future-proofing test (3) — a tenant white-label like
    `admin.aurem.live` or `tenant42.aurem.live` must work without a
    deploy."""
    pat = _extract_cors_regex_pattern()
    assert re.match(pat, "https://admin.aurem.live")
    assert re.match(pat, "https://app.aurem.live")
    assert re.match(pat, "https://tenant42.aurem.live")


def test_regex_matches_emergent_preview_rotations():
    """Future-proofing test (4) — Emergent rotates preview subdomain
    numbers. Both current and future numbers must match."""
    pat = _extract_cors_regex_pattern()
    assert re.match(pat, "https://ai-platform-preview-3.preview.emergentagent.com")
    assert re.match(pat, "https://ai-platform-preview-4.preview.emergentagent.com")
    assert re.match(pat, "https://some-other-app.preview.emergentagent.com")


def test_regex_rejects_lookalike_spoof_origin():
    """The regex MUST be anchored — otherwise `aurem.live.evil.com`
    matches and an attacker on a hostile origin gets API access."""
    pat = _extract_cors_regex_pattern()
    assert not re.match(pat, "https://aurem.live.attacker.com")
    assert not re.match(pat, "https://aurem.live@attacker.com")
    assert not re.match(pat, "https://attacker.com/aurem.live")


def test_regex_rejects_unrelated_origins():
    pat = _extract_cors_regex_pattern()
    assert not re.match(pat, "https://example.com")
    assert not re.match(pat, "https://aurem-live.com")  # hyphen substitution
    assert not re.match(pat, "http://aurem.live")        # http rejected; https only


# ─────────────────────────────────────────────────────────────────────────────
# (5) Debug log line on startup
# ─────────────────────────────────────────────────────────────────────────────
def test_startup_logs_final_cors_config():
    """One log line on startup must report the final allowlist + regex
    state. Without this, future CORS bugs cost 30 min of code-reading."""
    src = _server_src()
    assert "aurem.cors" in src
    assert "[CORS] allow_origins=" in src
    assert "regex=" in src


# ─────────────────────────────────────────────────────────────────────────────
# (6) Wildcard mode contract preserved
# ─────────────────────────────────────────────────────────────────────────────
def test_wildcard_mode_disables_credentials_and_regex():
    """When operator opts into `CORS_ORIGINS=*`, the spec mandates
    credentials=False AND we must not also pass a regex (mixing the
    two confuses Starlette and the wildcard wins anyway, but explicit
    is better)."""
    src = _server_src()
    # The conditional that disables credentials when wildcarding.
    assert "_allow_credentials = _cors_origins != [\"*\"]" in src
    # The conditional that skips regex when wildcarding.
    assert "None if _cors_origins == [\"*\"] else _cors_origin_regex" in src


# ─────────────────────────────────────────────────────────────────────────────
# (7) Server still boots — sanity import
# ─────────────────────────────────────────────────────────────────────────────
def test_server_module_imports_cleanly():
    """If the refactor broke a name or introduced a syntax error, the
    server module wouldn't import. This is a cheap smoke test."""
    # `import server` runs the whole module which is heavy (DB, scheduler,
    # 100+ routers) — instead, just compile the source.
    import py_compile
    py_compile.compile(str(SERVER_PY), doraise=True)
