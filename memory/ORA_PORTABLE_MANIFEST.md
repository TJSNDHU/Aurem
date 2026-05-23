# ORA Portable Manifest — Zero Vendor Lock-in

ORA can move to any platform. This is the canonical list of what to
copy and what env vars to set.

## What lives in ORA's "core" (copy these to migrate)

```
/app/backend/services/
├── ora_agent.py              # main loop, prose filter, tool dispatch
├── ora_tools.py              # tool registry + impls (read/edit/git/etc.)
├── ora_sprint2_tools.py      # iter 331a — 8 new Tier-1 tools
├── ora_guards.py             # iter 331a — 6 safety guards
├── ora_deploy_tool.py        # iter 331a — deploy + rollback (Tier-3)
├── ora_lessons_loader.py     # tier-1/2/3 memory injection
├── ora_prose_filter.py       # Rule Zero enforcement
├── ora_build_mode.py         # propose_build_plan + propose_lesson
└── db_manager.py             # iter 331a — portable Mongo connect

/app/backend/ora_skills/      # all .md skill files (any platform)

/app/memory/
├── tier1/                    # always-on rule book
├── tier2/                    # keyword-gated playbooks
├── tier3/                    # reference (never auto-injected)
└── PRD.md                    # product source-of-truth

/app/scripts/deploy.sh        # iter 331a — portable deploy script
/app/.vscode/tasks.json       # iter 331a — VS Code tasks
/app/.vscode/launch.json      # iter 331a — VS Code debug configs
```

That's **9 files + 4 folders**. Nothing else is needed.

## Env vars ORA needs to run

### Mandatory
| Var | Default | Purpose |
|---|---|---|
| `MONGO_URL` | — | Mongo connection string |
| `DB_NAME` | `aurem_db` | Mongo database name |
| `EMERGENT_LLM_KEY` | — | LLM key (Claude/Gemini/GPT via Emergent) |
| `JWT_SECRET` | — | Auth token signing key |

### ORA Tuning (iter 331a defaults shown)
| Var | Default | Purpose |
|---|---|---|
| `ORA_SESSION_USD_CAP` | `5.00` | Halt session at this $ cost |
| `ORA_USD_WARN_FRACTION` | `0.80` | Warn at this fraction of cap |
| `ORA_STUCK_MINUTES` | `5.0` | Stuck-process watchdog threshold |
| `ORA_IDEMP_HITS` | `3` | Identical-edit halt threshold |
| `ORA_INTEGRATION_WINDOW` | `5` | Turns to look back for web_search |
| `ORA_AUTONOMY_LEVEL` | `all` | `off`\|`tier1_only`\|`all` |
| `ORA_MEMORY_ROOT` | `/app/memory` | Override for non-/app installs |
| `ORA_TOOLS_ROOT` | `/app` | Override for non-/app installs |
| `ORA_LOG_DIR` | `/var/log/supervisor` | Where read_logs looks |
| `ORA_DEPLOY_SCRIPT` | `/app/scripts/deploy.sh` | Override deploy script path |
| `DB_TYPE` | auto-detected | `atlas`\|`legion`\|`docker`\|`hetzner`\|`local` |
| `DEPLOY_PLATFORM` | `emergent` | `emergent`\|`hetzner`\|`docker`\|`local` |

### Optional (3rd-party features, only if used)
| Var | Used by |
|---|---|
| `TELEGRAM_BOT_TOKEN` + `TELEGRAM_CHAT_ID` | Guard alerts |
| `STRIPE_SECRET_KEY` + `STRIPE_WEBHOOK_SECRET` | Stripe integration |
| `TWILIO_ACCOUNT_SID` + `TWILIO_AUTH_TOKEN` + `TWILIO_WHATSAPP_FROM` | SMS / WhatsApp |
| `RETELL_API_KEY` + `RETELL_AGENT_ID` + `RETELL_FROM_NUMBER` | Voice agent |
| `RESEND_API_KEY` + `RESEND_FROM_EMAIL` | Email send |

## Council portability

`council_consult` uses the **Emergent LLM key** for peer review.
Same key as the main LLM — no extra credentials needed. To use a
different multi-LLM provider:

1. Set `COUNCIL_LLM_ENDPOINT` env var to your endpoint base URL.
2. Set `COUNCIL_LLM_KEY` to your key.
3. Council roles live in `/app/memory/tier1/COUNCIL_CONFIG.md` if present
   (otherwise fallback to legacy `_COUNCIL_ROLES` constant in ora_agent.py).

If `COUNCIL_LLM_ENDPOINT` is empty, council falls back to `EMERGENT_LLM_KEY`.

## MongoDB portability

Use the `DB_TYPE` env var to switch backends without code changes.
See `/app/backend/services/db_manager.py` for the full map. Built-in
defaults:

| `DB_TYPE` | Connection string (if `MONGO_URL` empty) |
|---|---|
| `atlas` | (no default — supply MONGO_URL with the +srv URI) |
| `legion` | `mongodb://aurem:aurem@legion.local:27017/aurem_db` |
| `docker` | `mongodb://mongo:27017/aurem_db` |
| `hetzner` | `mongodb://aurem:aurem@hetzner.local:27017/aurem_db` |
| `local` | `mongodb://localhost:27017/aurem_db` |

`MONGO_URL`, if set, ALWAYS overrides the default. `DB_TYPE` is
informational only when `MONGO_URL` is set.

## Verification of zero lock-in

| Lock-in vector | Status | Notes |
|---|---|---|
| Hardcoded `aurem.live` URLs | NONE in ORA core | All in `frontend/.env` |
| Hardcoded Emergent domains | NONE in ORA core | |
| `emergentintegrations` SDK | Single optional import | Gracefully falls back if missing |
| K8s service names | NONE in ORA core | |
| Cloudflare-specific code | NONE in ORA core | |
| Supervisor paths | Configurable via `ORA_LOG_DIR` | |
| MongoDB Atlas | Configurable via `DB_TYPE`/`MONGO_URL` | |

## Daily DB backup health (Sprint 3.5)

`/api/health/db` returns the current connection info + ping latency.
Wire it into your Morning Brief by reading the `db_type`, `mongo_url_redacted`,
and `ok` fields. If `ok=false`, Telegram alert.

Backup freshness: when you set up a backup cron on the new host, also
set `MONGO_BACKUP_LAST_TS` env var (or a file at `/app/memory/last_backup.txt`)
that the next sprint's morning brief can read. Threshold for alert: > 25 h
since last successful backup.
