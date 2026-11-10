import asyncio
import hashlib
import json
from statistics import fmean

from fastapi import APIRouter, HTTPException

from ..connectors.nasa.nasadem import NasademConnector, NasademConnectorError
from ..connectors.nasa.power import PowerConnector, PowerConnectorError
from ..finance.engine import calculate_npv
from ..geospatial.geometry import GeometryValidationError, inspect_geometry
from ..schemas.analysis import (
    AnalysisRequest,
    AnalysisResponse,
    ComparisonRequest,
    ComparisonResponse,
    FinanceRequest,
    FinanceResponse,
    GeometryRequest,
    GeometryResponse,
    SiteComparisonResult,
)
from ..schemas.pipeline import SolarScreeningRequest, SolarScreeningResponse
from ..schemas.terrain import TerrainRequest, TerrainResponse
from ..connectors.copernicus.glofas import GlofasError
from ..schemas.hydro import HydroScreeningRequest, HydroScreeningResponse
from ..schemas.wind import WindScreeningRequest, WindScreeningResponse
from ..sectors.hydro import HydroDataError, HydroSiteError, run_hydro_screening
from ..sectors.solar import run_solar_screening
from ..sectors.wind import run_wind_screening
from ..statistics.trends import analyze_trend, decision_p_value
from ..statistics.multiple_testing import benjamini_hochberg

router = APIRouter(prefix="/api/v1")


@router.get("/health")
def health():
    return {"status": "ok", "service": "los-causas-espaciales"}


@router.get("/sources")
def sources():
    return [
        {"id": "nasa-power", "name": "NASA POWER", "status": "integrated", "access": "public API", "url": "https://power.larc.nasa.gov/docs/services/api/temporal/daily/"},
        {"id": "nasadem-hgt", "name": "NASADEM HGT V001", "status": "metadata_integrated_raster_requires_auth", "access": "CMR público; raster con Earthdata Login", "url": "https://doi.org/10.5067/MEaSUREs/NASADEM/NASADEM_HGT.001"},
        {"id": "nasadem-sc", "name": "NASADEM Slope and Curvature V001", "status": "metadata_integrated_raster_requires_auth", "access": "CMR público; raster con Earthdata Login", "url": "https://doi.org/10.5067/MEaSUREs/NASADEM/NASADEM_SC.001"},
        {"id": "nasa-power-hourly", "name": "NASA POWER Hourly (WS50M, WS10M)", "status": "integrated", "access": "public API", "url": "https://power.larc.nasa.gov/api/temporal/hourly/point"},
        {"id": "global-wind-atlas", "name": "Global Wind Atlas 4.0 (DTU · World Bank)", "status": "integrated_crosscheck", "access": "public country GeoTIFF by HTTP range, CC BY 4.0", "url": "https://globalwindatlas.info"},
        {"id": "glofas-openmeteo", "name": "GloFAS v4 river discharge (Copernicus EMS) via Open-Meteo Flood API", "status": "integrated", "access": "public API; free tier is non-commercial", "url": "https://open-meteo.com/en/docs/flood-api"},
        {"id": "geoglows", "name": "GEOGLOWS River Forecast System v2", "status": "integrated_crosscheck", "access": "public REST API, CC BY 4.0", "url": "https://geoglows.ecmwf.int"},
        {"id": "nasa-gpm-imerg", "name": "NASA GPM IMERG V07", "status": "catalogued_not_integrated", "access": "Earthdata/PPS; authentication may apply", "url": "https://gpm.nasa.gov/data/imerg"},
        {"id": "appeears", "name": "NASA AppEEARS", "status": "integrated_async", "access": "Earthdata Login; token kept in memory and revoked after each operation", "url": "https://appeears.earthdatacloud.nasa.gov/api/"},
        {"id": "cenepred-sigrid", "name": "CENEPRED SIGRID", "status": "integrated_with_license_caveat", "access": "public ArcGIS REST", "url": "https://sigrid.cenepred.gob.pe/sigridv3/"},
        {"id": "sernanp-anp", "name": "SERNANP Áreas Naturales Protegidas", "status": "integrated_with_license_caveat", "access": "public ArcGIS REST", "url": "https://geoportal.sernanp.gob.pe/servicios-list/"},
        {"id": "osinergmin-grid", "name": "Osinergmin GISEM", "status": "integrated_with_license_caveat", "access": "public ArcGIS REST", "url": "https://gisem.osinergmin.gob.pe/"},
        {"id": "cultura-sigda", "name": "Ministerio de Cultura SIGDA", "status": "integrated_with_license_caveat", "access": "public ArcGIS REST", "url": "https://sigda.cultura.gob.pe/"},
        {"id": "coes-generation", "name": "COES-SINAC Producción diaria por central", "status": "integrated_with_license_caveat", "access": "public monthly XLSX export; indicador=1 (medidores)", "url": "https://www.coes.org.pe/Portal/portalinformacion/generacion"},
        {"id": "peru-cod-ab", "name": "Peru COD-AB v01 (IGN via OCHA/HDX)", "status": "integrated_web_reference", "access": "versioned local derivative of public GeoJSON, CC BY-IGO", "url": "https://data.humdata.org/dataset/cod-ab-per"},
    ]


@router.post("/terrain/points", response_model=TerrainResponse)
async def terrain_points(request: TerrainRequest):
    try:
        return await NasademConnector().points(request.sites)
    except NasademConnectorError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.post("/projects/solar-screening", response_model=SolarScreeningResponse)
async def solar_screening(request: SolarScreeningRequest):
    try:
        return await run_solar_screening(request)
    except PowerConnectorError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.post("/projects/wind-screening", response_model=WindScreeningResponse)
async def wind_screening(request: WindScreeningRequest):
    try:
        return await run_wind_screening(request)
    except PowerConnectorError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.post("/projects/hydro-screening", response_model=HydroScreeningResponse)
async def hydro_screening(request: HydroScreeningRequest):
    try:
        return await run_hydro_screening(request)
    except HydroSiteError as exc:       # los puntos no permiten una central: el usuario debe corregirlos
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except (PowerConnectorError, GlofasError, HydroDataError) as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.post("/analyses/point", response_model=AnalysisResponse)
async def analyze_point(request: AnalysisRequest):
    try:
        observations, source = await PowerConnector().daily_point(
            request.location.latitude, request.location.longitude, request.variable, request.start_date, request.end_date
        )
    except PowerConnectorError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    if not observations:
        raise HTTPException(status_code=422, detail="No valid observations were returned by NASA POWER")
    fingerprint = hashlib.sha256(json.dumps(request.model_dump(mode="json"), sort_keys=True).encode()).hexdigest()[:16]
    return AnalysisResponse(
        analysis_id=fingerprint,
        location=request.location,
        period=f"{request.start_date.isoformat()}/{request.end_date.isoformat()}",
        observations=observations,
        trend=analyze_trend(observations),
        source=source,
    )


@router.post("/finance/npv", response_model=FinanceResponse)
def npv(request: FinanceRequest):
    return calculate_npv(request)


@router.post("/geospatial/inspect", response_model=GeometryResponse)
def inspect_geojson(request: GeometryRequest):
    try:
        return inspect_geometry(request.geometry)
    except GeometryValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/comparisons/sites", response_model=ComparisonResponse)
async def compare_sites(request: ComparisonRequest):
    connector = PowerConnector()
    tasks = [
        connector.daily_point(site.latitude, site.longitude, request.variable, request.start_date, request.end_date)
        for site in request.sites
    ]
    try:
        datasets = await asyncio.gather(*tasks)
    except PowerConnectorError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    results = []
    unit = "unknown"
    expected_days = (request.end_date - request.start_date).days + 1
    for site, (observations, source) in zip(request.sites, datasets, strict=True):
        if not observations:
            raise HTTPException(status_code=422, detail=f"No valid observations for {site.label or site.model_dump()}")
        values = [item.value for item in observations]
        fingerprint_payload = {"site": site.model_dump(), "variable": request.variable, "start": str(request.start_date), "end": str(request.end_date)}
        fingerprint = hashlib.sha256(json.dumps(fingerprint_payload, sort_keys=True).encode()).hexdigest()[:16]
        results.append(
            SiteComparisonResult(
                analysis_id=fingerprint,
                location=site,
                mean=fmean(values),
                minimum=min(values),
                maximum=max(values),
                valid_observations=len(values),
                completeness_percent=round(len(values) / expected_days * 100, 2),
                trend=analyze_trend(observations),
                provenance=source.provenance,
            )
        )
        unit = source.unit
    adjusted_p_values = benjamini_hochberg([decision_p_value(item.trend) for item in results])
    for item, adjusted_p_value in zip(results, adjusted_p_values, strict=True):
        item.adjusted_p_value = adjusted_p_value
        item.significant_after_bh = adjusted_p_value is not None and adjusted_p_value < item.trend.alpha
    return ComparisonResponse(
        variable=request.variable,
        unit=unit,
        period=f"{request.start_date.isoformat()}/{request.end_date.isoformat()}",
        sites=results,
        note="Los p-values se ajustan entre sitios con Benjamini-Hochberg. Se muestran observaciones sin un score compuesto arbitrario; las ponderaciones deben ser explícitas y documentadas.",
    )
