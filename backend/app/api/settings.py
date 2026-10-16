"""
System Settings and Enforcement Policy API Endpoints.

Implements:
- Validated settings retrieval and updates
- Strict Admin-only mutation authorization
- Mandatory audit logging on all policy threshold changes
"""

from typing import Dict, Any
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, status

from bson import ObjectId
from app.schemas.common import ApiResponse
from app.schemas.settings import SystemSettingsModel, SystemSettingsUpdate
from app.core.exceptions import NotFoundError, ValidationError
from app.core.dependencies import require_admin, require_authenticated_staff
from app.db.connection import get_db
from app.db.collections import COLLECTION_SYSTEM_SETTINGS, COLLECTION_AUDIT_LOGS
from app.db.default_settings import DEFAULT_SETTINGS_KEY

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get(
    "",
    response_model=ApiResponse[Dict[str, Any]],
    status_code=status.HTTP_200_OK,
    summary="Get current enforcement policies and thresholds",
)
async def get_system_settings(
    current_user: dict = Depends(require_authenticated_staff),
):
    """Retrieves operational policy parameters (confidence thresholds, penalty estimates, retention)."""
    db = get_db()
    settings_doc = db[COLLECTION_SYSTEM_SETTINGS].find_one({"key": DEFAULT_SETTINGS_KEY})
    if not settings_doc:
        raise NotFoundError(entity="System Settings", entity_id=DEFAULT_SETTINGS_KEY)

    clean = dict(settings_doc)
    clean["id"] = str(clean["_id"])
    clean["_id"] = str(clean["_id"])
    if clean.get("updatedBy"):
        clean["updatedBy"] = str(clean["updatedBy"])
    return ApiResponse(
        success=True,
        data=clean,
        message="System settings retrieved.",
    )


@router.patch(
    "",
    response_model=ApiResponse[Dict[str, Any]],
    status_code=status.HTTP_200_OK,
    summary="Update enforcement policy thresholds (Government Admin only)",
)
async def update_system_settings(
    payload: SystemSettingsUpdate,
    current_user: dict = Depends(require_admin),
):
    """
    Updates policy thresholds. Restricted exclusively to Government Admin.
    Changes are audited in the audit_logs collection.
    """
    db = get_db()
    updates = {k: v for k, v in payload.model_dump().items() if v is not None}
    if not updates:
        raise ValidationError(message="No policy setting fields provided for update.")

    now = datetime.now(timezone.utc)
    updates["updatedAt"] = now
    user_obj_id = ObjectId(current_user["id"]) if ObjectId.is_valid(current_user["id"]) else None
    updates["updatedBy"] = user_obj_id

    updated = db[COLLECTION_SYSTEM_SETTINGS].find_one_and_update(
        {"key": DEFAULT_SETTINGS_KEY},
        {"$set": updates},
        return_document=True,
    )
    if not updated:
        raise NotFoundError(entity="System Settings", entity_id=DEFAULT_SETTINGS_KEY)

    # Record audit log
    audit_meta = {k: v for k, v in updates.items() if k not in ("updatedBy", "updatedAt")}
    audit_doc = {
        "timestamp": now,
        "actorUserId": user_obj_id,
        "actorNameSnapshot": current_user["name"],
        "actorRoleSnapshot": current_user["role"],
        "action": "POLICY_THRESHOLDS_MODIFIED",
        "entityType": "settings",
        "entityId": DEFAULT_SETTINGS_KEY,
        "notes": f"Enforcement policy parameters adjusted by Admin {current_user['name']}.",
        "metadata": audit_meta,
        "requestId": None,
    }
    db[COLLECTION_AUDIT_LOGS].insert_one(audit_doc)

    clean = dict(updated)
    clean["id"] = str(clean["_id"])
    clean["_id"] = str(clean["_id"])
    if clean.get("updatedBy"):
        clean["updatedBy"] = str(clean["updatedBy"])

    return ApiResponse(
        success=True,
        data=clean,
        message="Enforcement policy parameters updated and logged in audit trail.",
    )
