"""
layer_agents — 8-layer specialist agents that subscribe to A2A topics
and feed both the per-BIN ORA and the global Admin ORA brain.
═══════════════════════════════════════════════════════════════════════════
Each layer has:
  • A logical scope (Identity, Plan, Billing, Trial, Gate, Data, Usage, UX)
  • A2A subscription topics (events it cares about)
  • A handler function (`handle_event(payload)`) that runs lightweight
    triage and writes a learning row to admin_ora_brain.

The architecture:
  • Per-BIN ORA (`/api/bin/ora/ask`) routes customer questions to the
    appropriate layer by keyword match.
  • Admin ORA (`/api/admin/ora/ask`) aggregates anonymized telemetry
    from all layer events to answer founder questions across BINs.
"""
