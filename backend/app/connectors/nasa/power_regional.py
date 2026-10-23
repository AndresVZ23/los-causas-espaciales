"""Area-weighted regional NASA POWER sampling with per-cell traceability."""

from __future__ import annotations

import math
from collections import defaultdict
from datetime import date, timedelta
from statistics import median
from typing import Any
from urllib.parse import urlparse

import httpx
from pyproj import CRS, Geod, Transformer
from shapely import transform
from shapely.geometry import box, shape
from shapely.validation import explain_validity

from ...core.config import Settings, get_settings
from ...schemas.analysis import Observation, Point, Provenance, SourceMetadata
from ...schemas.spatial_sampling import (
    PowerCellSeries,
    SamplingSubject,
    SpatialAggregateObservation,
    SpatialSamplingRequest,
    SpatialSamplingResponse,
)
from ..cache import RawPayloadCache
from .power import PowerConnector, PowerConnectorError, VARIABLE_UNITS

TIMEOUT = httpx.Timeout(connect=20, read=120, write=30, pool=20)
GEOD = Geod(ellps="WGS84")
MIN_REGIONAL_SPAN_DEGREES = 2.0
DOCUMENTED_CELL_DEGREES = 0.5
MAX_REGIONAL_SPAN_DEGREES = 10.0
MAX_REGIONAL_BYTES = 100 * 1024 * 1024


class RegionalPowerError(RuntimeError):
    pass


def _geodesic_area_sqkm(geometry) -> float:
    area, _ = GEOD.geometry_area_perimeter(geometry)
    return abs(area) / 1_000_000


def _subject(request: SpatialSamplingRequest):
    payload = request.subject
    if payload.get("type") == "Feature":
        geometry_payload = payload.get("geometry")
        properties = payload.get("properties") or {}
    else:
        geometry_payload = payload
        properties = {}
    if not isinstance(geometry_payload, dict):
        raise RegionalPowerError("El sujeto debe ser una geometría o Feature GeoJSON.")
    try:
        geometry = shape(geometry_payload)
    except Exception as exc:
        raise RegionalPowerError(f"GeoJSON inválido: {exc}") from exc
    if geometry.geom_type not in {"Point", "LineString", "MultiLineString", "Polygon", "MultiPolygon"}:
        raise RegionalPowerError("K1 admite Point, LineString, MultiLineString, Polygon y MultiPolygon.")
    if geometry.is_empty or not geometry.is_valid:
        raise RegionalPowerError(f"Geometría vacía o inválida: {explain_validity(geometry)}")
    minimum_x, minimum_y, maximum_x, maximum_y = geometry.bounds
    if minimum_x < -180 or maximum_x > 180 or minimum_y < -90 or maximum_y > 90:
        raise RegionalPowerError("Las coordenadas deben ser WGS84 longitud/latitud.")
    kind = str(properties.get("kind") or properties.get("level") or "geometry")
    name = str(properties.get("name") or properties.get("adm3_name") or "Área sin nombre")
    origin = str(properties.get("origin") or ("COD-AB" if properties.get("pcode") else "user"))
    corridor_buffer = None
    analytic_geometry = geometry
    if geometry.geom_type in {"LineString", "MultiLineString"}:
        center = geometry.centroid
        local_crs = CRS.from_proj4(
            f"+proj=aeqd +lat_0={center.y} +lon_0={center.x} +datum=WGS84 +units=m +no_defs"
        )
        forward = Transformer.from_crs("EPSG:4326", local_crs, always_xy=True)
        inverse = Transformer.from_crs(local_crs, "EPSG:4326", always_xy=True)
        projected = transform(geometry, forward.transform, interleaved=False)
        analytic_geometry = transform(
            projected.buffer(request.corridor_buffer_km * 1_000), inverse.transform, interleaved=False
        )
        corridor_buffer = request.corridor_buffer_km
        kind = str(properties.get("kind") or "corridor")
    area = None if geometry.geom_type == "Point" else _geodesic_area_sqkm(analytic_geometry)
    metadata = SamplingSubject(
        kind=kind,
        name=name,
        origin=origin,
        geometry_type=geometry.geom_type,
        area_km2=round(area, 6) if area is not None else None,
        corridor_buffer_km=corridor_buffer,
    )
    return geometry, analytic_geometry, metadata


def _nominal_cell_area_sqkm(latitude: float) -> float:
    cell = box(-DOCUMENTED_CELL_DEGREES / 2, latitude - DOCUMENTED_CELL_DEGREES / 2,
               DOCUMENTED_CELL_DEGREES / 2, latitude + DOCUMENTED_CELL_DEGREES / 2)
    return _geodesic_area_sqkm(cell)


def _pad_axis(minimum: float, maximum: float, lower_limit: float, upper_limit: float) -> tuple[float, float]:
    span = maximum - minimum
    if span > MAX_REGIONAL_SPAN_DEGREES:
        raise RegionalPowerError(f"La extensión regional supera {MAX_REGIONAL_SPAN_DEGREES}° por eje.")
    if span >= MIN_REGIONAL_SPAN_DEGREES:
        return minimum, maximum
    padding = (MIN_REGIONAL_SPAN_DEGREES - span) / 2 + 0.001
    minimum = max(lower_limit, minimum - padding)
    maximum = min(upper_limit, maximum + padding)
    if maximum - minimum < MIN_REGIONAL_SPAN_DEGREES:
        if minimum == lower_limit:
            maximum = minimum + MIN_REGIONAL_SPAN_DEGREES
        else:
            minimum = maximum - MIN_REGIONAL_SPAN_DEGREES
    return minimum, maximum


def _request_bounds(geometry) -> tuple[float, float, float, float]:
    minimum_x, minimum_y, maximum_x, maximum_y = geometry.bounds
    minimum_x, maximum_x = _pad_axis(minimum_x, maximum_x, -180, 180)
    minimum_y, maximum_y = _pad_axis(minimum_y, maximum_y, -90, 90)
    return minimum_x, minimum_y, maximum_x, maximum_y


def _spacing(values: list[float], fallback: float = DOCUMENTED_CELL_DEGREES) -> float:
    unique = sorted(set(values))
    differences = [round(second - first, 8) for first, second in zip(unique, unique[1:]) if second > first]
    return median(differences) if differences else fallback


class RegionalPowerConnector:
    def __init__(
        self,
        *,
        settings: Settings | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
        point_connector: PowerConnector | None = None,
    ):
        self.settings = settings or get_settings()
        self.transport = transport
        self.point_connector = point_connector or PowerConnector()
        self.cache = RawPayloadCache(self.settings.cache_dir, "nasa-power-regional")
        parsed = urlparse(self.settings.power_api_base)
        if parsed.scheme != "https" or parsed.hostname != "power.larc.nasa.gov":
            raise RegionalPowerError("NASA POWER debe usar el host HTTPS oficial.")

    async def _regional_payload(self, request: SpatialSamplingRequest, bounds):
        minimum_x, minimum_y, maximum_x, maximum_y = bounds
        params: dict[str, str | float] = {
            "latitude-min": round(minimum_y, 6),
            "latitude-max": round(maximum_y, 6),
            "longitude-min": round(minimum_x, 6),
            "longitude-max": round(maximum_x, 6),
            "parameters": request.variable,
            "community": "RE",
            "start": request.start_date.strftime("%Y%m%d"),
            "end": request.end_date.strftime("%Y%m%d"),
            "format": "JSON",
            "time-standard": "UTC",
        }
        key = self.cache.request_key(params)
        cached = self.cache.get(key, max_age=timedelta(hours=self.settings.cache_ttl_hours))
        if cached:
            import json

            return json.loads(cached.content), Provenance.CACHED, cached.downloaded_at
        url = f"{self.settings.power_api_base}/temporal/daily/regional"
        try:
            async with httpx.AsyncClient(timeout=TIMEOUT, transport=self.transport, follow_redirects=True) as client:
                response = await client.get(url, params=params)
                response.raise_for_status()
                if len(response.content) > MAX_REGIONAL_BYTES:
                    raise RegionalPowerError("La respuesta regional NASA POWER excede el límite seguro de 100 MB.")
                payload = response.json()
        except RegionalPowerError:
            raise
        except (httpx.HTTPError, ValueError) as exc:
            raise RegionalPowerError(f"La consulta regional NASA POWER falló: {exc}") from exc
        import json

        raw = self.cache.put(key, json.dumps(payload).encode(), suffix=".json")
        return payload, Provenance.REAL, raw.downloaded_at

    async def sample(self, request: SpatialSamplingRequest) -> SpatialSamplingResponse:
        source_geometry, analytic_geometry, subject = _subject(request)
        representative = analytic_geometry.representative_point()
        point_mode = source_geometry.geom_type == "Point"
        nominal_cell_area = _nominal_cell_area_sqkm(representative.y)
        if source_geometry.geom_type in {"Polygon", "MultiPolygon"} and subject.area_km2 is not None and subject.area_km2 < nominal_cell_area:
            point_mode = True
        if point_mode:
            try:
                observations, source = await self.point_connector.daily_point(
                    representative.y,
                    representative.x,
                    request.variable,
                    request.start_date,
                    request.end_date,
                )
            except PowerConnectorError as exc:
                raise RegionalPowerError(str(exc)) from exc
            cells = [PowerCellSeries(
                cell_id=f"point:{representative.y:.6f},{representative.x:.6f}",
                center=Point(latitude=representative.y, longitude=representative.x),
                bounds=(representative.x, representative.y, representative.x, representative.y),
                overlap_area_km2=subject.area_km2 or nominal_cell_area,
                weight=1,
                observations=observations,
            )]
            aggregate = [SpatialAggregateObservation(
                timestamp=item.timestamp,
                value=item.value,
                dispersion_stddev=0,
                minimum=item.value,
                maximum=item.value,
                contributing_cells=1,
            ) for item in observations]
            reason = (
                "El área es menor que una celda nominal de 0.5°; se declaró y consultó como punto representativo."
                if source_geometry.geom_type != "Point" else
                "El sujeto de entrada es un punto."
            )
            return SpatialSamplingResponse(
                mode="POINT",
                subject=subject,
                variable=request.variable,
                unit=source.unit,
                spatial_coverage_percent=100,
                cells=cells,
                aggregate=aggregate,
                source=source,
                method=reason,
                limitations=[
                    "El punto representativo no describe variación interna del territorio.",
                    "NASA POWER es una grilla; no sustituye medición in situ.",
                ],
            )

        bounds = _request_bounds(analytic_geometry)
        payload, provenance, downloaded_at = await self._regional_payload(request, bounds)
        features = payload.get("features")
        if not isinstance(features, list) or not features:
            raise RegionalPowerError("NASA POWER no devolvió celdas regionales.")
        parsed_cells: dict[tuple[float, float], dict[date, float]] = {}
        elevations: dict[tuple[float, float], float | None] = {}
        for feature in features:
            coordinates = feature.get("geometry", {}).get("coordinates", [])
            if len(coordinates) < 2:
                continue
            longitude, latitude = float(coordinates[0]), float(coordinates[1])
            key = (round(longitude, 8), round(latitude, 8))
            raw_series = feature.get("properties", {}).get("parameter", {}).get(request.variable)
            if not isinstance(raw_series, dict):
                continue
            series = {
                date(int(stamp[:4]), int(stamp[4:6]), int(stamp[6:8])): float(value)
                for stamp, value in raw_series.items()
                if value is not None and math.isfinite(float(value)) and float(value) > -900
            }
            if key in parsed_cells and parsed_cells[key] != series:
                raise RegionalPowerError(f"NASA POWER devolvió valores conflictivos para la celda {key}.")
            parsed_cells[key] = series
            elevations[key] = float(coordinates[2]) if len(coordinates) > 2 and coordinates[2] is not None else None
        if not parsed_cells:
            raise RegionalPowerError("NASA POWER no devolvió series válidas para la variable solicitada.")

        longitude_spacing = _spacing([item[0] for item in parsed_cells])
        latitude_spacing = _spacing([item[1] for item in parsed_cells])
        intersecting = []
        for (longitude, latitude), series in parsed_cells.items():
            cell_bounds = (
                longitude - longitude_spacing / 2,
                latitude - latitude_spacing / 2,
                longitude + longitude_spacing / 2,
                latitude + latitude_spacing / 2,
            )
            intersection = analytic_geometry.intersection(box(*cell_bounds))
            overlap = _geodesic_area_sqkm(intersection) if not intersection.is_empty else 0
            if overlap > 0:
                intersecting.append((longitude, latitude, cell_bounds, overlap, series, elevations[(longitude, latitude)]))
        if not intersecting:
            raise RegionalPowerError("Ninguna celda devuelta por NASA POWER intersecta el sujeto.")
        total_overlap = sum(item[3] for item in intersecting)
        cells = [PowerCellSeries(
            cell_id=f"{latitude:.6f},{longitude:.6f}",
            center=Point(latitude=latitude, longitude=longitude),
            bounds=cell_bounds,
            overlap_area_km2=round(overlap, 6),
            weight=overlap / total_overlap,
            observations=[Observation(timestamp=stamp, value=value) for stamp, value in sorted(series.items())],
        ) for longitude, latitude, cell_bounds, overlap, series, _ in intersecting]

        by_date: dict[date, list[tuple[float, float]]] = defaultdict(list)
        for cell in cells:
            for observation in cell.observations:
                by_date[observation.timestamp].append((observation.value, cell.weight))
        aggregate = []
        for stamp, values_and_weights in sorted(by_date.items()):
            available_weight = sum(weight for _, weight in values_and_weights)
            weighted_mean = sum(value * weight for value, weight in values_and_weights) / available_weight
            variance = sum(weight * (value - weighted_mean) ** 2 for value, weight in values_and_weights) / available_weight
            values = [value for value, _ in values_and_weights]
            aggregate.append(SpatialAggregateObservation(
                timestamp=stamp,
                value=weighted_mean,
                dispersion_stddev=math.sqrt(max(variance, 0)),
                minimum=min(values),
                maximum=max(values),
                contributing_cells=len(values),
            ))
        metadata = payload.get("parameters", {}).get(request.variable, {})
        header = payload.get("header", {})
        source = SourceMetadata(
            source_id="nasa-power",
            dataset="NASA POWER Daily Regional",
            version=str(header.get("api", {}).get("version", "respuesta vigente del API")),
            variable=request.variable,
            unit=str(metadata.get("units", VARIABLE_UNITS.get(request.variable, "unidad no informada"))),
            temporal_resolution="diaria UTC",
            spatial_resolution=f"centros devueltos: {latitude_spacing:g}° lat × {longitude_spacing:g}° lon",
            downloaded_at=downloaded_at,
            source_url=f"{self.settings.power_api_base}/temporal/daily/regional",
            provenance=provenance,
            quality_notes=["Se deduplicaron celdas por centro y se conservaron series por celda."],
        )
        coverage = min(100, total_overlap / (subject.area_km2 or total_overlap) * 100)
        return SpatialSamplingResponse(
            mode="REGIONAL",
            subject=subject,
            variable=request.variable,
            unit=source.unit,
            request_bounds=bounds,
            grid_spacing_degrees=(latitude_spacing, longitude_spacing),
            spatial_coverage_percent=round(coverage, 4),
            cells=cells,
            aggregate=aggregate,
            source=source,
            method=(
                "Intersección de cada celda devuelta por NASA POWER con el sujeto; promedio diario ponderado por "
                "área geodésica de intersección y desviación estándar ponderada entre celdas."
            ),
            limitations=[
                "La documentación regional indica 0.5° × 0.5°, pero se usan los centros realmente devueltos; variables MERRA-2 pueden espaciarse 0.5° lat × 0.625° lon.",
                "Las celdas se aproximan con límites a mitad de camino entre centros; costa y relieve no se fraccionan internamente.",
                "NASA POWER es una grilla y no sustituye medición in situ.",
            ],
        )
