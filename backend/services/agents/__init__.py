"""AUREM agents — Phase 1 canonical location."""
# Re-export the AuremAgent base class so legacy modules that do
# `from services.agents import AuremAgent` continue to work after the
# canonical location moved to shared.agents.
try:
    from shared.agents import AuremAgent  # noqa: F401
except Exception:  # pragma: no cover — base class is non-fatal
    AuremAgent = None  # type: ignore

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
