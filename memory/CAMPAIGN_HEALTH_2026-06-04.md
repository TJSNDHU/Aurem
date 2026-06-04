# Campaign Health Snapshot — 2026-06-04 (iter D-63)

## Health Map: 🟢 5 · 🟡 6 · 🔴 0

| Component        | Status   | Headline                                          |
|------------------|----------|---------------------------------------------------|
| ghost_scout      | 🟢 green  | 27 runs last 24h                                  |
| auto_blast       | 🟡 yellow | running but pool empty                            |
| resend           | 🟢 green  | 10 deliveries last 24h                            |
| twilio           | 🟡 yellow | SMS OK, WhatsApp number missing                   |
| whapi            | 🟡 yellow | WHAPI disabled by env flag                        |
| proactive_ora    | 🟢 green  | 1 rule(s) on                                      |
| template_perf    | 🟡 yellow | no events tracked yet                             |
| daily_brief      | 🟢 green  | last evening brief sent                           |
| lead_pool        | 🟡 yellow | campaign caught up · 1966 blasted / 2009 total    |
| emergent_llm     | 🟢 green  | EMERGENT_LLM_KEY set                              |
| resend_webhook   | 🟡 yellow | no webhook events last 24h                        |

## Lead Activity

| Metric                          | Value         |
|---------------------------------|---------------|
| Total leads in DB               | 2,009         |
| New leads today (UTC)           | 42            |
| Contacted today                 | 0             |
| With email                      | 1,396 (69%)   |
| With phone                      | 556 (27%)     |
| No contact data (silent)        | 277 (13%)     |

## Lead Status Distribution

| Status         | Count |
|----------------|-------|
| emailed        | 1,355 |
| new            | 470   |
| queued         | 100   |
| scanned        | 44    |
| internal_test  | 30    |
| whatsapp_sent  | 6     |
| contacted      | 4     |

## Issues (6 yellow — none blocking)

### 🟡 1 · auto_blast — pool empty
- **Why:** `1966/2009 blasted`. Campaign caught up. No fresh contactable leads.
- **Autofix available:** `topup_via_scout` (Ghost Scout already running 27x/24h).
- **Action:** Wait — scout will repopulate. Or trigger manual scout run from `/admin/scout`.

### 🟡 2 · twilio — WhatsApp number missing
- **Why:** `TWILIO_WA_FROM_NUMBER` env var not set.
- **Impact:** SMS works; WhatsApp via Twilio WABA doesn't.
- **Action:** Either set the env var or proceed with planned Meta WhatsApp Cloud API migration.

### 🟡 3 · whapi — disabled
- **Why:** WHAPI disabled by env flag (intentional). Twilio WABA fallback is wired (iter D-57).
- **Action:** No action needed; safe state.

### 🟡 4 · template_perf — no events tracked
- **Why:** Outgoing emails aren't tagged with `template_id` yet.
- **Action:** Add `template_id` to outgoing mail headers so opens/clicks attribute.

### 🟡 5 · lead_pool — caught up (same as #1)
- **Same root cause** as auto_blast. Will resolve when Scout adds new leads.

### 🟡 6 · resend_webhook — no webhook events
- **Why:** No webhook URL configured in Resend dashboard OR no emails opened in 24h.
- **Action:** Set webhook URL `${PROD}/api/admin/resend/webhook` in Resend dashboard.

## Read of the Day

System is **healthy, not broken**. The 6 yellows are all "waiting for a config to be filled in"
or "campaign caught up so engine idling" — neither is a bug. Auto-blast did `1966 sends` to
reach 98% saturation; today's 0 contacts reflects the pool-empty state. Once Scout drops
fresh leads (~27 cycles/day), the engine will fire again.

**One actionable item:** add Resend webhook URL → unlocks template_perf tracking which is
itself yellow. Two birds, one config.
