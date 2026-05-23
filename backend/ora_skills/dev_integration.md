# AUREM DEV SKILL: integration — The 3rd-Party Integration Playbook
## Context
Loaded whenever ORA needs to wire an external API (Stripe, Twilio,
Resend, Retell, Brightbean, GitHub, etc). Every integration must go
through this 8-step gate. The first 2 steps are HARD GATES enforced
by `services/ora_guards.check_integration_gate`.

## Trigger intent
Keywords: stripe, twilio, retell, resend, whatsapp, webhook, sdk,
api key, integration, "wire up", "connect to", oauth, third-party.

## Owner Agent
ORA. ORA REFUSES to call a vendor tool (`stripe_*`, `twilio_*`, etc.)
unless `web_search` was called within the last 5 turns. The hard gate
is in code, not just policy.

---

## The 8-Step Integration Playbook

### Step 1 — `web_search` for CURRENT docs (HARD GATE)
ORA's training data is months stale. Vendor APIs change.
- Query: `"{vendor} API {feature} latest docs"` (e.g. "Stripe checkout
  session 2026 reference").
- Read at least 1 recent result.
- WITHOUT this step, the integration_gate guard BLOCKS the vendor
  tool call with the error: *"Call web_search first."*

### Step 2 — Check `INTEGRATION_PLAYBOOK.md` (HARD GATE)
- `semantic_memory_search("{vendor} {feature}")` — AUREM-specific
  cheatsheet for known vendors lives in `/app/memory/tier2/`.
- Includes: key prefix format, webhook signature header, env var
  naming, common gotchas.

### Step 3 — Verify API key BEFORE writing code
- Check `os.environ.get("{VENDOR}_API_KEY")` — if missing, STOP and
  call `ask_human`: *"I need {VENDOR}_API_KEY in `.env` before I can
  proceed. Where can I get it?"*
- NEVER hardcode keys. NEVER log keys.
- The secrets scrubber (`ora_safety.scrub_secrets`) will redact any
  key that leaks into a log or file read.

### Step 4 — Sketch the data flow
On paper (or in the build plan):
- What does the vendor need from us? (payload shape)
- What does the vendor send back? (response + webhook events)
- Where do we persist the result? (Mongo collection + audit row)

### Step 5 — `propose_build_plan` (Tier-2 approval card)
The plan MUST include:
- Vendor + feature + reason.
- Env vars required.
- Files to create: client wrapper in `services/{vendor}_{feature}.py`,
  webhook handler if any, audit collection name.
- Test plan: 1 mock test + 1 `verify_endpoint` smoke test.

### Step 6 — Implement with retry+backoff
- Use `httpx` (async). Never `requests` (sync, blocks loop).
- Retry only on 5xx and network errors. NEVER retry 4xx (fix your code).
- Exponential backoff: 1s, 2s, 4s, max 3 attempts.
- Persist every call to an audit collection (`{vendor}_api_log`) so
  debugging doesn't require log archaeology.

### Step 7 — Test with mock + real verify
- **Mock test** (`respx` or `monkeypatch`): proves the code paths.
- **Real verify_endpoint test**: hit the actual sandbox/test endpoint
  with a real (sandbox) key. Saves you from "it worked in mock, broke
  in prod" disasters.
- Both go in `/app/backend/tests/test_iter{N}_{vendor}.py`.

### Step 8 — Webhook signature verification (if applicable)
- ALWAYS validate the vendor's signature header BEFORE trusting the
  body. Forged webhooks are how attackers reach production code.
- Stripe: `stripe.Webhook.construct_event(body, sig, whsec)`.
- Twilio: `RequestValidator(auth_token).validate(url, params, sig)`.
- Retell: HMAC-SHA256(body, secret) compared to `X-Retell-Signature`.
- Resend: HMAC-SHA256 same pattern.

---

## Hard rules

1. NEVER skip Step 1 — `web_search` is a code-enforced gate, not a
   suggestion.
2. NEVER skip Step 8 if the vendor sends webhooks.
3. NEVER retry 4xx — that means YOUR request is wrong.
4. NEVER log API keys, tokens, webhook secrets.
5. ALWAYS test with mock + real. Mock-only tests give false confidence.

## Vendor-specific quick reference

See `/app/memory/tier2/INTEGRATION_PLAYBOOK.md` for the AUREM cheatsheet
on:
- Stripe (`sk_live_` / `sk_test_` / `whsec_` / `Stripe-Signature`)
- Twilio (SID prefix, WhatsApp template SID, `X-Twilio-Signature`)
- Retell (Bearer auth, agent SID, `X-Retell-Signature`)
- Resend (`re_` prefix, verified-domain requirement)
- Emergent LLM Key (universal key for Claude/Gemini/GPT)

## Example invocation

```
Founder: "wire up Stripe metered billing for our $/lead pricing"

1. web_search("Stripe metered billing usage records 2026")
   → finds current API.
2. semantic_memory_search("stripe webhook AUREM")
   → INTEGRATION_PLAYBOOK chunks.
3. Check env: STRIPE_SECRET_KEY ✓, STRIPE_WEBHOOK_SECRET ✓,
   STRIPE_PRICE_METERED missing → ask_human.
4. Data flow: create_subscription → on each lead → usage_record →
   monthly invoice → webhook → mark paid.
5. propose_build_plan: services/stripe_metered.py, webhook handler,
   audit collection `stripe_metered_usage`, 2 tests.
6. Implement with httpx async + 3-attempt backoff.
7. Mock test passes. Real sandbox key test creates a $0.01
   usage record successfully.
8. Webhook handler validates Stripe-Signature before parsing body.
```
