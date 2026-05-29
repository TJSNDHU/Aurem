# SPEC 06 — Implementation Plan

> Read last (sixth). Updated 2026-05-28, iter D-57.
>
> This is the canonical build order. Phases marked ✅ are shipped;
> ⏳ are mid-flight; ⬜ are backlog.

## Phase 0 — Foundation ✅

- React 19 frontend bootstrap with CRA + Tailwind + shadcn/ui.
- FastAPI backend with Motor + APScheduler + uvicorn.
- MongoDB local (preview) + Atlas (prod, Canadian region).
- `.env` discipline: every URL/secret pulled from env, fail-fast on
  missing.

## Phase 1 — Auth + onboarding ✅

- bcrypt + JWT for user/admin/dev accounts.
- Email + 6-digit OTP for customers.
- Emergency reset secret one-shot for admin password recovery.
- Stripe Starter / Builder / Pro packages + webhook.

## Phase 2 — Customer-facing ORA ✅

- ORA chat (voice + text) for support, booking, reviews recovery,
  invoice nudges.
- Auto-website builder per-lead previews.
- Booking widget + ICS confirmation emails.
- Unsubscribe → 4-channel gate collapse.

## Phase 3 — Outreach engine ✅

- Ghost Scout (OSM + iProyal proxy harvest).
- CA / US country filter with NANP area-code allowlist (D-56).
- Multi-channel blast: Resend → Twilio SMS → WHAPI → Twilio WABA.
- WHAPI → Twilio WABA fall-through fix (D-57).
- Channel gating per lead.
- DNC + CASL block + unsubscribe enforcement.

## Phase 4 — Founder admin + AUREM CTO ✅

- Developer portal (BYOK + token wallet + dashboard).
- AUREM CTO chat with streaming + free-tier ladder + BYOK + Emergent
  LLM key.
- Per-turn model badges + temperature badge (D-57).
- ConfidenceBadge (D-53) + VerificationBadge (D-52) + HotLeadsBar (D-57).
- 3-layer auto-verification with code / GitHub / deploy gates.
- Real-execution tools (D-49): run-scout, import-leads, run-blast,
  db-stats.
- Real codebase + GitHub access (D-54): sandboxed file reads,
  /file slash command, GitHub commits API.
- Codebase Map drawer (D-55).
- Self-learning system with Sunday weekly review (D-53).
- Anti-hallucination GUARDRAIL (D-57).

## Phase 5 — Enterprise ✅

- SAML SSO with signed AuthnRequest, SCIM provisioning.
- Branding admin, trust center, SOC 2 PDF, MSA + SLA pages.
- Data residency selector (CA / US / EU).
- Unified audit log w/ 7-year retention.

## Phase 6 — Production deployment ⏳

- aurem.live live on Hetzner FSN1 + Cloudflare.
- Emergent platform "Save to Github" → push to `TJSNDHU/Aurem` →
  `commit_sha` populated on `/api/version` (PENDING founder action).
- Prod secret rotation (JWT, encryption key, emergency reset)
  + admin password reset — Mongo one-liner ready in
  `/app/memory/test_credentials.md` (PENDING founder action).
- Resend webhook URL → `https://aurem.live/api/webhooks/resend`
  (PENDING founder action in Resend dashboard).

## Phase 7 — Revenue acceleration ⬜

- D-58 candidate: auto-draft reply via LLM when hot-lead pill clicked.
- D-59 candidate: SMS reply webhook (Twilio status callback) for
  "🔥 Lead texted back" signals.
- Email-content A/B testing pipeline.
- Lead-scoring with verified-outcome learning loop.
- Stripe upsell nudges based on usage signals.

## Phase 8 — Scale + reliability ⬜

- ULTRAPLINIAN multi-model query scoring.
- GODMODE-CLASSIC parallel-race LLM pattern.
- AutoTune temperature + model-selection RL.
- Real Hetzner SSH deploy E2E (PENDING Hetzner API token).
- GitHub Repo Auto-Create + Branch Protection.
- Per-Message Rollback Button (backend logic).

## Phase 9 — Compliance + trust ⬜

- SOC 2 Type II audit (after 6 months evidence).
- Penetration testing.
- Data Subject Access Request (DSAR) workflow.
- French Canadian UI translation (Quebec / Law 25 strict-language).

## Phase 10 — Marketplace + multi-tenant scale ⬜

- White-label tenants (sub-domain).
- Plugin marketplace for third-party developers.
- Native PWA install prompts.
- Partner / referral program.

---

## Per-iter deliverables (D-40b → D-57)

| iter   | Deliverable                                                         | Tests       |
|---|---|---|
| D-40b  | "No code dump" output guard for non-tech replies                    | passing     |
| D-41   | AUREM-first rule (ban Figma / Vercel suggestions)                   | passing     |
| D-42   | GitHub OAuth one-click connect                                      | passing     |
| D-43   | Platform Secrets page + Maxx toggle + chat planning bar             | passing     |
| D-44   | Collapsible sidebar + Deploy / Domain / Database pages              | passing     |
| D-45   | Real backend deploy log stream                                      | passing     |
| D-46   | Security keys generation + Admin Security Keys panel                | passing     |
| D-47   | Save-to-GitHub dialog + model badges + rotation alerts              | passing     |
| D-48   | Cache-bust headers + /api/version + footer iter badge               | passing     |
| D-49   | CTO real-execution tools                                            | 6 / 6 ✅    |
| D-50   | Mobile composer fix + ORA bubble hidden                             | 8 / 8 ✅    |
| D-51   | Push + Deploy animations                                            | 14 / 14 ✅  |
| D-52   | 3-layer auto-verification                                           | 14 / 14 ✅  |
| D-52a  | Deploy CTA gated on GitHub GREEN                                    | 4 / 4 ✅    |
| D-53   | Self-learning + Sunday weekly review                                | 13 / 13 ✅  |
| D-54   | Real codebase + GitHub access                                       | 13 / 13 ✅  |
| D-55   | Codebase Map sidebar widget                                         | 8 / 8 ✅    |
| D-56   | Email-first blast + OSM Canada bug fix                              | 8 / 8 ✅    |
| D-57   | Temperature + Twilio WABA + Resend webhooks + hot-lead surfacing    | 11 / 11 ✅  |

Active ring: **166 / 166 pytests green**.

---

## How to add a new iter (canonical recipe)

1. Read `/app/memory/SPEC_INDEX.md` (you are here).
2. Read the relevant SPEC docs (1 through 5) for context.
3. Append your iter row to **Phase 6 / 7 / 8 …** above.
4. Add deliverables row to the per-iter table.
5. Bump `ITER` in `backend/routers/version_router.py`.
6. Write the pytest first (TDD) at
   `/app/backend/tests/test_<name>_d<N>.py`.
7. Code until green. Lint with ruff + ESLint.
8. Live E2E with curl against `REACT_APP_BACKEND_URL`.
9. One smoke screenshot (only one — never iterate
   implement → screenshot → implement).
10. Update `PRD.md` + `CHANGELOG.md` + this file.
11. Surface the iter in chat via the `finish` tool with brutal honesty.

## Anti-patterns to never repeat

- **Implement → screenshot → tweak → screenshot loop.** Trust your
  code; smoke-test once.
- **Adding routes without `/api` prefix.** Will silently 404 behind
  Kubernetes ingress.
- **Hardcoding secrets / URLs.** Forbidden — `.env` only.
- **Returning Mongo docs with `_id`.** Will 500 on JSON serialization.
- **Saying "sent ✅" when the channel actually failed.** Killed the
  D-56 / D-57 founder trust loop — fix the root cause, then say it.
- **Generating code from imagination instead of `_maybe_inject_codebase`.**
  D-54 + D-57 GUARDRAIL exist for exactly this reason.
- **Writing or modifying auth code without calling
  `integration_playbook_expert_v2`.** Auth is always an integration.
