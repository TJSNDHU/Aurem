"""AUREM agents — Phase 1 canonical location."""
from . import (  # noqa: F401
    closer_ora,
    followup_ora,
    referral_ora,
    pricing_agent,
)

# Back-compat: legacy code may import services.agents.hunter_ora,
# followup_listener — these still live in shared.agents
try:
    from shared.agents import hunter_ora, followup_listener  # noqa: F401
except Exception:
    pass
