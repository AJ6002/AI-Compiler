from fastapi import FastAPI

from apps.api.config import settings

app = FastAPI(
    title="AICONNEX Industrial Excel Compiler API",
    description="Control plane API for spreadsheet ingestion, validation, and execution.",
    version="0.1.0",
)


@app.get("/health", tags=["System"])
async def health_check():
    return {
        "status": "ok",
        "service": "aiconnex-compiler",
        "version": "0.1.0",
        "phase": 0,
        "environment": settings.app_env,
    }
