# Agent Context — STICKY RULES (do not violate)

**Last updated:** 2026-05-21 (iter 325z)

## 1. User's environment context
- **When user shares ANY screenshot, log, error, or behaviour report → ASSUME PRODUCTION (https://aurem.live)**
- DO NOT ask "preview vs production?" — user always means production
- DO NOT clarify environment unless user explicitly mentions "preview" or "preview environment"
- Preview is your sandbox for fixes; user's reports are always about live prod

## 2. Recurring issues the user has reported MORE THAN ONCE
- Online/offline blinking in topbar (iter 325s, 325u, 325z) — must be killed at the data layer, not patched in CSS
- ORA CTO panel showing wrong "DeepSeek unreachable" while DeepSeek is healthy (iter 325z)

## 3. Language
- Hinglish only. Friendly, blunt, action-first. No corporate fluff.

## 4. Tone
- User burns out from re-asking. Fix DEEP, not on surface. Add regression tests so it never returns.
