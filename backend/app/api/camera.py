from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(prefix="/cameras", tags=["cameras"])

class CameraRegisterRequest(BaseModel):
    name: str
    junction: str
    streamType: str
    ipOrDeviceUrl: str

@router.get("")
async def list_camera_sources():
    return {
        "status": "success",
        "data": []
    }

@router.post("")
async def register_camera(payload: CameraRegisterRequest):
    return {
        "status": "success",
        "data": payload,
        "message": f"Camera {payload.name} registered successfully."
    }
