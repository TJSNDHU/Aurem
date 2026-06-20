import datetime
from enum import Enum
from typing import Optional
from urllib.parse import urlparse

class VerdictState(Enum):
    RED = 1
    YELLOW_RECOVERING = 2
    GREEN = 3

class RepairEngine:
    MAX_ACTIONS_PER_HOUR = 30  # Default value
    MAX_BUSINESS_HOURS_ACTIONS = 50
    BUSINESS_HOURS_START = 13  # 13:00 UTC
    BUSINESS_HOURS_END = 21    # 21:00 UTC

    def __init__(self):
        self.current_actions = 0
        self.last_action_time = None

    def get_max_actions(self) -> int:
        now = datetime.datetime.utcnow()
        if self.BUSINESS_HOURS_START <= now.hour < self.BUSINESS_HOURS_END:
            return self.MAX_BUSINESS_HOURS_ACTIONS
        return self.MAX_ACTIONS_PER_HOUR

    def assess_recovery(self, error_count: int, previous_error_count: int) -> VerdictState:
        if error_count == 0:
            return VerdictState.GREEN
        elif error_count < previous_error_count:
            return VerdictState.YELLOW_RECOVERING
        return VerdictState.RED

    def classify_error(self, error_data: dict) -> float:
        severity = error_data.get('severity', 0)
        if 0 < severity < 1.0:
            return 1.0
        elif 1.0 <= severity < 2.0:
            return 2.0
        elif 2.0 <= severity < 2.5:
            return 2.5  # New partial recovery tier
        elif 2.5 <= severity < 3.0:
            return 3.0
        return 0.0

    def route_mitigation(self, severity_tier: float) -> str:
        if severity_tier == 2.5:
            return "tier2_mitigation"  # Route partial recoveries to Tier 2
        elif severity_tier >= 3.0:
            return "tier3_mitigation"
        elif severity_tier >= 2.0:
            return "tier2_mitigation"
        return "tier1_mitigation"
