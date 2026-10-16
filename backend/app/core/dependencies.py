"""
FastAPI Authentication, Context, and Role-Based Authorization Dependencies.

Implements:
- Bearer token extraction and JWT verification
- User status validation (ACTIVE vs INACTIVE)
- Least-privilege role-based access control (RBAC)
- Strict prevention of client-supplied identity forgery
"""

from typing import Dict, Any, List, Optional
from fastapi import Depends, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from bson import ObjectId

from app.core.security import decode_access_token
from app.core.exceptions import UnauthorizedError, ForbiddenError, DatabaseUnavailableError
from app.db.connection import get_db
from app.db.collections import COLLECTION_USERS

security_bearer = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_bearer),
) -> Dict[str, Any]:
    """
    Extracts and authenticates the actor from the JWT Bearer token.
    Never accepts actor identity from query or request body parameters.
    """
    if not credentials or not credentials.credentials:
        raise UnauthorizedError(message="Authentication credentials (Bearer token) were not provided.")

    payload = decode_access_token(credentials.credentials)
    user_id = payload.get("sub")
    if not user_id:
        raise UnauthorizedError(message="Token does not contain a valid subject identifier.")

    try:
        db = get_db()
        try:
            obj_id = ObjectId(user_id)
            user = db[COLLECTION_USERS].find_one({"_id": obj_id})
        except Exception:
            user = db[COLLECTION_USERS].find_one({"employeeId": user_id})

        if not user:
            raise UnauthorizedError(message="Authenticated user account no longer exists in system records.")

        if user.get("status") != "ACTIVE":
            raise ForbiddenError(message="Account is inactive. Contact the Government Administrator.")

        # Return sanitized user dictionary
        return {
            "id": str(user["_id"]),
            "employeeId": user["employeeId"],
            "name": user["name"],
            "email": user["email"],
            "role": user["role"],
            "department": user.get("department"),
            "rank": user.get("rank"),
            "status": user["status"],
        }
    except (UnauthorizedError, ForbiddenError):
        raise
    except Exception as exc:
        raise DatabaseUnavailableError(message=f"Database lookup failed during authentication: {str(exc)}")


def require_roles(*allowed_roles: str):
    """
    Role-checking dependency factory enforcing least-privilege access.
    Supervisors do NOT automatically receive admin permissions.
    """
    def _role_checker(current_user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
        user_role = current_user.get("role")
        if user_role not in allowed_roles:
            raise ForbiddenError(
                message=f"Role '{user_role}' is not authorized to access this resource. "
                        f"Requires one of: {', '.join(allowed_roles)}."
            )
        return current_user

    return _role_checker


# Convenient role dependency shortcuts
require_admin = require_roles("admin")
require_reviewer = require_roles("admin", "reviewer")
require_operator = require_roles("admin", "operator")
require_supervisor_or_admin = require_roles("admin", "supervisor")
require_authenticated_staff = require_roles("admin", "reviewer", "operator", "supervisor")
