"""Extracción común para todos los sectores: NASA POWER por punto y NASADEM, con tiempos medidos.

Los sectores pasan los puntos representativos de sus sujetos (sitios, tramos o terrenos); el conector es
el mismo. Un fallo de NASADEM se declara y no invalida el análisis climático.
"""

import asyncio
from collections.abc import Sequence
from datetime import date
from itertools import combinations
from time import perf_counter

from ..connectors.nasa.nasadem import NasademConnector, NasademConnectorError
from ..connectors.nasa.power import PowerConnector
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
    return list(datasets), elapsed_ms(start)


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
