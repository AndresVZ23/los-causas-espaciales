import asyncio
import zipfile
from datetime import datetime, timezone

from backend.app.connectors.nasa import nasadem
from backend.app.connectors.nasa.nasadem import NasademConnector, grid_index, read_metrics, tile_origin
from backend.app.schemas.analysis import Point, Provenance
from backend.app.schemas.terrain import TerrainGranule


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


def test_tile_origin_and_grid_index_use_lon_lat_in_wgs84():
    assert tile_origin("s18w071") == (-18, -71)
    row, column = grid_index("s18w071", -17.193, -70.934)
    assert row == 695
    assert column == 238


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
