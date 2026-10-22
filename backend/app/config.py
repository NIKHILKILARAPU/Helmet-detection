import os
from typing import Optional
from pydantic import Field, AliasChoices, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Base directory hierarchy
BACKEND_DIR: str = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
PROJECT_ROOT: str = os.path.abspath(os.path.join(BACKEND_DIR, ".."))
MODELS_DIR: str = os.path.join(PROJECT_ROOT, "models")
DEFAULT_YOLO_MODEL_PATH: str = os.path.join(MODELS_DIR, "yolov8n-traffic.pt")


def resolve_model_path(path_str: Optional[str] = None) -> str:
    """
    Centrally resolves a YOLO model weights path to a canonical absolute path.
    Prevents path resolution discrepancies caused by running processes from different directories
    (e.g., repository root vs backend directory vs test runner).

    Resolution hierarchy:
    1. If path is None/empty: returns DEFAULT_YOLO_MODEL_PATH (PROJECT_ROOT/models/yolov8n-traffic.pt).
    2. If path is already absolute: returns normalized absolute path.
    3. Checks if the relative path exists relative to BACKEND_DIR.
    4. Checks if the relative path exists relative to PROJECT_ROOT.
    5. Checks if the relative path exists relative to MODELS_DIR.
    6. If file is not yet on disk, resolves canonical destination:
       - paths starting with '../' or '../models' -> resolved relative to BACKEND_DIR
       - paths starting with 'models/' -> resolved relative to PROJECT_ROOT
       - filenames (e.g. 'yolov8n-traffic.pt') -> resolved relative to MODELS_DIR
    """
    if not path_str or not str(path_str).strip():
        return DEFAULT_YOLO_MODEL_PATH

    raw = str(path_str).strip()
    if os.path.isabs(raw):
        return os.path.abspath(raw)

    # 1. Check relative to backend directory
    cand_backend = os.path.abspath(os.path.join(BACKEND_DIR, raw))
    if os.path.isfile(cand_backend):
        return cand_backend

    # 2. Check relative to project root
    cand_root = os.path.abspath(os.path.join(PROJECT_ROOT, raw))
    if os.path.isfile(cand_root):
        return cand_root

    # 3. Check relative to models directory
    cand_models = os.path.abspath(os.path.join(MODELS_DIR, raw))
    if os.path.isfile(cand_models):
        return cand_models

    # 4. If file is not yet on disk, derive the canonical intended absolute path
    norm = raw.replace("\\", "/")
    if norm.startswith("../models/") or norm.startswith("../"):
        return os.path.abspath(os.path.join(BACKEND_DIR, raw))
    elif norm.startswith("models/"):
        return os.path.abspath(os.path.join(PROJECT_ROOT, raw))
    else:
        return os.path.abspath(os.path.join(MODELS_DIR, raw))


class Settings(BaseSettings):
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    API_PREFIX: str = "/api/v1"
    
    # MongoDB Database Configuration
    # Defaults to helmet_challan_db per Government Enforcement System architecture
    MONGO_URI: str = Field(
        default="mongodb://localhost:27017",
        validation_alias=AliasChoices("MONGO_URI", "MONGODB_URI")
    )
    MONGO_DB_NAME: str = "helmet_challan_db"
    MONGO_CONNECT_TIMEOUT_MS: int = 5000
    MONGO_SERVER_SELECTION_TIMEOUT_MS: int = 5000
    MONGO_SOCKET_TIMEOUT_MS: int = 10000
    
    # CORS (Frontend access)
    CORS_ORIGINS: list[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5174",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:4173",
        "http://127.0.0.1:4173",
    ]
    
    # Authentication & Security
    SECRET_KEY: str = Field(
        default="development_trafficguard_super_secret_key_change_in_production_32b",
        description="JWT cryptographic signing key"
    )
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 480  # 8 hours shift length
    
    # AI Model Path (Kept strictly outside frontend)
    YOLO_MODEL_PATH: str = Field(
        default=DEFAULT_YOLO_MODEL_PATH,
        description="Path to local YOLO model weights (*.pt)",
    )
    INFERENCE_CONFIDENCE_THRESHOLD: float = 0.50

    @field_validator("YOLO_MODEL_PATH", mode="after")
    @classmethod
    def _validate_model_path(cls, v: str) -> str:
        return resolve_model_path(v)

    # Roboflow Hosted Inference Configuration
    ROBOFLOW_API_KEY: Optional[str] = Field(
        default=None,
        description="Private API key for Roboflow hosted inference (never expose to client)",
    )
    ROBOFLOW_MODEL_ID: str = Field(
        default="helmet-and-no-helmet-rider-detection/6",
        description="Roboflow hosted model ID (project/version)",
    )
    ROBOFLOW_BASE_URL: str = Field(
        default="https://detect.roboflow.com",
        description="Base URL for Roboflow hosted inference service",
    )
    INFERENCE_PROVIDER: str = Field(
        default="roboflow",
        description="Inference engine provider: 'roboflow' or 'local'",
    )

    model_config = SettingsConfigDict(
        env_file=(".env", os.path.join(os.path.dirname(__file__), "../.env")),
        env_file_encoding="utf-8",
        extra="allow",
    )

settings = Settings()

