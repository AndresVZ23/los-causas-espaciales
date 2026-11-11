"""Alertas activas en el mundo: GDACS da el nivel de alerta y NASA EONET es el segundo testigo (ADR-046).

No se decide aquí qué lugar «necesita apoyo»: el nivel naranja o rojo es de GDACS, y su definición se cita. El cruce
con EONET solo dice si NASA publica un evento del mismo tipo, cerca y en fechas cercanas. Funciones puras salvo
`world_alerts`, que consulta las dos fuentes; si una falla, la otra sigue y la caída queda declarada.
"""

from datetime import date, datetime, timezone
from typing import Any

from pyproj import Geod

from ..connectors.gdacs.events import SITE as GDACS_SITE
from ..connectors.gdacs.events import GdacsConnector
from ..connectors.http_json import JsonSourceError
from ..connectors.nasa.eonet import SITE as EONET_SITE
from ..connectors.nasa.eonet import EonetConnector
from ..geospatial.countries import PERU, country_at
from ..schemas.analysis import Provenance
from ..schemas.world import WorldAlert, WorldAlertsResponse, WorldSource

WINDOW_DAYS = 60
MATCH_DAYS = 10                 # fechas «cercanas» entre las dos fuentes
MATCH_KM = {"cyclone": 600.0}   # un ciclón recorre cientos de km entre un reporte y otro
DEFAULT_MATCH_KM = 150.0
# Tipos equivalentes entre fuentes: EONET llama «tormenta severa» a los ciclones tropicales.
SAME_KIND = {"cyclone": {"storm", "cyclone"}, "storm": {"storm", "cyclone"}}
NAMED_KINDS = {"cyclone", "volcano"}
MAX_PLACE_COUNTRIES = 3
PERU_GREEN_LIMIT = 8            # alertas verdes del Perú: las más recientes
LEVEL_ORDER = {"red": 0, "orange": 1, "green": 2, "none": 3}
GEOD = Geod(ellps="WGS84")
METHOD = [
    "El nivel de alerta es el que publica GDACS (ONU y Comisión Europea): naranja y roja indican que el evento puede requerir, "
    "o probablemente requiera, asistencia internacional; verde, que no se espera. La plataforma no lo recalcula.",
    f"Se listan las alertas naranja y roja del mundo de los últimos {WINDOW_DAYS} días y, en el Perú, también las verdes de inundación, "
    "sequía, incendio, ciclón y erupción.",
    f"Segundo testigo: NASA EONET. Un evento lleva la marca «también en NASA EONET» si NASA publica uno del mismo tipo a menos de "
    f"{DEFAULT_MATCH_KM:.0f} km ({MATCH_KM['cyclone']:.0f} km en ciclones) y con fechas a {MATCH_DAYS} días o menos. Los eventos abiertos de "
    "EONET que GDACS no lista aparecen aparte y sin nivel; los incendios de EONET solo se usan para el cruce.",
    "El punto es el que publica la fuente: en sequías e inundaciones extensas representa el centro del área, no su extensión.",
]
DISCLAIMER = ("Lista informativa de eventos publicados por GDACS y NASA EONET. No es un sistema de alerta temprana ni reemplaza a las "
              "autoridades de cada país. Analizar un punto muestra sus tendencias y amenazas de fondo, no el estado del evento.")


def _km(a: dict[str, Any], b: dict[str, Any]) -> float:
    return GEOD.inv(a["longitude"], a["latitude"], b["longitude"], b["latitude"])[2] / 1000


def same_event(gdacs: dict[str, Any], eonet: dict[str, Any]) -> bool:
    kinds = SAME_KIND.get(gdacs["kind"], {gdacs["kind"]})
    days = min(abs((eonet["updated"] - gdacs["updated"]).days), abs((eonet["started"] - gdacs["started"]).days))
    return eonet["kind"] in kinds and days <= MATCH_DAYS and _km(gdacs, eonet) <= MATCH_KM.get(gdacs["kind"], DEFAULT_MATCH_KM)


def _place(countries: list[str]) -> str:
    unique = list(dict.fromkeys(countries))
    if len(unique) <= MAX_PLACE_COUNTRIES:
        return ", ".join(unique)
    return f"{', '.join(unique[:MAX_PLACE_COUNTRIES])} y {len(unique) - MAX_PLACE_COUNTRIES} países más"


def _in_peru(item: dict[str, Any]) -> bool:
    country = country_at(item["longitude"], item["latitude"])
    return bool(country and country.iso3 == PERU) or any(name.strip().lower() == "peru" for name in item.get("countries", []))


def merge_alerts(gdacs: list[dict[str, Any]], eonet: list[dict[str, Any]]) -> list[WorldAlert]:
    """Une las dos listas: cada evento de GDACS con su marca de EONET, y los eventos de EONET sin pareja (sin incendios)."""
    matched: set[str] = set()
    out: list[WorldAlert] = []
    greens = 0
    for item in sorted(gdacs, key=lambda entry: entry["updated"], reverse=True):
        in_peru = _in_peru(item)
        if item["level"] == "green":
            if not in_peru or greens >= PERU_GREEN_LIMIT:
                continue
            greens += 1
        pairs = [other for other in eonet if same_event(item, other)]
        matched.update(other["id"] for other in pairs)
        countries = item.get("countries", [])
        # Ciclones y volcanes tienen nombre propio; el resto llega como «Flood in Peru»: se usa el tipo y el lugar va aparte.
        title = item["name"] if item["kind"] in NAMED_KINDS and len(item["name"]) <= 70 else item["kind_label"]
        out.append(WorldAlert(
            id=item["id"], source="GDACS", kind=item["kind"], kind_label=item["kind_label"], level=item["level"], title=title,
            place=_place(countries), started=item["started"], updated=item["updated"], current=item["current"], latitude=item["latitude"],
            longitude=item["longitude"], severity=item["severity"], url=item["url"], also_seen_by=["NASA EONET"] if pairs else [], in_peru=in_peru))
    for item in eonet:
        if item["id"] in matched or item["kind"] == "wildfire":
            continue
        country = country_at(item["longitude"], item["latitude"])
        out.append(WorldAlert(
            id=item["id"], source="NASA EONET", kind=item["kind"], kind_label=item["kind_label"], level="none", title=item["name"],
            place=country.name if country else "Mar abierto", started=item["started"], updated=item["updated"],
            current=True, latitude=item["latitude"], longitude=item["longitude"], severity=item["severity"], url=item["url"],
            in_peru=bool(country and country.iso3 == PERU)))
    out.sort(key=lambda alert: (not alert.current, LEVEL_ORDER[alert.level], -alert.updated.toordinal()))
    return out


async def world_alerts(today: date | None = None) -> WorldAlertsResponse:
    today = today or date.today()
    sources: list[WorldSource] = []
    gdacs: list[dict[str, Any]] = []
    eonet: list[dict[str, Any]] = []
    try:
        gdacs, provenance, stamp, stale = await GdacsConnector().events(today, WINDOW_DAYS)
        sources.append(WorldSource(name="GDACS", organization="Naciones Unidas (OCHA) y Comisión Europea (JRC)", url=GDACS_SITE, provenance=provenance,
                                   downloaded_at=stamp, note=stale or "Niveles de alerta por evento; actualización continua."))
    except JsonSourceError as exc:
        sources.append(WorldSource(name="GDACS", organization="Naciones Unidas (OCHA) y Comisión Europea (JRC)", url=GDACS_SITE, provenance=Provenance.UNAVAILABLE,
                                   downloaded_at=None, note=f"No respondió: {exc}. Sin GDACS no hay niveles de alerta: la lista no los inventa."))
    try:
        eonet, provenance, stamp, stale = await EonetConnector().open_events(WINDOW_DAYS)
        sources.append(WorldSource(name="NASA EONET v3", organization="NASA Earth Observatory", url=EONET_SITE, provenance=provenance,
                                   downloaded_at=stamp, note=stale or "Eventos naturales abiertos; sin niveles de alerta."))
    except JsonSourceError as exc:
        sources.append(WorldSource(name="NASA EONET v3", organization="NASA Earth Observatory", url=EONET_SITE, provenance=Provenance.UNAVAILABLE,
                                   downloaded_at=None, note=f"No respondió: {exc}. Ningún evento lleva hoy la marca del segundo testigo."))
    return WorldAlertsResponse(generated_at=datetime.now(timezone.utc), window_days=WINDOW_DAYS, alerts=merge_alerts(gdacs, eonet),
                               sources=sources, method=METHOD, disclaimer=DISCLAIMER)
