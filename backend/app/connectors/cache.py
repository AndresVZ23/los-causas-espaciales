"""Content-addressed connector cache; provider payloads are never overwritten."""

import hashlib
import json
import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


# Última copia válida: si el proveedor falla, una copia ya vencida de hasta este tiempo puede mostrarse, declarada como tal
# y con su fecha original. Nunca reemplaza a una respuesta que sí llegó.
STALE_MAX_AGE = timedelta(days=90)
_MONTHS = ("ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic")


def stale_copy_note(reason: str, downloaded_at: datetime) -> str:
    """Frase única con la que una fuente declara que muestra su última copia válida, por qué y de cuándo es."""
    day = downloaded_at.astimezone(timezone.utc)
    return (f"El servicio oficial no respondió hoy ({reason or 'sin respuesta'}); se muestra la última copia válida, "
            f"del {day.day}-{_MONTHS[day.month - 1]}-{day.year}.")


@dataclass(frozen=True)
class CachedPayload:
    content: bytes
    downloaded_at: datetime
    provenance: str


class RawPayloadCache:
    def __init__(self, root: Path, namespace: str):
        self.root = root / namespace
        self.raw_dir = self.root / "raw"
        self.manifest_dir = self.root / "manifests"
        self.raw_dir.mkdir(parents=True, exist_ok=True)
        self.manifest_dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def request_key(payload: Any) -> str:
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
        return hashlib.sha256(canonical).hexdigest()

    def _manifest_path(self, request_key: str) -> Path:
        return self.manifest_dir / f"{request_key}.json"

    def get(self, request_key: str, *, max_age: timedelta | None = None) -> CachedPayload | None:
        manifest_path = self._manifest_path(request_key)
        if not manifest_path.exists():
            return None
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            downloaded_at = datetime.fromisoformat(manifest["downloaded_at"])
            if max_age is not None and datetime.now(timezone.utc) - downloaded_at > max_age:
                return None
            raw_path = self.raw_dir / manifest["raw_name"]
            content = raw_path.read_bytes()
            if hashlib.sha256(content).hexdigest() != manifest["sha256"]:
                return None
            return CachedPayload(content=content, downloaded_at=downloaded_at, provenance="CACHED_DATA")
        except (KeyError, ValueError, OSError, json.JSONDecodeError):
            return None

    def last_valid(self, request_key: str) -> CachedPayload | None:
        """La última copia válida aunque su vigencia normal haya vencido, con su fecha original.

        Solo para cuando el proveedor falla: quien la use debe declararlo (`stale_copy_note`).
        """
        return self.get(request_key, max_age=STALE_MAX_AGE)

    def put(self, request_key: str, content: bytes, *, suffix: str) -> CachedPayload:
        digest = hashlib.sha256(content).hexdigest()
        raw_name = f"{digest}{suffix}"
        raw_path = self.raw_dir / raw_name
        if not raw_path.exists():
            temporary = raw_path.with_suffix(raw_path.suffix + ".part")
            with temporary.open("wb") as output:
                output.write(content)
                output.flush()
                os.fsync(output.fileno())
            temporary.replace(raw_path)
        downloaded_at = datetime.now(timezone.utc)
        manifest = {
            "request_key": request_key,
            "sha256": digest,
            "raw_name": raw_name,
            "downloaded_at": downloaded_at.isoformat(),
        }
        manifest_path = self._manifest_path(request_key)
        temporary_manifest = manifest_path.with_suffix(".json.part")
        temporary_manifest.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        temporary_manifest.replace(manifest_path)
        return CachedPayload(content=content, downloaded_at=downloaded_at, provenance="REAL_DATA")
