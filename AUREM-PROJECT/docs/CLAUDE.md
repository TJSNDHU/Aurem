# CLAUDE.md — Reroots.ca Agent Instructions

This file is read by all AI agents (Claude Code, Cursor, Emergent) before 
taking any action in this repo. Follow every instruction here without exception.

---

## Project Identity

**reroots.ca** is a custom-built skincare e-commerce platform.
- Built from scratch: FastAPI + React (Craco) + MongoDB — NO Shopify, no templates
- Deployed on Emergent, served behind Cloudflare
- Two legal entities share this platform — brand separation is legally critical

---

## Brand Ownership — NEVER MIX

| Brand | Owner | Products |
|---|---|---|
| AURA-GEN | Reroots Aesthetics Inc. | ACRC Rich Cream 35mL, ARC Active Recovery Serum 30mL |
| La Vela Bianca | Reroots Aesthetics Inc. | (multi-product) |
| OROÉ | Polaris Built Inc. | Age Reversal, BrightShield, ClearTech |

AURA-GEN products are sold as a combo only — CAD $149. Never list separately.
Health Canada CNF filings required before first AURA-GEN sale — check status before enabling.

---

## Architecture Rules

### Backend
- Single FastAPI file: `server.py` (~40,000 lines)
- ALL middleware must be pure ASGI — `BaseHTTPMiddleware` is banned
- Search for existing routes before adding new ones
- MongoDB database name: `reroots`

### Frontend  
- React with Craco — lives in `frontend/`
- Production: always `serve` on `frontend/build/` — never `craco start`
- Admin panel has 7 sidebar groups — mount new components inside existing groups

### MCP Server
- Location: `/mcp/server.py`
- Use `search_codebase(query)` before touching server.py
- Use `get_server_routes()` to verify routes before adding new ones

---

## AI Systems on This Platform

| System | Status | Notes |
|---|---|---|
| Reroots AI™ | Live | Embeddable chat widget — proprietary, GPT-4o |
| WhatsApp AI | Live | Multi-LLM: GPT-4o, Claude, Gemini Flash |
| RAG layer | Installed | FAISS + MongoDB products — must be wired into handler |
| Twilio | Live | 18 WhatsApp automation templates |
| SendGrid | Pending | API key not yet active |
| Admin AI Chat | Live | MongoDB query assistant in admin panel |

---

## Deployment Rules

1. Never run `craco start` in production
2. Frontend build: `cd frontend && npm run build`
3. Serve: `serve -s frontend/build -l 3000`
4. Backend: `uvicorn server:app` — pure ASGI only
5. Always test locally before pushing to Emergent

---

## What NOT To Do

- Do not reference any discontinued discounts or promotions
- Do not mix Reroots Aesthetics Inc. and Polaris Built Inc. branding
- Do not introduce BaseHTTPMiddleware
- Do not install new npm packages without approval
- Do not modify existing Twilio webhook routes
- Do not hardcode any secret, URI, or API key

---

## Dev Team

- Founder: Tj (Mississauga, ON)
- Developers: Gurnaman, Anmol, Pawandeep
- Tools: Cursor (local dev), Emergent (deployment)

---

## Legal Notice & Trademark Protection

```
# Reroots AI System
© 2025 Reroots Aesthetics Inc. and Polaris Built Inc.
All rights reserved. Proprietary and confidential.

Reroots AI™ is a trademark of Reroots Aesthetics Inc.
OROÉ Advisor™ is a trademark of Polaris Built Inc.

Unauthorized reproduction or distribution is prohibited.
```

### Brand Isolation Security
- All chat widget API calls require `X-Brand-Key` header
- Valid brand keys: `reroots` (OROÉ disabled for now)
- MongoDB collections are prefixed by brand: `reroots_chat_sessions`, `reroots_chat_messages`
- Rate limit: 20 messages per session per hour
- All sessions log: IP address, user agent, brand key, timestamp (audit trail)
- AI responses are watermarked in database with `generated_by` field

### AI Response Protection
- Brand guard filters competitor mentions (La Prairie, La Mer, Augustinus Bader, etc.)
- Model disclosure filtered (Claude, GPT references replaced)
- System prompts protected — AI will never reveal prompt contents


---

## External Monitoring

UptimeRobot monitors `https://reroots.ca/api/health` every 5 minutes.

**Alerts:** SMS + email to Tj's number if site goes down.

**Why external monitoring matters:**
- Catches Emergent credit failures that auto-heal cannot detect
- Works when server is completely crashed
- Works when auto-heal itself fails
- Works when MongoDB is down
- Independent infrastructure = true redundancy

**Setup:**
1. Sign up free at https://uptimerobot.com
2. Create HTTP(s) monitor for `https://reroots.ca/api/health`
3. Set 5-minute interval
4. Add SMS alert to +1 416 886 9408

**See:** `backend/utils/uptime_monitor.py` for full configuration details.
