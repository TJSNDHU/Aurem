"""
test_isolation.py — Enforces the AUREM CTO isolation contract.

Scans every `.py` file under /app/aurem_cto/ and asserts that the only
imports from the host application are the 3 paths declared in
DEPENDENCIES.md. Any new top-level host import fails this test.

Run via pytest:
    pytest /app/aurem_cto/tests/test_isolation.py -v
"""
from __future__ import annotations

import ast
import pathlib

MODULE_ROOT = pathlib.Path("/app/aurem_cto")

# These are the only `from X import Y` / `import X` patterns that may
# reach outside the aurem_cto package. Anything else = fail.
ALLOWED_HOST_IMPORTS = {
    "routers.developer_portal_router",   # _current_dev
    "config",                            # JWT_SECRET, JWT_ALGORITHM
    "services.byok_store",               # _encrypt / _decrypt (host fernet)
}

# Std-lib + third-party prefixes that are always fine.
STDLIB_OK = {
    "__future__",
    "asyncio", "os", "sys", "time", "uuid", "json", "logging",
    "datetime", "typing", "pathlib", "re", "hashlib", "hmac",
    "base64", "secrets", "subprocess", "ipaddress", "socket",
    "collections", "functools", "itertools", "contextlib",
    "dataclasses", "enum", "math", "ast",
}
THIRD_PARTY_OK = {
    "fastapi", "pydantic", "asyncssh", "httpx", "cryptography",
    "dnspython", "dns", "motor", "bson", "starlette", "anyio",
    "jwt",      # PyJWT
    "pytest",   # tests
}
SELF_PREFIX = "aurem_cto"


def _is_local(mod: str) -> bool:
    return mod == SELF_PREFIX or mod.startswith(f"{SELF_PREFIX}.") or mod.startswith(".")


def _is_allowed(mod: str) -> bool:
    if not mod:
        return True
    if _is_local(mod):
        return True
    root = mod.split(".")[0]
    if root in STDLIB_OK or root in THIRD_PARTY_OK:
        return True
    if mod in ALLOWED_HOST_IMPORTS:
        return True
    # Allow submodules of allowed host imports too (e.g. "config.something").
    for allowed in ALLOWED_HOST_IMPORTS:
        if mod == allowed or mod.startswith(allowed + "."):
            return True
    return False


def _scan_file(path: pathlib.Path) -> list[str]:
    """Returns the list of forbidden imports found in `path` (empty = clean)."""
    src = path.read_text()
    tree = ast.parse(src, filename=str(path))
    bad: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if not _is_allowed(alias.name):
                    bad.append(f"import {alias.name}")
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            # All relative imports (level > 0) are local by definition.
            if node.level > 0:
                continue
            if not _is_allowed(mod):
                bad.append(f"from {mod} import "
                           + ",".join(a.name for a in node.names))
    return bad


def test_isolation_contract():
    offenders: dict[str, list[str]] = {}
    for py in MODULE_ROOT.rglob("*.py"):
        if "__pycache__" in py.parts:
            continue
        bad = _scan_file(py)
        if bad:
            offenders[str(py.relative_to(MODULE_ROOT))] = bad
    assert not offenders, (
        "AUREM CTO isolation contract broken — every host import must be "
        "declared in DEPENDENCIES.md.\nOffenders:\n"
        + "\n".join(f"  {f}: {imps}" for f, imps in offenders.items())
    )


def test_router_prefix_is_aurem_cto():
    """The root mount in __init__.py must declare prefix='/aurem-cto'.
    Sub-routers (under routers/) nest below it with their own prefixes."""
    init_src = (MODULE_ROOT / "__init__.py").read_text()
    assert 'prefix="/aurem-cto"' in init_src, (
        "aurem_cto.__init__.build_router() must mount at /aurem-cto"
    )


def test_collections_namespaced():
    """Heuristic: every `db.<name>` reference under routers/ must use the
    aurem_cto_ prefix (we whitelist a tiny set of host-side reads).

    The trust router intentionally COUNTS rows in legacy host collections
    (developer_deploy_runs, github_deployments, external_uptime_pings,
    referrals, onboarding_*) to surface trust signals — these are
    READ-ONLY counts using `db[\"name\"]` bracket access and stay
    outside this lint."""
    bad: list[str] = []
    import re as _re
    coll_re = _re.compile(r"db\.([a-z_][a-z0-9_]*)")
    HOST_READS = {
        "developer_accounts",       # for PAT lookup in codebase_indexer
        "developer_github_links",   # D-35: actual GitHub PAT storage
        "onboarding_projects",      # gallery + chat-commits hydration
        "onboarding_token_wallets", # streak counter
        "referrals",                # referral counts
        "referral_profiles",
        "verified_referrals",
        "external_uptime_pings",    # uptime badge
    }
    for py in (MODULE_ROOT / "routers").rglob("*.py"):
        src = py.read_text()
        for m in coll_re.finditer(src):
            coll = m.group(1)
            if coll in ("command_cursor", "name", "client"):
                continue
            if coll in HOST_READS:
                continue
            if not coll.startswith("aurem_cto_"):
                bad.append(f"{py.name}: db.{coll}")
    for py in (MODULE_ROOT / "services").rglob("*.py"):
        src = py.read_text()
        for m in coll_re.finditer(src):
            coll = m.group(1)
            if coll in ("command_cursor", "name", "client"):
                continue
            if coll in HOST_READS:
                continue
            if not coll.startswith("aurem_cto_"):
                bad.append(f"{py.name}: db.{coll}")
    assert not bad, f"Non-namespaced collection access: {bad}"
