"""
Authentication Endpoints: Staff Login and Identity Verification.

Implements:
- Secure credential verification via bcrypt
- Expiring JWT bearer token issuance
- Safe user profile inspection (/auth/me)
- Zero public registration endpoints
"""

from datetime import datetime, timezone
from fastapi import APIRouter, Depends, status

from app.schemas.common import ApiResponse
from app.schemas.auth import LoginRequest, TokenResponse, UserSummary
from app.core.security import verify_password, create_access_token
from app.core.exceptions import UnauthorizedError, ForbiddenError
from app.core.dependencies import get_current_user
from app.db.connection import get_db
from app.db.collections import COLLECTION_USERS
from app.config import settings

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/login",
    response_model=ApiResponse[TokenResponse],
    status_code=status.HTTP_200_OK,
    summary="Authenticate official enforcement staff officer",
)
async def login(payload: LoginRequest):
    """
    Verifies staff officer email and password.
    Returns signed short-lived JWT access token upon successful authentication.
    """
    db = get_db()
    email_clean = payload.email.strip().lower()

    user = db[COLLECTION_USERS].find_one({"email": email_clean})
    if not user or not verify_password(payload.password, user.get("passwordHash", "")):
        raise UnauthorizedError(message="Invalid official credentials provided.")

    if user.get("status") != "ACTIVE":
        raise ForbiddenError(message="Account has been deactivated. Please contact an Administrator.")

    now = datetime.now(timezone.utc)
    # Update last login timestamp
    db[COLLECTION_USERS].update_one(
        {"_id": user["_id"]},
        {"$set": {"lastLoginAt": now, "updatedAt": now}},
    )

    token_data = {
        "sub": str(user["_id"]),
        "employeeId": user["employeeId"],
        "name": user["name"],
        "role": user["role"],
    }
    token = create_access_token(data=token_data)

    user_summary = UserSummary(
        id=str(user["_id"]),
        employeeId=user["employeeId"],
        name=user["name"],
        email=user["email"],
        role=user["role"],
        department=user.get("department"),
        rank=user.get("rank"),
        status=user["status"],
    )

    token_resp = TokenResponse(
        accessToken=token,
        tokenType="bearer",
        expiresInMinutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES,
        user=user_summary,
    )

    return ApiResponse(
        success=True,
        data=token_resp,
        message=f"Welcome {user['name']}. Authorized as {user['role']}.",
    )


@router.get(
    "/me",
    response_model=ApiResponse[UserSummary],
    status_code=status.HTTP_200_OK,
    summary="Get currently authenticated officer profile",
)
async def get_current_user_profile(
    current_user: dict = Depends(get_current_user),
):
    """Returns the authenticated officer's profile derived exclusively from verified JWT."""
    user_dto = UserSummary(
        id=current_user["id"],
        employeeId=current_user["employeeId"],
        name=current_user["name"],
        email=current_user["email"],
        role=current_user["role"],
        department=current_user.get("department"),
        rank=current_user.get("rank"),
        status=current_user["status"],
    )
    return ApiResponse(
        success=True,
        data=user_dto,
        message="Active session verified.",
    )
