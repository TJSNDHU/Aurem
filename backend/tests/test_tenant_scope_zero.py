"""test_tenant_scope_zero.py — iter D-83.

Regression gate: the tenant-scope guard must report ZERO violations.

Every Mongo query touching a customer-data collection (campaign_leads,
scan_history, outreach_log, repair_jobs, pending_approvals, ...) must be
scoped by `business_id` (or an accepted equivalent tenant key:
tenant_bin / tenant_email / user_id), or carry an explicit, justified
`# tenant_scope_guard: admin_cross_tenant` inline allow comment.

If this test fails, a new unscoped query was introduced — fix the query,
do NOT weaken the guard. AUREM_TENANT_SCOPE_STRICT=true makes the
backend refuse to boot on violations, so a failure here would also take
production down.
"""
from services.tenant_scope_guard import scan_routers


def test_zero_tenant_scope_violations():
    violations = scan_routers()
    detail = "\n".join(
        f"{v.file}:{v.line}  {v.snippet[:90]}" for v in violations[:25]
    )
    assert len(violations) == 0, (
        f"{len(violations)} tenant-scope violations found:\n{detail}"
    )
