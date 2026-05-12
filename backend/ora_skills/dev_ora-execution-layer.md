# AUREM DEV SKILL: ora-execution-layer (P2 — Python Subprocess Bridge)

## Status
**LIVE as of iter 322em.** ORA now talks to the Linux kernel via `subprocess.run()`.
No mocks. Real argv-only execution. `shell=False`. Whitelisted commands only.

This is the bridge between ORA's brain (LLM) and the actual machine. When the founder asks "who is running this?" or "what's deployed?" or "is there free disk?", you USE this layer to get the real answer from the kernel.

---

## The Tool

Call it like any other ORA tool:
```json
POST /api/ora-tools/execute
{"tool": "shell_exec", "args": {"command": "whoami", "args": []}}
```

Response:
```json
{
  "ok": true,
  "command": "whoami",
  "binary": "/usr/bin/whoami",
  "returncode": 0,
  "stdout": "root\n",
  "stderr": "",
  "elapsed_ms": 8
}
```

---

## Whitelisted commands (verified iter 322em)

| Group | Commands | Use |
|---|---|---|
| **Identity** | `whoami`, `id`, `pwd`, `hostname`, `uname`, `uptime`, `date`, `env` | "Who am I? Where am I? What kernel?" |
| **Filesystem** | `ls`, `find`, `wc`, `stat`, `du`, `file` | Inspect paths under `/app`, `/var/log/supervisor`, `/tmp` |
| **System status** | `df`, `free`, `ps` | Disk / RAM / running processes |
| **Toolchain** | `which`, `whereis`, `python3 --version`, `node --version`, `pip list`, `yarn --version`, `ruff` | What's installed? What versions? |
| **VCS (read-only)** | `git status`, `git log`, `git diff`, `git show`, `git branch`, `git remote`, `git rev-parse`, `git describe`, `git blame`, `git config`, `git ls-files`, `git tag` | What's deployed? What changed? |
| **Services (read-only)** | `supervisorctl status` | Is backend/frontend up? |

Anything NOT in the whitelist returns `{ok:false, error:"command not in whitelist"}`. Don't try to bypass — ask the founder to extend the whitelist instead.

---

## Hard security rules

| Rule | What |
|---|---|
| `shell=False` always | No shell expansion. argv list only. |
| Argv-token blocklist | `;`, `&&`, `||`, `|`, `>`, `<`, `$(`, `` ` ``, `..`, `/etc/passwd`, `/etc/shadow` |
| Path-arg validation | `ls`, `find`, `wc`, `stat`, `du`, `file` only allow paths under `/app`, `/var/log/supervisor`, `/tmp`, `.`, or `-` flag |
| Per-command sub-allowlist | `git` accepts only read-only verbs (no push/commit/checkout/reset/rebase). `supervisorctl` accepts only `status`. `python3` only `--version`. |
| Stripped env | Subprocess gets only `PATH`, `HOME`, `LANG`. No `MONGO_URL`, `JWT_SECRET`, `STRIPE_KEY`, etc. |
| `env` output redaction | If you do call `env`, keys matching `KEY|SECRET|TOKEN|PASSWORD|MONGO_URL|STRIPE|RESEND|TWILIO|JWT_SECRET|GROQ|OPENAI|ANTHROPIC|EMERGENT` come back as `<redacted>`. |
| Hard timeout | Per-command, ranging 3-12s. Anything slower returns `{ok:false, error:"timeout after Ns"}` |
| Output cap | stdout capped at 4000 chars, stderr at 1000. `truncated:true` flag set if hit. |
| Audit log | Every call lands in `ora_tool_invocations` with actor email + args + ok status |

---

## How to USE this layer (the Charter still applies)

**Wrong**: "The host is named `aurem-prod-1`." ❌ (you didn't check)

**Right**:
```
Call: shell_exec(command="hostname")
→ stdout: "agent-env-5face3c8-a8b0-4e26-8615-9f6753aa148c"
Quote: The hostname is `agent-env-5face3c8-a8b0-4e26-8615-9f6753aa148c` (verified via shell_exec).
```

### Investigation patterns

**"What user is the backend running as?"**
```
shell_exec(command="whoami")
→ "root"
```

**"What's deployed?"**
```
shell_exec(command="git", args=["log", "--oneline", "-5"])
→ 5 real commit lines
```

**"How much disk left?"**
```
shell_exec(command="df", args=["-h"])
→ paste table, identify the row for `/`
```

**"Is some Python package installed?"**
```
shell_exec(command="pip", args=["show", "motor"])
→ Name, Version, Location
```

**"What changed since last deploy?"**
```
shell_exec(command="git", args=["status", "--short"])
→ list of modified files
```

---

## What you CANNOT do (P2 boundary)

| Want | Reason | When |
|---|---|---|
| `git commit` / `git push` | Write op. P3. | After approval-gate UI ships |
| `rm`, `mv`, `mkdir`, `chmod` | Filesystem write. P3. | Same |
| `supervisorctl restart` | Service control. P3. | With per-service whitelist |
| `pytest` execution | Compute-heavy + writes test reports. P2.5. | Coming next iter |
| `sudo *` | Privilege escalation. Hard-NEVER. | Never. Period. |
| External HTTP (`curl google.com`) | Egress = data exfiltration risk. P5. | Per-domain allowlist |
| `cat /etc/passwd` | Forbidden path. Hard-NEVER. | Never. |

When ANY of these come up, refuse and tell the founder which phase ships it.

---

## Audit trail

Every `shell_exec` call writes to `ora_tool_invocations`:
```json
{
  "ts": "2026-05-12T04:38:26",
  "actor": "<admin_email>",
  "tool": "shell_exec",
  "args": {"command": "whoami", "args": []},
  "ok": true,
  "elapsed_ms": 8
}
```

You can grep your own history:
```
curl /api/ora-tools/invocations?tool=shell_exec&limit=30
```

This is HOW the founder verifies you actually ran the command and didn't fabricate the output.

---

## Founder rule (THE LAW still applies)

Even with execution power, the Zero Hallucination Charter wins. If the kernel returns `rc=1` or `stderr` has an error, you state that plainly. You don't say "it probably worked." You don't say "let's assume." You quote the real return code and the real stderr.

The kernel doesn't lie. You don't either.

---

## Iter index addition

| Iter | Lesson |
|---|---|
| 322ej | P1 — 9 read-only tools (grep/curl/db/git/lint) |
| 322ek | Zero Hallucination Charter (THE LAW) |
| 322el | Tool-call loop in `llm_gateway.call_llm_with_tools` — LLM can actually invoke tools mid-conversation |
| 322em | **THIS SKILL — Python Subprocess Bridge** (Execution Layer, real kernel calls) |

---

**Bottom line**: You can now talk to the Linux kernel. Use it like a senior dev does — surgical, audited, never `rm -rf`. The founder is watching the audit log.
