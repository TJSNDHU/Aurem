# FreeLLMAPI Self-Hosted Proxy — AUREM Integration Guide

**Iter 326a** — wires the [tashfeenahmed/freellmapi](https://github.com/tashfeenahmed/freellmapi)
OpenAI-compatible proxy into AUREM's ORA agent as the **#2 provider in
the fallback chain**.

## What you get
- 11-provider parallel fallover behind a single OpenAI-compat endpoint
- ~1.3 B free tokens/month total inference capacity
- Per-key rate-limit tracking — never accidentally exceeds free tiers
- AES-256-GCM encrypted key storage
- Sticky sessions for multi-turn (no mid-conversation model switches)
- AUREM-side: ORA agent treats the proxy as ONE upstream, so a single
  outage there only burns one slot in our chain

## Architecture
```
user → ORA chat
         │
         ▼
   ┌─────────────────────────────────────────────────────────────┐
   │ ORA_AGENT_PROVIDER_ORDER (env, default below):              │
   │   1. deepseek      (OpenRouter)                             │
   │   2. freellmapi    ← self-hosted proxy, multiplexes 11      │
   │   3. claude        (Emergent Universal Key)                 │
   │   4. legion_ollama (sovereign, laptop — optional)           │
   │   5. groq          (rate-limited safety net)                │
   └─────────────────────────────────────────────────────────────┘
                          │ provider="freellmapi"
                          ▼
   ┌─────────────────────────────────────────────────────────────┐
   │ FreeLLMAPI proxy (Node + SQLite, runs on $5 VPS / Pi)       │
   │   ┌──────┬──────┬──────────┬───────────┬─────────┐          │
   │   │Google│Groq  │Cerebras  │SambaNova  │Mistral  │ ...      │
   │   │Gemini│Llama4│Qwen3 235B│DeepSeek V3│Large 3  │          │
   │   └──────┴──────┴──────────┴───────────┴─────────┘          │
   └─────────────────────────────────────────────────────────────┘
```

## Step 1 — Deploy the proxy (operator action)

On any cheap VPS, Pi, or even your laptop:

```bash
git clone https://github.com/tashfeenahmed/freellmapi.git
cd freellmapi
npm install

# Generate the at-rest encryption key
cp .env.example .env
echo "ENCRYPTION_KEY=$(node -e "console.log(require('crypto').randomBytes(32).toString('hex'))")" >> .env

# Start
npm run build
node server/dist/index.js   # listens on :3001
```

Open `http://your-vps:3001` (or `http://localhost:5173` for the dev
dashboard), add free-tier API keys from each provider you want to
plug in (Google AI Studio, GroqCloud, Cerebras Cloud, etc.), reorder
the fallback chain to taste, and copy the unified `freellmapi-…`
bearer token from the **Keys** page header.

> The README in the proxy repo has provider-by-provider signup links
> and free-tier quotas. Recommended starter set: Google + Groq +
> Cerebras + Mistral (free, generous, all OpenAI-compatible).

## Step 2 — Point AUREM at the proxy

Set these env vars on the AUREM backend pod (`/app/backend/.env` or
deployment manager):

```
FREELLMAPI_BASE_URL=http://your-proxy-host:3001/v1
FREELLMAPI_API_KEY=freellmapi-XXXXXXXXXXXXXXXXXX
FREELLMAPI_MODEL=auto                 # or pin to e.g. gemini-2.5-flash

# Optional — change provider chain order (default already includes freellmapi)
ORA_AGENT_PROVIDER_ORDER=deepseek,freellmapi,claude,legion_ollama,groq
```

Restart AUREM backend. That's it — no code change.

## Step 3 — Verify

```bash
# Hits the new watchdog endpoint that probes every provider in the chain
curl -H "Authorization: Bearer <admin_token>" \
     https://aurem.live/api/admin/ora/providers/health | jq

# Expected: providers.freellmapi.ok == true
# And providers.freellmapi.models_total == count of models you've enabled
```

## What changed in AUREM code (iter 326a)

| File                                            | Change                                                            |
|-------------------------------------------------|-------------------------------------------------------------------|
| `services/ora_agent.py`                         | New `_freellmapi_with_tools()`, `freellmapi_health()`, `warm_freellmapi()` |
| `services/ora_agent.py:_llm_turn()`             | New `provider == "freellmapi"` branch                              |
| `services/ora_agent.py` chain default           | `deepseek,freellmapi,claude,legion_ollama,groq`                    |
| `server.py` startup                             | Fire-and-forget `warm_freellmapi()` after `warm_deepseek()`        |
| `routers/ora_providers_router.py`               | NEW — `/api/admin/ora/providers/health` watchdog                   |
| `backend/.env`                                  | `ORA_AGENT_PROVIDER_ORDER` updated to include `freellmapi`         |

## Telemetry

Every successful FreeLLMAPI call logs `[ora-agent] freellmapi served via <platform>/<model>`
to `/var/log/supervisor/backend.out.log`, so you can trace which
upstream actually answered each request:

```bash
grep "freellmapi served" /var/log/supervisor/backend.out.log | tail
# [ora-agent] freellmapi served via google/gemini-2.5-flash
# [ora-agent] freellmapi served via groq/llama-4-scout
```

## Failure modes

| Symptom                                | Cause                                              | Fix                                                       |
|----------------------------------------|----------------------------------------------------|-----------------------------------------------------------|
| `provider=freellmapi … HTTP 401`       | Wrong `FREELLMAPI_API_KEY`                          | Re-copy unified key from proxy dashboard                  |
| `provider=freellmapi … connect error`  | Proxy host unreachable                              | Check VPS firewall / proxy `pm2 status`                   |
| `models_total: 0` in /health           | No provider keys added to proxy yet                 | Add keys via proxy dashboard's Keys page                  |
| Falls straight through to claude       | Both proxy keys exhausted (daily caps hit)          | Wait for UTC midnight reset OR add more provider keys     |

## Future enhancements (open PRs welcome)
- Cost-aware routing — prefer faster providers (Cerebras, Groq) for
  short turns, save Gemini Pro for long-context reasoning
- Streaming integration — the proxy supports SSE; AUREM's ORA chain
  currently uses non-streaming for tool calls
- Per-tenant key isolation — useful once AUREM goes multi-tenant
