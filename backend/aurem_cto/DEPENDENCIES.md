# AUREM CTO — Module Dependencies

> Updated 2026-05-26 · iter D-31 isolation slice

This module is **self-contained**. It can be extracted to a standalone
repo and deployed on its own domain in one day. The entire portability
contract lives below.

---

## Router prefix
All routes mount under `/aurem-cto/` (FastAPI APIRouter prefix). The
host application includes the router with `app.include_router(...)` and
nothing else.

## Database collections
Every Mongo write goes to a collection prefixed `aurem_cto_`:

| Collection                          | Purpose                              |
|-------------------------------------|--------------------------------------|
| `aurem_cto_deploy_configs`          | SSH target + encrypted private key   |
| `aurem_cto_deploy_runs`             | Live + historical deploy logs        |
| `aurem_cto_domain_configs`          | Apex domain + IP + DNS verification  |
| `aurem_cto_domain_verifications`    | 60-s probe history per domain        |
| `aurem_cto_github_links`            | Customer PAT (encrypted) + bot link  |
| `aurem_cto_github_repos`            | Repos managed by AUREM CTO bot       |
| `aurem_cto_chat_commits`            | Chat message ↔ commit SHA mapping    |
| `aurem_cto_unlock_requests`         | Customer code-access requests        |
| `aurem_cto_vault_audit_log`         | Every key encrypt/decrypt event      |
| `aurem_cto_server_hardenings`       | Server bootstrap reports             |

## Environment variables
All env vars are prefixed `AUREM_CTO_`. None are inherited from the host
application except where the host explicitly forwards them.

| Variable                       | Purpose                                          |
|--------------------------------|--------------------------------------------------|
| `AUREM_CTO_MASTER_KEY`         | HKDF master key for per-customer key derivation  |
| `AUREM_CTO_HETZNER_TOKEN`      | Hetzner Cloud API token (P0/P1)                  |
| `AUREM_CTO_GITHUB_BOT_PAT`     | Admin-scope PAT for the AUREM GitHub bot         |
| `AUREM_CTO_GITHUB_OAUTH_ID`    | OAuth app client_id (P3)                         |
| `AUREM_CTO_GITHUB_OAUTH_SECRET`| OAuth app client_secret (P3)                     |
| `AUREM_CTO_LE_STAGING`         | "1" → Let's Encrypt staging (default for E2E)    |
| `AUREM_CTO_PUBLIC_URL`         | Public URL of the AUREM CTO host (for redirects) |

The host application may forward `MONGO_URL` and `DB_NAME` via the
`set_db(db)` registration call — the module never imports them directly.

---

## Whitelisted external imports — **the only 3 allowed**

Per Watchdog review (D-30), the following three imports from the host
application are explicitly whitelisted because forking them would
duplicate ~80 LOC of security-critical code we want to keep
centrally-managed:

| Import                                              | Why                                |
|-----------------------------------------------------|------------------------------------|
| `services.byok_store._encrypt / _decrypt`           | Fernet at-rest secrets encryption  |
| `routers.developer_portal_router._current_dev`      | Dev-portal + admin JWT decode      |
| `config.JWT_SECRET, config.JWT_ALGORITHM`           | JWT validation constants           |

**Every other module import is forbidden.** A unit test in
`/app/aurem_cto/tests/test_isolation.py` enforces this by AST-scanning
all `.py` files under `/app/aurem_cto/`.

If a future feature needs a fourth host import:
1. Open an issue + Watchdog review.
2. Either fork the dependency into `/app/aurem_cto/services/`
3. Or update this DEPENDENCIES.md and the isolation test.

---

## External Python packages

Production-required (all already in `/app/backend/requirements.txt`):

| Package      | Used by                                 |
|--------------|-----------------------------------------|
| `fastapi`    | router + endpoint wiring                |
| `pydantic`   | request/response validation             |
| `asyncssh`   | non-blocking SSH for deploy + harden    |
| `httpx`      | GitHub API + Hetzner API + DNS-over-HTTPS|
| `cryptography`| HKDF + Fernet (via byok_store)         |
| `dnspython`  | local DNS probe for domain verification (added D-31) |
| `motor`      | async Mongo driver (host provides)      |

---

## External services

| Service           | Purpose                                |
|-------------------|----------------------------------------|
| GitHub REST API   | Repo create, branch protection, OAuth  |
| Hetzner Cloud API | CX22 provisioning for customer servers |
| Let's Encrypt     | TLS issuance via Caddy on customer box |
| Customer SSH host | All deploy + hardening operations      |

---

## Extraction recipe

To spin out `aurem_cto` into its own repo + domain:

1. Copy `/app/aurem_cto/` into the new repo root.
2. Replace the 3 whitelisted imports with the forked copies in
   `services/byok_store.py`, `services/_current_dev.py`,
   `services/jwt_config.py` (stubs already shipped in this folder for
   easy swap).
3. Create a FastAPI entrypoint that mounts only the AUREM CTO router.
4. Point a new `MONGO_URL` at a dedicated database.
5. Set the 7 `AUREM_CTO_*` env vars.
6. Deploy. Estimated time: one working day.
