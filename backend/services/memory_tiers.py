"""SHIM — this module has been migrated to `shared.memory_tiers`.
All existing `from services.memory_tiers import X` statements continue to work.
New code should import from `shared.memory_tiers` directly.
Shim will be removed after 48h stability window (Phase 0.1 cleanup).
"""
from shared.memory_tiers import *  # noqa: F401,F403
