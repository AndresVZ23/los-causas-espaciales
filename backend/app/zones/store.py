"""Zonas para explorar ya construidas: archivos JSON versionados en backend/data/zones (los genera scripts/zones/build_zones.py)."""

import re
from functools import lru_cache
from pathlib import Path

from ..schemas.zones import Zone, ZoneSummary

ZONES_DIR = Path(__file__).resolve().parents[2] / "data" / "zones"
ZONE_ID = re.compile(r"^[a-z0-9-]{1,40}$")


@lru_cache(maxsize=8)
def _load(path: Path) -> Zone:
    return Zone.model_validate_json(path.read_text(encoding="utf-8"))


def list_zones(directory: Path = ZONES_DIR) -> list[ZoneSummary]:
    """Resumen de cada zona disponible, por nombre."""
    zones = [_load(path) for path in sorted(directory.glob("*.json"))] if directory.is_dir() else []
    return sorted((ZoneSummary(**zone.model_dump(include=set(ZoneSummary.model_fields))) for zone in zones), key=lambda item: item.name)


def get_zone(zone_id: str, directory: Path = ZONES_DIR) -> Zone | None:
    """La zona completa, o None si no existe. El identificador se valida antes de tocar el disco."""
    if not ZONE_ID.match(zone_id):
        return None
    path = directory / f"{zone_id}.json"
    return _load(path) if path.is_file() else None
