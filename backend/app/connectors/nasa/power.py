import asyncio
import hashlib
import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import httpx

from ...core.config import get_settings
from ...schemas.analysis import Observation, Provenance, SourceMetadata

VARIABLE_UNITS = {
    "T2M": "deg C",
    "PRECTOTCORR": "mm/day",
    "ALLSKY_SFC_SW_DWN": "kWh/m2/day",
    "WS10M": "m/s",
    "WS50M": "m/s",
}


class PowerConnectorError(RuntimeError):
    pass


class PowerConnector:
    def __init__(self):
        self.settings = get_settings()
        self.settings.cache_dir.mkdir(parents=True, exist_ok=True)

    def _cache_path(self, params: dict[str, str | float]) -> Path:
        digest = hashlib.sha256(json.dumps(params, sort_keys=True).encode()).hexdigest()
        return self.settings.cache_dir / f"{digest}.json"

    async def _request(self, params: dict[str, str | float]):
        cache_path = self._cache_path(params)
        now = datetime.now(timezone.utc)
        if cache_path.exists() and now - datetime.fromtimestamp(cache_path.stat().st_mtime, timezone.utc) < timedelta(hours=self.settings.cache_ttl_hours):
            # Lectura y parseo de varios MB fuera del bucle de eventos para no bloquear consultas concurrentes.
            payload = await asyncio.to_thread(lambda: json.loads(cache_path.read_text(encoding="utf-8")))
            return (
                payload,
                Provenance.CACHED,
                datetime.fromtimestamp(cache_path.stat().st_mtime, timezone.utc),
            )

        url = f"{self.settings.power_api_base}/temporal/daily/point"
        try:
            async with httpx.AsyncClient(timeout=60, follow_redirects=True) as client:
                response = await client.get(url, params=params)
                response.raise_for_status()
                payload = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise PowerConnectorError(f"La consulta a NASA POWER falló: {exc}") from exc
        cache_path.write_text(json.dumps(payload), encoding="utf-8")
        return payload, Provenance.REAL, now

    async def daily_point_multi(
        self,
        latitude: float,
        longitude: float,
        variables: list[str],
        start: date,
        end: date,
    ) -> dict[str, tuple[list[Observation], SourceMetadata]]:
        unique_variables = list(dict.fromkeys(variables))
        if not unique_variables or len(unique_variables) > 20:
            raise PowerConnectorError("NASA POWER admite entre 1 y 20 variables por consulta puntual.")
        params: dict[str, str | float] = {
            "parameters": ",".join(unique_variables),
            "community": "RE",
            "longitude": longitude,
            "latitude": latitude,
            "start": start.strftime("%Y%m%d"),
            "end": end.strftime("%Y%m%d"),
            "format": "JSON",
            "time-standard": "UTC",
        }
        payload, provenance, downloaded_at = await self._request(params)
        return self._parse_multi(payload, provenance, downloaded_at, unique_variables)

    @staticmethod
    def _parse_multi(
        payload: dict,
        provenance: Provenance,
        downloaded_at: datetime,
        unique_variables: list[str],
    ) -> dict[str, tuple[list[Observation], SourceMetadata]]:
        parameters_payload = payload.get("properties", {}).get("parameter", {})
        if not isinstance(parameters_payload, dict):
            raise PowerConnectorError("NASA POWER devolvió una estructura inesperada.")

        header = payload.get("header", {})
        parameter_metadata = payload.get("parameters", {})
        results: dict[str, tuple[list[Observation], SourceMetadata]] = {}
        for variable in unique_variables:
            raw = parameters_payload.get(variable)
            if not isinstance(raw, dict):
                raise PowerConnectorError(f"NASA POWER no devolvió la variable solicitada {variable}.")
            observations = []
            for key, value in raw.items():
                if value is None or float(value) <= -900:
                    continue
                # date() rechaza fechas inválidas y float() valores no numéricos; model_construct evita revalidar ~35 000 filas por sitio.
                timestamp = date(int(key[:4]), int(key[4:6]), int(key[6:8]))
                observations.append(Observation.model_construct(timestamp=timestamp, value=float(value)))
            metadata = parameter_metadata.get(variable, {}) if isinstance(parameter_metadata, dict) else {}
            source = SourceMetadata(
                source_id="nasa-power",
                dataset="NASA POWER Daily Point",
                version=str(header.get("api", {}).get("version", "respuesta vigente del API")),
                variable=variable,
                unit=str(metadata.get("units", VARIABLE_UNITS.get(variable, "unidad no informada"))),
                temporal_resolution="diaria; análisis agregado a escala anual",
                spatial_resolution="grilla nativa del producto; consultar metadatos NASA POWER",
                downloaded_at=downloaded_at,
                source_url="https://power.larc.nasa.gov/api/temporal/daily/point",
                provenance=provenance,
            )
            results[variable] = observations, source
        return results

    async def daily_point(self, latitude: float, longitude: float, variable: str, start: date, end: date):
        result = await self.daily_point_multi(latitude, longitude, [variable], start, end)
        return result[variable]
