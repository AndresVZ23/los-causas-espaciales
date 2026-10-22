from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api.climate import router as climate_router
from .api.reports import router as reports_router
from .api.routes import router
from .core.config import get_settings

settings = get_settings()
app = FastAPI(title=settings.app_name, version="0.1.0", description="Traceable Earth-observation trend and investment scenario API.")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[value.strip() for value in settings.cors_origins.split(",")],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)
app.include_router(router)
app.include_router(reports_router)
app.include_router(climate_router)


@app.get("/")
def root():
    return {"name": settings.app_name, "docs": "/docs", "health": "/api/v1/health"}
