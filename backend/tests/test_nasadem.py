import asyncio
import io
import time
import zipfile
from datetime import datetime, timezone

import httpx
import pytest

from backend.app.connectors.nasa import nasadem
from backend.app.connectors.nasa.nasadem import (
    NasademConnector,
    NasademConnectorError,
    grid_index,
    read_metrics,
    tile_origin,
)
from backend.app.schemas.analysis import Point, Provenance
from backend.app.schemas.terrain import TerrainGranule, TerrainMetrics


@pytest.fixture(autouse=True)
def reset_nasadem_runtime_state():
    NasademConnector._download_locks.clear()
    NasademConnector._inflight_downloads.clear()
    NasademConnector._access_failures.clear()
    yield
    NasademConnector._download_locks.clear()
    NasademConnector._inflight_downloads.clear()
    NasademConnector._access_failures.clear()


def _granule(product: str) -> TerrainGranule:
    tile_id = "s18w071"
    return TerrainGranule(
        short_name=product,
        granule_id=f"G-{product}",
        title=f"{product}_{tile_id}",
        tile_id=tile_id,
        bounding_box=(-71.0001389, -18.0001389, -69.9998611, -16.9998611),
        updated_at=datetime(2018, 9, 12, tzinfo=timezone.utc),
        data_url=f"https://data.lpdaac.earthdatacloud.nasa.gov/lp-prod-protected/{product}.001/{product}_{tile_id}.zip",
        preview_url=f"https://data.lpdaac.earthdatacloud.nasa.gov/lp-prod-public/{product}.001/{product}_{tile_id}.1.jpg",
        doi_url=f"https://doi.org/{product}",
        catalogue_url="https://search.earthdata.nasa.gov/",
    )


def _zip_payload() -> bytes:
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as archive:
        archive.writestr("tile.bin", b"nasadem-test-payload")
    return output.getvalue()


def test_tile_origin_and_grid_index_use_lon_lat_in_wgs84():
    assert tile_origin("s18w071") == (-18, -71)
    row, column = grid_index("s18w071", -17.193, -70.934)
    assert row == 695
    assert column == 238


def test_download_rejects_non_lp_daac_host_before_sending_token(monkeypatch, tmp_path):
    connector = NasademConnector()
    connector.cache_dir = tmp_path
    monkeypatch.setattr(connector.settings, "earthdata_token", "secret-test-token")
    granule = _granule("NASADEM_HGT").model_copy(update={"data_url": "https://example.test/steal.zip"})

    with pytest.raises(NasademConnectorError, match="host LP DAAC"):
        asyncio.run(connector._download(granule))


def test_read_metrics_applies_documented_units(monkeypatch, tmp_path):
    hgt = tmp_path / "hgt.zip"
    sc = tmp_path / "sc.zip"
    with zipfile.ZipFile(hgt, "w") as archive:
        archive.writestr("tile.hgt", b"00")
    with zipfile.ZipFile(sc, "w") as archive:
        archive.writestr("tile.slope", b"00")
        archive.writestr("tile.aspect", b"00")

    def fake_read(_archive, member, *_args, **_kwargs):
        if member.endswith(".hgt"):
            return 1842
        if member.endswith(".slope"):
            return 1275
        return 22500

    monkeypatch.setattr(nasadem, "_read_cell", fake_read)
    result = read_metrics(hgt, sc, "s18w071", Point(label="Moquegua", latitude=-17.193, longitude=-70.934))
    assert result.elevation_m == 1842
    assert result.slope_degrees == 12.75
    assert result.aspect_degrees == 225
    assert result.aspect_cardinal == "SO"
    assert result.vertical_datum == "EGM96 geoid"


def test_missing_earthdata_token_keeps_official_metadata_without_fake_metrics(monkeypatch, tmp_path):
    connector = NasademConnector()
    connector.cache_dir = tmp_path
    connector.settings.earthdata_token = None

    async def fake_granule(product, _point):
        return _granule(product), Provenance.REAL

    monkeypatch.setattr(connector, "_granule", fake_granule)
    result = asyncio.run(connector.point(Point(label="Moquegua", latitude=-17.193, longitude=-70.934)))

    assert result.status == "METADATA_ONLY"
    assert result.provenance == Provenance.UNAVAILABLE
    assert result.metrics.elevation_m is None
    assert result.metrics.slope_degrees is None
    assert result.metrics.aspect_degrees is None
    assert len(result.granules) == 2
    assert any("EARTHDATA_TOKEN" in limitation for limitation in result.limitations)


def test_cold_download_writes_valid_zip_then_renames_atomically(monkeypatch, tmp_path):
    payload = _zip_payload()
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, content=payload)

    connector = NasademConnector(transport=httpx.MockTransport(handler))
    connector.cache_dir = tmp_path
    monkeypatch.setattr(connector.settings, "earthdata_token", "test-token")
    granule = _granule("NASADEM_HGT")

    target, provenance = asyncio.run(connector._download(granule))

    assert provenance == Provenance.REAL
    assert target.read_bytes() == payload
    assert zipfile.is_zipfile(target)
    assert not target.with_suffix(".zip.part").exists()
    assert len(requests) == 1
    assert "Range" not in requests[0].headers


def test_partial_download_resumes_with_http_range(monkeypatch, tmp_path):
    payload = _zip_payload()
    prefix = payload[: len(payload) // 2]
    seen_range: list[str | None] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen_range.append(request.headers.get("Range"))
        return httpx.Response(
            206,
            headers={"Content-Range": f"bytes {len(prefix)}-{len(payload) - 1}/{len(payload)}"},
            content=payload[len(prefix) :],
        )

    connector = NasademConnector(transport=httpx.MockTransport(handler))
    connector.cache_dir = tmp_path
    monkeypatch.setattr(connector.settings, "earthdata_token", "test-token")
    granule = _granule("NASADEM_HGT")
    connector._target(granule).with_suffix(".zip.part").write_bytes(prefix)

    target, provenance = asyncio.run(connector._download(granule))

    assert provenance == Provenance.REAL
    assert target.read_bytes() == payload
    assert seen_range == [f"bytes={len(prefix)}-"]


def test_cancelled_download_keeps_partial_file_for_next_request(monkeypatch, tmp_path):
    connector = NasademConnector()
    connector.cache_dir = tmp_path
    monkeypatch.setattr(connector.settings, "earthdata_token", "test-token")
    granule = _granule("NASADEM_HGT")
    partial = connector._target(granule).with_suffix(".zip.part")

    async def interrupted(_granule, temporary):
        temporary.write_bytes(b"partial-nasadem")
        raise asyncio.CancelledError

    monkeypatch.setattr(connector, "_stream_to_partial", interrupted)

    with pytest.raises(asyncio.CancelledError):
        asyncio.run(connector._download(granule))

    assert partial.read_bytes() == b"partial-nasadem"


def test_transient_download_failure_retries_then_completes(monkeypatch, tmp_path):
    payload = _zip_payload()
    request_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal request_count
        request_count += 1
        if request_count == 1:
            return httpx.Response(503, request=request)
        return httpx.Response(200, content=payload, request=request)

    connector = NasademConnector(transport=httpx.MockTransport(handler))
    connector.cache_dir = tmp_path
    monkeypatch.setattr(connector.settings, "earthdata_token", "test-token")

    target, provenance = asyncio.run(connector._download(_granule("NASADEM_HGT")))

    assert provenance == Provenance.REAL
    assert zipfile.is_zipfile(target)
    assert request_count == 2


def test_hot_cache_never_opens_network(monkeypatch, tmp_path):
    def unexpected_request(_request: httpx.Request) -> httpx.Response:
        raise AssertionError("La caché caliente no debe abrir una solicitud HTTP.")

    connector = NasademConnector(transport=httpx.MockTransport(unexpected_request))
    connector.cache_dir = tmp_path
    monkeypatch.setattr(connector.settings, "earthdata_token", "test-token")
    granule = _granule("NASADEM_HGT")
    target = connector._target(granule)
    target.write_bytes(_zip_payload())

    returned, provenance = asyncio.run(connector._download(granule))

    assert returned == target
    assert provenance == Provenance.CACHED


def test_concurrent_downloads_share_one_tile_lock(monkeypatch, tmp_path):
    payload = _zip_payload()
    request_count = 0

    def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal request_count
        request_count += 1
        return httpx.Response(200, content=payload)

    connector = NasademConnector(transport=httpx.MockTransport(handler))
    connector.cache_dir = tmp_path
    monkeypatch.setattr(connector.settings, "earthdata_token", "test-token")
    granule = _granule("NASADEM_HGT")

    async def run_concurrently():
        return await asyncio.gather(connector._download(granule), connector._download(granule))

    results = asyncio.run(run_concurrently())

    assert request_count == 1
    assert [result[1] for result in results] == [Provenance.REAL, Provenance.CACHED]


def test_points_returns_pending_without_waiting_for_background_download(monkeypatch, tmp_path):
    connector = NasademConnector()
    connector.cache_dir = tmp_path
    monkeypatch.setattr(connector.settings, "earthdata_token", "test-token")
    started = asyncio.Event()
    release = asyncio.Event()

    async def fake_granule(product, _point):
        return _granule(product), Provenance.REAL

    async def slow_download(granule):
        started.set()
        await release.wait()
        return connector._target(granule), Provenance.REAL

    monkeypatch.setattr(connector, "_granule", fake_granule)
    monkeypatch.setattr(connector, "_download", slow_download)

    async def scenario():
        before = time.perf_counter()
        response = await connector.points([Point(label="Moquegua", latitude=-17.193, longitude=-70.934)])
        elapsed = time.perf_counter() - before
        await asyncio.wait_for(started.wait(), timeout=0.5)
        tasks = list(NasademConnector._inflight_downloads.values())
        release.set()
        await asyncio.gather(*tasks)
        return response, elapsed

    response, elapsed = asyncio.run(scenario())

    assert elapsed < 0.5
    assert response.sites[0].status == "PENDING"
    assert response.sites[0].provenance == Provenance.UNAVAILABLE
    assert any("segundo plano" in limitation for limitation in response.sites[0].limitations)


@pytest.mark.parametrize(
    ("status_code", "expected_guidance"),
    [(401, "renueve el token"), (403, "aplicación LP DAAC")],
)
def test_access_denied_changes_followup_status_to_metadata_only(
    monkeypatch,
    tmp_path,
    status_code,
    expected_guidance,
):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code, request=request)

    connector = NasademConnector(transport=httpx.MockTransport(handler))
    connector.cache_dir = tmp_path
    monkeypatch.setattr(connector.settings, "earthdata_token", "rejected-token")

    async def fake_granule(product, _point):
        return _granule(product), Provenance.REAL

    monkeypatch.setattr(connector, "_granule", fake_granule)
    point = Point(label="Piloto", latitude=-17.193, longitude=-70.934)

    async def scenario():
        first = await connector.points([point])
        tasks = list(NasademConnector._inflight_downloads.values())
        await asyncio.gather(*tasks, return_exceptions=True)
        await asyncio.sleep(0)
        second = await connector.points([point])
        return first, second

    first, second = asyncio.run(scenario())

    assert first.sites[0].status == "PENDING"
    assert second.sites[0].status == "METADATA_ONLY"
    assert any(f"HTTP {status_code}" in limitation for limitation in second.sites[0].limitations)
    assert any(expected_guidance in limitation for limitation in second.sites[0].limitations)


def test_prefetch_starts_downloads_without_waiting_for_completion(monkeypatch, tmp_path):
    connector = NasademConnector()
    connector.cache_dir = tmp_path
    monkeypatch.setattr(connector.settings, "earthdata_token", "test-token")
    started = asyncio.Event()
    release = asyncio.Event()

    async def fake_granule(product, _point):
        return _granule(product), Provenance.REAL

    async def slow_download(granule):
        started.set()
        await release.wait()
        return connector._target(granule), Provenance.REAL

    monkeypatch.setattr(connector, "_granule", fake_granule)
    monkeypatch.setattr(connector, "_download", slow_download)

    async def scenario():
        before = time.perf_counter()
        await connector.prefetch([Point(label="Piloto K2", latitude=-17.5, longitude=-70.5)])
        elapsed = time.perf_counter() - before
        await asyncio.wait_for(started.wait(), timeout=0.5)
        tasks = list(NasademConnector._inflight_downloads.values())
        release.set()
        await asyncio.gather(*tasks)
        return elapsed

    assert asyncio.run(scenario()) < 0.5


def test_cached_points_remain_ready_in_under_one_second(monkeypatch, tmp_path):
    connector = NasademConnector()
    connector.cache_dir = tmp_path
    monkeypatch.setattr(connector.settings, "earthdata_token", "test-token")
    for product in nasadem.PRODUCTS:
        connector._target(_granule(product)).write_bytes(_zip_payload())

    async def fake_granule(product, _point):
        return _granule(product), Provenance.CACHED

    monkeypatch.setattr(connector, "_granule", fake_granule)
    monkeypatch.setattr(
        nasadem,
        "read_metrics",
        lambda *_args: TerrainMetrics(elevation_m=1420, slope_degrees=5.47, aspect_degrees=315.1, aspect_cardinal="NO"),
    )

    async def scenario():
        before = time.perf_counter()
        response = await connector.points(
            [
                Point(label="Moquegua", latitude=-17.193, longitude=-70.934),
                Point(label="Arequipa", latitude=-16.409, longitude=-71.537),
            ]
        )
        return response, time.perf_counter() - before

    response, elapsed = asyncio.run(scenario())

    assert elapsed < 1
    assert [site.status for site in response.sites] == ["READY", "READY"]
    assert all(site.provenance == Provenance.CACHED for site in response.sites)
