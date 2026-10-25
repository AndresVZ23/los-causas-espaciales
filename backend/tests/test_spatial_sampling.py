from datetime import date, datetime, timedelta, timezone

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
    second_values = [
        (cell.observations[1].value, cell.weight)
        for cell in first.cells
        if len(cell.observations) > 1
    ]
    expected_second = sum(value * weight for value, weight in second_values) / sum(
        weight for _, weight in second_values
    )
    assert first.aggregate[1].value == pytest.approx(expected_second)
    assert first.source.dataset == "NASA POWER Daily Regional"


@pytest.mark.asyncio
async def test_regional_sampling_splits_multi_year_period_into_calendar_year_requests(tmp_path):
    requested_periods: list[tuple[date, date]] = []

    def handler(request: httpx.Request):
        raw_start = request.url.params["start"]
        raw_end = request.url.params["end"]
        start = date(int(raw_start[:4]), int(raw_start[4:6]), int(raw_start[6:8]))
        end = date(int(raw_end[:4]), int(raw_end[4:6]), int(raw_end[6:8]))
        requested_periods.append((start, end))
        assert (end - start).days + 1 <= 366
        stamp = start.strftime("%Y%m%d")
        features = [
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [longitude, latitude, 100]},
                "properties": {"parameter": {"T2M": {stamp: 10 + row + column}}},
            }
            for row, latitude in enumerate([-17.5, -17.0])
            for column, longitude in enumerate([-71.0, -70.5])
        ]
        return httpx.Response(200, json=_payload(features))

    request = _polygon_request().model_copy(update={
        "start_date": date(2023, 7, 1),
        "end_date": date(2025, 2, 1),
    })
    connector = RegionalPowerConnector(
        settings=Settings(_env_file=None, cache_dir=tmp_path),
        transport=httpx.MockTransport(handler),
    )

    first = await connector.sample(request)
    second = await connector.sample(request)

    assert requested_periods == [
        (date(2023, 7, 1), date(2023, 12, 31)),
        (date(2024, 1, 1), date(2024, 12, 31)),
        (date(2025, 1, 1), date(2025, 2, 1)),
    ]
    assert [item.timestamp for item in first.aggregate] == [
        date(2023, 7, 1),
        date(2024, 1, 1),
        date(2025, 1, 1),
    ]
    assert all(len(cell.observations) == 3 for cell in first.cells)
    assert first.source.provenance == Provenance.REAL
    assert second.source.provenance == Provenance.CACHED
    assert "3 solicitud(es)" in second.source.quality_notes[-1]

    extended = await connector.sample(request.model_copy(update={"end_date": date(2025, 3, 1)}))
    assert requested_periods[-1] == (date(2025, 1, 1), date(2025, 3, 1))
    assert len(requested_periods) == 4
    assert extended.source.provenance == Provenance.REAL
    assert "1 nueva(s) y 2 en caché" in extended.source.quality_notes[-1]


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


def _precipitation_payload(multiplier_by_longitude: dict[float, float]):
    features = []
    for longitude, multiplier in multiplier_by_longitude.items():
        for latitude in (-17.5, -17.0):
            features.append({
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [longitude, latitude, 100]},
                "properties": {"parameter": {"PRECTOTCORR": {
                    "20260101": 1 * multiplier,
                    "20260102": 2 * multiplier,
                    "20260103": 3 * multiplier,
                }}},
            })
    return {
        "type": "FeatureCollection",
        "features": features,
        "header": {"api": {"version": "v2.10.1"}, "time_standard": "UTC"},
        "parameters": {"PRECTOTCORR": {"units": "mm/day"}},
        "messages": [],
    }


@pytest.mark.asyncio
async def test_recent_regional_precipitation_is_verified_per_cell_before_aggregation(tmp_path):
    cutoff = date.today() - timedelta(days=60)

    def handler(request: httpx.Request):
        end = date.fromisoformat(
            f"{request.url.params['end'][:4]}-{request.url.params['end'][4:6]}-{request.url.params['end'][6:]}"
        )
        multipliers = {-71.0: 24.0, -70.5: 1.0} if end > cutoff else {-71.0: 1.0, -70.5: 1.0}
        return httpx.Response(200, json=_precipitation_payload(multipliers))

    request = _polygon_request().model_copy(update={
        "variable": "PRECTOTCORR",
        "start_date": date(date.today().year, 1, 1),
        "end_date": date.today(),
    })
    result = await RegionalPowerConnector(
        settings=Settings(_env_file=None, cache_dir=tmp_path),
        transport=httpx.MockTransport(handler),
    ).sample(request)

    assert {cell.observations[0].value for cell in result.cells} == {1.0}
    assert result.aggregate[0].value == pytest.approx(1.0)
    assert any("2 corregida(s) ÷24, 2 verificada(s) ×1" in note for note in result.source.quality_notes)


@pytest.mark.asyncio
async def test_recent_regional_precipitation_rejects_unknown_scale(tmp_path):
    cutoff = date.today() - timedelta(days=60)

    def handler(request: httpx.Request):
        end = date.fromisoformat(
            f"{request.url.params['end'][:4]}-{request.url.params['end'][4:6]}-{request.url.params['end'][6:]}"
        )
        multiplier = 3.0 if end > cutoff else 1.0
        return httpx.Response(200, json=_precipitation_payload({-71.0: multiplier, -70.5: multiplier}))

    request = _polygon_request().model_copy(update={
        "variable": "PRECTOTCORR",
        "start_date": date(date.today().year, 1, 1),
        "end_date": date.today(),
    })
    connector = RegionalPowerConnector(
        settings=Settings(_env_file=None, cache_dir=tmp_path),
        transport=httpx.MockTransport(handler),
    )
    with pytest.raises(RegionalPowerError, match="razón 3.00"):
        await connector.sample(request)


class _ScaledPrecipitationPointConnector:
    async def daily_point(self, latitude, longitude, variable, start, end):
        multiplier = 24 if end > date.today() - timedelta(days=60) else 1
        observations = [
            Observation(timestamp=date(date.today().year, 1, day), value=float(day * multiplier))
            for day in (1, 2, 3)
        ]
        return observations, SourceMetadata(
            source_id="nasa-power", dataset="NASA POWER Daily Point", version="test",
            variable=variable, unit="mm/day", temporal_resolution="daily UTC",
            spatial_resolution="native grid", downloaded_at=datetime.now(timezone.utc),
            source_url="https://power.larc.nasa.gov/api/temporal/daily/point", provenance=Provenance.REAL,
        )


@pytest.mark.asyncio
async def test_recent_point_mode_precipitation_applies_same_scale_guard(tmp_path):
    request = SpatialSamplingRequest(
        subject={"type": "Point", "coordinates": [-70.934, -17.193]},
        variable="PRECTOTCORR", start_date=date(date.today().year, 1, 1), end_date=date.today(),
    )
    result = await RegionalPowerConnector(
        settings=Settings(_env_file=None, cache_dir=tmp_path),
        point_connector=_ScaledPrecipitationPointConnector(),
    ).sample(request)
    assert [item.value for item in result.aggregate] == [1.0, 2.0, 3.0]
    assert any("se dividió por 24" in note for note in result.source.quality_notes)
