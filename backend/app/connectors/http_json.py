"""GET de JSON con caché, vigencia y última copia válida (ADR-044), para fuentes pequeñas de consulta única."""

import json
from datetime import datetime, timedelta
from typing import Any

import httpx

from ..schemas.analysis import Provenance
from .cache import RawPayloadCache, stale_copy_note

TIMEOUT = httpx.Timeout(connect=15, read=45, write=15, pool=15)
USER_AGENT = "los-causas-espaciales/0.1 (NASA Space Apps 2026)"


class JsonSourceError(RuntimeError):
    pass


async def cached_json(cache: RawPayloadCache, url: str, params: dict[str, str], *, max_age: timedelta,
                      transport: httpx.AsyncBaseTransport | None = None) -> tuple[Any, Provenance, datetime, str | None]:
    """Devuelve (contenido, procedencia, fecha de descarga, nota de copia). Primero la caché vigente, luego la fuente y,
    si la fuente falla, la última copia válida con su fecha original. Sin copia, la falla se propaga."""
    key = cache.request_key({"url": url, "params": params, "v": 1})
    cached = cache.get(key, max_age=max_age)
    if cached:
        return json.loads(cached.content), Provenance.CACHED, cached.downloaded_at, None
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT, transport=transport, follow_redirects=True, headers={"User-Agent": USER_AGENT}) as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
        payload = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        stale = cache.last_valid(key)
        if stale is None:
            raise JsonSourceError(str(exc) or type(exc).__name__) from exc
        return json.loads(stale.content), Provenance.CACHED, stale.downloaded_at, stale_copy_note(str(exc) or type(exc).__name__, stale.downloaded_at)
    stored = cache.put(key, response.content, suffix=".json")
    return payload, Provenance.REAL, stored.downloaded_at, None
