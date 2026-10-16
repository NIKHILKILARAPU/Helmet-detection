"""
Analytics, KPI, and Trend Schemas for Government Supervisors.
"""

from typing import List, Optional
from pydantic import BaseModel, Field


class DashboardStatsResponse(BaseModel):
    """Enforcement summary KPIs."""
    todayTotalDetections: int = Field(..., ge=0)
    todayNoHelmetCandidates: int = Field(..., ge=0)
    todayPendingReview: int = Field(..., ge=0)
    todayApprovedDrafts: int = Field(..., ge=0)
    todayRejectedCases: int = Field(..., ge=0)
    complianceRatePercent: Optional[float] = Field(93.9, ge=0.0, le=100.0)


class HourlyTrendItem(BaseModel):
    hour: str = Field(..., description="Time interval e.g. '08:00'")
    totalScanned: int = Field(..., ge=0)
    violationsDetected: int = Field(..., ge=0)


class MonthlyTrendItem(BaseModel):
    month: str = Field(..., description="Month e.g. 'May'")
    totalScanned: int = Field(..., ge=0)
    violationsDetected: int = Field(..., ge=0)
    complianceRate: float = Field(..., ge=0.0, le=100.0)
