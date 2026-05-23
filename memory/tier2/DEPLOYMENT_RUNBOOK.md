# AUREM DEPLOYMENT RUNBOOK

When things break in production or staging, follow this runbook.

## Service Architecture

- Preview (dev): the pod ORA lives in. Auto-deploy on save.
- Production: `aurem.live`. Founder triggers via "Save to GitHub".
- Backend: FastAPI on `0.0.0.0:8001` (internal), supervisor-managed.
- Frontend: React dev server on `:3000`, supervisor-managed.
- MongoDB: Atlas cluster, env var `MONGO_URL`, db name `DB_NAME`.
- All external traffic flows through K8s ingress → `/api/*` → 8001,
  everything else → 3000.

## Health Check

```bash
curl -s -o /dev/null -w "%{http_code}\n" https://aurem.live/api/health
# Expect: 200
curl -s https://aurem.live/api/health | head -c 200
```

If 502: pod is starting. Wait 10s, retry.
If 503: backend supervisord stopped. Check logs.
If 200 but JSON missing fields: code bug, read backend logs.

## Restart Procedures

Local preview:
```bash
sudo supervisorctl restart backend
sudo supervisorctl restart frontend
sudo supervisorctl restart all
sudo supervisorctl status
```

Production:
- Cannot restart from preview pod.
- Use Emergent dashboard or `Save to GitHub` for redeploy.
- Contact Emergent Support for prod env issues.

## Reading Logs

```bash
tail -n 100 /var/log/supervisor/backend.err.log
tail -n 100 /var/log/supervisor/backend.out.log
tail -n 50  /var/log/supervisor/frontend.err.log
```

Or via ORA tool: `read_logs("backend", lines=100)`.

## Common Errors

- `[breakers] REDIS_URL unset — breakers will use in-memory state`
  → benign, REDIS_URL is intentionally empty.
- `[startup-validation] N REQUIRED env vars missing`
  → check `/app/backend/.env`, never delete keys.
- `No module named 'X'` → run `pip install X && pip freeze > /tmp/req.txt`
  then merge into requirements.txt by hand. NEVER overwrite requirements.txt.
- `MotorEngine ConnectionError` → MONGO_URL malformed or Atlas IP whitelist.

## Rollback

Emergent platform auto-commits on each step. To roll back:
1. Use Emergent UI → Checkpoints → Restore.
2. Or `git log --oneline | head -20`, pick a commit, ask founder to
   restore from that point (ORA cannot git-reset).

## Smoke Tests Post-Deploy

```bash
curl https://aurem.live/api/health
curl https://aurem.live/api/public/status
curl -X POST https://aurem.live/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"test@aurem.live","password":"test"}'
# Expect 401 with {"detail":"Invalid credentials"} — proves /api wiring.
```

## Env Vars That Matter

- `MONGO_URL`, `DB_NAME` — Atlas
- `JWT_SECRET` — auth
- `EMERGENT_LLM_KEY` — Claude/Gemini/OpenAI fallback
- `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`
- `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_WHATSAPP_FROM`
- `RETELL_API_KEY`, `RETELL_AGENT_ID`
- `RESEND_API_KEY`, `RESEND_FROM_EMAIL`
- `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`
- `ORA_SESSION_USD_CAP` (iter 331a, default $5.00)
- `ORA_AUTONOMY_LEVEL` (off|tier1_only|all)

Never delete any of these from `.env`.
