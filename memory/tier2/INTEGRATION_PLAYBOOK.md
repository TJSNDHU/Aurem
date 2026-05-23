# AUREM INTEGRATION PLAYBOOK — 3rd Party Cheat Sheets

Loaded when keywords trigger: stripe, twilio, retell, resend, mongodb,
mongo, motor, atlas, webhook, sdk, api key.

ALWAYS call `web_search` first for current docs — vendor APIs change.

## Stripe (Payments)

- Secret key prefix: `sk_live_` (prod), `sk_test_` (dev). Never log.
- Publishable key prefix: `pk_live_` / `pk_test_`. Safe in frontend.
- Webhook signing secret prefix: `whsec_`.
- Webhook signature header: `Stripe-Signature`.
- Verify with `stripe.Webhook.construct_event(body, sig, secret)`.
- Test card: `4242 4242 4242 4242`, any future date, any CVC.
- For metered billing: `customer.subscriptions.create` with
  `items=[{price, quantity}]`. Update usage via
  `subscription_items.create_usage_record`.
- Env: `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`, `STRIPE_PUBLIC_KEY`.

## Twilio (SMS / WhatsApp)

- Account SID prefix: `AC...`. Auth token: 32 chars hex.
- SMS from number must be a Twilio-purchased number, E.164 format.
- WhatsApp: send via `whatsapp:+14155238886` (sandbox) or your WABA number.
- WABA template name required for first message to new user — pre-approved
  in Twilio Console > WhatsApp > Templates. Body params interpolated by
  index `{{1}} {{2}}`.
- Verify webhook with `X-Twilio-Signature` header + `RequestValidator`.
- Env: `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_SMS_FROM`,
  `TWILIO_WHATSAPP_FROM`.

## Retell (AI Voice)

- API key header: `Authorization: Bearer ${RETELL_API_KEY}`.
- Create call: `POST https://api.retellai.com/v2/create-phone-call`
  with `{from_number, to_number, override_agent_id}`.
- Agent must be pre-built in Retell dashboard.
- Webhook events: `call_started`, `call_ended`, `call_analyzed`.
- Signature header: `X-Retell-Signature` — HMAC-SHA256 of body with
  webhook secret.
- Env: `RETELL_API_KEY`, `RETELL_AGENT_ID`, `RETELL_FROM_NUMBER`,
  `RETELL_WEBHOOK_SECRET`.

## Resend (Email)

- API key prefix: `re_`. Header: `Authorization: Bearer ${KEY}`.
- From email MUST be on a domain you verified in Resend dashboard.
- DNS records to verify: SPF, DKIM, DMARC (Resend shows them).
- Propagation: 5–30 min typically, up to 48 h.
- POST `https://api.resend.com/emails` with `{from, to, subject, html}`.
- 200 → returns `{id}`. Save for tracking.
- Env: `RESEND_API_KEY`, `RESEND_FROM_EMAIL`.

## MongoDB Motor (Async Driver)

- Connection pattern (already wired in `server.py`):
  ```python
  from motor.motor_asyncio import AsyncIOMotorClient
  client = AsyncIOMotorClient(os.environ["MONGO_URL"])
  db = client[os.environ["DB_NAME"]]
  ```
- All queries are `await`-able. Never use `pymongo` (sync, blocks loop).
- Exclude `_id`: `await db.col.find_one({...}, {"_id": 0})`.
- Insert/Update mutate the input dict by adding `_id`. Copy before returning.
- For bulk writes: `bulk_write([UpdateOne(...), InsertOne(...)])` is
  one round-trip.
- Index creation: idempotent — safe to call on every startup.
- Aggregation returns full docs by default → still strip `_id` at the
  `$project` stage or post-process.

## Emergent LLM Key (Claude / Gemini / GPT)

- Single key works across Anthropic, Google, OpenAI via `emergentintegrations`.
- Use `EMERGENT_LLM_KEY` env var.
- Install: `pip install emergentintegrations --extra-index-url https://d33sy5i8bnduwe.cloudfront.net/simple/`
- Code pattern: `LlmChat(api_key=..., session_id=..., system_message=...)`
- Best models: `claude-sonnet-4-5-20250929` (text), `gemini-3-flash` (fast),
  `gpt-5.2` (reasoning). Verify with `integration_playbook_expert_v2`
  before each new integration.
- For image gen: Nano Banana (Gemini). For voice: OpenAI Whisper.

## General Rules

1. Verify the key exists in `.env` BEFORE writing the integration.
2. NEVER log API keys, tokens, or webhook secrets.
3. ALWAYS validate webhook signatures BEFORE trusting the body.
4. Implement retry+backoff for 5xx but NOT for 4xx (fix your code).
5. Persist external call results in a Mongo audit collection so
   debugging doesn't require log archaeology.
