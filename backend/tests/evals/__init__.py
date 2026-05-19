"""ORA agent response evaluation harness.

Lightweight asserts on response *shape* and *content presence* — not
exact text matches (LLM output is non-deterministic). Designed to run
fast in CI as a regression net for ORA prompt/tool changes.

Usage:
    cd /app/backend
    pytest tests/evals/test_ora_responses.py -v

To skip when LLM keys are unavailable, set EVALS_OFFLINE=1.
"""
