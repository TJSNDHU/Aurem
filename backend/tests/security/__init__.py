"""AUREM adversarial + BIN-scoping security test suite.

This suite proves three things about ORA on aurem.live:

  1. Standard LLM jailbreak families (system-prompt leak, instruction
     injection, persona escape, encoding tricks, CoT hijack, tool-call
     abuse, multi-turn ramping) are resisted.
  2. Multi-tenant data isolation holds — no prompt, no header trick,
     no ID enumeration can pull rows from another BIN.
  3. Secrets and bulk PII never escape.

All prompts here are ORIGINAL — written from the public attack-pattern
taxonomy. No external corpus is fetched or copied.

LLM-cost tests are gated behind env `RUN_SEC_LLM=1` so CI can run the
structural tenant-scoping tests for free and only burn LLM budget on
deploy gates / weekly runs.

Suite results are aggregated into /app/test_reports/security_suite_*.json
by the report fixture, doubling as a marketing trust artifact.
"""
