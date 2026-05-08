# AUREM Cross-Platform Migration Audit
## From Shopify-Centric Tool to Universal Commercial Operating System
**Date**: April 6, 2026 | **Auditor**: AUREM Engineering

---

## EXECUTIVE SUMMARY

AUREM is **75% platform-agnostic** today. The core AI engine (ORA Chat, V2V Voice, ULTRAPLINIAN Scorer, Invoice System, Revenue Engine) has **zero Shopify dependencies**. The Shopify coupling is surgically isolated in 7 dedicated files. Migration to a Universal Commercial OS requires:
1. Building a **Universal Connector Middleware** layer
2. Generalizing 2 MongoDB collections
3. Creating a **Generic Tracking Pixel** to replace the Shopify-only Web Pixel
4. Adding CSV/API product import alongside Shopify GraphQL

---

## 1. DATABASE AUDIT ("The Memory")

### 1.1 Schema Generalization

| Collection | Shopify-Dependent? | Fix Required |
|---|---|---|
| `tenant_customers` | **Partially** — `source` field accepts `shopify_sync` but also `manual`, `bulk_import`, `enrichment`, `web_scrape`. Schema is already generalized. | LOW: Add `woocommerce_sync`, `magento_sync`, `csv_import` to source enum |
| `shopify_connections` | **YES** — Hard-coded to Shopify OAuth + GraphQL structure | HIGH: Rename to `platform_connections` with a `platform_type` discriminator field (`shopify`, `woocommerce`, `magento`, `stripe`, `manual`) |
| `shopify_products` | **YES** — Uses Shopify GraphQL GID format (`gid://shopify/Product/...`) | HIGH: Rename to `products` with a `source_platform` field. Normalize product schema to accept any source |
| `invoices` | **NO** — Fully platform-agnostic. Supports e-transfer, cheque, cash, Stripe | NONE |
| `payments` | **NO** — Generic payment recording | NONE |
| `ora_chat_sessions` | **NO** — Pure AI conversation storage | NONE |
| `knowledge_base` | **NO** — Platform-agnostic training data | NONE |
| `revenue_events` | **NO** — Generic event tracking | NONE |

### 1.2 Multi-Tenant Isolation Verdict
**ROBUST.** Every query in every router uses `tenant_id` from JWT. A merchant CAN have both a Shopify store and a local shop using manual invoicing — the `tenant_id` is derived from the user account, NOT from the Shopify domain. The only exception is `shopify_webhook_router.py` which constructs `tenant_id = f"shopify_{shop_domain}"` for webhook-initiated operations — this needs to map to the actual user tenant.

**Fix**: Create a lookup table `platform_tenant_map` that maps `shopify_shop_domain -> tenant_id`, so webhooks from any platform can resolve to the correct tenant.

---

## 2. ENGINE AUDIT ("The Brain")

### 2.1 AI Context Injection

| Component | Shopify-Dependent? | Status |
|---|---|---|
| ORA Chat (`aurem_chat.py`) | **NO** | Clean. Pulls context from `knowledge_base` collection |
| V2V Voice Engine (`v2v_stream_engine.py`) | **NO** | Clean. Uses generic Whisper STT + GPT-4o + TTS |
| ULTRAPLINIAN Scorer (`ultraplinian_scorer.py`) | **NO** | Clean. Scores on 5 axes: Completeness, Structure, Data Integrity, Directness, Relevance. Zero brand-specific logic |
| Intelligence Engine (`intelligence_engine.py`) | **NO** | Clean. No Shopify references |
| AI Repair Engine (`ai_repair_router.py`) | **NO** | Fetches any URL's HTML via `httpx` and repairs SEO/accessibility. NOT Liquid-specific — uses BeautifulSoup for generic HTML parsing |

**Verdict**: The AI brain is already a **Universal Connector**. It can analyze any website (HTML, React, WordPress). The only missing piece is a **product context loader** that can ingest products from CSV, API, or SQL alongside Shopify GraphQL.

### 2.2 ULTRAPLINIAN Scorer Audit
The scorer is **fully platform-agnostic**. It evaluates AI response quality using linguistic patterns (preamble detection, hedge patterns, completeness metrics). It does NOT check for "Shopify Brand Voice" or any platform-specific criteria. It can score responses for a B2B wholesaler or local service business identically.

---

## 3. "WHOLE STACK" GAP ANALYSIS

### 3.1 Feature-by-Feature Platform Dependency Matrix

| Feature | Platform Status | Gap |
|---|---|---|
| **Invoice System** | UNIVERSAL | None. Supports cash, cheque, e-transfer, Stripe scaffold |
| **Invoice PDF Generation** | UNIVERSAL | None. ReportLab-based, no platform deps |
| **Payment Reminders** | UNIVERSAL | None. Works with any invoice regardless of source |
| **Revenue Dashboard** | UNIVERSAL | None. Aggregates from generic `payments` collection |
| **Sales Pipeline** | UNIVERSAL | None. Generic deal tracking |
| **Customer Scanner** | MOSTLY UNIVERSAL | Customer source includes `shopify_sync` but supports manual/CSV import |
| **ORA Chat AI** | UNIVERSAL | None. Knowledge base is platform-agnostic |
| **V2V Voice Agent** | UNIVERSAL | None. WebSocket-based, platform-independent |
| **AI Training Center** | UNIVERSAL | None. Trains on uploaded knowledge, not platform data |
| **Cart Recovery** | **SHOPIFY-DEPENDENT** | Uses Shopify webhooks (`orders/create`, `checkouts/create`). Needs a Generic Tracking Pixel for custom sites |
| **Product Sync** | **SHOPIFY-DEPENDENT** | Uses Shopify GraphQL Admin API. Needs CSV/API import alternative |
| **Attribution Tracking** | **PARTIALLY DEPENDENT** | Token system is generic, but webhook matching assumes Shopify order format |
| **SEO Repair** | UNIVERSAL | Uses `httpx` + BeautifulSoup. Can repair any HTML site |
| **Shopify App Bridge** | **SHOPIFY-ONLY** | Expected — this is the Shopify embed layer |
| **Web Pixel (ORA Pixel)** | **SHOPIFY-ONLY** | Runs in Shopify's Web Pixel sandbox. Needs a standalone JS alternative |

### 3.2 Cart Recovery — Gap Analysis
**Current**: Shopify webhooks (`checkouts/create`, `orders/create`) trigger cart recovery flows.
**Needed**: 
- A **Generic Tracking Pixel** (`<script src="https://aurem.live/pixel.js">`) that works on ANY website
- The pixel captures: page views, add-to-cart events, checkout starts, checkout completions
- Events POST to `/api/pixel/events` with a `platform: "generic"` flag
- Recovery engine triggers on abandoned events regardless of source

### 3.3 Payments — Gap Analysis
**Current**: Invoice-to-Ledger flow is COMPLETE for manual payments (cash, cheque, e-transfer). Stripe scaffold exists but requires live keys.
**Needed**: The manual Invoice → Payment → Ledger flow is ready for non-e-commerce businesses. The gap is only in auto-reconciliation: when a Stripe payment comes in, auto-match it to an invoice. This is a Stripe webhook integration, not a Shopify dependency.

### 3.4 SEO Repair — Gap Analysis
**Current**: `ai_repair_router.py` fetches ANY URL via `httpx`, parses with BeautifulSoup, and generates AI-powered SEO fixes. It is NOT Liquid-specific.
**Needed**: NONE. It already handles generic HTML/React. For deployment, the fixes are stored in `pending_approval` state. A deployment mechanism (FTP, Git push, API call) is needed for non-Shopify sites.

---

## 4. V2V OUTBOUND EXPANSION

### 4.1 Current State
V2V Voice Agent is inbound-only (customer calls in via WebSocket). The engine uses:
- Whisper STT (speech-to-text)
- GPT-4o (conversation)
- TTS (text-to-speech)
- WebSocket transport (secure `wss://`)

### 4.2 Outbound Feasibility
**Trigger Points Available Today:**
- Stripe Payment Failure → Can trigger via Stripe webhook `payment_intent.payment_failed`
- Manual Invoice Overdue → Already tracked in `invoices` collection with `overdue` status
- Abandoned Cart (Shopify) → Via webhook
- Pipeline Deal Stagnation → Via Sales Pipeline status check

**What's Needed for Outbound:**
1. A **Trigger Engine** that watches events (payment failures, overdue invoices) and initiates calls
2. Integration with a telephony provider (Twilio Voice, Vapi) for outbound SIP/PSTN calls
3. Call scripts generated from invoice/deal context by GPT-4o
4. Call outcome recording back into the relevant invoice/deal record

**Distance**: ~60% of the logic exists. The trigger events exist, the AI conversation engine exists. The missing piece is the telephony bridge (Twilio/Vapi) and the trigger-to-call orchestration layer.

---

## 5. HARD-CODED RED FLAGS

### 5.1 `shopify_` Prefixed Files (7 total)
| File | Purpose | Action |
|---|---|---|
| `routers/shopify_sync_engine.py` | Customer sync via GraphQL | Refactor to `external_sync_engine.py` with platform adapter pattern |
| `routers/shopify_webhook_router.py` | Order/inventory/product webhooks | Refactor to `webhook_router.py` with platform discriminator |
| `routers/shopify_storefront_engine.py` | Product catalog + connection management | Refactor to `storefront_engine.py` |
| `routers/shopify_billing_router.py` | Shopify usage charges | Keep as-is (Shopify-specific billing is a real feature) |
| `routers/shopify_app_store.py` | App listing metadata | Keep as-is (Shopify App Store specific) |
| `routers/shopify_listing_router.py` | App store screenshots/assets | Keep as-is |
| `services/shopify_live_sync_service.py` | Background sync service | Refactor to `external_sync_service.py` with platform adapters |

### 5.2 `.liquid` Files
**NONE FOUND.** Zero `.liquid` files exist in the codebase. The SEO repair engine works on generic HTML.

### 5.3 App Proxy Dependency
**NONE.** ORA Chat is a standalone embeddable widget (`services/chat_widget.py`) that serves its own JavaScript. It does NOT rely on Shopify's `apps/aurem` proxy.

### 5.4 MongoDB Collection Names
- `shopify_connections` → Should rename to `platform_connections`
- `shopify_products` → Should rename to `products`

---

## 6. UNIVERSAL CONNECTOR MIDDLEWARE — Architecture Blueprint

```
                    +--------------------+
                    | Universal Connector|
                    |    Middleware       |
                    +--------+-----------+
                             |
              +--------------+--------------+
              |              |              |
    +---------+    +---------+    +---------+
    | Shopify |    |WooCommerce|  | Manual  |
    | Adapter |    | Adapter  |   | CSV/API |
    +---------+    +---------+    +---------+
              |              |              |
              +--------------+--------------+
                             |
                    +--------+-----------+
                    |  Unified Data      |
                    |  Model (MongoDB)   |
                    +--------------------+
```

### Implementation Steps:
1. Create `services/universal_connector.py` with adapter pattern
2. Rename `shopify_connections` → `platform_connections` with `platform_type` field
3. Rename `shopify_products` → `products` with `source_platform` field
4. Build CSV product import endpoint (`POST /api/products/import/csv`)
5. Build generic webhook receiver (`POST /api/webhooks/{platform}`)
6. Create standalone tracking pixel (`/static/pixel.js`)

---

## 7. PRIORITY IMPLEMENTATION ROADMAP

### Phase 1: Foundation (P0)
- [x] Invoice System (platform-agnostic) — DONE
- [x] Revenue Dashboard — DONE
- [x] PDF Generation — DONE
- [x] Payment Reminders — DONE
- [ ] Rename `shopify_connections` → `platform_connections`
- [ ] Rename `shopify_products` → `products`
- [ ] Create `services/universal_connector.py` base

### Phase 2: Product Import (P1)
- [ ] CSV product import endpoint
- [ ] Generic REST API product import
- [ ] Product context loader for ORA Chat (any source)

### Phase 3: Tracking & Recovery (P1)
- [ ] Standalone JavaScript tracking pixel
- [ ] Generic webhook receiver for WooCommerce/Stripe
- [ ] Platform-agnostic cart recovery engine

### Phase 4: Outbound Voice (P2)
- [ ] Trigger engine for overdue invoices → outbound call
- [ ] Telephony bridge (Twilio Voice/Vapi)
- [ ] Call script generation from deal/invoice context
