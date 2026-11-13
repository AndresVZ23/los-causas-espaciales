"""Misiones del «modo jugador» ya construidas: un archivo JSON versionado (lo genera scripts/missions/build_missions.py)."""

import json
import re
from functools import lru_cache
from pathlib import Path

from ..schemas.missions import MissionsResponse

MISSIONS_FILE = Path(__file__).resolve().parents[2] / "data" / "missions" / "missions.json"


@lru_cache(maxsize=2)
def _load(path: Path, modified: float) -> MissionsResponse:
    return MissionsResponse.model_validate_json(path.read_text(encoding="utf-8"))


def load_missions(path: Path = MISSIONS_FILE) -> MissionsResponse | None:
    """Las misiones, o None si todavía no se construyeron. Se relee el archivo si cambió en disco."""
    if not path.is_file():
        return None
    return _load(path, path.stat().st_mtime)


TERRAIN_DIR = MISSIONS_FILE.parent / "terrain"
MISSION_ID = re.compile(r"^[a-z0-9-]{1,40}$")


def load_terrain(mission_id: str, directory: Path = TERRAIN_DIR) -> dict | None:
    """Terreno 3D ya construido de una misión (scripts/missions/build_terrain.py), o None. El id se valida antes del disco."""
    if not MISSION_ID.match(mission_id):
        return None
    path = directory / f"{mission_id}.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else None
