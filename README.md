# AUREM

**Autonomous AI platform for Canadian trades businesses.**
Outreach · Auto-Built Websites · CASL-compliant SMS/Email · Self-healing infrastructure.

---

## What AUREM does

AUREM is a full-stack AI orchestration platform ("ORA") that turns cold Canadian leads into paying customers without human drip-feeding:

- **Scout** — scans Canadian trades directories, scores digital gaps, picks high-signal leads
- **Outreach** — CASL-compliant email / SMS / WhatsApp drips with timing-optimised sends
- **Auto Website Builder** — generates per-lead demo sites (Gemini → Claude refine → publish to R2/CF)
- **ORA God Mode** — one AI voice that synthesises 20 specialised skills (scout, outreach, CASL, SEO, code, etc.)
- **Sovereign Truth** — founder anti-sycophancy mode; grounds every strategy reply in real 30-day performance metrics
- **Site QA & auto-repair** — test-lab.ai validates every built site; failures auto-refund + re-outreach
- **Sentinel** — self-healing React + flood-gated API + circuit-broken Redis

---

## Stack

| Layer | Tech |
|---|---|
| Backend | FastAPI · Motor (MongoDB async) · APScheduler · Starlette ASGI |
| Frontend | React 18 · TailwindCSS · Shadcn UI · PWA |
| AI | Emergent Universal Key (Claude 4.5 / Gemini 3 / GPT-5.2) + local Ollama fallback |
| Scraping | Scrapling (Cloudflare bypass) + httpx fallback |
| Infra | Kubernetes · Redis Cloud · MongoDB Atlas · Cloudflare R2 |

---

## Repository layout

```
backend/          FastAPI app, routers, services, schedulers, tests
frontend/         React PWA (admin console + customer /ora shell)
memory/           PRD + changelog (internal product docs)
README.md         this file
```

Backend API entry: `backend/server.py` · Frontend entry: `frontend/src/App.js` · PWA shell: `frontend/src/platform/OraPWA.jsx`

---

## Running locally

Services are supervised. Environment is managed through Emergent platform secrets (not `.env` in git).

```bash
# Backend
cd backend && pip install -r requirements.txt
sudo supervisorctl restart backend

# Frontend
cd frontend && yarn && sudo supervisorctl restart frontend
```

Health probes:
- `GET /health` — liveness (ASGI shim, <1 ms)
- `GET /api/health` — full stack (Mongo + scheduler + pillars)
- `GET /api/pillars/health` — P1/P2/P3/P4 infrastructure status (founder JWT required)

---

## Key endpoints

| Endpoint | Purpose |
|---|---|
| `POST /api/aurem/chat` | ORA God-Mode brain entry point |
| `POST /api/onboarding/tenant/{bin}/pixel/verify` | Customer pixel install verification |
| `GET /api/admin/sms/status` | SMS kill-switch + CA allowlist state |
| `GET /api/admin/skills/health` | 22-skill library health |
| `GET /api/founder/sovereign-truth/state` | Founder-only anti-sycophancy toggle |

---

## Security & secrets

- `.env` files are **never** committed. Emergent platform injects them at runtime via Secrets Manager.
- JWT auth (HS256) with tenant-isolation middleware
- Twilio A2P 10DLC gate active (US blocked, CA allowlist enabled) — see `services/sms_killswitch.py`
- ASGI-level flood gate (`middleware/health_probe.py`) prevents `/api/sentinel/client-error` flooding
- Founder-only endpoints (Sovereign Truth, SMS admin) gated on email allowlist + admin role

---

## Contact

**Maintainer**: TJ Sandhu · [aurem.live](https://aurem.live)

---

© 2026 AUREM. Canadian Moat · Built for trades.
