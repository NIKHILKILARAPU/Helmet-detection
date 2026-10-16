"""
Analytics & Statistics API Endpoints.

Implements:
- Typed Pydantic models for dashboard KPIs and trends
- Consistent ApiResponse envelope format
- Suitable HTTP status codes (200 OK)
"""

from typing import List
from fastapi import APIRouter, status

from app.schemas.common import ApiResponse
from app.schemas.stats import (
    DashboardStatsResponse,
    HourlyTrendItem,
    MonthlyTrendItem,
)

router = APIRouter(prefix="/stats", tags=["stats"])


@router.get(
    "/dashboard",
    response_model=ApiResponse[DashboardStatsResponse],
    status_code=status.HTTP_200_OK,
    summary="Get overall daily enforcement KPI statistics",
)
async def get_dashboard_stats():
    """Returns today's total detections, pending queue count, and draft volume."""
    stats_data = DashboardStatsResponse(
        todayTotalDetections=1428,
        todayNoHelmetCandidates=87,
        todayPendingReview=14,
        todayApprovedDrafts=58,
        todayRejectedCases=15,
        complianceRatePercent=93.9,
    )
    return ApiResponse(
        success=True,
        data=stats_data,
        message="Daily enforcement statistics retrieved.",
    )


@router.get(
    "/hourly",
    response_model=ApiResponse[List[HourlyTrendItem]],
    status_code=status.HTTP_200_OK,
    summary="Get hourly detection distribution",
)
async def get_hourly_trends():
    """Returns hourly volume of scanned riders and detected violations."""
    sample_trends: List[HourlyTrendItem] = [
        HourlyTrendItem(hour="08:00", totalScanned=180, violationsDetected=12),
        HourlyTrendItem(hour="10:00", totalScanned=320, violationsDetected=24),
        HourlyTrendItem(hour="12:00", totalScanned=210, violationsDetected=15),
        HourlyTrendItem(hour="14:00", totalScanned=190, violationsDetected=9),
        HourlyTrendItem(hour="16:00", totalScanned=290, violationsDetected=18),
        HourlyTrendItem(hour="18:00", totalScanned=238, violationsDetected=9),
    ]
    return ApiResponse(
        success=True,
        data=sample_trends,
        message="Hourly enforcement trends retrieved.",
    )


@router.get(
    "/monthly",
    response_model=ApiResponse[List[MonthlyTrendItem]],
    status_code=status.HTTP_200_OK,
    summary="Get monthly compliance and detection trends",
)
async def get_monthly_trends():
    """Returns monthly multi-week trend telemetry."""
    sample_monthly: List[MonthlyTrendItem] = [
        MonthlyTrendItem(month="Jan", totalScanned=38000, violationsDetected=2800, complianceRate=92.6),
        MonthlyTrendItem(month="Feb", totalScanned=41200, violationsDetected=2650, complianceRate=93.5),
        MonthlyTrendItem(month="Mar", totalScanned=44500, violationsDetected=2700, complianceRate=93.9),
    ]
    return ApiResponse(
        success=True,
        data=sample_monthly,
        message="Monthly enforcement trends retrieved.",
    )
