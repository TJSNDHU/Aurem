"""SHIM — migrated to `shared.agents.hunter_ora`. Explicit re-exports."""
from shared.agents.hunter_ora import (
    HunterORA,
    TERRITORY_DISTRIBUTION,
    WEEKLY_ROTATION,
)

__all__ = ["HunterORA", "TERRITORY_DISTRIBUTION", "WEEKLY_ROTATION"]
