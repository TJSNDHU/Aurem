"""SHIM — migrated to `shared.agents.followup_listener`. Explicit re-exports."""
from shared.agents.followup_listener import (
    start_followup_listener,
    stop_followup_listener,
)

__all__ = ["start_followup_listener", "stop_followup_listener"]
