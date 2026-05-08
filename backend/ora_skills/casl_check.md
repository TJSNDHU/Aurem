# CASL Compliance Skill (Value-First)
## Trigger intent
User asks about compliance, opt-out, CASL, or whether a message is legal to send.
Keywords: CASL, opt out, compliant, legal, can we send, is this allowed.
## Owner Agent
None — LLM only (no agent owns compliance).
## What ORA does
Run a value-first CASL audit on the message and return PASS or FAIL with specific reason.

## CASL Value-First Rules

PASS requires ALL of:
- ✓ Opt-out present (STOP / unsubscribe)
- ✓ Physical address in email footer (7221 Sigsbee Dr, Mississauga ON L4T 3L6)
- ✓ Sender identified (AUREM / ora@aurem.live)
- ✓ Value offered BEFORE any ask
- ✓ B2B context clear (business to business)
- ✓ No false urgency ("Act now or lose forever")
- ✓ No deceptive subject lines

AUTOMATIC FAIL if:
- ✗ Subject line is clickbait/deceptive (Re:, Fwd:, "you won", urgent, final warning, last chance)
- ✗ No opt-out
- ✗ No sender identification
- ✗ Pure promotional (no value offered)
- ✗ Sent to consumer (B2C) without consent

CASL PENALTY CONTEXT (for ORA awareness):
- Individual: up to $1M per violation
- Business: up to $10M per violation
- These are real numbers. Every message must be defensible.

## Hard rule
Never approve a message without opt-out + sender ID + value offered.
