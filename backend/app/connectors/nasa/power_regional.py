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
from .power_scale import (
    KNOWN_SCALE,
    PRECIPITATION,
    RECENT_DAYS,
    PrecipitationScaleError,
    precipitation_divisor,
    reference_period,
)

TIMEOUT = httpx.Timeout(connect=20, read=120, write=30, pool=20)
GEOD = Geod(ellps="WGS84")
MIN_REGIONAL_SPAN_DEGREES = 2.0
DOCUMENTED_CELL_DEGREES = 0.5
MAX_REGIONAL_SPAN_DEGREES = 10.0
MAX_REGIONAL_BYTES = 100 * 1024 * 1024


class RegionalPowerError(RuntimeError):
    pass


def _annual_periods(start: date, end: date) -> list[tuple[date, date]]:
    """Split an inclusive range into calendar years accepted by POWER Regional."""
    periods: list[tuple[date, date]] = []
    cursor = start
    while cursor <= end:
        chunk_end = min(end, date(cursor.year, 12, 31))
        periods.append((cursor, chunk_end))
        cursor = chunk_end + timedelta(days=1)
    return periods


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


def aggregate_cells(cells: list[PowerCellSeries]) -> list[SpatialAggregateObservation]:
    """Promedio diario ponderado por área entre celdas y desviación estándar ponderada; el peso se renormaliza
    sobre las celdas con dato ese día. Extraída sin cambios para reutilizarla en el análisis territorial (Claude)."""
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
    return aggregate


def _request_bounds(geometry) -> tuple[float, float, float, float]:
    minimum_x, minimum_y, maximum_x, maximum_y = geometry.bounds
    minimum_x, maximum_x = _pad_axis(minimum_x, maximum_x, -180, 180)
    minimum_y, maximum_y = _pad_axis(minimum_y, maximum_y, -90, 90)
    return minimum_x, minimum_y, maximum_x, maximum_y


def _spacing(values: list[float], fallback: float = DOCUMENTED_CELL_DEGREES) -> float:
    unique = sorted(set(values))
    differences = [round(second - first, 8) for first, second in zip(unique, unique[1:]) if second > first]
    return median(differences) if differences else fallback


def _payload_cell_series(payload: dict[str, Any], variable: str) -> dict[tuple[float, float], dict[date, float]]:
    """Parse valid cell series from a POWER FeatureCollection for scale comparison."""
    result: dict[tuple[float, float], dict[date, float]] = {}
    for feature in payload.get("features") or []:
        coordinates = feature.get("geometry", {}).get("coordinates", [])
        raw_series = feature.get("properties", {}).get("parameter", {}).get(variable)
        if len(coordinates) < 2 or not isinstance(raw_series, dict):
            continue
        key = (round(float(coordinates[0]), 8), round(float(coordinates[1]), 8))
        series: dict[date, float] = {}
        for raw_stamp, raw_value in raw_series.items():
            if raw_value is None:
                continue
            try:
                stamp = date(int(raw_stamp[:4]), int(raw_stamp[4:6]), int(raw_stamp[6:8]))
                value = float(raw_value)
            except (TypeError, ValueError) as exc:
                raise RegionalPowerError("NASA POWER devolvió una fecha o valor regional inválido.") from exc
            if math.isfinite(value) and value > -900:
                series[stamp] = value
        result[key] = series
    return result


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

    async def _regional_payload(
        self,
        request: SpatialSamplingRequest,
        bounds,
        start: date,
        end: date,
    ):
        minimum_x, minimum_y, maximum_x, maximum_y = bounds
        params: dict[str, str | float] = {
            "latitude-min": round(minimum_y, 6),
            "latitude-max": round(maximum_y, 6),
            "longitude-min": round(minimum_x, 6),
            "longitude-max": round(maximum_x, 6),
            "parameters": request.variable,
            "community": "RE",
            "start": start.strftime("%Y%m%d"),
            "end": end.strftime("%Y%m%d"),
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
            if request.variable == PRECIPITATION and request.end_date > date.today() - timedelta(days=RECENT_DAYS):
                reference_start, reference_end = reference_period(request.start_date, request.end_date)
                notes = list(source.quality_notes)
                if reference_end <= reference_start:
                    notes.append("Escala de precipitación no verificable: no existe una ventana histórica suficiente.")
                else:
                    try:
                        reference, _ = await self.point_connector.daily_point(
                            representative.y, representative.x, request.variable, reference_start, reference_end
                        )
                        scale, divisor = precipitation_divisor(
                            {item.timestamp: item.value for item in observations},
                            {item.timestamp: item.value for item in reference},
                        )
                    except (PowerConnectorError, PrecipitationScaleError) as exc:
                        raise RegionalPowerError(str(exc)) from exc
                    if divisor is None:
                        notes.append(
                            f"Escala de precipitación no verificable: menos de 3 días húmedos entre "
                            f"{reference_start} y {reference_end}."
                        )
                    elif divisor == KNOWN_SCALE:
                        observations = [
                            Observation.model_construct(timestamp=item.timestamp, value=item.value / divisor)
                            for item in observations
                        ]
                        notes.append(
                            f"NASA POWER devolvió precipitación ×24; se dividió por 24 tras compararla con "
                            f"{reference_start} a {reference_end} (razón {scale:.2f})."
                        )
                    else:
                        notes.append(
                            f"Escala de precipitación verificada contra {reference_start} a {reference_end} "
                            f"(razón {scale:.2f})."
                        )
                source = source.model_copy(update={"quality_notes": notes})
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
        parsed_cells: dict[tuple[float, float], dict[date, float]] = {}
        elevations: dict[tuple[float, float], float | None] = {}
        expected_cell_keys: set[tuple[float, float]] | None = None
        parameter_metadata: dict[str, Any] | None = None
        api_versions: set[str] = set()
        provenances: list[Provenance] = []
        download_times = []
        scale_quality_notes: list[str] = []
        periods = _annual_periods(request.start_date, request.end_date)
        for chunk_start, chunk_end in periods:
            payload, chunk_provenance, chunk_downloaded_at = await self._regional_payload(
                request,
                bounds,
                chunk_start,
                chunk_end,
            )
            provenances.append(chunk_provenance)
            download_times.append(chunk_downloaded_at)
            header = payload.get("header", {})
            api_versions.add(str(header.get("api", {}).get("version", "respuesta vigente del API")))
            chunk_metadata = payload.get("parameters", {}).get(request.variable, {})
            if parameter_metadata is None:
                parameter_metadata = chunk_metadata
            elif chunk_metadata.get("units") != parameter_metadata.get("units"):
                raise RegionalPowerError("NASA POWER devolvió unidades incompatibles entre tramos anuales.")

            features = payload.get("features")
            if not isinstance(features, list) or not features:
                raise RegionalPowerError("NASA POWER no devolvió celdas regionales.")
            chunk_cells: dict[tuple[float, float], dict[date, float]] = {}
            chunk_elevations: dict[tuple[float, float], float | None] = {}
            for feature in features:
                coordinates = feature.get("geometry", {}).get("coordinates", [])
                if len(coordinates) < 2:
                    continue
                longitude, latitude = float(coordinates[0]), float(coordinates[1])
                key = (round(longitude, 8), round(latitude, 8))
                raw_series = feature.get("properties", {}).get("parameter", {}).get(request.variable)
                if not isinstance(raw_series, dict):
                    continue
                series: dict[date, float] = {}
                for raw_stamp, raw_value in raw_series.items():
                    if raw_value is None:
                        continue
                    try:
                        stamp = date(int(raw_stamp[:4]), int(raw_stamp[4:6]), int(raw_stamp[6:8]))
                        value = float(raw_value)
                    except (TypeError, ValueError) as exc:
                        raise RegionalPowerError("NASA POWER devolvió una fecha o valor regional inválido.") from exc
                    if stamp < chunk_start or stamp > chunk_end:
                        raise RegionalPowerError("NASA POWER devolvió una fecha fuera del tramo anual solicitado.")
                    if not math.isfinite(value) or value <= -900:
                        continue
                    if stamp in series and series[stamp] != value:
                        raise RegionalPowerError(f"NASA POWER devolvió valores conflictivos para la celda {key}.")
                    series[stamp] = value
                if key in chunk_cells and chunk_cells[key] != series:
                    raise RegionalPowerError(f"NASA POWER devolvió valores conflictivos para la celda {key}.")
                chunk_cells[key] = series
                elevation = float(coordinates[2]) if len(coordinates) > 2 and coordinates[2] is not None else None
                if key in chunk_elevations and chunk_elevations[key] != elevation:
                    raise RegionalPowerError(f"NASA POWER devolvió elevaciones conflictivas para la celda {key}.")
                chunk_elevations[key] = elevation
            if not chunk_cells:
                raise RegionalPowerError("NASA POWER no devolvió series válidas para la variable solicitada.")
            if request.variable == PRECIPITATION and chunk_end > date.today() - timedelta(days=RECENT_DAYS):
                reference_start, reference_end = reference_period(chunk_start, chunk_end)
                if reference_end <= reference_start:
                    scale_quality_notes.append(
                        f"Escala no verificable para {chunk_start}–{chunk_end}: no existe ventana histórica suficiente."
                    )
                else:
                    reference_payload, _, _ = await self._regional_payload(
                        request, bounds, reference_start, reference_end
                    )
                    reference_cells = _payload_cell_series(reference_payload, request.variable)
                    if set(reference_cells) != set(chunk_cells):
                        raise RegionalPowerError(
                            "NASA POWER cambió el conjunto de celdas entre la serie reciente y su referencia."
                        )
                    corrected = verified = unverifiable = 0
                    for key, series in chunk_cells.items():
                        try:
                            scale, divisor = precipitation_divisor(series, reference_cells[key])
                        except PrecipitationScaleError as exc:
                            raise RegionalPowerError(f"Celda {key}: {exc}") from exc
                        if divisor is None:
                            unverifiable += 1
                        elif divisor == KNOWN_SCALE:
                            chunk_cells[key] = {stamp: value / divisor for stamp, value in series.items()}
                            corrected += 1
                        else:
                            verified += 1
                    scale_quality_notes.append(
                        f"Escala PRECTOTCORR por celda contra {reference_start}–{reference_end}: "
                        f"{corrected} corregida(s) ÷24, {verified} verificada(s) ×1 y "
                        f"{unverifiable} no verificable(s)."
                    )
            chunk_cell_keys = set(chunk_cells)
            if expected_cell_keys is None:
                expected_cell_keys = chunk_cell_keys
            elif chunk_cell_keys != expected_cell_keys:
                raise RegionalPowerError("NASA POWER cambió el conjunto de celdas entre tramos anuales.")
            for key, series in chunk_cells.items():
                existing = parsed_cells.setdefault(key, {})
                for stamp, value in series.items():
                    if stamp in existing and existing[stamp] != value:
                        raise RegionalPowerError(
                            f"NASA POWER devolvió valores conflictivos para la celda {key} en {stamp.isoformat()}."
                        )
                    existing[stamp] = value
                elevation = chunk_elevations[key]
                if key in elevations and elevations[key] != elevation:
                    raise RegionalPowerError(f"NASA POWER devolvió elevaciones conflictivas para la celda {key}.")
                elevations[key] = elevation
        if not parsed_cells:
            raise RegionalPowerError("NASA POWER no devolvió series válidas para la variable solicitada.")

        provenance = Provenance.REAL if Provenance.REAL in provenances else Provenance.CACHED
        downloaded_at = max(download_times)

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

        aggregate = aggregate_cells(cells)
        metadata = parameter_metadata or {}
        real_chunks = sum(item == Provenance.REAL for item in provenances)
        cached_chunks = len(provenances) - real_chunks
        source = SourceMetadata(
            source_id="nasa-power",
            dataset="NASA POWER Daily Regional",
            version=", ".join(sorted(api_versions)),
            variable=request.variable,
            unit=str(metadata.get("units", VARIABLE_UNITS.get(request.variable, "unidad no informada"))),
            temporal_resolution="diaria UTC",
            spatial_resolution=f"centros devueltos: {latitude_spacing:g}° lat × {longitude_spacing:g}° lon",
            downloaded_at=downloaded_at,
            source_url=f"{self.settings.power_api_base}/temporal/daily/regional",
            provenance=provenance,
            quality_notes=[
                "Se deduplicaron celdas por centro y se conservaron series por celda.",
                *scale_quality_notes,
                (
                    f"El período se dividió en {len(periods)} solicitud(es) por año calendario, "
                    f"cada una de hasta 366 días inclusivos: {real_chunks} nueva(s) y {cached_chunks} en caché."
                ),
            ],
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
