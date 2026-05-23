# AUREM Migration Checklist — Move to Any Platform

This checklist lets you move AUREM + ORA from Emergent to **Hetzner /
AWS / DigitalOcean / Docker / bare-metal** with zero surprises.

## 1. Copy these folders

```
/app/backend/services/ora_agent.py
/app/backend/services/ora_tools.py
/app/backend/services/ora_sprint2_tools.py     # iter 331a
/app/backend/services/ora_guards.py             # iter 331a
/app/backend/services/ora_deploy_tool.py        # iter 331a
/app/backend/services/ora_lessons_loader.py
/app/backend/services/ora_prose_filter.py
/app/backend/services/db_manager.py             # iter 331a
/app/backend/ora_skills/                        # all .md skill files
/app/memory/tier1/                              # always-on rules
/app/memory/tier2/                              # keyword-gated playbooks
/app/memory/tier3/                              # reference docs
/app/memory/PRD.md
/app/scripts/deploy.sh                          # iter 331a
/app/.vscode/tasks.json + launch.json           # iter 331a
```

## 2. Set these env vars on the new platform

### Required
```
MONGO_URL=<your-mongo-connection-string>
DB_NAME=aurem_db
JWT_SECRET=<32+ random chars>
EMERGENT_LLM_KEY=<from Emergent Profile → Universal Key>
```

### MongoDB Portability
```
DB_TYPE=atlas|legion|docker|hetzner|local
# If DB_TYPE is set but MONGO_URL is empty, db_manager picks a default
# connection string per type.
```

### Deploy
```
DEPLOY_PLATFORM=emergent|hetzner|docker|local
HETZNER_HOST=<host>             # if hetzner
HETZNER_USER=aurem
HETZNER_APP_DIR=/opt/aurem
HEALTH_URL=<your-health-check>  # if non-default
```

### ORA Guardrails (iter 331a)
```
ORA_SESSION_USD_CAP=5.00       # halt-cost cap
ORA_USD_WARN_FRACTION=0.80     # warn at 80% of cap
ORA_STUCK_MINUTES=5.0          # stuck-watchdog threshold
ORA_IDEMP_HITS=3               # identical-edit halt
ORA_INTEGRATION_WINDOW=5       # turns to look back for web_search
ORA_AUTONOMY_LEVEL=all         # off|tier1_only|all
ORA_MEMORY_ROOT=/app/memory    # override if path differs
ORA_TOOLS_ROOT=/app
ORA_LOG_DIR=/var/log/supervisor
```

### 3rd-Party Vendors (only if used)
```
STRIPE_SECRET_KEY=
STRIPE_WEBHOOK_SECRET=
TWILIO_ACCOUNT_SID=
TWILIO_AUTH_TOKEN=
TWILIO_WHATSAPP_FROM=
RETELL_API_KEY=
RETELL_AGENT_ID=
RESEND_API_KEY=
RESEND_FROM_EMAIL=
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=
```

## 3. Run these commands on the new host

```bash
# Install deps
cd /app/backend && pip install -r requirements.txt
cd /app/frontend && yarn install

# Backup database (from old host)
mongodump --uri="$OLD_MONGO_URL" --out=/tmp/aurem-backup

# Restore to new host
mongorestore --uri="$NEW_MONGO_URL" /tmp/aurem-backup

# Start services
sudo supervisorctl start backend
sudo supervisorctl start frontend

# Verify
curl -s "$HEALTH_URL/api/health"
```

## 4. Verify with these health checks

```bash
# Backend health
curl https://<new-domain>/api/health
# Expect: {"ok": true, ...}

# MongoDB ping
curl https://<new-domain>/api/health/db
# Expect: {"ok": true, "db_type": "<your-type>", ...}

# ORA cockpit loads
curl https://<new-domain>/admin
# Expect: 200 (HTML)
```

## 5. Smoke-test ORA's tools

```bash
# Run the iter-331a regression suite on the new host
cd /app/backend && python -m pytest tests/test_iter331a_sprints_1_2_3.py -v
# Expect: 18 passed
```

## Optional — alternate MongoDB topologies

### Local-dev MongoDB (no external service)
```
DB_TYPE=local
# db_manager will use mongodb://localhost:27017/aurem_db automatically.
```

### Docker-compose MongoDB
```
DB_TYPE=docker
# db_manager will use mongodb://mongo:27017/aurem_db
# Add `mongo:` service to your docker-compose.yml
```

### Self-hosted MongoDB on Hetzner
```
DB_TYPE=hetzner
MONGO_URL=mongodb://aurem:<password>@<hetzner-ip>:27017/aurem_db?authSource=admin
```

## Confirmation — Zero Platform Lock-in

After running this checklist, AUREM has:
- ✓ No Emergent-specific URLs in core code
- ✓ All paths env-overridable (`ORA_MEMORY_ROOT`, `ORA_TOOLS_ROOT`, etc.)
- ✓ MongoDB connection portable via `DB_TYPE` switch
- ✓ Deploy script supports 4 platforms (`emergent | hetzner | docker | local`)
- ✓ All tool registry entries spliced via patches (drop a file, get a tool)

To rollback to Emergent: just point `MONGO_URL` back to Atlas + set
`DEPLOY_PLATFORM=emergent`. No code changes needed.
