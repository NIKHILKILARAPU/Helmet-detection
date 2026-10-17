"""
Plate Reader & Vehicle Registry Matching Service.

Provides:
- Safe license plate crop extraction and OCR text detection
- Registration plate normalization (whitespace/punctuation stripped, uppercase)
- Registry lookup against vehicles and person_vehicles/persons collections
- Strict separation between registered vehicle owner and actual rider (never facial recognition)
- Explicit match status: VERIFIED, UNVERIFIED, MANUAL_REQUIRED
- Visibility preservation for unverified plates to enable manual officer investigation
- Rejection of placeholder/sentinel strings ("string", "null", "undefined")
"""

import os
import re
import time
import logging
from typing import Dict, Any, Optional, Tuple, List
from bson import ObjectId
import numpy as np
import cv2

from app.api.vehicles import normalize_plate_number
from app.db.collections import (
    COLLECTION_VEHICLES,
    COLLECTION_PERSON_VEHICLES,
    COLLECTION_PERSONS,
)

logger = logging.getLogger("trafficguard.plate_reader")

# Regex pattern for standard Indian motor vehicle registration numbers
# e.g., DL01AB1234, KA05MH9876, MH12DE1432, HR26DQ5551
INDIAN_PLATE_PATTERN = re.compile(r"^[A-Z]{2}[0-9]{1,2}[A-Z]{0,3}[0-9]{4}$")

# Check for pytesseract availability once at module load
_HAS_PYTESSERACT = False
try:
    import pytesseract
    _HAS_PYTESSERACT = True
except ImportError:
    _HAS_PYTESSERACT = False


def is_placeholder_string(val: Optional[str]) -> bool:
    """Returns True if string is None, empty, whitespace, or a common placeholder/sentinel."""
    if val is None:
        return True
    s = str(val).strip().lower()
    return not s or s in ("string", "null", "undefined", "none", "nan")


def extract_plate_text_from_crop(
    plate_crop: Optional[np.ndarray],
    ocr_override: Optional[str] = None,
) -> Tuple[Optional[str], float]:
    """
    Attempts optical character recognition (OCR) on a license plate image crop.
    
    If ocr_override is provided (e.g. from tests or specialized upstream OCR engines),
    validates that it is not a placeholder and normalizes it.

    Returns:
        (extracted_text, confidence)
    """
    if ocr_override is not None:
        if is_placeholder_string(ocr_override):
            return None, 0.0
        clean = normalize_plate_number(ocr_override)
        return (clean if clean else None, 0.95 if clean else 0.0)

    if plate_crop is None or plate_crop.size == 0:
        return None, 0.0

    h, w = plate_crop.shape[:2]
    if h < 10 or w < 20:
        return None, 0.0

    # Image enhancement for optical plate readability
    try:
        gray = cv2.cvtColor(plate_crop, cv2.COLOR_BGR2GRAY) if len(plate_crop.shape) == 3 else plate_crop
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        enhanced = clahe.apply(gray)
        filtered = cv2.bilateralFilter(enhanced, 9, 75, 75)
        thresh = cv2.adaptiveThreshold(
            filtered, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2
        )

        if _HAS_PYTESSERACT:
            try:
                raw_text = pytesseract.image_to_string(
                    thresh,
                    config="--psm 7 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789",
                )
                normalized = normalize_plate_number(raw_text)
                if normalized:
                    conf = 0.85 if INDIAN_PLATE_PATTERN.match(normalized) else 0.60
                    return normalized, conf
            except Exception:
                pass
    except Exception as exc:
        logger.debug(f"Plate image preprocessing warning: {exc}")

    return None, 0.0


def match_plate_against_registry(
    db: Any,
    raw_plate: Optional[str],
    ocr_confidence: float = 0.0,
) -> Dict[str, Any]:
    """
    Matches extracted plate text against registered vehicles and registered owners.

    Returns structured dictionary:
    {
        "plateDetected": bool,
        "rawText": Optional[str],
        "normalizedPlate": Optional[str],
        "matchStatus": "VERIFIED" | "UNVERIFIED" | "MANUAL_REQUIRED",
        "matchSource": Optional[str],
        "confidence": float,
        "matchedVehicleId": Optional[str],
        "matchedPersonId": Optional[str],
        "ownerNameSnapshot": Optional[str],
        "vehicleDetails": Optional[Dict[str, Any]]
    }

    CRITICAL PRIVACY PRINCIPLE:
    - matchedPersonId is the REGISTERED OWNER of the vehicle, NOT the detected rider.
    - Facial recognition is strictly forbidden; legal identity is never inferred from rider crops.
    """
    if is_placeholder_string(raw_plate):
        return {
            "plateDetected": False,
            "rawText": None,
            "normalizedPlate": None,
            "matchStatus": "MANUAL_REQUIRED",
            "matchSource": None,
            "confidence": 0.0,
            "matchedVehicleId": None,
            "matchedPersonId": None,
            "ownerNameSnapshot": None,
            "vehicleDetails": None,
        }

    raw_cleaned = str(raw_plate).strip()
    normalized = normalize_plate_number(raw_cleaned)
    if not normalized:
        return {
            "plateDetected": True,
            "rawText": raw_cleaned,
            "normalizedPlate": None,
            "matchStatus": "MANUAL_REQUIRED",
            "matchSource": "OCR_EXTRACTION",
            "confidence": ocr_confidence,
            "matchedVehicleId": None,
            "matchedPersonId": None,
            "ownerNameSnapshot": None,
            "vehicleDetails": None,
        }

    # Query vehicle registry
    vehicle = db[COLLECTION_VEHICLES].find_one({"plateNumber": normalized})
    if not vehicle:
        # Plate detected, but not found in existing vehicle database
        # Unmatched plate results must remain visible for reviewer investigation
        return {
            "plateDetected": True,
            "rawText": raw_cleaned,
            "normalizedPlate": normalized,
            "matchStatus": "UNVERIFIED",
            "matchSource": "OCR_EXTRACTION",
            "confidence": ocr_confidence or 0.70,
            "matchedVehicleId": None,
            "matchedPersonId": None,
            "ownerNameSnapshot": None,
            "vehicleDetails": None,
        }

    vehicle_id = vehicle["_id"]
    vehicle_details = {
        "vehicleType": vehicle.get("vehicleType"),
        "model": vehicle.get("model"),
        "registrationStatus": vehicle.get("registrationStatus"),
    }

    # Query registered owner link
    pv = db[COLLECTION_PERSON_VEHICLES].find_one({"vehicleId": vehicle_id})
    person_id = None
    owner_name = None

    if pv and "personId" in pv:
        person = db[COLLECTION_PERSONS].find_one({"_id": pv["personId"]})
        if person:
            person_id = str(person["_id"])
            owner_name = person.get("fullName")

    return {
        "plateDetected": True,
        "rawText": raw_cleaned,
        "normalizedPlate": normalized,
        "matchStatus": "VERIFIED",
        "matchSource": "STATE_VEHICLE_REGISTRY",
        "confidence": max(ocr_confidence, 0.90),
        "matchedVehicleId": str(vehicle_id),
        "matchedPersonId": person_id,
        "ownerNameSnapshot": owner_name,  # Registered owner, not rider!
        "vehicleDetails": vehicle_details,
    }
