"""Aislamiento común: ninguna prueba sale a la red por CHIRPS (NASA SERVIR ClimateSERV), por los deslizamientos de NASA,
por ERA5 (PVGIS), por Copernicus DEM ni por ESA WorldCover."""

from collections import Counter
from datetime import datetime, timedelta, timezone

import pytest

from backend.app.connectors.copernicus.dem import DemPoint
from backend.app.connectors.esa.worldcover import Composition
from backend.app.connectors.jrc.pvgis import Era5Annual
from backend.app.orchestration import cover_crosscheck, era5_crosscheck, extraction, rainfall_crosscheck
from backend.app.schemas.analysis import Observation, Provenance, SourceMetadata
from backend.app.schemas.data_sources import TerritorialSourceResult
from backend.app.sectors import baseline


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


@pytest.fixture(scope="session", autouse=True)
def offline_connectors():
    """Instala los dobles antes de cualquier fixture de módulo que construya sobres completos."""
    patch = pytest.MonkeyPatch()
    patch.setattr(rainfall_crosscheck, "ChirpsConnector", FlatChirps)
    patch.setattr(baseline, "NasaLandslidesConnector", EmptyLandslides)
    patch.setattr(era5_crosscheck, "PvgisConnector", FlatEra5)
    patch.setattr(extraction, "CopernicusDemConnector", FixedCopernicus)
    patch.setattr(cover_crosscheck, "WorldCoverConnector", DesertWorldCover)
    yield
    patch.undo()


@pytest.fixture(autouse=True)
def clear_background_tasks():
    """Evita que una descarga simulada de una prueba contamine la siguiente."""
    rainfall_crosscheck._inflight.clear()
    era5_crosscheck._inflight.clear()
    yield
    rainfall_crosscheck._inflight.clear()
    era5_crosscheck._inflight.clear()
