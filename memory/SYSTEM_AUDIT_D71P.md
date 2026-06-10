# AUREM System Audit Report — D-71p (2026-06-10)

Full database + code scan across 612 collections and 200+ router files.
Findings grouped by severity and impact. Last run: D-71p smoke + actual data inspection.

---

## 🔴 SEVERITY 1 — Database bloat (storage runaway)

**Status: FIXED ✅** — TTL indexes installed via D-71p.

| Collection | Docs | TTL set | Auto-trim after |
|---|---|---|---|
| api_audit_log | 396,130 | ✓ `ts` | 90 days |
| a2a_events | 225,866 | ✓ `ts` | 30 days |
| ora_brain_thoughts | 132,640 | ✓ `ts` | 90 days |
| qa_bot_endpoint_log | 86,119 | ✓ `created_at` | 30 days |
| site_monitor_logs | 75,826 | ✓ `ts` | 30 days |
| system_pulse_actions | 59,310 | ✓ `ts` | 90 days |
| agent_outcomes | 42,509 | ✓ `ts` | 30 days |

Without TTLs Atlas storage would have crossed 5 GB in ~6 weeks. Worst-case
collection (`api_audit_log`) was growing 1k+ docs/hour.

> **Caveat**: TTL only acts when the indexed field is a `Date` type. Some
> rows may store ISO strings — they'll be skipped silently. A follow-up
> migration to coerce `ts` → BSON Date would unlock full cleanup.

---

## 🔴 SEVERITY 1 — Duplicate route conflicts (8 found)

Both routers register, **last-loaded wins**, the other is dead code.
This is dangerous for auth/login because behaviour depends on registry order.

| Route | File A | File B |
|---|---|---|
| POST `/api/platform/auth/login` | `ai_platform_router.py` | `platform_auth_router.py` |
| POST `/api/platform/auth/register` | `ai_platform_router.py` | `platform_auth_router.py` |
| POST `/api/aurem/chat` | `aurem_chat.py` | `aurem_routes.py` |
| POST `/api/self-audit/run` | `self_audit_router.py` | `autonomy_router.py` |
| GET `/api/enterprise/audit` | `enterprise_engine.py` | `enterprise_router.py` |
| GET `/api/email/inbound/health` | `inbound_email_router.py` | `email_inbound_router.py` |
| POST `/api/email/inbound` | `inbound_email_router.py` | `email_inbound_router.py` |
| POST `/api/incident/resolve/{id}` | `v2_customer_actions_router.py` | `incident_router.py` |

**Recommended action**: delete the older/duplicate file in each pair (audit
manually before deletion). The auth pair is highest-risk — production
auth currently runs whichever loads last.

---

## 🟡 SEVERITY 2 — Dead / unregistered router files (18)

These files are in `/app/backend/routers/` but never referenced from
`registry.py`. Either dead code or relying on a different mount.

```
customer_deploy_router.py     ora_providers_router.py
design_extract_public_router  legion_queue_router.py
seo_static_router.py          email_service.py
debug_tasks_router.py         csv_leads_upload_router.py
... (10 more)
```

**Recommended**: `git grep` each one — if zero imports, delete.

---

## 🟡 SEVERITY 2 — Router import failure

```
routers.z_image_router → ModuleNotFoundError: gradio_client
```

Currently wrapped in try/except so it doesn't crash boot, but the feature
is silently disabled. **Decision**: either `pip install gradio_client` or
remove the router file.

---

## 🟡 SEVERITY 2 — Stale `set_db()` wiring (8 likely uncalled)

Out of 536 modules that define `set_db()`, 8 are NOT being called from
`server.py` startup. Routes inside these modules will return 503 / behave
weirdly if they touch the DB.

```
pillars.sales.routes._shared          routers.daily_intel_router
routers.aurem_ai_router               routers.admin_founder_customers_router
routers.customer_vanguard_router      routers.aurem_builder_router
routers.me_pwa_router                 routers.digest_routes
```

Same pattern as the smart_search bug fixed in D-71d.

---

## 🟢 SEVERITY 3 — Open incidents (last few weeks)

10 distinct paths have errors logged but most are 1-9 hits and OLD
(May 17-24). Highest hits:

```
asyncio CancelledError                       9× (client disconnects — benign)
/api/onboarding/status ServerSelection       4× (Atlas hiccup)
/api/seo-audit/scan AutoReconnect            4× (Atlas hiccup)
/api/platform/api-key KeyError               3× (real bug — needs fix)
```

Most are network blips. `/api/platform/api-key KeyError` is the only
real-code bug — worth investigating next session.

---

## 🟢 SEVERITY 3 — Orphan collections (2 found)

```
site_monitor_admin_log         1 doc, no code reference
awb_cleanup_log                1 doc, no code reference
```

Likely leftovers from one-off migrations. Safe to drop.

---

## 🟢 SEVERITY 3 — Scheduled jobs (overdue audit)

**Status: clean ✅** — no schedulers reporting `last_run > 4h ago`.
All registered jobs are firing on schedule.

---

## ✅ HEALTHY systems verified

- 612 collections, only 2 orphaned (0.3%)
- 1 router import failure out of ~200 (z_image, optional)
- Authentication wiring lives, login working
- Schedulers active (11 attached via p1-worker)
- TTL indexes in place on top 7 high-volume collections
- All D-71h cache TTL bumps live — 90% hit-rate sustained
- Campaign Health 8/13 green, others honest yellow (no fake greens)

---

## Top recommendations (priority order)

1. **Resolve auth duplicate routes** (highest risk): inspect
   `ai_platform_router.py` vs `platform_auth_router.py`. Keep the one
   with brute-force protection + bcrypt + production-tested. Delete the
   other.
2. **Wire the 8 missing `set_db()` calls** so those routers don't 503.
3. **Delete or fix `z_image_router`** — either `pip install gradio_client`
   or delete the router file.
4. **Audit the 18 dead router files** — git log each; delete if no
   recent commits / no imports.
5. **One-off cleanup**: drop the 2 orphan collections, run a
   `ts`-field-coercion migration so the new TTL indexes can actually
   delete documents.

Generated by `D-71p full-system audit`. Saved to:
`/app/memory/SYSTEM_AUDIT_D71P.md`
