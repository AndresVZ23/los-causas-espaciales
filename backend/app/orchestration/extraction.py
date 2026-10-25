"""Extracción común para todos los sectores: NASA POWER por punto y NASADEM, con tiempos medidos.

Los sectores pasan los puntos representativos de sus sujetos (sitios, tramos o terrenos); el conector es
el mismo. Un fallo de NASADEM se declara y no invalida el análisis climático.
"""

import asyncio
from collections.abc import Sequence
from datetime import date, timedelta
from itertools import combinations
from time import perf_counter

from ..connectors.nasa.nasadem import NasademConnector, NasademConnectorError
from ..connectors.nasa.power import PowerConnector, PowerConnectorError
from ..connectors.nasa.power_scale import (
    KNOWN_SCALE,
    PRECIPITATION,
    RECENT_DAYS,
    PrecipitationScaleError,
    precipitation_divisor,
    precipitation_scale,
    reference_period,
)
from ..geospatial.geometry import GEOD
from ..schemas.analysis import Observation, Point, SourceMetadata
from ..schemas.terrain import TerrainResponse

TERRAIN_TIMEOUT_SECONDS = 45

PowerDataset = dict[str, tuple[list[Observation], SourceMetadata]]


def elapsed_ms(start: float) -> float:
    return round((perf_counter() - start) * 1000, 1)


async def extract_power(points: Sequence[Point], variables: Sequence[str], start_date: date, end_date: date) -> tuple[list[PowerDataset], float]:
    connector = PowerConnector()
    start = perf_counter()
    datasets = await asyncio.gather(*(
        connector.daily_point_multi(point.latitude, point.longitude, list(variables), start_date, end_date)
        for point in points
    ))
    if PRECIPITATION in variables and end_date > date.today() - timedelta(days=RECENT_DAYS):
        datasets = await asyncio.gather(*(
            _verify_precipitation_scale(connector, point, dataset, start_date, end_date) for point, dataset in zip(points, datasets, strict=True)
        ))
    return list(datasets), elapsed_ms(start)


# Defecto observado en la API NASA POWER Daily v2.10.1 (2026-10-22): si el rango incluye los días más recientes,
# toda la serie PRECTOTCORR de la respuesta llega multiplicada por 24, aunque declara mm/day. Se verifica contra una
# ventana de referencia antigua y se corrige solo si la razón es exactamente la del defecto.
async def _verify_precipitation_scale(connector: PowerConnector, point: Point, dataset: PowerDataset, start_date: date, end_date: date) -> PowerDataset:
    observations, source = dataset[PRECIPITATION]
    reference_start, reference_end = reference_period(start_date, end_date)
    if reference_end <= reference_start:
        note = "Escala de precipitación no verificable: el período no tiene una ventana de referencia anterior a los datos recientes."
        return {**dataset, PRECIPITATION: (observations, source.model_copy(update={"quality_notes": [*source.quality_notes, note]}))}
    reference = await connector.daily_point_multi(point.latitude, point.longitude, [PRECIPITATION], reference_start, reference_end)
    try:
        scale, divisor = precipitation_divisor(
            {item.timestamp: item.value for item in observations},
            {item.timestamp: item.value for item in reference[PRECIPITATION][0]},
        )
    except PrecipitationScaleError as exc:
        raise PowerConnectorError(str(exc)) from exc
    if scale is None:
        note = f"Escala de precipitación no verificable: menos de 3 días húmedos entre {reference_start} y {reference_end}."
        return {**dataset, PRECIPITATION: (observations, source.model_copy(update={"quality_notes": [*source.quality_notes, note]}))}
    if divisor == 1:
        note = f"Escala de precipitación verificada contra la ventana {reference_start} a {reference_end} (razón 1.00)."
        return {**dataset, PRECIPITATION: (observations, source.model_copy(update={"quality_notes": [*source.quality_notes, note]}))}
    if divisor == KNOWN_SCALE:
        corrected = [Observation.model_construct(timestamp=item.timestamp, value=item.value / KNOWN_SCALE) for item in observations]
        note = (f"NASA POWER devolvió la precipitación multiplicada por 24 al incluir días recientes; se dividió por 24 tras verificarlo "
                f"contra la ventana {reference_start} a {reference_end} (razón {scale:.2f}).")
        return {**dataset, PRECIPITATION: (corrected, source.model_copy(update={"quality_notes": [*source.quality_notes, note]}))}
    raise PowerConnectorError("La escala de precipitación no pudo clasificarse.")


async def extract_terrain(points: Sequence[Point]) -> tuple[TerrainResponse | None, str | None, float]:
    start = perf_counter()
    try:
        terrain = await asyncio.wait_for(NasademConnector().points(list(points)), timeout=TERRAIN_TIMEOUT_SECONDS)
        return terrain, None, elapsed_ms(start)
    except NasademConnectorError as exc:
        return None, str(exc), elapsed_ms(start)
    except TimeoutError:
        return None, f"NASADEM no respondió en {TERRAIN_TIMEOUT_SECONDS} s.", elapsed_ms(start)


def max_separation_km(points: Sequence[Point]) -> float | None:
    distances = [GEOD.inv(a.longitude, a.latitude, b.longitude, b.latitude)[2] / 1000 for a, b in combinations(points, 2)]
    return max(distances) if distances else None
