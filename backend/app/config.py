import os
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
        "http://127.0.0.1:5173"
    ]
    
    # AI Model Path (Kept strictly outside frontend)
    YOLO_MODEL_PATH: str = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "../../../models/yolov8n-traffic.pt")
    )
    INFERENCE_CONFIDENCE_THRESHOLD: float = 0.65

    model_config = SettingsConfigDict(env_file=".env", extra="allow")

settings = Settings()
