"""Aislamiento común: ninguna prueba sale a la red por CHIRPS (NASA SERVIR ClimateSERV), por los deslizamientos de NASA,
por ERA5 (PVGIS), por Copernicus DEM, por ESA WorldCover, por NASA POWER horario, por el Atlas Eólico Global ni por el
caudal de GloFAS y GEOGLOWS."""

import math
from collections import Counter
from datetime import date, datetime, timedelta, timezone

import numpy as np
import pytest

from backend.app.connectors.copernicus.dem import DemPoint
from backend.app.connectors.copernicus.glofas import FlowCell, GlofasSeries
from backend.app.connectors.esa.worldcover import Composition
from backend.app.connectors.geoglows.streamflow import RiverChoice
from backend.app.connectors.gwa.wind_atlas import AtlasPoint
from backend.app.connectors.nasa.power_hourly import HourlyWind
from backend.app.connectors.jrc.pvgis import Era5Annual
from backend.app.orchestration import cover_crosscheck, era5_crosscheck, extraction, rainfall_crosscheck
from backend.app.schemas.analysis import Observation, Provenance, SourceMetadata
from backend.app.schemas.data_sources import TerritorialSourceResult
from backend.app.sectors import baseline, hydro, wind


class FlatChirps:
    """CHIRPS sintético: un día de 4–8 mm cada diez y el resto secos, igual todos los años (sin tendencia)."""

    def __init__(self, *args, **kwargs):
        pass

    async def daily(self, geometry, longitude, latitude, start, end):
        days = (end - start).days + 1
        observations = [Observation(timestamp=start + timedelta(days=offset), value=4.0 + (offset // 10) % 5 if offset % 10 == 0 else 0.0)
                        for offset in range(days)]
        source = SourceMetadata(source_id="chirps-prueba", dataset="CHIRPS sintético", version="prueba", variable="CHIRPS", unit="mm/day",
                                temporal_resolution="Diaria", spatial_resolution="0.05°", downloaded_at=datetime(2026, 10, 26, tzinfo=timezone.utc),
                                source_url="https://example.org", provenance=Provenance.CACHED)
        return observations, source


class FlatEra5:
    """ERA5 sintético: 2005–2023 sin tendencia (18 °C y 6.0 kWh/m²/día), sin red."""

    def __init__(self, *args, **kwargs):
        pass

    async def era5_annual(self, latitude, longitude):
        years = range(2005, 2024)
        wobble = lambda year: ((year * 7) % 5 - 2) * 0.01   # noqa: E731 — variación sin tendencia para que Mann–Kendall no empate
        return Era5Annual(temperature=[Observation(timestamp=datetime(year, 7, 1).date(), value=18.0 + wobble(year)) for year in years],
                          irradiance=[Observation(timestamp=datetime(year, 7, 1).date(), value=6.0 + wobble(year)) for year in years],
                          provenance=Provenance.CACHED, downloaded_at=datetime(2026, 10, 27, tzinfo=timezone.utc))

    async def era5_wind(self, latitude, longitude):
        return [Observation(timestamp=datetime(year, 7, 1).date(), value=2.0 + ((year * 7) % 5 - 2) * 0.01) for year in range(2005, 2024)]


class FixedCopernicus:
    """Copernicus GLO-30 sintético: 1,400 m y 5° en cualquier punto, sin red."""

    def __init__(self, *args, **kwargs):
        pass

    async def point(self, latitude, longitude):
        return DemPoint(elevation_m=1400.0, slope_degrees=5.0, tile_url="https://example.org/cop.tif", provenance=Provenance.CACHED,
                        downloaded_at=datetime(2026, 10, 27, tzinfo=timezone.utc), limitations=[])


class DesertWorldCover:
    """WorldCover sintético: 80 % suelo desnudo y 20 % pastizal en tierra, más algo de agua que no cuenta, sin red."""

    def __init__(self, *args, **kwargs):
        pass

    async def composition(self, geometry):
        return Composition(counts=Counter({60: 800, 30: 200, 80: 50}), resolution_m=9.3, urls=["https://example.org/wc.tif"],
                           provenance=Provenance.CACHED, downloaded_at=datetime(2026, 10, 28, tzinfo=timezone.utc))


class EmptyLandslides:
    """Deslizamientos de NASA sin registros en el área: las tres consultas responden, ninguna inventa un valor."""

    def __init__(self, *args, **kwargs):
        pass

    @staticmethod
    def _empty(source_id: str) -> TerritorialSourceResult:
        return TerritorialSourceResult(source_id=source_id, organization="NASA · Earthdata GIS", dataset=f"Capa {source_id}", status="READY",
                                       intersection_count=0, provenance=Provenance.CACHED, downloaded_at=datetime(2026, 10, 27, tzinfo=timezone.utc),
                                       source_url="https://example.org", crs="EPSG:4326", coverage="Global", scale_or_resolution="—", license="—",
                                       limitations=["Sin registros en la prueba."])

    async def susceptibility(self, geometry, representative):
        return self._empty("nasa-landslide-susceptibility")

    async def nowcast(self, geometry, representative):
        return self._empty("nasa-lhasa-nowcast")

    async def reports(self, geometry):
        return self._empty("nasa-coolr-reports")


class SteadyHourlyWind:
    """NASA POWER horario sintético: un ciclo diario de 3 a 11 m/s a 50 m (10 m = 80 %), igual todos los años, sin red."""

    def __init__(self, *args, **kwargs):
        pass

    async def wind(self, latitude, longitude, years):
        hours = np.arange(8760)
        high = 7.0 + 4.0 * np.sin(2 * np.pi * hours / 24)
        return HourlyWind(by_year={year: (high, high * 0.8) for year in years}, provenance=Provenance.CACHED,
                          downloaded_at=datetime(2026, 10, 30, tzinfo=timezone.utc), version="prueba")


class FixedWindAtlas:
    """Atlas Eólico Global sintético de costa: 10.0 m/s a 50 m y 11.0 m/s a 100 m en cualquier punto, sin red."""

    def __init__(self, *args, **kwargs):
        pass

    async def point(self, latitude, longitude):
        return AtlasPoint(speeds={50: 10.0, 100: 11.0}, urls=["https://example.org/gwa.tif"], provenance=Provenance.CACHED,
                          downloaded_at=datetime(2026, 10, 30, tzinfo=timezone.utc), limitations=[])


def seasonal_flow(day: date, mean: float = 30.0) -> float:
    """Caudal sintético: ciclo anual (máximo a mediados de febrero) y un vaivén sin tendencia entre años."""
    return mean + mean * 2 / 3 * math.cos(2 * math.pi * (day.timetuple().tm_yday - 45) / 365.25) + ((day.year * 7) % 5 - 2) * 0.2


class SeasonalGlofas:
    """GloFAS sintético: 30 m³/s de media con ciclo anual, igual todos los años, en la celda del punto. Sin red."""

    def __init__(self, *args, **kwargs):
        pass

    async def discharge(self, latitude, longitude, start, end):
        observations = [Observation(timestamp=start + timedelta(days=offset), value=seasonal_flow(start + timedelta(days=offset)))
                        for offset in range((end - start).days + 1)]
        cell = FlowCell(latitude=round(latitude, 3), longitude=round(longitude, 3), distance_km=1.2, moved=False, point_cell_mean=30.0,
                        used_cell_mean=30.0, neighborhood_max=31.0, scan_year=end.year - 1)
        return GlofasSeries(observations=observations, cell=cell, provenance=Provenance.CACHED, downloaded_at=datetime(2026, 11, 10, tzinfo=timezone.utc))


class NearbyGeoglows:
    """GEOGLOWS sintético: el mismo río con 10 % más de caudal medio y sin tendencia. Sin red."""

    def __init__(self, *args, **kwargs):
        pass

    async def river_near(self, latitude, longitude):
        annual = [Observation(timestamp=date(year, 7, 1), value=33.0 + ((year * 7) % 5 - 2) * 0.2) for year in range(1990, 2025)]
        return RiverChoice(river_id=670000001, nearest_river_id=670000001, candidates=1, annual=annual, nearest_mean=33.0,
                           provenance=Provenance.CACHED, downloaded_at=datetime(2026, 11, 10, tzinfo=timezone.utc))


@pytest.fixture(scope="session", autouse=True)
def offline_connectors():
    """Instala los dobles antes de cualquier fixture de módulo que construya sobres completos."""
    patch = pytest.MonkeyPatch()
    patch.setattr(rainfall_crosscheck, "ChirpsConnector", FlatChirps)
    patch.setattr(baseline, "NasaLandslidesConnector", EmptyLandslides)
    patch.setattr(era5_crosscheck, "PvgisConnector", FlatEra5)
    patch.setattr(extraction, "CopernicusDemConnector", FixedCopernicus)
    patch.setattr(cover_crosscheck, "WorldCoverConnector", DesertWorldCover)
    patch.setattr(wind, "PowerHourlyConnector", SteadyHourlyWind)
    patch.setattr(wind, "WindAtlasConnector", FixedWindAtlas)
    patch.setattr(hydro, "GlofasConnector", SeasonalGlofas)
    patch.setattr(hydro, "GeoglowsConnector", NearbyGeoglows)
    yield
    patch.undo()


@pytest.fixture(autouse=True)
def clear_background_tasks():
    """Evita que una descarga simulada de una prueba contamine la siguiente."""
    for pending in (rainfall_crosscheck._inflight, era5_crosscheck._inflight, hydro._inflight):
        pending.clear()
    yield
    for pending in (rainfall_crosscheck._inflight, era5_crosscheck._inflight, hydro._inflight):
        pending.clear()
