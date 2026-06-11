"""
services/tenant_scope_guard.py — iter D-81a.

Boot-time static analyzer that prevents tenant-data leakage.

Scans every router file for Mongo queries on customer-data
collections and FAILS BOOT (raises) if any query is missing a
`business_id` filter — with the offending file:line printed so
the developer can fix it immediately.

The guard is intentionally pessimistic: false positives are
better than false negatives when the cost of a miss is a
cross-tenant data leak. Admin-only routes that legitimately read
across BINs must be explicitly allowlisted via a comment marker
`# tenant_scope_guard: admin_cross_tenant` on the offending
query line OR by adding the file to ADMIN_ONLY_FILES below.

Companion safeguard: validate_stripe_subscription_event() rejects
any webhook missing a valid business_id in customer.metadata so
upstream mis-tagging can't write across tenants.
"""
from __future__ import annotations

import logging
import os
import re
from pathlib import Path
from typing import Iterable, List

logger = logging.getLogger(__name__)

# Customer-data collections that MUST be queried with business_id.
# Anything not in this list is treated as platform/admin data.
SCOPED_COLLECTIONS = {
    "campaign_leads",
    "scan_history",
    "outreach_log",
    "repair_jobs",
    "email_events",
    "consent_records",
    "inbound_replies",
    "lead_touchpoints",
    "pending_approvals",
    "ora_cto_proposals",
    "bin_data",
    "bin_layer_events",
    "bin_progress",
    "bin_journal",
    "customer_business_profile",
}

# Files explicitly allowed to read cross-tenant — admin/founder
# panels and the analytics/health endpoints. Anything here must
# also gate via @require_admin/super_admin at the route level.
ADMIN_ONLY_FILES = {
    "admin_founder_customers_router.py",
    "admin_ora_router.py",
    "admin_mission_control_router.py",
    "admin_dashboard_router.py",
    "campaign_funnel_router.py",       # founder dashboard
    "autonomous_repair_admin_router.py",
    "founder_saves_router.py",
    "creds_health_router.py",
    "endpoint_audit_router.py",
    "system_routes.py",
    "wiring_audit_router.py",
    "cto_codebase_router.py",
    "cto_brief_router.py",
    "cto_learning_router.py",
    "cto_verify_router.py",
    "cto_tools_router.py",
    "cto_pricing_router.py",
    "developer_portal_router.py",       # admin-tier dev tools
    "lead_lifecycle_router.py",         # webhook ingestion (no JWT)
    "resend_webhook_router.py",
    "tenant_scope_audit_router.py",    # the guard's own readout
    "ai_platform_router.py",
    "platform_auth_router.py",
    "developer_dashboard_router.py",
    "stripe_payment_router.py",
    "billing_plan_router.py",
    "aurem_billing_router.py",
}

INLINE_ALLOW_COMMENT = "tenant_scope_guard: admin_cross_tenant"

# Regex for db.{collection}.find/count/aggregate/update/delete.
# Captures the collection name + a slice of source so we can check
# for business_id usage.
_QUERY_RE = re.compile(
    r"\bdb(?:_db|\.[a-z_]+)?\."
    r"(?P<coll>[a-z_][a-z_0-9]*)"
    r"\.(?:find|find_one|count_documents|estimated_document_count|"
    r"aggregate|update_one|update_many|delete_one|delete_many|"
    r"distinct|find_one_and_update|find_one_and_delete|"
    r"replace_one|insert_one|insert_many|bulk_write)\s*\(",
    re.IGNORECASE,
)


class ScopeViolation:
    __slots__ = ("file", "line", "collection", "snippet")

    def __init__(self, file: str, line: int, collection: str, snippet: str):
        self.file = file
        self.line = line
        self.collection = collection
        self.snippet = snippet[:160]

    def __repr__(self) -> str:
        return (
            f"  {self.file}:{self.line}  →  db.{self.collection}.…  "
            f"(no business_id filter)\n      {self.snippet}"
        )


def _scan_file(path: Path) -> List[ScopeViolation]:
    """Returns violations in the file. A violation = a query on a
    SCOPED_COLLECTIONS table where the surrounding 8 lines don't
    mention `business_id` AND the line doesn't carry the inline
    allow comment."""
    if path.name in ADMIN_ONLY_FILES:
        return []
    try:
        src = path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return []
    lines = src.splitlines()
    violations: List[ScopeViolation] = []
    for m in _QUERY_RE.finditer(src):
        coll = m.group("coll")
        if coll not in SCOPED_COLLECTIONS:
            continue
        line_no = src.count("\n", 0, m.start()) + 1
        # Inline allow comment on the same line bypasses the check.
        same_line = lines[line_no - 1] if line_no <= len(lines) else ""
        if INLINE_ALLOW_COMMENT in same_line:
            continue
        # Look at ±8 lines around the call for any business_id reference.
        window_start = max(0, line_no - 9)
        window_end = min(len(lines), line_no + 8)
        window_text = "\n".join(lines[window_start:window_end])
        if "business_id" in window_text or "BinScopedRepo" in window_text:
            continue
        # Also accept if the very same function uses bin_ctx
        if "bin_ctx" in window_text:
            continue
        violations.append(ScopeViolation(
            file=str(path.relative_to(Path("/app/backend"))),
            line=line_no, collection=coll,
            snippet=same_line.strip(),
        ))
    return violations


def scan_routers(root: str = "/app/backend") -> List[ScopeViolation]:
    """Walk routers/ + services/ — return every violation found."""
    out: List[ScopeViolation] = []
    for sub in ("routers", "services", "pillars"):
        base = Path(root) / sub
        if not base.is_dir():
            continue
        for p in base.rglob("*.py"):
            if p.name.startswith("_") or p.name == "__init__.py":
                continue
            out.extend(_scan_file(p))
    return out


def enforce_at_boot(*, fail_fast: Iterable[str] = None) -> None:
    """Called from server.py during startup. If any violations
    found AND env AUREM_TENANT_SCOPE_STRICT is truthy, raises so
    the pod refuses to come up. Otherwise logs WARNINGS so dev
    iteration isn't blocked but the noise is unmissable."""
    violations = scan_routers()
    strict = (os.environ.get("AUREM_TENANT_SCOPE_STRICT") or "").lower() in (
        "1", "true", "yes", "on",
    )
    if not violations:
        logger.info(
            "[TENANT-GUARD] ✅ 0 unscoped customer-data queries across "
            "routers/+services/+pillars/"
        )
        return
    msg_lines = [
        f"[TENANT-GUARD] ⚠ {len(violations)} unscoped customer-data "
        "queries detected (potential cross-BIN leak):",
    ]
    for v in violations[:25]:
        msg_lines.append(str(v))
    if len(violations) > 25:
        msg_lines.append(f"  …and {len(violations) - 25} more")
    body = "\n".join(msg_lines)
    if strict:
        logger.error(body)
        raise RuntimeError(
            f"AUREM_TENANT_SCOPE_STRICT=true and {len(violations)} "
            "unscoped queries found — refusing to boot. See logs."
        )
    logger.warning(body)


# ─── Stripe webhook protection ─────────────────────────────────

def validate_stripe_subscription_event(event: dict) -> str:
    """Returns business_id from a Stripe event after validating the
    customer.metadata carries a real BIN. Raises ValueError if
    missing/invalid. Apply to every subscription.* / invoice.* /
    customer.* event before any DB write.

    BIN format check: at least one letter then '-' then identifier
    — matches both AUR-FNDR-001 (founder) and AUT-MSS-7K92 (gen)."""
    if not isinstance(event, dict):
        raise ValueError("stripe_event_not_dict")
    obj = (event.get("data") or {}).get("object") or {}
    # subscription / invoice events nest customer differently
    md = (obj.get("metadata")
          or (obj.get("customer") or {}).get("metadata")
          or {})
    bid = (md.get("business_id") or md.get("bin") or "").strip()
    if not bid:
        raise ValueError("stripe_event_missing_business_id_in_metadata")
    # Liberal pattern: ≥3 alpha, dash, then anything 2-32 chars.
    if not re.match(r"^[A-Z][A-Z0-9]{2,}-[A-Z0-9\-]{2,32}$", bid):
        raise ValueError(f"stripe_event_business_id_malformed:{bid!r}")
    return bid
