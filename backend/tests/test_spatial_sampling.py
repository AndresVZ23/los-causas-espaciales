from datetime import date, datetime, timezone

import httpx
import pytest

from backend.app.connectors.nasa.power_regional import RegionalPowerConnector, RegionalPowerError
from backend.app.core.config import Settings
from backend.app.schemas.analysis import Observation, Provenance, SourceMetadata
from backend.app.schemas.spatial_sampling import SpatialSamplingRequest


def _feature(longitude, latitude, first, second=20):
    return {
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [longitude, latitude, 100]},
        "properties": {"parameter": {"T2M": {"20250101": first, "20250102": second}}},
    }


def _payload(features):
    return {
        "type": "FeatureCollection",
        "features": features,
        "header": {"api": {"version": "v2.10.1"}, "time_standard": "UTC"},
        "parameters": {"T2M": {"units": "C"}},
        "messages": [],
    }


def _polygon_request():
    return SpatialSamplingRequest(
        subject={
            "type": "Feature",
            "properties": {"kind": "territory", "name": "Área de prueba", "origin": "COD-AB"},
            "geometry": {
                "type": "Polygon",
                "coordinates": [[[-71.25, -17.75], [-70.25, -17.75], [-70.25, -16.75], [-71.25, -16.75], [-71.25, -17.75]]],
            },
        },
        variable="T2M",
        start_date=date(2025, 1, 1),
        end_date=date(2025, 1, 2),
    )


@pytest.mark.asyncio
async def test_regional_sampling_deduplicates_cells_weights_by_area_and_keeps_cell_series(tmp_path):
    calls = 0
    features = [
        _feature(-71.0, -17.5, 10),
        _feature(-70.5, -17.5, 20),
        _feature(-71.0, -17.0, 30, -999),
        _feature(-70.5, -17.0, 40),
        _feature(-71.0, -17.5, 10),  # exact provider duplicate must not duplicate the cell
    ]

    def handler(request: httpx.Request):
        nonlocal calls
        calls += 1
        assert request.url.path.endswith("/api/temporal/daily/regional")
        assert request.url.params["parameters"] == "T2M"
        assert "," not in request.url.params["parameters"]
        assert request.url.params["time-standard"] == "UTC"
        assert float(request.url.params["latitude-max"]) - float(request.url.params["latitude-min"]) >= 2
        assert float(request.url.params["longitude-max"]) - float(request.url.params["longitude-min"]) >= 2
        return httpx.Response(200, json=_payload(features))

    connector = RegionalPowerConnector(
        settings=Settings(_env_file=None, cache_dir=tmp_path),
        transport=httpx.MockTransport(handler),
    )
    first = await connector.sample(_polygon_request())
    second = await connector.sample(_polygon_request())

    assert calls == 1
    assert first.mode == "REGIONAL"
    assert second.source.provenance == Provenance.CACHED
    assert len(first.cells) == 4
    assert sum(cell.weight for cell in first.cells) == pytest.approx(1)
    assert first.grid_spacing_degrees == (0.5, 0.5)
    assert first.spatial_coverage_percent > 99.9
    expected = sum(cell.observations[0].value * cell.weight for cell in first.cells)
    assert first.aggregate[0].value == pytest.approx(expected)
    assert first.aggregate[0].dispersion_stddev > 0
    assert first.aggregate[0].contributing_cells == 4
    assert first.aggregate[1].contributing_cells == 3
    assert first.source.dataset == "NASA POWER Daily Regional"


class _FakePointConnector:
    async def daily_point(self, latitude, longitude, variable, start, end):
        assert -18 < latitude < -17
        assert -71 < longitude < -70
        observations = [Observation(timestamp=start, value=17.5), Observation(timestamp=end, value=18.5)]
        source = SourceMetadata(
            source_id="nasa-power",
            dataset="NASA POWER Daily Point",
            version="test",
            variable=variable,
            unit="C",
            temporal_resolution="daily UTC",
            spatial_resolution="native grid",
            downloaded_at=datetime.now(timezone.utc),
            source_url="https://power.larc.nasa.gov/api/temporal/daily/point",
            provenance=Provenance.REAL,
        )
        return observations, source


@pytest.mark.asyncio
async def test_polygon_smaller_than_nominal_cell_is_explicit_point_mode(tmp_path):
    def unexpected_network(_request):
        raise AssertionError("small polygon must use the point endpoint abstraction")

    request = SpatialSamplingRequest(
        subject={
            "type": "Feature",
            "properties": {"level": "district", "name": "Distrito pequeño", "pcode": "PE180101"},
            "geometry": {
                "type": "Polygon",
                "coordinates": [[[-70.95, -17.25], [-70.85, -17.25], [-70.85, -17.15], [-70.95, -17.15], [-70.95, -17.25]]],
            },
        },
        variable="T2M",
        start_date=date(2025, 1, 1),
        end_date=date(2025, 1, 2),
    )
    result = await RegionalPowerConnector(
        settings=Settings(_env_file=None, cache_dir=tmp_path),
        transport=httpx.MockTransport(unexpected_network),
        point_connector=_FakePointConnector(),
    ).sample(request)
    assert result.mode == "POINT"
    assert result.subject.kind == "district"
    assert result.subject.origin == "COD-AB"
    assert "menor que una celda" in result.method
    assert result.aggregate[0].dispersion_stddev == 0


@pytest.mark.asyncio
async def test_corridor_feature_keeps_kind_name_origin_and_uses_buffered_regional_sampling(tmp_path):
    features = [
        _feature(longitude, latitude, 10 + row + column)
        for row, latitude in enumerate([-18, -17.5, -17, -16.5, -16])
        for column, longitude in enumerate([-71.5, -71, -70.5, -70, -69.5])
    ]

    def handler(_request: httpx.Request):
        return httpx.Response(200, json=_payload(features))

    request = SpatialSamplingRequest(
        subject={
            "type": "Feature",
            "properties": {"kind": "corridor", "name": "Moquegua–Ilo", "origin": "drawn"},
            "geometry": {"type": "LineString", "coordinates": [[-71.5, -17.8], [-69.5, -16.2]]},
        },
        variable="T2M",
        start_date=date(2025, 1, 1),
        end_date=date(2025, 1, 2),
        corridor_buffer_km=2,
    )
    result = await RegionalPowerConnector(
        settings=Settings(_env_file=None, cache_dir=tmp_path),
        transport=httpx.MockTransport(handler),
    ).sample(request)
    assert result.mode == "REGIONAL"
    assert result.subject.kind == "corridor"
    assert result.subject.name == "Moquegua–Ilo"
    assert result.subject.origin == "drawn"
    assert result.subject.corridor_buffer_km == 2
    assert result.cells


@pytest.mark.asyncio
async def test_invalid_geojson_is_rejected_before_network(tmp_path):
    request = SpatialSamplingRequest(
        subject={"type": "Polygon", "coordinates": [[[0, 0], [1, 1], [1, 0], [0, 1], [0, 0]]]},
        variable="T2M",
        start_date=date(2025, 1, 1),
        end_date=date(2025, 1, 2),
    )
    connector = RegionalPowerConnector(settings=Settings(_env_file=None, cache_dir=tmp_path))
    with pytest.raises(RegionalPowerError, match="inválida"):
        await connector.sample(request)


@pytest.mark.asyncio
async def test_external_regional_error_is_not_replaced_with_fiction(tmp_path):
    def handler(_request: httpx.Request):
        return httpx.Response(503, json={"message": "temporarily unavailable"})

    connector = RegionalPowerConnector(
        settings=Settings(_env_file=None, cache_dir=tmp_path),
        transport=httpx.MockTransport(handler),
    )
    with pytest.raises(RegionalPowerError, match="falló"):
        await connector.sample(_polygon_request())


@pytest.mark.asyncio
async def test_region_larger_than_ten_degrees_is_rejected_before_network(tmp_path):
    request = SpatialSamplingRequest(
        subject={
            "type": "Polygon",
            "coordinates": [[[-80, -20], [-65, -20], [-65, -5], [-80, -5], [-80, -20]]],
        },
        variable="T2M",
        start_date=date(2025, 1, 1),
        end_date=date(2025, 1, 2),
    )
    connector = RegionalPowerConnector(settings=Settings(_env_file=None, cache_dir=tmp_path))
    with pytest.raises(RegionalPowerError, match="supera 10"):
        await connector.sample(request)
