# AUREM (aurem.live) — Admin + Customer Interface Blueprint
### Code-level audit + reorganization plan · June 12, 2026
Read by Claude: full route map (App.js, 177 routes), router registry (4,666 lines),
RouteGuards, wiring_audit_router manifest, platform/ (200+ components),
platform/customer/ + platform/luxe/, registry LEAN config + prune lists.

---

## PART 1 — CONFIRMED PROBLEMS (verified in code, not guessed)

### P0-1 · Secret file committed in repo
`/.jwt_secret` (64 bytes) sits at repo root. Anyone with repo access can mint
admin JWTs (AdminGuard only checks `role=admin` claims signed with this).
**Fix:** rotate the secret, delete the file, add to .gitignore, purge from git
history (`git filter-repo --path .jwt_secret --invert-paths`), keep the
3-tier resolver in config.py (env → file → ephemeral) but the file must
never be committed.

### P0-2 · The entire 12-page customer portal is ORPHANED
`platform/customer/` contains a complete portal: CustomerHome, CustomerWebsite,
CustomerReviews, CustomerSocial, CustomerReport, CustomerReferrals,
CustomerBilling, CustomerOra, CustomerSettings, CustomerOnboarding,
CustomerIntegrations + widgets. **Zero imports anywhere.**
Meanwhile App.js routes ALL of `/my/*` to `LuxeDashboardPreview` (a single
component with internal tabs, no URL sub-routing), and your own
`wiring_audit_router.py` CUSTOMER_CHECKLIST still declares `/my/website`,
`/my/reviews`, `/my/social`, `/my/report`, `/my/settings`, `/my/referrals`,
`/my/ora` as the canonical customer surface — pages that currently all render
the same preview dashboard.
**Fix:** Part 3 below — wire the customer pages under a guarded shell.

### P0-3 · TenantGuard exists but is used NOWHERE
`platform/RouteGuards.jsx` exports TenantGuard ("Any logged-in user accesses
/dashboard/*") — App.js never imports it. `/dashboard` and `/dashboard/*`
mount AuremDashboard with no route-level guard.
**Fix:** `<Route element={<TenantGuard><Outlet/></TenantGuard>}>` around the
dashboard block (exact code in Part 3).

### P0-4 · Unguarded operational pages
These routes are outside every guard and the components contain no auth check
(verified by grep — no token/Navigate-to-login logic):
- `/leads` → LeadsDashboard
- `/settings/panic` → PanicSettings
- `/alerts/panic` → PanicAlerts
Even if their APIs 401, the pages render and leak UI/feature surface.
**Fix:** move under TenantGuard (they are tenant features) — Part 3.

### P1-5 · 41 frontend API calls have no static backend match
Cross-check script (delivered: `scripts/wiring_check.py`) found 41 frontend
`/api/...` calls with no matching backend route in static analysis. Some are
parser noise (template literals), some are LEAN-prune victims, some are real
gaps. **Don't trust the static list blindly** — run the live mode against
`/openapi.json` (script does this) or extend your existing
`wiring_audit_router` checklists with these candidates. Highest-suspicion:
`/api/analytics/dashboard`, `/api/analytics/revenue`, `/api/accounting/*`,
`/api/loyalty/*`, `/api/sales/pipeline`, `/api/customer/scan-schedule`,
`/api/sentinel/fixes-log`, `/api/site-monitor/me/sites`,
`/api/admin/truth-ledger`, `/api/admin/evolver/status`.

### P1-6 · LEAN prune list can silently kill live features
`_registry_lean_prune.py` deletes ~1,600 routes in production by path prefix,
justified as "0 frontend refs" — but nothing enforces that claim over time.
One drift = a working preview feature that 404s in prod only.
**Fix:** add a CI test that extracts frontend `/api/` refs (wiring_check.py
does this) and fails if any ref matches a prune prefix or skip-listed router.

### P1-7 · Admin IA sprawl: 60+ routes vs "32 sidebar items"
The admin surface has ~60 live pages + 8 alias redirects. README promises 32
sidebar items. Pages like hunter-test, openfang, case-study, design-extract
sit at top level beside boardroom. **Fix:** Part 2 consolidation.

### P2-8 · Duplicates & dead weight
- `pages/MyBilling.jsx` (routed at /my/billing) duplicates
  `platform/customer/CustomerBilling.jsx` (orphaned) — keep ONE (Part 3 keeps
  CustomerBilling, deletes MyBilling).
- ~35 platform components imported nowhere (script lists them:
  `wiring_check.py --orphans`) — e.g. SuperAdminDashboard, DarkScoutDashboard,
  NegotiationDashboard, GEODashboard. Archive or wire deliberately.
- Catch-all `*` → Navigate("/") = soft-404 (same issue as auremcto repo);
  add a real NotFound page.

---

## PART 2 — ADMIN INTERFACE (founder cockpit) · final structure

Consolidate ~60 pages into 9 sidebar groups. No page deleted — grouped,
merged into tabs, or demoted to Labs. AdminShell already supports this.

**1. Boardroom** (home — /admin/boardroom)
   Morning brief, P&L, KPIs, founder-saves, daily-log

**2. Mission Control** (/admin/mission-control)
   Campaign command, campaign health, leads-mining, apollo-cost,
   hunt/scout views — as tabs of one page, not 5 sidebar items

**3. Customers** (/admin/customers)
   Customer-health panel, Customer 360 (/admin/customer/:id),
   founder-customers, impersonation-log, plans manager

**4. ORA** (/admin/ora — already unified with ?tab=)
   chat · cockpit · optimizer · settings (existing tabs)
   + fold in: council-audit, brain, brain-graph, watchdog, voice, skills
   (each becomes a tab; their routes 301 to /admin/ora?tab=X like the
   existing ora-chat/ora-cto redirects already do)

**5. Sentinel & Self-Repair** (/admin/sentinel)
   sentinel (diagnostics) · auto-fixer · self-repair · stem-fix ·
   incident-ledger · git-gate · vanguard
   + NEW: **Supply-Chain tab** (the D-82b work: 250 findings, 3 lanes,
   "Apply safe upgrades" button hitting POST /remediate?auto_apply=true)

**6. System Health** (/admin/system)
   system-overview · system-pulse-live · codebase-health · wiring-audit ·
   system-audit · site-monitor · pillars-map · breakers · cache

**7. Revenue** (/admin/revenue)
   financials · analytics · apollo budget · sovereignty-score

**8. Security & Access** (/admin/security)
   security-keys · api-keys · 2FA enroll · business-ids · SSOT ·
   developer-signups

**9. Labs** (collapsed by default)
   hunter-test · openfang · case-study · design-extract · evolver ·
   avatar-manager · memoir · blocks · browser-agent

Rules that make it "properly managed":
- Every admin page lives in exactly ONE group; aliases stay as redirects.
- Every sidebar item maps 1:1 to a row in wiring_audit ADMIN_CHECKLIST —
  the audit page then verifies the whole sidebar automatically.
- Anything not in a group after this exercise goes to `_archive/`.

---

## PART 3 — CUSTOMER INTERFACE (/my) · final structure + exact code

Adopt the orphaned `platform/customer/` pages as the real portal, Luxe as the
visual shell. URL-routed (deep-linkable, matches your own audit manifest).

**Portal map (9 routes):**
| Route | Page | Backend (already exists per manifest) |
|---|---|---|
| /my | LuxeDashboard home (keep) | /api/customer/* aggregate |
| /my/website | CustomerWebsite | /api/customer/website, scan-history, github/status, tokens |
| /my/reviews | CustomerReviews | /api/customer/reviews |
| /my/social | CustomerSocial | /api/customer/social/status |
| /my/report | CustomerReport | /api/customer/reports |
| /my/referrals | CustomerReferrals | /api/customer/referrals |
| /my/billing | CustomerBilling (delete pages/MyBilling.jsx) | /api/stripe-embed/* |
| /my/ora | CustomerOra | /api/bin-auth/customer-context |
| /my/settings | CustomerSettings (+ onboarding resume) | /api/customer/api-key, smart-onboarding |

**Step 1 — CustomerGuard** (add to platform/RouteGuards.jsx, mirrors AdminGuard):
```jsx
export const CustomerGuard = ({ children }) => {
  const [status, setStatus] = useState('checking');
  useEffect(() => {
    const token = localStorage.getItem('aurem_customer_token');
    if (!token) return setStatus('no_token');
    const payload = decodeToken(token);
    if (!payload) { clearCustomerAuth(); flagSessionExpired('customer'); return setStatus('invalid'); }
    if (isExpired(payload)) { clearCustomerAuth(); flagSessionExpired('customer'); return setStatus('expired'); }
    setStatus('authorized');
  }, []);
  if (status === 'checking') return null;
  if (status !== 'authorized') return <Navigate to="/my" replace />; /* LuxeAuthOverlay handles login on /my */
  return children;
};
```

**Step 2 — App.js route block** (replace the current 3-line /my block):
```jsx
import { CustomerGuard, TenantGuard } from './platform/RouteGuards';
const CustomerShell    = React.lazy(() => import('./platform/customer/CustomerShell'));
const CustomerWebsite  = React.lazy(() => import('./platform/customer/CustomerWebsite'));
const CustomerReviews  = React.lazy(() => import('./platform/customer/CustomerReviews'));
const CustomerSocial   = React.lazy(() => import('./platform/customer/CustomerSocial'));
const CustomerReport   = React.lazy(() => import('./platform/customer/CustomerReport'));
const CustomerReferrals= React.lazy(() => import('./platform/customer/CustomerReferrals'));
const CustomerBilling  = React.lazy(() => import('./platform/customer/CustomerBilling'));
const CustomerOra      = React.lazy(() => import('./platform/customer/CustomerOra'));
const CustomerSettings = React.lazy(() => import('./platform/customer/CustomerSettings'));

{/* Customer portal — Luxe home stays public-with-overlay, sub-pages guarded */}
<Route path="/my" element={<LuxeDashboardPreview />} />
<Route element={<CustomerGuard><CustomerShell /></CustomerGuard>}>
  <Route path="/my/website"   element={<CustomerWebsite />} />
  <Route path="/my/reviews"   element={<CustomerReviews />} />
  <Route path="/my/social"    element={<CustomerSocial />} />
  <Route path="/my/report"    element={<CustomerReport />} />
  <Route path="/my/referrals" element={<CustomerReferrals />} />
  <Route path="/my/billing"   element={<CustomerBilling />} />
  <Route path="/my/ora"       element={<CustomerOra />} />
  <Route path="/my/settings"  element={<CustomerSettings />} />
</Route>
<Route path="/my/*" element={<Navigate to="/my" replace />} />

{/* Tenant dashboard + tenant tools — finally use TenantGuard */}
<Route element={<TenantGuard><Outlet /></TenantGuard>}>
  <Route path="/dashboard"   element={<AuremDashboard />} />
  <Route path="/dashboard/*" element={<AuremDashboard />} />
  <Route path="/leads"          element={<LeadsDashboard />} />
  <Route path="/settings/panic" element={<PanicSettings />} />
  <Route path="/alerts/panic"   element={<PanicAlerts />} />
</Route>
```
(CustomerShell = thin wrapper: Luxe tokens + left nav of the 8 items +
<Outlet/>. If you want, ORA can generate it from LuxeDashboardPreview's
sidebar in one task.)

**Step 3 — Update wiring_audit_router.py** CUSTOMER_CHECKLIST stays as-is —
it now becomes TRUE instead of aspirational. Add the new routes to the
sitemap-equivalent and run GET /api/admin/wiring-audit to verify green.

---

## PART 4 — EXECUTION ORDER (hand this to ORA / developer)

1. **Day 1 (security):** P0-1 secret rotation + history purge.
2. **Day 1:** Add CustomerGuard, wire Part 3 route block, create CustomerShell.
   Delete pages/MyBilling.jsx. Smoke: /my/website renders + auth-gates.
3. **Day 2:** TenantGuard wrap (/dashboard, /leads, panic pages). NotFound page
   replaces catch-all redirect.
4. **Day 2:** Run `python scripts/wiring_check.py --live https://aurem.live`
   → fix/registry the real gaps from the 41 candidates; add the CI test
   (P1-6) so prune-list drift fails the build.
5. **Day 3:** Admin sidebar regroup to the 9 groups (config-only change in
   AdminShell sidebar data; pages untouched). Add Supply-Chain tab to
   Sentinel (D-82b endpoints already live: /remediate, /remediations).
6. **Day 3:** Archive orphan components list from `wiring_check.py --orphans`.
7. Re-run GET /api/admin/wiring-audit → everything "ok"/"wired", zero
   "missing". That endpoint is now your permanent regression gate.

## Deliberate honesty notes
- The "41 missing endpoints" list is static analysis — treat as candidates,
  verify live. Your registry is dynamic (LEAN mode, prefix variance) and a
  static parser can't see everything.
- I did NOT verify every one of the ~60 admin pages' internal data calls —
  the wiring-audit endpoint + script combo is the scalable way to do that,
  not manual reading.
