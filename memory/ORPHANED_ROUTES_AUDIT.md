# Orphaned Routes Audit — server.py

## Date: April 6, 2026

## Summary
server.py contains ~1,288 routes across 113 API prefixes. 
55+ routes in server.py have NO frontend callers (legacy from pre-AUREM app).

## Safe to Remove (Legacy App Routes — Not Used by AUREM)
These are from the original aurem.live skincare app. None are called by AUREM frontend.

| Prefix | Routes | Type |
|--------|--------|------|
| /admin/clinical-logic | 5 | Skincare clinical logic |
| /admin/marketing-lab | 7 | Old marketing lab |
| /admin/marketing-programs | 3 | Old marketing programs |
| /admin/paypal-links | 2 | PayPal link management |
| /admin/referral-programs | 3 | Old referral system |
| /admin/referral-stats | 1 | Referral analytics |
| /admin/shipping-policy | 1 | Shipping policy editor |
| /admin/founding-pricing | 1 | Founding member pricing |
| /admin/generate-product-details | 1 | Product detail generator |
| /admin/marketing-audience | 1 | Audience targeting |
| /admin/security-settings | 1 | Old security settings |
| /admin/security-status | 1 | Old security status |
| /ai/generate-product-engine | 1 | AI product generator |
| /ai/science-assistant | 1 | Skincare science AI |
| /ai/science-content | 1 | Science content generator |
| /categories | 2 | Product categories CRUD |
| /products/{id} | 1 | Product detail |
| /founding-member/pricing | 1 | Founding member pricing |
| /marketing-programs | 1 | Public marketing programs |
| /paypal-links/match | 1 | PayPal link matching |
| /public/paypal-links | 1 | Public PayPal links |
| /quiz/* | 2 | Skin quiz system |
| /shipping-policy | 1 | Public shipping policy |
| /site-content/* | 7 | CMS content (hero, footer, etc) |
| /sms/* | 2 | SMS verification |
| /transformation-calendar/* | 4 | Skincare calendar |
| /zip-code/lookup | 1 | Zip code lookup |
| /webhook/whapi | 2 | WhAPI webhooks |

**Total legacy routes: ~55**

## DO NOT Remove (Active AUREM Routes)
All routes under these prefixes are actively used:
- /api/auth, /api/aurem, /api/critic, /api/security, /api/openrouter
- /api/clawchief, /api/highsignal, /api/ora, /api/shopify*
- /api/payments, /api/enrichment, /api/attribution, /api/comms
- /api/repair, /api/scanner, /api/intelligence, /api/voice
- /api/health, /api/leads, /api/crm-sync, /api/integration

## Recommendation
Remove legacy routes in a dedicated session with:
1. Backup server.py first
2. Remove one prefix group at a time
3. Run full test suite after each removal
4. Never remove more than 10 routes per commit
