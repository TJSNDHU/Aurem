# AUREM Sovereignty Migration — Copy-Paste Runbook (iter 323i)

> **Goal:** Take AUREM from ~46% sovereign (Emergent-hosted, Atlas-backed) to ~73% sovereign (Hetzner-hosted, Legion-Mongo, self-Redis, sovereign LLM).

---

## Pre-flight checklist

| Need | Where | Status |
|---|---|---|
| Legion laptop with Docker + Ollama running | Your Windows machine | ✅ Confirmed (models loaded) |
| Cloudflare account with `aurem.live` zone | dash.cloudflare.com | ✅ You have this |
| Atlas connection string | Emergent backend `.env` or support@emergent.sh | ❓ Need to extract |
| Hetzner account | hetzner.com | ❌ Create now if not done |
| GitHub repo with main branch access | github.com | ✅ Confirmed |
| ~4 hours total (split across weekends) | Calendar | — |

---

## STEP 1 — Sovereign LLM (DONE today, just needs redeploy)

✅ Done in code (iter 323b-h committed):
- `LOCAL_LLM_ENABLED=true`, `LOCAL_LLM_MODEL=llama3.1`, `SOVEREIGN_NODE_URL=https://kite-moodiness-routine.ngrok-free.dev`, `AUREM_ENV=sovereign`
- Ollama models loaded on Legion: `qwen2.5-coder:7b`, `llama3.1:latest`

**Your action (30 seconds):**
1. Open https://app.emergent.sh → Deployments → AUREM
2. Click **Redeploy**
3. Wait 3-5 min, then verify:
   ```bash
   curl https://aurem.live/api/customer/vanguard/status   # expect 401
   curl https://aurem.live/api/admin/pixel-bridge/status  # expect 401
   ```

After this: **Production sovereignty → 46%**

---

## STEP 2 — MongoDB Migration (Weekend, ~2 hrs)

### 2.1 — Bring up Legion Mongo + Redis

On your **Legion Windows laptop**, in PowerShell or WSL:

```powershell
cd C:\path\to\aurem\legion
docker compose pull aurem-mongodb aurem-redis
docker compose up -d aurem-mongodb aurem-redis
sleep 30
docker exec aurem-mongodb mongosh -u aurem -p "AuremMongo2026Strong!" --eval "db.adminCommand('ping')"
docker exec aurem-main-redis redis-cli ping
```

Expected: `{ ok: 1 }` for Mongo, `PONG` for Redis.

### 2.2 — Get Atlas connection string

```bash
# Option A — from your Emergent preview pod (if you can SSH there):
echo $MONGO_URL

# Option B — email support@emergent.sh:
#   "Please provide the Atlas connection string for my AUREM production database. — TJ"
```

### 2.3 — Migrate data (Legion machine, WSL or git bash)

```bash
cd /path/to/aurem/legion
chmod +x migrate_atlas_to_legion.sh
ATLAS_URI="mongodb+srv://USER:PASS@cluster.mongodb.net/aurem_db" \
AUREM_MONGO_PASSWORD="AuremMongo2026Strong!" \
  ./migrate_atlas_to_legion.sh
```

Expected: collection count match between Atlas and Legion. **Atlas is read-only during migration — production stays alive.**

### 2.4 — Cloudflare TCP Tunnel for Mongo

In Cloudflare Zero Trust → Tunnels → your existing tunnel:

```yaml
# Add a public hostname:
Subdomain:  mongo-internal
Domain:     aurem.live
Type:       TCP
URL:        localhost:27017
```

**Security:** This must be in your Zero Trust Tunnel (not raw DNS). Restrict access policy to your prod pod IP if Hetzner provides static IPs.

Verify from any machine (with mongosh + tunnel):
```bash
mongosh "mongodb://aurem:AuremMongo2026Strong!@mongo-internal.aurem.live:27017/aurem_db?authSource=admin" \
  --eval "db.adminCommand('ping')"
```

### 2.5 — Switch Emergent .env.production to Legion Mongo

In Emergent dashboard → AUREM → Environment Variables:
```
MONGO_URL = mongodb://aurem:AuremMongo2026Strong!@mongo-internal.aurem.live:27017/aurem_db?authSource=admin
REDIS_URL = redis://aurem-redis-tunnel.aurem.live:6379    # if you also tunnel Redis
```

**Test on PREVIEW first** (NOT production), redeploy preview, run smoke tests, then switch production.

After this: **Sovereignty → 58%**

---

## STEP 3 — Hetzner Migration (Weekend, ~3 hrs)

### 3.1 — Provision Hetzner server

1. https://hetzner.com → Sign up → Add payment
2. Cloud → New Project → "aurem"
3. Add Server:
   - Location: **Nuremberg** (eu-central, lowest latency to Toronto)
   - Image: **Ubuntu 24.04**
   - Type: **CX32** (4 vCPU, 8GB RAM, ~€8.29/mo)
   - SSH Key: paste your `~/.ssh/id_ed25519.pub`
4. Create → note the IPv4 address

### 3.2 — Bootstrap server (one command)

```bash
# Local laptop
ssh root@<HETZNER_IP>

# On the server:
REPO_URL=git@github.com:<YOUR_USER>/aurem.git \
DOMAIN=aurem.live \
EMAIL=tj@aurem.live \
  bash <(curl -fsSL https://raw.githubusercontent.com/<YOUR_USER>/aurem/main/hetzner/setup.sh)
```

This script does ALL of: apt update, Docker install, ufw firewall (22/80/443), repo clone, .env scaffold, nginx config, certbot SSL, docker compose up, smoke test.

**~10 min total.** Watch the output — every step is `✓` or `✗`.

### 3.3 — Fill backend/.env with real secrets

```bash
# On Hetzner server:
nano /opt/aurem/backend/.env
# Copy every CHANGE_ME value from your Emergent .env.production
# Especially: JWT_SECRET, ENCRYPTION_KEY, AUREM_MASTER_KEY, EMERGENT_LLM_KEY, STRIPE_*, RESEND_*, TWILIO_*
docker compose -f /opt/aurem/hetzner/docker-compose.yml restart backend
```

### 3.4 — Cloudflare DNS switch

In Cloudflare dashboard → aurem.live → DNS:

| Type | Name | Content | Proxy |
|---|---|---|---|
| A | `@` | `<HETZNER_IP>` | ✅ Proxied (orange cloud) |
| A | `www` | `<HETZNER_IP>` | ✅ Proxied |

**Delete** the old Emergent IP records.

Wait 2-5 min for DNS propagation. Test:
```bash
dig +short aurem.live   # should show Cloudflare IPs (104.x.x.x or 172.x.x.x)
curl -I https://aurem.live/health   # should show "server: cloudflare" + 200 OK
```

### 3.5 — GitHub Actions auto-deploy

In GitHub repo → Settings → Secrets and variables → Actions → New repository secret:

| Secret name | Value |
|---|---|
| `HETZNER_HOST` | your Hetzner server IP |
| `HETZNER_USER` | `root` (or your created user) |
| `HETZNER_SSH_KEY` | contents of `~/.ssh/id_ed25519` (private key) |
| `HETZNER_PORT` | `22` |

Then push to main:
```bash
git add .github/workflows/hetzner-deploy.yml
git commit -m "feat: Hetzner auto-deploy via GitHub Actions"
git push origin main
```

Watch the Actions tab — should show green checkmark in ~3 min.

After this: **Sovereignty → 73%**

---

## Verification gauntlet (run after each step)

```bash
# Health
curl https://aurem.live/health                  # 200
curl https://aurem.live/api/health              # 200
curl https://aurem.live/api/platform/health     # 200

# Sovereign endpoints (iter 323b-h)
curl https://aurem.live/api/customer/vanguard/status    # 401
curl https://aurem.live/api/admin/pixel-bridge/status   # 401

# LLM sovereign check (need admin token)
TOKEN="<your admin JWT>"
curl -X POST https://aurem.live/api/ora-chat/ask \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"prompt":"reply: ok"}' | jq -r .provider
# Expected: "sovereign"
```

---

## Rollback paths

| If something breaks at step | Rollback action |
|---|---|
| Step 1 (Redeploy fails) | Emergent dashboard → previous deployment → Re-promote |
| Step 2 (Mongo switch) | Revert `MONGO_URL` in Emergent .env to Atlas string, redeploy |
| Step 3 (Hetzner fails) | Cloudflare DNS → revert to Emergent IP, problem solved in 5 min |

Atlas data is never deleted during migration. Old Emergent pod is never destroyed automatically. Both are safety nets.

---

## What sovereignty ceiling really looks like

| % | Stack |
|---|---|
| ~46% | Today (after Step 1 redeploy) — Emergent-hosted, Atlas, sovereign LLM, in-memory cache |
| ~58% | After Step 2 — Emergent-hosted, Legion Mongo, sovereign LLM, Legion Redis |
| **~73%** | After Step 3 — **Hetzner-hosted, Legion Mongo+Redis, sovereign LLM** |
| ~85% theoretical | Replace Stripe+Resend+Twilio (impractical — loses regulatory + deliverability + carrier deals) |
| 100% | Cult-of-purity. Don't. Customers care about reliability, not RMS-grade purity. |

**73% is the realistic ceiling. Stop there.**

---

## File index

| File | Purpose |
|---|---|
| `legion/docker-compose.yml` | Added `aurem-mongodb` + `aurem-redis` services |
| `legion/migrate_atlas_to_legion.sh` | One-shot Atlas → Legion data migration |
| `hetzner/docker-compose.yml` | Full prod stack: backend + frontend + redis + watchtower |
| `hetzner/nginx.conf` | Reverse proxy + SSL + headers |
| `hetzner/setup.sh` | One-command bootstrap (apt → docker → nginx → certbot → compose → smoke) |
| `.github/workflows/hetzner-deploy.yml` | Auto-deploy on `git push origin main` |
| `MIGRATION_RUNBOOK.md` | This file |

---

**Built by Supervisor agent, iter 323i. Approve via `/admin/git-gate`.**
