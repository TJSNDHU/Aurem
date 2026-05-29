# SPEC 03 — App Flow Document (founder + developer surfaces)

> Read fourth. Updated 2026-05-28, iter D-57.
>
> Covers the AUREM CTO chat, developer portal, and admin CTO surfaces
> built in iters D-40b → D-57. For the CUSTOMER + admin mission-control
> flow (homepage, /platform/signup, /my portal, repair funnel, edit
> portal, 35+ admin sub-routes) read **`USER_FLOW_MAP.md`** —
> the two files are complementary.
>
> Every screen + every meaningful click. Use this when wiring UI →
> backend endpoint pairs.

## Top-level surfaces

```
/                          Public landing (marketing + lead capture)
/book                      Public booking widget (per-tenant)
/portal/*                  Customer portal (post-OTP)
/developers/*              Developer portal (BYOK + AUREM CTO)
/admin/*                   Founder admin
/enterprise/*              Enterprise portal (SAML / SCIM / audit)
/trust-center              Public compliance hub (SOC 2 PDF, MSA, SLA)
```

---

## Founder journey — AUREM CTO chat (the daily driver)

1. `/developers/login`
   - Email + password → `/api/auth/login` → JWT in localStorage.
2. `/developers/dashboard`
   - Mounts `DevCtoChatPanel.jsx`. Renders:
     - Sidebar (collapsible, D-44)
     - HotLeadsBar at top (D-57) — 🔥 pills if Resend webhooks fired
     - VerificationBadge below (D-52) — ⏳ / ✅ / ❌ for code / github / deploy
     - ConfidenceBadge (D-53) — "Used 47×, 94% verified ✅"
     - Chat scroll area with per-turn ModelBadge + TemperatureBadge (D-57)
     - PlanningBar (horizontal scroll on mobile, D-50)
     - Composer (textarea + Attach / Maxx / Github / Send buttons)
3. **Composer button actions**
   - **Attach (📎)** → file picker → POST `/api/developers/cto/upload`
   - **Maxx (⚡)** → toggle localStorage `aurem.maxx_mode`; emits
     `aurem-maxx-toggle` event.
   - **Github (🐙)** → opens `SaveToGithubDialog` (D-47).
   - **Send (➤)** → POST `/api/developers/cto/chat/stream` (SSE).
   - **Files** (D-55) — toggles `CodebaseMap` drawer on the right.
4. **Slash commands**
   - `/file <path>` → D-54 sandboxed file read injected as system msg.
   - `/file <path> <start> <end>` → specific line range.
   - `/search <query>` → Tavily web search injected.
   - Free text "line N of <file>" → same as `/file` shortcut.
5. **Save to GitHub flow (D-47 + D-51)**
   - Open dialog → list repos via `/api/developers/github/repos`.
   - Pick repo + branch + message → POST `/commit`.
   - Animated push: spinner → progress bar (0→35→60→85→100) →
     SuccessCelebration (confetti + commit SHA + auto-dismiss 3s).
   - On success → D-52 verify via `/cto/verify/github` → if GREEN,
     Deploy CTA appears (D-52a gate).
   - Deploy CTA → `DeployProgressDialog` → POST `/cto/verify/deploy`
     polls `aurem.live/api/version` every 5s for up to 120s.
6. **Hot-lead pill click (D-57)**
   - Composer auto-fills: "Draft a reply to {business} ({email}) —
     they just opened our email 5 min ago."
   - Founder presses Send.

### Empty / loading / error states for the chat panel

| State                                | What founder sees |
|---|---|
| First load, no history               | Empty chat with "Tell AUREM CTO what to build…" placeholder. |
| Streaming a turn                     | ProgressBar fills as tokens arrive; ModelBadge shows tier+provider. |
| Verification CHECKING                | Yellow ⏳ row in VerificationBadge. |
| Verification RED                     | Red ❌ row with reason ("commit not found"). |
| Verification GREEN                   | Green ✅ row + clickable "view" link to GitHub. |
| Deploy CTA gated                     | "Deploy unlocks once GitHub verification turns ✅ GREEN" pill (D-52a). |
| GitHub OAuth not connected           | Save dialog: "Connect GitHub on /developers/connect first." |
| Token wallet empty                   | Banner: "Out of free tokens — top up or BYOK." |

---

## SMB customer journey

1. **Land on AI-built preview**
   - Email click → `/preview/<lead_id>` → personalized AUREM-built site.
   - Loud orange CTA: "Book a free 15-min call".
2. **Booking**
   - `/book?tenant=<slug>` → email + 6-digit OTP.
   - Calendar picker → confirms → Resend confirmation + ICS attached.
3. **Portal (`/portal`)**
   - Upcoming bookings, recent messages, invoices, lead history.
   - "Talk to ORA" — chat with the customer-facing agent.
4. **Unsubscribe**
   - Every email footer: 1-click `/api/leads/unsub?token=…`.
   - Server flips all 4 channel-gates to False + writes to
     `unified_audit_log`.

---

## Developer journey (BYOK)

1. `/developers/signup` → email + password + invite/code.
2. Email OTP verify → JWT.
3. `/developers/keys` — paste OpenAI / Anthropic / Gemini key →
   stored encrypted in `customer_security_keys` (AES-256-GCM).
4. `/developers/api-tokens` → mint long-lived token for the AUREM
   CTO API.
5. `/developers/dashboard` → same chat as founder but scoped to
   their own `project_id`.
6. `/developers/connect` → GitHub OAuth (D-42) → token saved to
   `developer_github_links`.

---

## Admin journey

1. `/admin/login` → bcrypt + JWT super_admin.
2. `/admin/security-keys` (D-46) — view + rotate JWT / encryption /
   emergency-reset secrets.
3. `/admin/founder-customers` — read-only customer list with quick
   actions (impersonate, refund, dunning).
4. `/admin/leads` — campaign_leads table with filters: status,
   country, hot_lead_flag, channel_gating.
5. `/admin/blast` — run-now, dry-run, pause, status.
6. `/admin/audit` — `unified_audit_log` paged view.

---

## Enterprise journey

1. `/enterprise/leads` — public form → `enterprise_leads` collection.
2. `/enterprise/sso/saml/init` — generate SP metadata XML.
3. `/enterprise/sso/saml/acs` — receives IdP POST → user provisioned
   or matched → JWT.
4. `/enterprise/scim/v2/Users` — IdP pushes user lifecycle events.
5. `/enterprise/audit` — paged audit log per org.
6. `/enterprise/residency` — region selector (CA / US / EU).

---

## Critical empty / error states

| Surface                       | Empty                              | Error                                                         |
|---|---|---|
| Founder dashboard             | "First time? Ask AUREM CTO to scout 20 salons in Mississauga."     | Loud red banner: "Backend unreachable — preview env starting up."    |
| Hot leads bar (D-57)          | Hidden (renders nothing)           | Hidden + console warn.                                        |
| VerificationBadge (D-52)      | Hidden until first event           | RED row with reason text.                                     |
| ConfidenceBadge (D-53)        | Hidden when n=0                    | Hidden — silent fail allowed.                                 |
| CodebaseMap (D-55)            | "Loading backend…" / "No files."   | Red error block with detail.                                  |
| Save-to-GitHub                | "Could not list repos — connect GitHub on /developers/connect."     | Red error pill below input.                                          |
| DeployProgressDialog (D-51)   | n/a                                | "Deploy did not flip to D-57 within 2 minutes."               |
| Auto-blast                    | "no-eligible-leads" reason         | last_run_note carries the reason. UI shows yellow ⚠ banner.   |
