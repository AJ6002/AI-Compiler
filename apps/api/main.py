"""Main FastAPI entrypoint for the AICONNEX Compiler Control Plane."""

from fastapi import FastAPI

from apps.api.config import settings
from apps.api.routers.uploads import router as uploads_router

app = FastAPI(
    title="AICONNEX Industrial Excel Compiler API",
    description="Control plane API for spreadsheet ingestion, validation, and execution.",
    version="0.1.0",
)

# Register API routers
app.include_router(uploads_router, prefix="/api/v1")


@app.get("/health", tags=["System"])
async def health_check():
    return {
        "status": "ok",
        "service": "aiconnex-compiler",
        "version": "0.1.0",
        "phase": 0,
        "environment": settings.app_env,
    }
