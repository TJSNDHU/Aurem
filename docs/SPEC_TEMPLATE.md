# AUREM Feature Spec Template
> Every new feature MUST follow this 4-step discipline. No exceptions.

---

## STEP 1 — SPEC (before any code)

Write exactly 3 sentences:
1. **What** we are building (the feature name and scope)
2. **Why** it matters (what problem it solves for the user/business)
3. **Done when** (specific measurable success criteria)

Example:
> We are building a Partner Referral Portal where tenants earn rewards for referring other tenants.
> This creates viral growth loops and reduces customer acquisition cost by leveraging existing customers.
> Done when: referral link generation works, referred tenant signup is tracked, and reward credits appear in the referrer's dashboard.

**Show spec. Wait for user confirmation before proceeding.**

---

## STEP 2 — PLAN (before any implementation)

Break into tasks, each max 2-5 minutes of work:

| # | File | Change | Verify |
|---|------|--------|--------|
| 1 | /app/backend/routers/referral_router.py | Create POST /api/referral/generate-link | curl returns valid link |
| 2 | /app/backend/routers/referral_router.py | Create GET /api/referral/stats | curl returns stats JSON |
| 3 | /app/frontend/src/platform/ReferralPortal.jsx | Build referral dashboard UI | Screenshot shows cards |

**Show plan. Wait for user confirmation before proceeding.**

---

## STEP 3 — BUILD (only after both confirmed)

- Execute plan task by task
- Run tests after each task (curl, screenshot, or testing_agent)
- Do NOT proceed to next task if current task's verification fails
- If scope changes discovered during build → pause, update spec, get confirmation

---

## STEP 4 — REVIEW (two-stage gate)

### Stage 1: Spec Compliance
> "Does this implementation match the stated spec exactly? List any gaps."

Checklist:
- [ ] All 3 spec sentences are satisfied
- [ ] No extra features were added (YAGNI)
- [ ] Success criteria measurably met

### Stage 2: Code Quality
> "Are there any security, performance, or pattern violations?"

Checklist:
- [ ] No hardcoded secrets or URLs
- [ ] MongoDB _id excluded from responses
- [ ] All endpoints prefixed with /api
- [ ] Pure ASGI (no BaseHTTPMiddleware)
- [ ] `if collection is None` checks present
- [ ] Error handling doesn't crash server

**Both stages must pass before declaring the feature complete.**

---

## Anti-Patterns to Avoid
- Jumping straight to code without spec confirmation
- Adding "nice to have" features during build phase
- Declaring done without running tests
- Skipping the two-stage review
