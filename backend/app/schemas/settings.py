"""
System Settings Domain and Mutation Schemas.
"""

from typing import Optional
from datetime import datetime, timezone
from pydantic import BaseModel, Field


class SystemSettingsModel(BaseModel):
    """Enforcement policy parameters."""
    key: str = Field(default="default", description="Partition identifier")
    minConfidenceThreshold: float = Field(0.55, ge=0.0, le=1.0)
    autoFlagPillionWithoutHelmet: bool = True
    autoFlagTripleRiding: bool = True
    requireSecondaryReviewForNightDetections: bool = True
    dataRetentionDays: int = Field(90, ge=1, le=3650)
    defaultDraftPenaltyInr: float = Field(1000.0, ge=0.0)
    updatedBy: Optional[str] = None
    updatedAt: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class SystemSettingsUpdate(BaseModel):
    """Payload to adjust enforcement policies."""
    minConfidenceThreshold: Optional[float] = Field(None, ge=0.0, le=1.0)
    autoFlagPillionWithoutHelmet: Optional[bool] = None
    autoFlagTripleRiding: Optional[bool] = None
    requireSecondaryReviewForNightDetections: Optional[bool] = None
    dataRetentionDays: Optional[int] = Field(None, ge=1, le=3650)
    defaultDraftPenaltyInr: Optional[float] = Field(None, ge=0.0)
