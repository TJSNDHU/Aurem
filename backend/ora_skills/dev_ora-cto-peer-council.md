# AUREM SKILL: ora-cto-peer-council (HISTORICAL — superseded)

> **CANONICAL SOURCE:** `dev_ora-cto-final-complete.md`
>
> This file documents the **P4 Council layer only** (iter 322eo). For the
> full 35-tool ORA CTO surface — including governance gates
> (`safe_edit_with_council`, `shell_exec_with_council`, `propose_commit`)
> and infrastructure / business-engine tools — see the canonical file.
>
> **Do not extend this file.** Add new tools or workflows to the
> canonical doc instead.

---

## What this file still documents — the 5-layer foundation

The ORA CTO stack was built in layers. This is the historical record of
how Layer 5 (Council) came online at iter 322eo.

| Layer | Iter | Capability |
|---|---|---|
| Brain   | 322ek | Zero Hallucination Charter (THE LAW) |
| Read    | 322ej | Read-only tools (grep / view / curl / db / git / lint) |
| Loop    | 322el | LLM gateway tool-calling — agents invoke tools mid-conversation |
| Execute | 322em | `shell_exec` — kernel-level subprocess |
| Write   | 322en | `safe_edit` + `restart_service` |
| Council | 322eo | `peer_review` / `code_review` / `security_scan` / `council_consult` |
| Gates   | 322eq | `safe_edit_with_council`, `shell_exec_with_council` |
| Commit  | 322er | `propose_commit` |
| Surface | 322es | `/admin/ora-chat` CTO Mode (full preview→deploy→rollback) |
| Build   | 322eu+ | `create_file`, `pytest_run`, `pip_propose`, `cloudflare_dns_*`, business engines |

---

## The 4 Council tools — exact signatures

### `code_review` (deterministic, no LLM cost)

```json
POST /api/ora-tools/execute
{"tool":"code_review","args":{"file_path":"/app/backend/services/foo.py","review_type":"full"}}
```

Wraps `services/aurem_agents/AUREMCodeReviewer`. Returns `score` (0-100),
issue list with `severity` + `line`, and concrete suggestions.

### `security_scan` (deterministic, no LLM cost)

```json
{"tool":"security_scan","args":{"scan_type":"full","target":"backend"}}
```

Wraps `services/aurem_agents/AUREMSecurityScanner`. Covers OWASP Top 10
+ SaaS auth/payment paths + Mongo injection + frontend XSS/CSRF/secrets.

### `peer_review` (LLM, single role)

```json
{"tool":"peer_review","args":{
  "role":"security",
  "question":"<proposed change>",
  "context":"<optional diff/log>"
}}
```

Loads `/app/backend/ora_skills/agent_<role>.md` as the peer's system
prompt. Roles: `security`, `backend`, `devops`, `qa`, `design`,
`finance`, `marketing`, `pricing`.

### `council_consult` (LLM × N, parallel, max 5 peers)

```json
{"tool":"council_consult","args":{
  "question":"<the change>",
  "roles":["security","backend","qa"]
}}
```

Same per-role logic as `peer_review`, fanned out concurrently.

---

## Audit trail

All 4 tools land in `ora_tool_invocations` with `tool=peer_review` /
`code_review` / `security_scan` / `council_consult`. The founder grep:

```bash
curl -s "$BACKEND_URL/api/ora-tools/invocations?tool=council_consult&limit=10"
```

Governance overrides land in the separate `ora_governance_overrides`
collection (added in iter 322eq).

---

## How the council layer plugs into the autonomous loop

See the **Mandatory workflow** section of `dev_ora-cto-final-complete.md`
— the canonical doc owns the loop spec. This file only documents the
council tools themselves and their iter 322eo origin.

---

**Status**: Historical reference. New work must extend the canonical doc.
