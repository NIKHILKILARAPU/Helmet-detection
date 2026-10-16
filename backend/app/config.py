import os
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    API_PREFIX: str = "/api/v1"
    
    # MongoDB
    MONGO_URI: str = "mongodb://localhost:27017"
    MONGO_DB_NAME: str = "trafficguard_ai"
    
    # CORS
    CORS_ORIGINS: list[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173"
    ]
    
    # Model
    YOLO_MODEL_PATH: str = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../models/yolov8n-traffic.pt"))
    INFERENCE_CONFIDENCE_THRESHOLD: float = 0.65

    class Config:
        env_file = ".env"
        extra = "allow"

settings = Settings()
