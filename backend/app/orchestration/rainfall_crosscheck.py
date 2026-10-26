"""Contraste de los extremos de lluvia con CHIRPS, compartido por Clima y Amenazas.

Cada sujeto pide su serie CHIRPS (área o celda del punto) a ClimateSERV. La primera consulta de un área nueva puede
tardar minutos; si no termina dentro del presupuesto de espera, el análisis sigue sin CHIRPS y lo declara como
«descargándose», mientras la descarga continúa en segundo plano y llena la caché para la siguiente ejecución.
Nada se rellena: un sujeto sin serie queda sin contraste, no con ceros.
"""

import asyncio
import hashlib
import json
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import date
from typing import Any

from ..connectors.nasa.climateserv import ChirpsConnector
from ..connectors.nasa.power import PowerConnectorError
from ..schemas.analysis import Point
from ..schemas.climate import ExtremeIndexSummary
from ..schemas.screening import DataGap
from .analysis import analyze_extremes, attach_countercheck

CHIRPS = "CHIRPS"
CHIRPS_SOURCE = "CHIRPS (UCSB · NASA SERVIR)"
WAIT_SECONDS = 45.0
_inflight: dict[str, asyncio.Task] = {}


@dataclass
class ChirpsResult:
    extremes: list[list[ExtremeIndexSummary] | None]
    pending: list[str] = field(default_factory=list)   # sujetos cuya serie sigue descargándose
    errors: list[str] = field(default_factory=list)


def _key(geometry: dict[str, Any] | None, point: Point, start: date, end: date) -> str:
    payload = json.dumps({"g": geometry, "p": [round(point.longitude, 4), round(point.latitude, 4)], "s": start.isoformat(), "e": end.isoformat()},
                         sort_keys=True, default=str)
    return hashlib.sha256(payload.encode()).hexdigest()


def _task(geometry: dict[str, Any] | None, point: Point, start: date, end: date) -> asyncio.Task:
    """Una descarga por área, compartida entre consultas simultáneas y que sobrevive al presupuesto de espera."""
    key = _key(geometry, point, start, end)
    task = _inflight.get(key)
    if task is None or (task.done() and task.exception() is not None):
        task = asyncio.get_running_loop().create_task(ChirpsConnector().daily(geometry, point.longitude, point.latitude, start, end))
        _inflight[key] = task
        task.add_done_callback(lambda t, k=key: _inflight.pop(k, None) if t.exception() is None else None)
    return task


async def chirps_extremes(subjects: Sequence[tuple[str, dict[str, Any] | None, Point]], start: date, end: date, wait: float = WAIT_SECONDS) -> ChirpsResult:
    """Índices ETCCDI con CHIRPS por sujeto (etiqueta, geometría o None para un punto, punto representativo)."""
    tasks = [_task(geometry, point, start, end) for _, geometry, point in subjects]
    done, _ = await asyncio.wait(tasks, timeout=wait)
    result = ChirpsResult(extremes=[None] * len(subjects))
    series: dict[int, dict] = {}
    for index, ((label, _, _), task) in enumerate(zip(subjects, tasks, strict=True)):
        if task not in done:
            result.pending.append(label)
        elif task.exception() is not None:
            result.errors.append(f"{label}: {task.exception()}")
        else:
            series[index] = {CHIRPS: task.result()}
    # Un área sin días húmedos en CHIRPS (desierto costero) sale sola, sin dejar sin contraste a las demás.
    for index in list(series):
        try:
            analyze_extremes([series[index]], CHIRPS)
        except PowerConnectorError as exc:
            result.errors.append(f"{subjects[index][0]}: CHIRPS no permite calcular los índices ({exc})")
            del series[index]
    if series:
        # Juntas, para que Benjamini–Hochberg ajuste entre sitios igual que con MERRA-2 e IMERG.
        computed, _ = analyze_extremes(list(series.values()), CHIRPS)
        for index, summaries in zip(series, computed, strict=True):
            result.extremes[index] = summaries
    return result


def attach_chirps(primary: list[list[ExtremeIndexSummary]], chirps: ChirpsResult) -> None:
    attach_countercheck(primary, chirps.extremes, CHIRPS_SOURCE, legacy_slot=False)


CHIRPS_NOTE = (
    "Tercer contraste: los mismos índices con CHIRPS v2.0 (satélite infrarrojo + climatología + estaciones, 0.05°), servido por "
    "NASA SERVIR ClimateSERV con unas semanas de latencia. CHIRPS suaviza los extremos; su acuerdo pesa más en dirección que en magnitud."
)


def chirps_gaps(chirps: ChirpsResult) -> list[DataGap]:
    gaps = []
    if chirps.pending:
        gaps.append(DataGap(dataset="CHIRPS (tercer contraste de la lluvia)",
                            impact=f"La serie se está descargando para: {', '.join(chirps.pending)}. Esta ejecución usa solo MERRA-2 e IMERG en esos sujetos.",
                            next_action="Volver a ejecutar en unos minutos: la descarga continúa en segundo plano y queda en caché."))
    if chirps.errors:
        gaps.append(DataGap(dataset="CHIRPS · fuente con error", impact="; ".join(chirps.errors)[:400],
                            next_action="Reintentar; un sujeto sin CHIRPS queda sin ese contraste, no con ceros."))
    return gaps
