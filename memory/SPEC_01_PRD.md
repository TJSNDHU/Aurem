# SPEC 01 — Product Requirements Document (PRD)

> Read second, after SPEC_INDEX.md. Updated 2026-05-28, iter D-57.
>
> Live diary of completed iters: `PRD.md` (append-only).
> Older 322a→322fa-era platform metrics + Legion Bridge context:
> `SYSTEM_OVERVIEW.md` (REFERENCE).

## App name

**AUREM** — *Autonomous Business Operating System for Canadian SMBs*

## One-line idea

A self-running OS that finds local SMBs, books them, runs their ops on
autopilot (campaigns, scheduling, reviews, finances), and is built /
maintained by the founder through a single chat called **AUREM CTO**.

## Target users (personas)

1. **Founder (Tejinder Sandhu)** — operates the entire platform via
   plain-English chat with ORA (customer-facing AI) and AUREM CTO
   (developer / ops AI). Polaris Built Inc., Mississauga, Ontario.
2. **Canadian SMB customer** — salons, spas, clinics, wellness, beauty,
   home services. Wants more bookings, less ad spend, less admin.
3. **Developer (BYOK tenant)** — third-party who plugs in their own
   LLM key and ships agentic features inside AUREM via the developer
   portal.
4. **Enterprise procurement** — needs SOC 2, MSA, SLA, SAML SSO,
   SCIM provisioning, data residency proof.

## Problem we solve

Canadian SMBs need first-page Google presence, lead capture, 24/7
booking, review collection, and follow-ups — but they cannot hire 5
specialists. AUREM packs the entire CMO + COO + CTO + receptionist
+ collections agent into one autonomous platform that obeys PIPEDA +
Law 25 + GDPR.

## Main features (live as of D-57)

- **Lead acquisition**
  - Ghost Scout — OSM Places + iProyal proxy mass-harvest of SMB leads
    with strict CA / US country filtering (D-56).
  - CSV import + dedupe.
  - Channel-gating per lead: email / sms / call / whatsapp.
- **Outreach**
  - Multi-channel blast: Resend email → Twilio SMS → WHAPI / Twilio
    WABA. Auto fall-through (D-57 Twilio WABA fix).
  - Auto-website builder previews per lead (signed link → CTA).
  - Compliance: PIPEDA + Law 25 unsubscribe footer on every email.
- **Customer-facing ORA**
  - Voice + chat support, booking, FAQ, reviews recovery, payment
    reminders, abandoned-cart winback.
- **AUREM CTO** (developer-facing super-agent)
  - Real tool execution (D-49): run-scout, import-leads, run-blast, db-stats.
  - Real codebase + GitHub access (D-54): sandboxed file reads,
    GitHub commits API, codebase search.
  - Real-time push + deploy animation (D-51) with progress steppers.
  - 3-layer auto-verification (D-52): code syntax + GitHub push +
    deploy version. RED / GREEN / CHECKING badges. Deploy CTA is
    gated on GitHub GREEN (D-52a).
  - Self-learning (D-53): records only system-verified outcomes,
    weekly self-review Sundays 02:00 UTC, confidence badges.
  - Codebase Map sidebar (D-55) — click any file to inject into chat.
  - Hot-lead surfacing (D-57): Resend webhook → 🔥 pill in chat with
    "5 min ago" timing; click to draft reply.
  - Anti-hallucination GUARDRAIL (D-57): bans invented SHAs / dates /
    iter tags / endpoints. Intent-aware temperature (0.0 / 0.1 / 0.2).
- **Settings + admin**
  - Developer portal — BYOK, GitHub OAuth (D-42), GitHub Save dialog
    (D-47), security keys generator + rotation alerts (D-46).
  - Admin Security Keys panel, secrets whitelist (D-43).
  - Mobile composer fix (D-50) + ORA help-bubble hidden on mobile.
- **Billing**
  - Stripe — Starter / Builder / Pro packages + webhook + churn nudges.
- **Enterprise**
  - SAML SSO (signed AuthnRequests), SCIM provisioning, audit log,
    branding admin, trust center, SOC 2 PDF, MSA + SLA pages.

## User roles + access

| Role          | Where they live                       | Auth method            |
|---|---|---|
| founder       | /admin/* + /developers/*              | JWT + super_admin flag |
| customer      | /, /book, /portal/*                   | email + OTP            |
| developer     | /developers/*                         | JWT + dev account      |
| enterprise    | /enterprise/* + SSO IdP-initiated     | SAML / SCIM            |
| anonymous     | / + /preview/*                        | none                   |

## User stories (top 12)

1. *As a founder* I open AUREM CTO and say "deploy to aurem.live" — the
   system pushes to GitHub, waits for /api/version to flip, and shows
   me a real commit SHA.
2. *As a founder* I ask "what is line 43 of aurem_routes.py" — I get
   the REAL line, not a hallucination.
3. *As a founder* I see a 🔥 pill saying "Hot Salon opened your email
   5 min ago" — I click and a reply draft is prefilled.
4. *As an SMB customer* I get a personalized AI-built preview website
   in my email — clicking unlocks booking.
5. *As an SMB customer* I miss a call → ORA texts the caller back,
   books them, and writes the recap to my dashboard.
6. *As a developer* I pop in my Anthropic key, get a token wallet, and
   stream from the AUREM CTO endpoint.
7. *As an enterprise* I configure SAML SSO + SCIM in /enterprise →
   users provision automatically.
8. *As a founder* I trigger Ghost Scout for "salon Mississauga" — the
   harvest never returns Vermont (CA country filter, D-56).
9. *As a founder* my campaigns auto-pause if 3 consecutive sends fail
   (no silent failures).
10. *As a founder* I see iter D-57 in the footer cache-bust badge.
11. *As a founder* the AUREM CTO refuses to fabricate a commit SHA when
    it doesn't have one (GUARDRAIL).
12. *As a customer* I unsubscribe → all four channels (email / sms /
    call / whatsapp) auto-gate to False immediately.

## Success metrics

- **Revenue**: $X MRR from Canadian SMBs (target: $50K MRR by Aug 2026).
- **Outreach**: ≥ 1,000 verified-delivery emails / week (Resend IDs).
- **Activation**: % of SMB leads that book within 7 days of first email.
- **AUREM CTO**: 0 fabricated facts per week (D-52 verification badges).
- **Reliability**: 99.5 % uptime on aurem.live; pytest suite 100 %.
- **Compliance**: 0 PIPEDA / Law 25 / GDPR complaints.

## MVP scope (already shipped)

- Founder console + AUREM CTO (D-57).
- ORA customer agent + auto-website builder + booking.
- Multi-channel blast (Resend / Twilio / WHAPI / Twilio WABA).
- Ghost Scout harvest + country filter.
- Developer portal + BYOK + GitHub OAuth.
- Stripe Starter / Builder / Pro.
- Enterprise SAML + SCIM + audit log + trust center + SOC 2 PDF.
- pytest 166 / 166 green across D-40b → D-57.

## Out-of-scope for v1

- Native mobile apps (PWA only).
- Multi-language UI beyond English + Hinglish chat (next: French Canadian).
- Crypto / Web3 payments.
- Marketplace / app store for third-party plugins.
- Voice biometrics / face auth.

## Compliance / regulatory baseline

- **PIPEDA** (Canada federal).
- **Law 25** (Quebec).
- **GDPR** (EU customers via opt-in).
- **CASL** — every outbound email carries a Polaris Built Inc. mailing
  address + one-click unsubscribe.
- **SOC 2 Type I report** — exposed via /trust-center and PDF download.
- **Data residency** — Canadian region default for MongoDB Atlas
  + Hetzner FSN1 (Helsinki) for compute.
