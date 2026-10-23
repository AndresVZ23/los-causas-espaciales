"""Build small, reproducible web assets from the official Peru COD-AB GeoJSON archive."""

from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
import zipfile
from pathlib import Path

import httpx
from pyproj import Geod, Transformer
from shapely import transform
from shapely.geometry import mapping, shape

SOURCE_URL = (
    "https://data.humdata.org/dataset/54fc7f4d-f4c0-4892-91f6-2fe7c1ecf363/"
    "resource/63647792-0951-40d2-a30e-4a0e60f7a176/download/per_admin_boundaries.geojson.zip"
)
SOURCE_SHA256 = "2f0ec51b7a0899b407546aa644621e1c3255cba59fdda76fcde6975ca6baafb3"
EXPECTED_COUNTS = {1: 25, 2: 196, 3: 1873}
TOLERANCE_METRES = {1: 1_500, 2: 750, 3: 250}
LEVEL_NAMES = {1: "department", 2: "province", 3: "district"}
WGS84 = "EPSG:4326 (CRS84 longitude/latitude)"
GEOD = Geod(ellps="WGS84")
TO_WEB_MERCATOR = Transformer.from_crs("EPSG:4326", "EPSG:3857", always_xy=True)
TO_WGS84 = Transformer.from_crs("EPSG:3857", "EPSG:4326", always_xy=True)


def _vertices(geometry: dict) -> int:
    def count(value):
        if isinstance(value, (list, tuple)) and value and isinstance(value[0], (int, float)):
            return 1
        return sum(count(item) for item in value) if isinstance(value, (list, tuple)) else 0

    return count(geometry["coordinates"])


def _geodesic_area_sqkm(geometry) -> float:
    area, _ = GEOD.geometry_area_perimeter(geometry)
    return abs(area) / 1_000_000


def _simplify_with_area_guard(original, maximum_tolerance_metres: float):
    source_area = _geodesic_area_sqkm(original)
    projected = transform(original, TO_WEB_MERCATOR.transform, interleaved=False)
    tolerance = maximum_tolerance_metres
    for _ in range(8):
        candidate_projected = projected.simplify(tolerance, preserve_topology=True)
        candidate = transform(candidate_projected, TO_WGS84.transform, interleaved=False)
        candidate_area = _geodesic_area_sqkm(candidate)
        area_change = abs(candidate_area - source_area) / source_area * 100 if source_area else 0
        if not candidate.is_empty and candidate.is_valid and area_change <= 1:
            return candidate, tolerance, area_change
        tolerance /= 2
    return original, 0, 0


def _properties(level: int, raw: dict) -> dict:
    pcode = raw[f"adm{level}_pcode"]
    parent_pcode = raw.get(f"adm{level - 1}_pcode") if level > 1 else None
    return {
        "level": LEVEL_NAMES[level],
        "name": raw[f"adm{level}_name"],
        "ubigeo": pcode.removeprefix("PE"),
        "pcode": pcode,
        "parent_ubigeo": parent_pcode.removeprefix("PE") if parent_pcode else None,
        "parent_pcode": parent_pcode,
        "department": raw.get("adm1_name"),
        "province": raw.get("adm2_name") if level >= 2 else None,
        "area_sqkm": raw.get("area_sqkm"),
        "center_lat": raw.get("center_lat"),
        "center_lon": raw.get("center_lon"),
        "valid_on": raw.get("valid_on"),
        "version": raw.get("version"),
    }


def _download(target: Path) -> None:
    with httpx.stream("GET", SOURCE_URL, timeout=180, follow_redirects=False) as response:
        response.raise_for_status()
        with target.open("wb") as output:
            for chunk in response.iter_bytes():
                output.write(chunk)


def build(output_dir: Path, archive: Path | None = None) -> dict:
    output_dir.mkdir(parents=True, exist_ok=True)
    temporary: tempfile.TemporaryDirectory[str] | None = None
    if archive is None:
        temporary = tempfile.TemporaryDirectory(prefix="peru-cod-ab-")
        archive = Path(temporary.name) / "per_admin_boundaries.geojson.zip"
        _download(archive)
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    if digest != SOURCE_SHA256:
        raise RuntimeError(f"Unexpected source SHA-256: {digest}; review the HDX revision before rebuilding")

    index: list[dict] = []
    level_stats: dict[str, dict] = {}
    with zipfile.ZipFile(archive) as bundle:
        for level, expected_count in EXPECTED_COUNTS.items():
            source_name = f"per_admin{level}.geojson"
            raw_collection = json.loads(bundle.read(source_name))
            crs_name = raw_collection.get("crs", {}).get("properties", {}).get("name")
            if crs_name != "urn:ogc:def:crs:OGC:1.3:CRS84":
                raise RuntimeError(f"Unexpected CRS for {source_name}: {crs_name}")
            if len(raw_collection["features"]) != expected_count:
                raise RuntimeError(f"Unexpected count for {source_name}: {len(raw_collection['features'])}")

            features = []
            original_vertices = 0
            simplified_vertices = 0
            maximum_area_change = 0.0
            applied_tolerances: list[float] = []
            seen_ubigeos: set[str] = set()
            for raw_feature in raw_collection["features"]:
                properties = _properties(level, raw_feature["properties"])
                if properties["ubigeo"] in seen_ubigeos:
                    raise RuntimeError(f"Duplicate ubigeo at level {level}: {properties['ubigeo']}")
                seen_ubigeos.add(properties["ubigeo"])
                original = shape(raw_feature["geometry"])
                if original.is_empty or not original.is_valid:
                    raise RuntimeError(f"Invalid source geometry: {properties['pcode']}")
                simplified, applied_tolerance, area_change = _simplify_with_area_guard(
                    original, TOLERANCE_METRES[level]
                )
                maximum_area_change = max(maximum_area_change, area_change)
                applied_tolerances.append(applied_tolerance)
                geometry = mapping(simplified)
                original_vertices += _vertices(raw_feature["geometry"])
                simplified_vertices += _vertices(geometry)
                feature = {"type": "Feature", "id": properties["pcode"], "properties": properties, "geometry": geometry}
                features.append(feature)
                index.append(properties)

            collection = {
                "type": "FeatureCollection",
                "name": f"peru_{LEVEL_NAMES[level]}s_web",
                "features": features,
            }
            output = output_dir / f"admin{level}.geojson"
            output.write_text(json.dumps(collection, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
            level_stats[str(level)] = {
                "level": LEVEL_NAMES[level],
                "count": len(features),
                "maximum_simplification_tolerance_metres": TOLERANCE_METRES[level],
                "minimum_applied_tolerance_metres": min(applied_tolerances),
                "mean_applied_tolerance_metres": round(sum(applied_tolerances) / len(applied_tolerances), 3),
                "source_vertices": original_vertices,
                "web_vertices": simplified_vertices,
                "vertex_reduction_percent": round((1 - simplified_vertices / original_vertices) * 100, 3),
                "maximum_geodesic_area_change_percent": round(maximum_area_change, 4),
                "bytes": output.stat().st_size,
                "sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
            }

    index.sort(key=lambda item: (len(item["ubigeo"]), item["ubigeo"]))
    index_path = output_dir / "index.json"
    index_path.write_text(
        json.dumps({"territories": index}, ensure_ascii=False, separators=(",", ":")), encoding="utf-8"
    )
    manifest = {
        "dataset": "Peru - Subnational Administrative Boundaries (COD-AB) v01",
        "source_organization": "Instituto Geográfico Nacional del Perú (IGN)",
        "publisher": "OCHA Field Information Services / HDX",
        "source_url": SOURCE_URL,
        "source_sha256": digest,
        "license": "Creative Commons Attribution for Intergovernmental Organisations (CC BY-IGO)",
        "created_by_source": "2015-07-24",
        "valid_for_humanitarian_use": "2020-07-14",
        "reviewed": "2025-10-30",
        "resource_last_modified": "2026-01-26",
        "generated_at": "2026-10-23",
        "crs": WGS84,
        "processing_crs": "EPSG:3857; used only for metre-based display simplification",
        "warning": "Reference boundaries created in 2015; districts created later are absent. Not cadastral.",
        "index_sha256": hashlib.sha256(index_path.read_bytes()).hexdigest(),
        "levels": level_stats,
    }
    (output_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    if temporary is not None:
        temporary.cleanup()
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path("backend/data/territory"))
    parser.add_argument("--archive", type=Path)
    arguments = parser.parse_args()
    print(json.dumps(build(arguments.output, arguments.archive), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
