"""Read-only catalog for the pinned IGN/OCHA COD-AB Peru web assets."""

from __future__ import annotations

import hashlib
import json
import unicodedata
from functools import lru_cache
from pathlib import Path
from typing import Any

from ...schemas.analysis import Point
from ...schemas.territory import (
    TerritoryGeometryResponse,
    TerritoryHierarchyResponse,
    TerritoryLevel,
    TerritorySearchResponse,
    TerritorySourceMetadata,
    TerritorySummary,
)

DATA_ROOT = Path(__file__).resolve().parents[3] / "data" / "territory"
LEVEL_TO_ADMIN: dict[TerritoryLevel, int] = {"department": 1, "province": 2, "district": 3}
ADMIN_TO_LEVEL = {value: key for key, value in LEVEL_TO_ADMIN.items()}
LEVEL_TO_UBIGEO_LENGTH: dict[TerritoryLevel, int] = {"department": 2, "province": 4, "district": 6}
REFERENCE_WARNING = (
    "Los trazos fueron creados por la fuente en 2015: no incluyen distritos creados después y no son catastrales."
)


class TerritoryCatalogError(RuntimeError):
    pass


class TerritoryNotFoundError(TerritoryCatalogError):
    pass


def _normalized(value: str) -> str:
    return "".join(
        character
        for character in unicodedata.normalize("NFKD", value.strip()).casefold()
        if not unicodedata.combining(character)
    )


def _read_verified(path: Path, expected_sha256: str) -> dict[str, Any]:
    try:
        content = path.read_bytes()
    except OSError as exc:
        raise TerritoryCatalogError(f"No se pudo leer el activo territorial {path.name}.") from exc
    if hashlib.sha256(content).hexdigest() != expected_sha256:
        raise TerritoryCatalogError(f"Falló la verificación SHA-256 del activo territorial {path.name}.")
    try:
        return json.loads(content)
    except json.JSONDecodeError as exc:
        raise TerritoryCatalogError(f"El activo territorial {path.name} no es JSON válido.") from exc


@lru_cache(maxsize=1)
def _manifest() -> dict[str, Any]:
    try:
        return json.loads((DATA_ROOT / "manifest.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise TerritoryCatalogError("El manifiesto territorial no está disponible.") from exc


@lru_cache(maxsize=1)
def _index() -> tuple[dict[str, Any], ...]:
    manifest = _manifest()
    payload = _read_verified(DATA_ROOT / "index.json", manifest["index_sha256"])
    records = tuple(payload.get("territories", []))
    expected = sum(item["count"] for item in manifest["levels"].values())
    if len(records) != expected:
        raise TerritoryCatalogError("El índice territorial no coincide con los conteos del manifiesto.")
    return records


@lru_cache(maxsize=3)
def _features(level: TerritoryLevel) -> dict[str, dict[str, Any]]:
    admin = LEVEL_TO_ADMIN[level]
    manifest = _manifest()
    level_manifest = manifest["levels"][str(admin)]
    payload = _read_verified(DATA_ROOT / f"admin{admin}.geojson", level_manifest["sha256"])
    features = {feature["properties"]["ubigeo"]: feature for feature in payload.get("features", [])}
    if len(features) != level_manifest["count"]:
        raise TerritoryCatalogError(f"El GeoJSON {level} no coincide con el manifiesto.")
    return features


def _source() -> TerritorySourceMetadata:
    manifest = _manifest()
    return TerritorySourceMetadata(
        dataset=manifest["dataset"],
        source_organization=manifest["source_organization"],
        publisher=manifest["publisher"],
        source_url=manifest["source_url"],
        source_sha256=manifest["source_sha256"],
        license=manifest["license"],
        source_created=manifest["created_by_source"],
        reviewed=manifest["reviewed"],
        crs=manifest["crs"],
        warnings=[REFERENCE_WARNING, "La geometría servida está simplificada para visualización web."],
    )


def _summary(record: dict[str, Any]) -> TerritorySummary:
    return TerritorySummary(
        level=record["level"],
        name=record["name"],
        ubigeo=record["ubigeo"],
        pcode=record["pcode"],
        parent_ubigeo=record.get("parent_ubigeo"),
        department=record.get("department"),
        province=record.get("province"),
        area_sqkm=record["area_sqkm"],
        center=Point(latitude=record["center_lat"], longitude=record["center_lon"]),
    )


def _record(level: TerritoryLevel, ubigeo: str) -> dict[str, Any]:
    expected_length = LEVEL_TO_UBIGEO_LENGTH[level]
    if not ubigeo.isdigit() or len(ubigeo) != expected_length:
        raise TerritoryCatalogError(f"El ubigeo de {level} debe tener {expected_length} dígitos.")
    match = next((item for item in _index() if item["level"] == level and item["ubigeo"] == ubigeo), None)
    if match is None:
        raise TerritoryNotFoundError(f"No existe {level} con ubigeo {ubigeo} en COD-AB Perú v01.")
    return match


class PeruTerritoryCatalog:
    def search(
        self,
        query: str,
        *,
        level: TerritoryLevel | None = None,
        parent_ubigeo: str | None = None,
        limit: int = 20,
    ) -> TerritorySearchResponse:
        normalized_query = _normalized(query)
        if not normalized_query:
            raise TerritoryCatalogError("La búsqueda no puede estar vacía.")
        matches = []
        for record in _index():
            if level and record["level"] != level:
                continue
            if parent_ubigeo is not None and record.get("parent_ubigeo") != parent_ubigeo:
                continue
            normalized_name = _normalized(record["name"])
            if normalized_query not in normalized_name and normalized_query not in record["ubigeo"]:
                continue
            rank = (
                0 if record["ubigeo"] == query else
                1 if normalized_name == normalized_query else
                2 if normalized_name.startswith(normalized_query) else 3
            )
            matches.append((rank, normalized_name, record))
        matches.sort(key=lambda item: (item[0], item[1], item[2]["ubigeo"]))
        results = [_summary(item[2]) for item in matches[:limit]]
        return TerritorySearchResponse(query=query, count=len(results), results=results, source=_source())

    def hierarchy(self, parent_ubigeo: str | None = None) -> TerritoryHierarchyResponse:
        if parent_ubigeo is None:
            parent = None
            children_level: TerritoryLevel = "department"
        elif parent_ubigeo.isdigit() and len(parent_ubigeo) == 2:
            parent = _summary(_record("department", parent_ubigeo))
            children_level = "province"
        elif parent_ubigeo.isdigit() and len(parent_ubigeo) == 4:
            parent = _summary(_record("province", parent_ubigeo))
            children_level = "district"
        else:
            raise TerritoryCatalogError("parent_ubigeo debe omitirse o tener 2/4 dígitos.")
        children = [
            _summary(record)
            for record in _index()
            if record["level"] == children_level
            and (parent_ubigeo is None or record.get("parent_ubigeo") == parent_ubigeo)
        ]
        children.sort(key=lambda item: (_normalized(item.name), item.ubigeo))
        return TerritoryHierarchyResponse(
            parent=parent,
            children_level=children_level,
            count=len(children),
            children=children,
            source=_source(),
        )

    def geometry(self, level: TerritoryLevel, ubigeo: str) -> TerritoryGeometryResponse:
        record = _record(level, ubigeo)
        feature = _features(level).get(ubigeo)
        if feature is None:
            raise TerritoryNotFoundError(f"La geometría {level}/{ubigeo} no está disponible.")
        level_manifest = _manifest()["levels"][str(LEVEL_TO_ADMIN[level])]
        return TerritoryGeometryResponse(
            territory=_summary(record),
            feature=feature,
            crs="EPSG:4326; GeoJSON RFC 7946 longitude/latitude",
            maximum_simplification_tolerance_metres=level_manifest["maximum_simplification_tolerance_metres"],
            maximum_level_area_change_percent=level_manifest["maximum_geodesic_area_change_percent"],
            source=_source(),
            limitations=[
                REFERENCE_WARNING,
                "La simplificación conserva topología por entidad y limita el cambio de área geodésica a 1 %, pero no garantiza bordes compartidos sin microdesajustes.",
                "Para análisis legal, catastral o distritos posteriores a 2015 se requiere una fuente oficial actualizada.",
            ],
        )
