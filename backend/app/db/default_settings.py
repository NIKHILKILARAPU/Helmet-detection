"""
Safe baseline default document for system_settings collection.

Contains initial algorithmic thresholds and operational parameters.
Does NOT assert statutory legal authorization; penalty amounts represent
provisional advisory baseline draft figures pending state legislative integration.
"""

from datetime import datetime, timezone
from typing import Dict, Any

DEFAULT_SETTINGS_KEY = "default"

DEFAULT_SYSTEM_SETTINGS: Dict[str, Any] = {
    "key": DEFAULT_SETTINGS_KEY,
    "minConfidenceThreshold": 0.55,
    "autoFlagPillionWithoutHelmet": True,
    "autoFlagTripleRiding": True,
    "requireSecondaryReviewForNightDetections": True,
    "dataRetentionDays": 90,
    "defaultDraftPenaltyInr": 1000.0,
    "updatedBy": None,
    "updatedAt": datetime.now(timezone.utc),
}
