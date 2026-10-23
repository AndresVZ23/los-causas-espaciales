import json
import hashlib
from datetime import date

import httpx
import pytest

from backend.app.connectors.nasa.appeears import AppEEARSConnector, AppEEARSConnectorError
from backend.app.core.config import Settings
from backend.app.schemas.analysis import Point, Provenance
from backend.app.schemas.data_sources import AppEEARSAreaTaskRequest, AppEEARSPointTaskRequest


@pytest.mark.asyncio
async def test_point_task_logs_in_submits_pending_logs_out_and_never_caches_token(tmp_path):
    calls = []

    def handler(request: httpx.Request):
        calls.append((request.method, request.url.path))
        if request.url.path.endswith("/login"):
            assert request.headers["authorization"].startswith("Basic ")
            return httpx.Response(200, json={"token": "super-secret-token", "expiration": "2099-01-01T00:00:00Z"})
        if request.url.path.endswith("/task"):
            assert request.headers["authorization"] == "Bearer super-secret-token"
            payload = json.loads(request.content)
            assert payload["task_type"] == "point"
            assert {item["product"] for item in payload["params"]["layers"]} == {"MOD13Q1.061", "MOD44W.061"}
            return httpx.Response(202, json={"task_id": "12345678-1234-1234-1234-123456789abc", "status": "pending"})
        if request.url.path.endswith("/logout"):
            return httpx.Response(204)
        raise AssertionError(request.url)

    settings = Settings(_env_file=None, cache_dir=tmp_path, earthdata_username="user", earthdata_password="password")
    connector = AppEEARSConnector(settings=settings, transport=httpx.MockTransport(handler))
    result = await connector.submit_points(AppEEARSPointTaskRequest(
        task_name="moquegua-vegetation",
        start_date=date(2024, 1, 1), end_date=date(2024, 1, 16),
        points=[Point(label="Moquegua", latitude=-17.193, longitude=-70.934)],
    ))
    assert result.status == "PENDING"
    assert result.provenance == Provenance.REAL
    assert calls == [("POST", "/api/login"), ("POST", "/api/task"), ("POST", "/api/logout")]
    cached = b"".join(path.read_bytes() for path in tmp_path.rglob("*.json"))
    assert b"super-secret-token" not in cached
    assert b"password" not in cached


@pytest.mark.asyncio
async def test_expired_token_is_renewed_once_and_revoked(tmp_path):
    logins = 0
    task_attempts = 0

    def handler(request: httpx.Request):
        nonlocal logins, task_attempts
        if request.url.path.endswith("/login"):
            logins += 1
            return httpx.Response(200, json={"token": f"token-{logins}", "expiration": "2099-01-01T00:00:00Z"})
        if request.url.path.endswith("/task"):
            task_attempts += 1
            if task_attempts == 1:
                return httpx.Response(403, json={"message": "expired"})
            assert request.headers["authorization"] == "Bearer token-2"
            return httpx.Response(202, json={"task_id": "12345678-1234-1234-1234-123456789abc", "status": "pending"})
        if request.url.path.endswith("/logout"):
            return httpx.Response(204)
        raise AssertionError(request.url)

    settings = Settings(_env_file=None, cache_dir=tmp_path, earthdata_username="user", earthdata_password="password")
    connector = AppEEARSConnector(settings=settings, transport=httpx.MockTransport(handler))
    await connector.submit_points(AppEEARSPointTaskRequest(
        task_name="renew-token", start_date=date(2024, 1, 1), end_date=date(2024, 1, 2),
        points=[Point(latitude=-17.193, longitude=-70.934)],
    ))
    assert logins == 2
    assert task_attempts == 2


@pytest.mark.asyncio
async def test_missing_credentials_returns_honest_unavailable(tmp_path):
    settings = Settings(_env_file=None, cache_dir=tmp_path, earthdata_username=None, earthdata_password=None)
    connector = AppEEARSConnector(settings=settings)
    result = await connector.submit_points(AppEEARSPointTaskRequest(
        task_name="no-secrets", start_date=date(2024, 1, 1), end_date=date(2024, 1, 2),
        points=[Point(latitude=-17.193, longitude=-70.934)],
    ))
    assert result.status == "DATA_UNAVAILABLE"
    assert result.provenance == Provenance.UNAVAILABLE


@pytest.mark.asyncio
async def test_area_task_rejects_non_polygon_before_network(tmp_path):
    settings = Settings(_env_file=None, cache_dir=tmp_path, earthdata_username="user", earthdata_password="password")
    connector = AppEEARSConnector(settings=settings)
    with pytest.raises(AppEEARSConnectorError, match="Polygon"):
        await connector.submit_area(AppEEARSAreaTaskRequest(
            task_name="not-an-area", start_date=date(2024, 1, 1), end_date=date(2024, 1, 2),
            geometry={"type": "Point", "coordinates": [-70.934, -17.193]},
        ))


@pytest.mark.asyncio
async def test_area_task_submits_valid_geojson_as_asynchronous_geographic_job(tmp_path):
    def handler(request: httpx.Request):
        if request.url.path.endswith("/login"):
            return httpx.Response(200, json={"token": "secret", "expiration": "2099-01-01T00:00:00Z"})
        if request.url.path.endswith("/task"):
            payload = json.loads(request.content)
            assert payload["task_type"] == "area"
            assert payload["params"]["geo"]["features"][0]["geometry"]["type"] == "Polygon"
            assert payload["params"]["output"]["projection"] == "geographic"
            assert {item["product"] for item in payload["params"]["layers"]} == {"MOD13Q1.061", "MOD44W.061"}
            return httpx.Response(202, json={"task_id": "12345678-1234-1234-1234-123456789abc", "status": "pending"})
        if request.url.path.endswith("/logout"):
            return httpx.Response(204)
        raise AssertionError(request.url)

    settings = Settings(_env_file=None, cache_dir=tmp_path, earthdata_username="user", earthdata_password="password")
    connector = AppEEARSConnector(settings=settings, transport=httpx.MockTransport(handler))
    result = await connector.submit_area(AppEEARSAreaTaskRequest(
        task_name="moquegua-area",
        start_date=date(2024, 1, 1),
        end_date=date(2024, 1, 16),
        geometry={"type": "Polygon", "coordinates": [[
            [-70.95, -17.21], [-70.91, -17.21], [-70.91, -17.17], [-70.95, -17.21],
        ]]},
    ))
    assert result.status == "PENDING"
    assert result.task_type == "area"


@pytest.mark.asyncio
async def test_bundle_lists_official_checksums_without_account_identifier(tmp_path):
    def handler(request: httpx.Request):
        if request.url.path.endswith("/login"):
            return httpx.Response(200, json={"token": "secret", "expiration": "2099-01-01T00:00:00Z"})
        if "/bundle/" in request.url.path:
            return httpx.Response(200, json={
                "task_id": "12345678-1234-1234-1234-123456789abc",
                "user_id": "private@example.test",
                "files": [{"file_id": "file-1", "file_name": "results.csv", "file_size": 10,
                           "file_type": "csv", "sha256": "a" * 64}],
            })
        if request.url.path.endswith("/logout"):
            return httpx.Response(204)
        raise AssertionError(request.url)

    settings = Settings(_env_file=None, cache_dir=tmp_path, earthdata_username="user", earthdata_password="password")
    connector = AppEEARSConnector(settings=settings, transport=httpx.MockTransport(handler))
    result = await connector.bundle("12345678-1234-1234-1234-123456789abc")
    assert result.files[0].sha256 == "a" * 64
    cached = b"".join(path.read_bytes() for path in tmp_path.rglob("*.json"))
    assert b"private@example.test" not in cached
    assert b"secret" not in cached


@pytest.mark.asyncio
async def test_file_download_checks_sha_and_does_not_forward_token_to_object_storage(tmp_path):
    content = b"date,NDVI\n2024-01-01,0.2\n"
    digest = hashlib.sha256(content).hexdigest()
    file_id = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
    task_id = "12345678-1234-1234-1234-123456789abc"
    object_downloads = 0

    def handler(request: httpx.Request):
        nonlocal object_downloads
        if request.url.path.endswith("/login"):
            return httpx.Response(200, json={"token": "secret", "expiration": "2099-01-01T00:00:00Z"})
        if request.url.path == f"/api/bundle/{task_id}":
            return httpx.Response(200, json={"task_id": task_id, "files": [{
                "file_id": file_id, "file_name": "results.csv", "file_size": len(content),
                "file_type": "csv", "sha256": digest,
            }]})
        if request.url.path == f"/api/bundle/{task_id}/{file_id}":
            assert request.headers["authorization"] == "Bearer secret"
            return httpx.Response(302, headers={"location": "https://d2v96idf0qj40l.cloudfront.net/results.csv"})
        if request.url.host == "d2v96idf0qj40l.cloudfront.net":
            object_downloads += 1
            assert "authorization" not in request.headers
            return httpx.Response(200, content=content)
        if request.url.path.endswith("/logout"):
            return httpx.Response(204)
        raise AssertionError(request.url)

    settings = Settings(_env_file=None, cache_dir=tmp_path, earthdata_username="user", earthdata_password="password")
    connector = AppEEARSConnector(settings=settings, transport=httpx.MockTransport(handler))
    first = await connector.download(task_id, file_id)
    second = await connector.download(task_id, file_id)
    assert first.content == content
    assert first.provenance == Provenance.REAL
    assert second.provenance == Provenance.CACHED
    assert object_downloads == 1


@pytest.mark.asyncio
async def test_file_download_rejects_content_disposition_header_injection(tmp_path):
    task_id = "12345678-1234-1234-1234-123456789abc"
    file_id = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"

    def handler(request: httpx.Request):
        if request.url.path.endswith("/login"):
            return httpx.Response(200, json={"token": "secret", "expiration": "2099-01-01T00:00:00Z"})
        if request.url.path == f"/api/bundle/{task_id}":
            return httpx.Response(200, json={"task_id": task_id, "files": [{
                "file_id": file_id,
                "file_name": 'result.csv"\r\nX-Injected: true',
                "file_size": 0,
                "file_type": "csv",
                "sha256": hashlib.sha256(b"").hexdigest(),
            }]})
        if request.url.path.endswith("/logout"):
            return httpx.Response(204)
        raise AssertionError(request.url)

    settings = Settings(_env_file=None, cache_dir=tmp_path, earthdata_username="user", earthdata_password="password")
    connector = AppEEARSConnector(settings=settings, transport=httpx.MockTransport(handler))
    with pytest.raises(AppEEARSConnectorError, match="nombre de archivo no seguro"):
        await connector.download(task_id, file_id)
