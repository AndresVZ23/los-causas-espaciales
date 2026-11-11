from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api.assistant import router as assistant_router
from .api.baseline import router as baseline_router
from .api.climate import router as climate_router
from .api.data_sources import router as data_sources_router
from .api.map_layers import router as map_router
from .api.reports import router as reports_router
from .api.road import router as road_router
from .api.real_estate import router as real_estate_router
from .api.routes import router
from .api.scoring import router as scoring_router
from .api.spatial_sampling import router as spatial_sampling_router
from .api.territories import router as territories_router
from .api.world import router as world_router
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
app.include_router(road_router)
app.include_router(real_estate_router)
app.include_router(climate_router)
app.include_router(baseline_router)
app.include_router(data_sources_router)
app.include_router(scoring_router)
app.include_router(assistant_router)
app.include_router(map_router)
app.include_router(spatial_sampling_router)
app.include_router(territories_router)
app.include_router(world_router)


@app.get("/")
def root():
    return {"name": settings.app_name, "docs": "/docs", "health": "/api/v1/health"}
