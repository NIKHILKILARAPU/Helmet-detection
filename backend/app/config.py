import os
from typing import Optional
from pydantic import Field, AliasChoices
from pydantic_settings import BaseSettings, SettingsConfigDict

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
    YOLO_MODEL_PATH: str = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "../../../models/yolov8n-traffic.pt")
    )
    INFERENCE_CONFIDENCE_THRESHOLD: float = 0.50

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

