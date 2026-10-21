#!/usr/bin/env python3
"""Validación estructural y de rangos para GeoJSON WGS84."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import sys
from typing import Any, Iterable


def positions(coords: Any) -> Iterable[list[float]]:
    if isinstance(coords, list) and len(coords) >= 2 and all(isinstance(v, (int, float)) for v in coords[:2]):
        yield coords
    elif isinstance(coords, list):
        for item in coords:
            yield from positions(item)


def validate_geometry(geometry: dict[str, Any], errors: list[str]) -> None:
    kind = geometry.get("type")
    coords = geometry.get("coordinates")
    if kind not in {"Point", "MultiPoint", "LineString", "MultiLineString", "Polygon", "MultiPolygon"}:
        errors.append(f"Tipo geométrico no soportado: {kind}")
        return
    pts = list(positions(coords))
    if not pts:
        errors.append("Geometría sin posiciones")
        return
    for index, point in enumerate(pts):
        lon, lat = point[:2]
        if not math.isfinite(lon) or not math.isfinite(lat):
            errors.append(f"Posición {index} no finita")
        if not -180 <= lon <= 180 or not -90 <= lat <= 90:
            errors.append(f"Posición {index} fuera de rango WGS84: {lon},{lat}")
    if kind == "LineString" and len(coords) < 2:
        errors.append("LineString requiere al menos dos posiciones")
    rings = coords if kind == "Polygon" else [ring for polygon in coords for ring in polygon] if kind == "MultiPolygon" else []
    for index, ring in enumerate(rings):
        if len(ring) < 4:
            errors.append(f"Anillo {index} requiere al menos cuatro posiciones")
        elif ring[0][:2] != ring[-1][:2]:
            errors.append(f"Anillo {index} no está cerrado")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("geojson", help="Ruta GeoJSON o - para stdin")
    args = parser.parse_args()
    raw = sys.stdin.read() if args.geojson == "-" else Path(args.geojson).read_text(encoding="utf-8")
    data = json.loads(raw)
    errors: list[str] = []
    geometries: list[dict[str, Any]] = []
    if data.get("type") == "FeatureCollection":
        for feature in data.get("features", []):
            if isinstance(feature, dict) and isinstance(feature.get("geometry"), dict):
                geometries.append(feature["geometry"])
            else:
                errors.append("Feature sin geometry")
    elif data.get("type") == "Feature" and isinstance(data.get("geometry"), dict):
        geometries.append(data["geometry"])
    else:
        geometries.append(data)
    for geometry in geometries:
        validate_geometry(geometry, errors)
    pts = [point for geometry in geometries for point in positions(geometry.get("coordinates"))]
    bbox = [min(p[0] for p in pts), min(p[1] for p in pts), max(p[0] for p in pts), max(p[1] for p in pts)] if pts else None
    print(json.dumps({"ok": not errors, "geometry_count": len(geometries), "bbox": bbox, "errors": errors}, ensure_ascii=False, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
