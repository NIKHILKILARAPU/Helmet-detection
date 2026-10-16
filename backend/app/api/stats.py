from fastapi import APIRouter

router = APIRouter(prefix="/stats", tags=["stats"])

@router.get("/dashboard")
async def get_dashboard_stats():
    return {
        "status": "success",
        "data": {
            "todayTotalDetections": 1428,
            "todayNoHelmetCandidates": 87,
            "todayPendingReview": 14,
            "todayApprovedDrafts": 58,
            "todayRejectedCases": 15
        }
    }

@router.get("/hourly")
async def get_hourly_trends():
    return {
        "status": "success",
        "data": []
    }

@router.get("/monthly")
async def get_monthly_trends():
    return {
        "status": "success",
        "data": []
    }
