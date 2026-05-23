# T4 Unclassified Endpoint Purge Report
**Date**: 2026-04-23 (iter 276)
**Trigger**: User demanded evidence on 380 "unclassified" endpoints
**Outcome**: **380 → 0** unclassified endpoints. Zero orphans remain.

---

## Root Cause

The classifier in `endpoint_audit_router.py` used a substring-keyword rubric
to assign every endpoint to a Pillar (P1/P2/P3/P4), Sub-Product (T2), Infra
(T0) or Experimental (T3). **380 endpoints** fell to `T4_unclassified` not
because they were dead — but because the keyword list was incomplete.

Evidence: the top T4 router `omnidim_router` had 10 endpoints all handling
voice dispatch (clearly P1/Voice territory), yet none matched any existing
keyword because "omnidim" was missing from the rubric.

---

## Classifier Expansion (iter 276)

### T0 Infra — +28 keywords
`redis, github, settings, mission-control, pillars-map, root-command,
gateway, deployment, provisioning, modularization, db-optimizer, cache,
diagnostic, server-misc, system_routes, system_overview, infra-settings,
business-id, business_routes, activity-feed, legal, admin-links,
admin-cache, hooks, batch, connector, integration_api, upload, pwa,
live-sync, ucp, dashboard-feeds, super-admin, automations, approval_router`

### T1_P1 Acquisition — +16 keywords
`appointment, scheduler, client-manager, attribution, churn,
recovery-comms, resend, omnichannel, trial, viral-gate, honeypot, pixel,
marketing, customer-360, /push/, push_notification`

### T1_P2 Monetization — +5 keywords
`premium, catalog, service-catalog, financials, admin-customers`

### T1_P4 Cognition — +18 keywords
`vector, embedding, approval, swarm, critic, qa-bot, a2a, action-engine,
sentiment, invisible-coach, ai-platform, ai_router, aurem-chat,
openrouter, case-study, conviction, /search/, smart_search`

### NEW Sub-Products (T2) — 4 new SKU buckets
| Bucket | Endpoint Count | 30d Hits | Status |
|---|---|---|---|
| `T2_subproduct_customer_portal` | 24 | 739 | Active (client-facing dashboard) |
| `T2_subproduct_vanguard` | 8 | **5,887** | **HOT** — security sub-product drawing heavy traffic |
| `T2_subproduct_omnidim` | 14 | 2 | Dormant — voice dispatch SKU, wire-up needed |
| `T2_subproduct_aurem_suite` | 23 | 895 | Active (aurem-routes/keys/admin/public-report) |

### T3 Experimental — +3 keywords
`robotics, bitnet, mmx`

---

## Final Tier Distribution (1,704 endpoints)

| Tier | Count | 30d Hits | Notes |
|---|---|---|---|
| T0 Infra | 569 | 14,309 | Heaviest traffic — expected |
| P1 Acquisition | 299 | 1,777 | Sales pipeline + outreach |
| P2 Monetization | 172 | 2,902 | Billing + catalog |
| P3 Sentinel | 190 | 2,862 | Monitoring + healing |
| P4 Cognition | 297 | 3,030 | AI brain + content |
| T2 Sub-Products | 146 | 7,746 | **12 distinct SKUs** |
| T3 Experimental | 39 | 451 | R&D (robotics, bitnet, mmx, etc.) |
| **T4 Unclassified** | **0** | — | **Fully absorbed** |

## Dignity Rollup (unchanged methodology)
- **Alive**: 414 (24%) — last hit within 30d + frontend surface + data + scheduler
- **Ghost**: 726 (43%) — partial signals missing
- **Leaky**: 564 (33%) — minimal evidence, candidates for purge review
- **Dead**: 0

## Hidden Gems Revealed

1. **Vanguard** (`aurem_vanguard_router`): 8 endpoints but 5,887 hits/30d —
   this security sub-product is **clearly in production traffic**. Worth
   promoting to its own Command Block in the sidebar.
2. **Customer Portal** (`customer_portal_router` + `client_portal_router`):
   24 endpoints, 739 hits. Existing but not surfaced prominently in admin UI.
3. **OmniDim** (`omnidim_router` + A2A handoff): 14 endpoints, only 2 hits.
   Voice dispatch SKU built but not activated. Wire-up candidate for Phase 2.
4. **Aurem Suite** (keys/admin/public-report): 23 endpoints, 895 hits.
   Foundational operations layer, needs own admin page.

## Next Actions

1. Pillars Map UI (`AdminPillarsMap.jsx`) now shows 4 new T2 buckets with
   proper labels.
2. Phase 2 excavation can now target Vanguard + OmniDim as highest-value
   resurrection candidates (based on existing endpoint count vs. current
   traffic ratio).
