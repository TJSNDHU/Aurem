# AUREM Public API — Usage Guide

> Iter D-59 Part B. Live since 2026-02-06.
> Base URL (preview): `https://api.preview.aurem.live` (your `REACT_APP_BACKEND_URL`)
> Base URL (production): `https://aurem.live`

---

## 1. Get an API key

1. Sign in to the AUREM admin console.
2. Open **Settings → Public API Keys** in the sidebar (or visit `/admin/api-keys` directly).
3. Click **Issue key**:
   * **name** — friendly label (e.g. `“StackBuddy backend”`)
   * **owner email** — who is responsible
   * **scopes** — tick the ones you need (`ora_chat`, `cto_chat`, `leads_read`)
   * **daily limit** — calls/day cap (default 5000)
4. Copy the secret IMMEDIATELY. It is shown **once**. AUREM stores only the SHA-256 hash.

Secrets look like: `aurem_sk_live_<43-char-urlsafe-random>`.

## 2. Authentication

Every call needs a Bearer header:

```
Authorization: Bearer aurem_sk_live_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

Errors:

| Code | Meaning |
|------|---------|
| 401  | missing or malformed Bearer / unknown key |
| 403  | valid key but scope not allowed for this endpoint |
| 429  | daily quota exceeded (resets at UTC midnight) |
| 500  | upstream LLM error (request not counted against quota) |

## 3. Endpoints

### `GET /api/v1/public/health` (no auth)

Cheap sanity ping. Returns `{ ok: true, platform: "aurem-public-api", version: "v1" }`.

### `POST /api/v1/public/ora/chat`  (scope: `ora_chat`)

Customer-facing assistant. Warm, on-brand.

```bash
curl -X POST https://aurem.live/api/v1/public/ora/chat \
  -H "Authorization: Bearer aurem_sk_live_..." \
  -H "Content-Type: application/json" \
  -d '{
        "message":     "Tell me what AUREM does in one sentence.",
        "session_id":  "user-42",
        "system_hint": "Speak to a small business owner in Toronto."
      }'
```

Response:

```json
{
  "ok": true,
  "reply": "AUREM is an autonomous business operating system that...",
  "session_id": "user-42",
  "tier": "free",
  "model": "deepseek-v3"
}
```

### `POST /api/v1/public/cto/chat`  (scope: `cto_chat`)

Engineering / code assistant. Deterministic, 1–3 sentences, no SHA fabrication.

```bash
curl -X POST https://aurem.live/api/v1/public/cto/chat \
  -H "Authorization: Bearer aurem_sk_live_..." \
  -H "Content-Type: application/json" \
  -d '{
        "message": "How do I add an idempotent Mongo upsert in FastAPI?",
        "system_hint": "Project uses motor 3.x"
      }'
```

### `GET /api/v1/public/leads/lookup`  (scope: `leads_read`)

Look up an AUREM lead by email or phone. Returns up to `limit` matches with public fields only.

```bash
curl -G https://aurem.live/api/v1/public/leads/lookup \
  --data-urlencode "email=owner@somespa.ca" \
  --data-urlencode "limit=5" \
  -H "Authorization: Bearer aurem_sk_live_..."
```

Response:

```json
{
  "ok": true,
  "count": 1,
  "items": [
    {
      "lead_id": "L-3091",
      "business_name": "Some Spa",
      "email": "owner@somespa.ca",
      "phone": "+14165550199",
      "city": "Toronto",
      "country": "CA",
      "status": "contacted",
      "hot_lead_flag": false
    }
  ]
}
```

## 4. Python example

```python
import os, requests

AUREM_KEY = os.environ["AUREM_API_KEY"]      # aurem_sk_live_...
BASE      = os.environ["AUREM_BASE_URL"]      # https://aurem.live

def ora_chat(message, session_id="anon", hint=""):
    r = requests.post(
        f"{BASE}/api/v1/public/ora/chat",
        headers={"Authorization": f"Bearer {AUREM_KEY}"},
        json={"message": message,
              "session_id": session_id,
              "system_hint": hint},
        timeout=30,
    )
    r.raise_for_status()
    return r.json()["reply"]

print(ora_chat("Hi ORA, who are you?"))
```

## 5. Quotas, rotation, revocation

* Quotas reset at UTC midnight.
* Revoke a key at `/admin/api-keys` → click ⛔ next to the key. Revocation is **immediate**.
* Rotate by issuing a new key, updating the consumer, then revoking the old one. Both keys can co-exist for handover.

## 6. Privacy & audit

* AUREM stores **only the SHA-256 hash** of the secret. We can never display or recover the raw value.
* Every accepted call is logged in `aurem_api_usage` (key_id, endpoint, status, latency, ts).
* Admin can view 7-day usage breakdown from the key's row in the admin page.
