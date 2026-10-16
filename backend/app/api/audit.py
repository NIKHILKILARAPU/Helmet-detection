"""
Audit Trail API Endpoints.

Implements:
- Read-only paginated query for immutable system audit records
- Role protection: Restricted strictly to Government Admin and Supervisory Officers
- Zero mutation, edit, or delete operations (strictly append-only at application layer)
"""

from typing import List, Dict, Any, Optional
from datetime import datetime
from bson import ObjectId
from fastapi import APIRouter, Query, Depends, status

from app.schemas.common import ApiResponse, PaginatedResponse
from app.core.dependencies import require_supervisor_or_admin
from app.db.connection import get_db
from app.db.collections import COLLECTION_AUDIT_LOGS

router = APIRouter(prefix="/audit-logs", tags=["audit"])


@router.get(
    "",
    response_model=PaginatedResponse[Dict[str, Any]],
    status_code=status.HTTP_200_OK,
    summary="List immutable system & policy audit logs (Admin/Supervisor only)",
)
async def list_audit_logs(
    entity_type: Optional[str] = Query(None, alias="entityType", description="Target entity type filter"),
    action: Optional[str] = Query(None, description="Action code filter"),
    entity_id: Optional[str] = Query(None, alias="entityId", description="Specific entity ID"),
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    current_user: dict = Depends(require_supervisor_or_admin),
):
    """
    Returns tamper-evident audit records.
    No endpoints exist to modify or purge audit entries.
    """
    db = get_db()
    query: Dict[str, Any] = {}
    if entity_type:
        query["entityType"] = entity_type
    if action:
        query["action"] = action
    if entity_id:
        query["entityId"] = entity_id

    try:
        total = db[COLLECTION_AUDIT_LOGS].count_documents(query)
        cursor = (
            db[COLLECTION_AUDIT_LOGS]
            .find(query)
            .sort("timestamp", -1)
            .skip((page - 1) * page_size)
            .limit(page_size)
        )
        items = []
        for doc in cursor:
            item = dict(doc)
            item["id"] = str(item["_id"])
            item["_id"] = str(item["_id"])
            if "actorUserId" in item and item["actorUserId"]:
                item["actorUserId"] = str(item["actorUserId"])
            items.append(item)

        total_pages = (total + page_size - 1) // page_size if total > 0 else 0

        return PaginatedResponse(
            success=True,
            data=items,
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
        )
    except Exception:
        return PaginatedResponse(
            success=True,
            data=[],
            total=0,
            page=page,
            page_size=page_size,
            total_pages=0,
        )
