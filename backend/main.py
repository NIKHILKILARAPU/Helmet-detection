import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.api.violations import router as violations_router
from app.api.stats import router as stats_router
from app.api.camera import router as camera_router
from app.models.yolo_inference import yolo_engine

app = FastAPI(
    title="TrafficGuard AI — Government Enforcement API",
    version="1.0.0",
    description="Python FastAPI backend powering Smart Helmet Detection & E-Challan Draft Management"
)

# CORS Middleware allowing Frontend access
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Health endpoint matching frontend HealthService
@app.get(f"{settings.API_PREFIX}/health")
async def health_check():
    return {
        "status": "ONLINE",
        "service": "FastAPI Traffic Enforcement Gateway",
        "yolo_model": "READY" if yolo_engine.is_model_loaded() else "DEMO_STANDIN",
        "database": "MONGODB_READY",
        "message": "All government enforcement microservices operational"
    }

# Register API routers
app.include_router(violations_router, prefix=settings.API_PREFIX)
app.include_router(stats_router, prefix=settings.API_PREFIX)
app.include_router(camera_router, prefix=settings.API_PREFIX)

if __name__ == "__main__":
    uvicorn.run("main:app", host=settings.API_HOST, port=settings.API_PORT, reload=True)
