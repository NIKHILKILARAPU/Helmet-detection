"""
Vehicle Registration and Owner Association Endpoints.

Implements:
- Registration plate normalization (uppercase, whitespace/dash stripped)
- Duplicate vehicle collision prevention
- Unique person-vehicle relationship enforcement
- Access control for state transport vehicle registry
"""

from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
import re
from bson import ObjectId
from fastapi import APIRouter, Path, Query, Depends, status
from pydantic import BaseModel, Field

from app.schemas.common import ApiResponse
from app.core.exceptions import NotFoundError, ConflictError, ValidationError
from app.core.dependencies import require_authenticated_staff, require_admin
from app.db.connection import get_db
from app.db.collections import COLLECTION_VEHICLES, COLLECTION_PERSON_VEHICLES, COLLECTION_PERSONS

router = APIRouter(tags=["vehicles"])


def normalize_plate_number(plate: str) -> str:
    """Normalizes motor vehicle registration numbers (e.g. 'ka-01 mj 4892' -> 'KA01MJ4892')."""
    return re.sub(r"[^A-Za-z0-9]", "", plate).upper()


class VehicleCreatePayload(BaseModel):
    plateNumber: str = Field(..., min_length=4, max_length=20, description="License plate number")
    vehicleType: Optional[str] = Field("Two-Wheeler", max_length=50)
    model: Optional[str] = Field(None, max_length=100)
    registeredDate: Optional[datetime] = None
    registrationStatus: str = Field("ACTIVE", pattern=r"^(ACTIVE|EXPIRED|FLAGGED)$")
    verificationStatus: str = Field("VERIFIED", pattern=r"^(VERIFIED|UNVERIFIED|MANUAL_REQUIRED)$")


class LinkPersonVehiclePayload(BaseModel):
    personId: str = Field(..., description="ID reference to person")
    vehicleId: str = Field(..., description="ID reference to vehicle or plate number")
    relationshipType: str = Field("REGISTERED_OWNER", max_length=50)


@router.get(
    "/vehicles",
    response_model=ApiResponse[List[Dict[str, Any]]],
    status_code=status.HTTP_200_OK,
    summary="Search motor vehicle records",
)
async def list_vehicles(
    plate: Optional[str] = Query(None, description="Search by plate number"),
    status_filter: Optional[str] = None,
    current_user: dict = Depends(require_authenticated_staff),
):
    """Searches vehicle records matching normalized registration plate."""
    db = get_db()
    query: Dict[str, Any] = {}
    if plate and plate.strip():
        norm = normalize_plate_number(plate)
        query["plateNumber"] = {"$regex": norm, "$options": "i"}
    if status_filter:
        query["registrationStatus"] = status_filter

    cursor = db[COLLECTION_VEHICLES].find(query).limit(50)
    items = []
    for doc in cursor:
        item = dict(doc)
        item["id"] = str(item["_id"])
        item["_id"] = str(item["_id"])
        items.append(item)

    return ApiResponse(
        success=True,
        data=items,
        message=f"Retrieved {len(items)} vehicle record(s).",
    )


@router.post(
    "/vehicles",
    response_model=ApiResponse[Dict[str, Any]],
    status_code=status.HTTP_201_CREATED,
    summary="Register a verified vehicle record (Admin only)",
)
async def create_vehicle(
    payload: VehicleCreatePayload,
    current_user: dict = Depends(require_admin),
):
    """Registers motor vehicle. Enforces plate normalization and rejects duplicates."""
    db = get_db()
    norm_plate = normalize_plate_number(payload.plateNumber)
    if not norm_plate:
        raise ValidationError(message="Vehicle plate number cannot be empty or invalid.")

    # Check for existing vehicle
    existing = db[COLLECTION_VEHICLES].find_one({"plateNumber": norm_plate})
    if existing:
        raise ConflictError(entity="Vehicle", identifier=norm_plate)

    now = datetime.now(timezone.utc)
    doc = payload.model_dump()
    doc["plateNumber"] = norm_plate
    doc["createdAt"] = now
    doc["updatedAt"] = now

    result = db[COLLECTION_VEHICLES].insert_one(doc)
    doc["id"] = str(result.inserted_id)
    doc["_id"] = str(result.inserted_id)

    return ApiResponse(
        success=True,
        data=doc,
        message=f"Vehicle '{norm_plate}' registered successfully.",
    )


@router.post(
    "/person-vehicles",
    response_model=ApiResponse[Dict[str, Any]],
    status_code=status.HTTP_201_CREATED,
    summary="Link vehicle to registered person (Admin only)",
)
async def link_person_to_vehicle(
    payload: LinkPersonVehiclePayload,
    current_user: dict = Depends(require_admin),
):
    """Creates ownership or driver association. Prevents duplicate active relationship."""
    db = get_db()

    # Resolve person
    p_query = {"_id": ObjectId(payload.personId)} if ObjectId.is_valid(payload.personId) else {"personReference": payload.personId}
    person = db[COLLECTION_PERSONS].find_one(p_query)
    if not person:
        raise NotFoundError(entity="Person", entity_id=payload.personId)

    # Resolve vehicle
    norm_plate = normalize_plate_number(payload.vehicleId)
    v_query = {"$or": [{"plateNumber": norm_plate}]}
    if ObjectId.is_valid(payload.vehicleId):
        v_query["$or"].append({"_id": ObjectId(payload.vehicleId)})
    vehicle = db[COLLECTION_VEHICLES].find_one(v_query)
    if not vehicle:
        raise NotFoundError(entity="Vehicle", entity_id=payload.vehicleId)

    # Check duplicate relationship
    existing = db[COLLECTION_PERSON_VEHICLES].find_one({
        "personId": person["_id"],
        "vehicleId": vehicle["_id"],
        "relationshipType": payload.relationshipType,
    })
    if existing:
        raise ConflictError(
            message=f"Relationship '{payload.relationshipType}' between person and vehicle already exists."
        )

    link_doc = {
        "personId": person["_id"],
        "vehicleId": vehicle["_id"],
        "relationshipType": payload.relationshipType,
        "validFrom": datetime.now(timezone.utc),
        "validTo": None,
        "verificationSource": "STATE_VAHAN_PORTAL",
    }
    result = db[COLLECTION_PERSON_VEHICLES].insert_one(link_doc)
    link_doc["id"] = str(result.inserted_id)
    link_doc["_id"] = str(result.inserted_id)
    link_doc["personId"] = str(link_doc["personId"])
    link_doc["vehicleId"] = str(link_doc["vehicleId"])

    return ApiResponse(
        success=True,
        data=link_doc,
        message=f"Linked vehicle {vehicle['plateNumber']} to {person['fullName']} as {payload.relationshipType}.",
    )
