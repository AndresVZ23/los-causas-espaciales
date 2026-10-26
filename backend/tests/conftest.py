"""Aislamiento común: ninguna prueba sale a la red por CHIRPS (NASA SERVIR ClimateSERV)."""

from datetime import datetime, timedelta, timezone

import pytest

from backend.app.orchestration import rainfall_crosscheck
from backend.app.schemas.analysis import Observation, Provenance, SourceMetadata


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


@pytest.fixture(autouse=True)
def offline_chirps(monkeypatch):
    monkeypatch.setattr(rainfall_crosscheck, "ChirpsConnector", FlatChirps)
    rainfall_crosscheck._inflight.clear()
    yield
    rainfall_crosscheck._inflight.clear()
