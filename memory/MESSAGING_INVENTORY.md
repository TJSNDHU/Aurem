# AUREM — Outbound Messaging Inventory
**Date**: 2026-04-29 (iter 282d) · **Scope**: Every email / SMS / WhatsApp / push the system sends · Audit only

---

## 📊 Totals at a glance
- **Email subjects found**: 66 distinct (some dynamic, e.g. `{biz}`)
- **SMS templates**: 11 (ReRoots-branded, tenant-scoped)
- **WhatsApp sends**: 30+ call sites, ~15 distinct templates
- **Push notifications**: 8 trigger types (VAPID, `notification_triggers.py`)
- **Active sequences (multi-step drips)**: 3
- **Transport**: Resend (email), Twilio (SMS), Twilio WA (WhatsApp), pywebpush (web push)

⚠️ **ReRoots/OROÉ/AURA-GEN subjects** are tenant-white-label templates (same engine, different brand) — **not sent under AUREM brand**.

---

## 🟠 1. EMAIL — by category

### A. Authentication & account lifecycle (transactional, critical)
| # | Subject | Trigger | File |
|---|---|---|---|
| 1 | `AUREM - Verify Your Email` | Signup | `email_service.py` |
| 2 | `Welcome to AUREM` (short) | Post-signup | `email_service.py` |
| 3 | `Welcome to AUREM, {to_name} — Your AI Employee Awaits` | First login welcome | `welcome_package.py` |
| 4 | `Welcome to AUREM — Your Business ID: {bid}` | BIN provisioned | `welcome_package.py` |
| 5 | `Reset your ReRoots password` | Password reset (⚠ branded ReRoots) | `password_reset_router.py` |

### B. Trial drip sequence (6 emails over 30 days)
Trigger: `trial_sessions` collection · runs on `trial_scheduler` cron · file: `services/trial_scheduler.py`
| Day | Subject |
|---|---|
| 3  | `Your AUREM Power Trial is working` |
| 5  | `2 days left in your AUREM Trial` |
| 6  | `Tomorrow is your final trial day` |
| 7  | `Trial ends today — your wins at risk` |
| 14 | `Check your AUREM score this week` |
| 30 | `Your AUREM site score dropped` |

### C. Lead-stage drip (6 steps over 60 days)
Trigger: lead enters `called_no_response` → `drip_sequencer.py`  
Channels mixed (E = email, W = WhatsApp, S = SMS, C = call)
| Day | Channel | Template ID |
|---|---|---|
| 1  | W | `drip_day1_wa_nudge` |
| 3  | E | `drip_day3_email_trial` — subj: `{biz} — extended 14-day free trial` |
| 7  | W | `drip_day7_wa_objection` |
| 14 | S | `drip_day14_sms_urgency` |
| 30 | C | `drip_day30_ora_redial` (voice, not email) |
| 60 | E | `drip_day60_email_final_offer` — subj: `{biz} — final 50% off offer (today only)` |

### D. Winback sequence (3 emails post-churn)
File: `services/winback_sequence.py`
| # | Subject |
|---|---|
| 1 | `{biz} — sorry we let you down` |
| 2 | `{biz} — 15 minutes with me, on the house` |
| 3 | `{biz} — ${29} CAD on the house` (domain credit) |

### E. Site Monitor alerts (free + paid tier)
File: `services/site_monitor.py` + `routers/site_monitor_router.py`
| Subject | When |
|---|---|
| `[AUREM] Now monitoring {url}` | Endpoint added |
| `[AUREM] DOWN: {result['url']}` | Endpoint goes down |
| `[AUREM] RECOVERED: {result['url']}` | Endpoint recovers |
| `[AUREM] System Pulse Alert — {len(to_alert)} endpoint(s) failing` | Multi-endpoint alert (admin/founder) |
| `[AUREM] AWB safety alert — {N} lead(s) flagged` | **NEW iter 282b** · founder alert on duplicate-site loop |

### F. Customer lifecycle & outreach
| Subject | Trigger |
|---|---|
| `Activate AUREM — paste this snippet (30 seconds)` | Pixel not installed, 24h after signup |
| `One step left — install your AUREM pixel` | Pixel nudge (later) |
| `{biz} — your free site is live` | AWB built a site · **iter 282 fixed URL bug** |
| `Edit your {biz} site` | Customer edit magic link |
| `AUREM check-in — {biz}` | Manual outreach |
| `AUREM — let's talk about your {biz}` | Upgrade nudge |
| `Your AUREM monthly report — {month}` | 1st of month auto-PDF |
| `Your AUREM AI Cost Report — {month}` | Monthly cost breakdown |
| `AUREM found {N} issues on {domain} — fixing tonight` | Autonomous repair engine |
| `Tried reaching you about {business}'s website` | Day-1 post-call follow-up |
| `Your AUREM scan: {domain} — score {X}/100` | Public scan completes |
| `Your AUREM SEO preview for {url} — Grade {grade}` | SEO preview |
| `Free website audit — {business_name}` | Lead magnet outcome |
| `Free 6-point website audit — {biz}` | Lead magnet (v2) |
| `Your AUREM trial ends tomorrow — keep your fixes` | Trial T-1 |

### G. Daily Intel newsletter (opted-in subscribers)
File: `routers/daily_intel_router.py`
| Subject |
|---|
| `Confirm your AUREM Daily Intel subscription` |
| `AUREM Daily Intel · {niche} · {date}` |

### H. System/admin notifications
| Subject | To |
|---|---|
| `[AUREM] New {lead['topic']} request — {lead['name']}` | Admin/founder |

### I. Tenant white-label (not AUREM brand)
ReRoots / Maison OROÉ / AURA-GEN templates — triggered by tenant platform, not AUREM corporate. Includes:
- ReRoots VIP welcome, order confirmation, refill reminders, skincare weather tips, cart abandonment, review requests, birthday discount, refund approved, store credit added, VIP status unlocked, founding member discount
- Maison OROÉ VIP welcome
- AURA-GEN 3-day tips, cart abandonment

➡️ **These fire only when a ReRoots/OROÉ/AURA-GEN tenant's events trigger them.** AUREM corporate has ZERO of these subjects going out.

---

## 💬 2. SMS (Twilio)

### ReRoots-branded (tenant white-label)
File: `pillars/sales/routes/blast_service.py`
1. Order confirmation
2. Shipping tracking
3. Delivery confirmation
4. Verification code (OTP)
5. VIP welcome
6. Promo code blast
7. Back-in-stock alert
8. Cart abandonment
9. Review request
10. Birthday discount
11. (Drip day-14 urgency — from `drip_sequencer.py`)

### AUREM corporate SMS
- **Very few** — most outbound goes via WhatsApp (cheaper + no 10DLC block). Main AUREM SMS uses:
  - Drip day 14 urgency template (from lead drip sequence)
  - Test/debug sends via `sms_alerts_router.py`

⚠️ **10DLC status**: still pending carrier approval (known blocker from iter 281). Right now AUREM-originated SMS may be filtered. ReRoots SMS runs under a different Twilio account/brand.

---

## 📱 3. WHATSAPP (Twilio WhatsApp Business)

### Customer/lead-facing (via `drip_sequencer.py` + outreach)
1. **Day-1 drip nudge** — "Just tried calling you about {biz}'s free sample website"
2. **Day-7 drip objection** — "What's holding you back?"
3. **Welcome WhatsApp** — "Welcome to *AUREM*, {business_name}! 🎉"
4. **Post-payment confirmation** (from `stripe_payment_router.py`)
5. **Site monitor incident notice** (if WhatsApp preferred over email)
6. **Lead lifecycle manual blasts** (`routers/lead_lifecycle_router.py` → `_send_wa`)
7. **Omnichannel hub outbound** (agent-triggered via `routers/omnichannel_hub.py`)
8. **Customer 360 actions** (admin-triggered via `routers/customer_360_actions_router.py`)

### Admin/founder alerts (sent to `FOUNDER_WHATSAPP`)
9. **AWB Safety Alert** — NEW iter 282b · "3+ duplicate sites in 24h for lead X"
10. **Verification regression** — "AUREM VERIFICATION REGRESSION: {lead}"
11. **Pipeline escalation Safe Mode** — "AUREM PIPELINE ESCALATION: Tenant {id} entered Safe Mode"
12. **Boardroom digest** — "👔 *AUREM Boardroom — last {days}d*"
13. **Anomaly alerts** (3 flavors: cache hit drop, pixel buffer flush fail, system verdict degraded)
14. **Auto-restore complete** — "AUREM: Auto-restore completed. Backup from {col} restored."
15. **Sovereign node status** (routed via sovereign_node_router)

---

## 🔔 4. WEB PUSH (VAPID, pywebpush)

File: `services/notification_triggers.py` — 8 trigger types
| Type | Title | Example body |
|---|---|---|
| `vip_lead` | **New VIP Lead** | "{lead_name} — {win_prob}% win prob" (Approve/Skip actions) |
| `invoice_paid` | **Payment Received** | "${amount} from {client_name}" |
| `approval_needed` | **ORA Needs You** | "{action_description}" (Yes/No actions) |
| `morning_brief` | **Morning Brief** | "{handled_count} done. {attention_count} need you" |
| `website_issue` | **Site Issue Fixed** | "{issue_type} auto-repaired" |
| `anomaly_detected` | **AUREM Alert** | "{anomaly_description}" |
| `pipeline_completed` | **OODA Complete** | "{actions_taken} actions today" |
| `welcome` | **Welcome to AUREM** | "Your Business ID: {business_id}" |

---

## 🤖 5. TELEGRAM (admin ops only)
Files: `services/monday_brief.py` (lines 92), `services/autopilot_brief_notifier.py` (line 62)
- **Monday morning board digest** — sent to admin Telegram chat
- **Autopilot morning run report** — after AWB autopilot finishes nightly run

---

## 🗂️ Summary by Tier

| Channel | AUREM-branded | Tenant-branded | Admin/founder-only |
|---|---|---|---|
| Email  | ~30 templates across auth + lifecycle + drips + monitors + system | ~16 (ReRoots/OROÉ/AURA-GEN) | 3 (Pillars, AWB Safety, new lead alerts) |
| SMS    | ~2 (drip day-14 + debug) | 11 (all ReRoots) | 0 |
| WhatsApp | ~8 customer-facing | 0 | 7 (Founder alerts) |
| Push   | 8 trigger types | 0 | (same, scoped per-tenant) |
| Telegram | 0 | 0 | 2 (Monday digest + autopilot brief) |

---

## 🎯 Observations (no code changes suggested — just visibility)

1. **High volume risk**: Trial drip (6) + lead drip (6) + winback (3) + monthly report + pixel nudges + scan reports can stack up for one customer. Worth checking `communication_preferences` honors `email_frequency_cap`.
2. **ReRoots tenant templates** live inside the AUREM codebase. If you ever decommission that tenant, consider moving tenant-specific templates to `pillars/sales/templates/reroots/` for clean separation.
3. **Iter 282 AWB bug** would have triggered template #47 (`{biz} — your free site is live`) 400+ times per lead. Already fixed — DB unique index + daily safety cron will alert founder (WhatsApp + email) if >3 active sites per lead per 24h.
4. **SMS is light** — only ~2 AUREM corporate templates. Most lead comms routed through WhatsApp to dodge 10DLC pending status. When 10DLC approves, SMS drip expansion is an option.
5. **Push notifications** are wired but require user to have granted permission in the `/ora` PWA or portal. Current adoption unknown (worth checking `push_subscriptions` count).
6. **Telegram briefs** assume `TELEGRAM_CHAT_ID` env var set. If not, fails silently — worth surfacing in admin diagnostics.

---

**File saved**: `/app/memory/MESSAGING_INVENTORY.md`
