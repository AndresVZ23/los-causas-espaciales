"""Spatial intersection queries against allow-listed official Peruvian ArcGIS layers."""

import asyncio
import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import urlparse

import httpx
from shapely.geometry import shape

from ...core.config import Settings, get_settings
from ...geospatial.geometry import GeometryValidationError, inspect_geometry
from ...schemas.analysis import Provenance
from ...schemas.data_sources import (
    TerritorialFeature,
    TerritorialQueryRequest,
    TerritorialQueryResponse,
    TerritorialSourceResult,
)
from ..cache import RawPayloadCache, stale_copy_note

TIMEOUT = httpx.Timeout(connect=20, read=45, write=20, pool=20)
CULTURA_CACHE_TTL = timedelta(days=7)


class TerritoryConnectorError(RuntimeError):
    pass


@dataclass(frozen=True)
class OfficialLayer:
    source_id: str
    organization: str
    dataset: str
    base_url: str
    layer_ids: tuple[int, ...]
    coverage: str
    scale_or_resolution: str
    license: str
    limitations: tuple[str, ...] = ()
    unavailable_reason: str | None = None


PUBLIC_LICENSE_NOTE = (
    "Consulta pública con atribución a la entidad; el servicio no publica una licencia explícita de reutilización "
    "en sus metadatos REST. Confirmar condiciones antes de redistribuir datos derivados."
)

LAYERS: dict[str, OfficialLayer] = {
    "cenepred-flood-risk": OfficialLayer(
        "cenepred-flood-risk", "CENEPRED · SIGRID",
        "Escenario de riesgo por inundaciones ante lluvias intensas/FEN",
        "https://sigrid.cenepred.gob.pe/arcgis/rest/services/FEN/ER_NINO2027_BD/MapServer", (4,),
        "Perú; polígonos distritales del escenario El Niño actualizado con Informe Técnico 69-2026 de SENAMHI",
        "Escala no declarada; fuente EPSG:32718 y respuesta reproyectada a EPSG:4326", PUBLIC_LICENSE_NOTE,
        ("Es un escenario prospectivo de riesgo, no un inventario exhaustivo ni una probabilidad predial.",),
    ),
    "cenepred-mass-movement-risk": OfficialLayer(
        "cenepred-mass-movement-risk", "CENEPRED · SIGRID",
        "Escenario de riesgo por movimientos en masa ante lluvias intensas/FEN",
        "https://sigrid.cenepred.gob.pe/arcgis/rest/services/FEN/ER_NINO2027_BD/MapServer", (5,),
        "Perú; polígonos distritales del escenario El Niño actualizado con Informe Técnico 69-2026 de SENAMHI",
        "Escala no declarada; fuente EPSG:32718 y respuesta reproyectada a EPSG:4326", PUBLIC_LICENSE_NOTE,
        ("No reemplaza estudios geotécnicos ni cartografía de detalle de INGEMMET.",),
    ),
    "sernanp-anp": OfficialLayer(
        "sernanp-anp", "SERNANP", "Áreas Naturales Protegidas establecidas",
        "https://geoservicios.sernanp.gob.pe/arcgis/rest/services/servicios_ogc/peru_sernanp_0102/MapServer", (0, 1, 2, 3),
        "Perú; ANP nacionales definitivas/transitorias, regionales y privadas",
        "Vector EPSG:4326; escala de compilación no declarada", PUBLIC_LICENSE_NOTE,
        ("La superposición es una alerta de debida diligencia y no constituye opinión legal de compatibilidad.",),
    ),
    "osinergmin-grid": OfficialLayer(
        "osinergmin-grid", "Osinergmin · GISEM", "Líneas de transmisión y subestaciones en operación",
        "https://gisem.osinergmin.gob.pe/serverosih/rest/services/Electricidad/ELECTRICIDAD/MapServer", (15, 18),
        "Perú; infraestructura publicada por Osinergmin/MINEM/COES/empresas",
        "Vector EPSG:4326; escala de compilación no declarada", PUBLIC_LICENSE_NOTE,
        ("Una intersección no informa capacidad disponible, derecho de conexión ni estado en tiempo real.",),
    ),
    "cultura-archaeology": OfficialLayer(
        "cultura-archaeology", "Ministerio de Cultura · SIGDA",
        "Bienes inmuebles prehispánicos registrados referencialmente",
        "https://sigda.cultura.gob.pe/sigda/rest/services/v_4/registrado_v4/MapServer", (0,),
        "Perú; registros referenciales publicados por DSFL/Geomática",
        "Vector EPSG:4326; escala de levantamiento no declarada", PUBLIC_LICENSE_NOTE,
        ("La ausencia de intersección en SIGDA no prueba ausencia de patrimonio arqueológico.",),
    ),
    "cultura-archaeology-declared": OfficialLayer(
        "cultura-archaeology-declared", "Ministerio de Cultura · SIGDA",
        "Bienes inmuebles prehispánicos declarados",
        "https://sigda.cultura.gob.pe/sigda/rest/services/v_4/declarados_v4/MapServer", (0,),
        "Perú; bienes inmuebles prehispánicos declarados",
        "Vector EPSG:4326; escala de levantamiento no declarada", PUBLIC_LICENSE_NOTE,
        ("La consulta no sustituye un CIRA ni la evaluación formal del Ministerio de Cultura.",),
    ),
    # Línea base ambiental y patrimonial (módulos 4 y 5, Claude, 24-oct-2026): servicios ArcGIS verificados con
    # metadatos y una consulta de conteo sobre Moquegua–Ilo antes de agregarlos.
    "cultura-ciras": OfficialLayer(
        "cultura-ciras", "Ministerio de Cultura · SIGDA", "Certificados de Inexistencia de Restos Arqueológicos (CIRA) emitidos",
        "https://sigda.cultura.gob.pe/sigda/rest/services/v_4/CIRAS_V4/MapServer", (0,),
        "Perú; ámbitos de CIRA publicados por DSFL/Geomática",
        "Vector EPSG:4326; escala de levantamiento no declarada", PUBLIC_LICENSE_NOTE,
        ("Un CIRA vale para el ámbito y proyecto que lo solicitó; no se extiende a un proyecto nuevo.",),
    ),
    "cultura-das": OfficialLayer(
        "cultura-das", "Ministerio de Cultura · SIGDA", "Diagnósticos arqueológicos en superficie (DAS)",
        "https://sigda.cultura.gob.pe/sigda/rest/services/v_4/das/MapServer", (0,),
        "Perú; áreas de diagnóstico comunicadas por proyectos",
        "Vector EPSG:4326; escala de levantamiento no declarada", PUBLIC_LICENSE_NOTE,
        ("Un DAS es un antecedente de evaluación de otro proyecto; no reemplaza el propio.",),
    ),
    "cultura-qhapaq-nan": OfficialLayer(
        "cultura-qhapaq-nan", "Ministerio de Cultura · Qhapaq Ñan", "Caminos prehispánicos registrados y proyectados",
        "https://sigda.cultura.gob.pe/sigda/rest/services/v_4/pqn_v4/MapServer", (0, 1),
        "Perú; red vial inca registrada (capa 0) y proyección de caminos (capa 1)",
        "Vector EPSG:4326; escala de levantamiento no declarada", PUBLIC_LICENSE_NOTE,
        ("Las proyecciones de camino (capa 1) son trazos inferidos, no tramos registrados en campo.",),
    ),
    "cultura-cultural-landscape": OfficialLayer(
        "cultura-cultural-landscape", "Ministerio de Cultura · SIGDA", "Paisajes culturales",
        "https://sigda.cultura.gob.pe/sigda/rest/services/v_4/Paisaje_Cultural/MapServer", (0,),
        "Perú; paisajes culturales a nivel nacional", "Vector EPSG:4326; escala no declarada", PUBLIC_LICENSE_NOTE,
    ),
    "cultura-world-heritage": OfficialLayer(
        "cultura-world-heritage", "Ministerio de Cultura · SIGDA", "Sitios del Patrimonio Mundial",
        "https://sigda.cultura.gob.pe/sigda/rest/services/v_4/spm_v4/MapServer", (0,),
        "Perú; sitios inscritos en la Lista del Patrimonio Mundial", "Vector EPSG:4326; escala no declarada", PUBLIC_LICENSE_NOTE,
    ),
    "cultura-prior-consultation": OfficialLayer(
        "cultura-prior-consultation", "Ministerio de Cultura · Consulta previa", "Ámbitos con procesos de consulta previa",
        "https://sigda.cultura.gob.pe/sigda/rest/services/v_4/consulta_previa_v4/MapServer", (0,),
        "Perú; ámbitos distritales con procesos de consulta previa publicados", "Vector EPSG:4326; nivel distrital", PUBLIC_LICENSE_NOTE,
        ("El campo «tipo» es un código sin tabla publicada en el servicio; no identifica pueblos ni comunidades.",
         "Esta capa no reemplaza la Base de Datos de Pueblos Indígenas ni la identificación formal de pueblos.",),
    ),
    "cultura-citizen-records": OfficialLayer(
        "cultura-citizen-records", "Ministerio de Cultura · SIGDA", "Bienes inmuebles prehispánicos reportados por ciudadanos",
        "https://sigda.cultura.gob.pe/sigda/rest/services/v_4/registro_externo/MapServer", (0,),
        "Perú; reportes ciudadanos publicados por DSFL/Geomática", "Vector EPSG:4326; escala no declarada", PUBLIC_LICENSE_NOTE,
        ("Son reportes ciudadanos: indican dónde revisar, no son registros oficiales validados.",),
    ),
    "minam-ecosystems": OfficialLayer(
        "minam-ecosystems", "MINAM · GeoPerú", "Mapa Nacional de Ecosistemas",
        "https://geoservidorperu.minam.gob.pe/arcgis/rest/services/Servicios_GeoPERU/ServicioEcosistemas_MINAM/MapServer", (0,),
        "Perú; ecosistemas continentales", "Vector; escala nacional de compilación", PUBLIC_LICENSE_NOTE,
        ("Escala nacional: no delimita ecosistemas a nivel de proyecto.",),
    ),
    "minam-vegetation-cover": OfficialLayer(
        "minam-vegetation-cover", "MINAM · Geoservidor", "Mapa de Cobertura Vegetal 2015",
        "https://geoservidorperu.minam.gob.pe/arcgis/rest/services/Servicio_cobertura_vegetal/MapServer", (0,),
        "Perú; cobertura vegetal aprobada por R.M. 059-2015-MINAM", "Vector; escala nacional de compilación", PUBLIC_LICENSE_NOTE,
        ("Refleja la cobertura de 2013–2015; los cambios posteriores se leen con MODIS.",),
    ),
    "minam-coastal-lomas": OfficialLayer(
        "minam-coastal-lomas", "MINAM · Geoservidor", "Lomas costeras (ecosistema frágil)",
        "https://geoservidorperu.minam.gob.pe/arcgis/rest/services/Loma_costera/MapServer", (0,),
        "Costa peruana; ecosistemas frágiles de lomas", "Vector; escala no declarada", PUBLIC_LICENSE_NOTE,
        ("Las lomas dependen de la neblina estacional; su extensión real varía entre años.",),
    ),
    "minam-ramsar": OfficialLayer(
        "minam-ramsar", "MINAM · GeoPerú", "Sitios Ramsar (humedales de importancia internacional)",
        "https://geoservidorperu.minam.gob.pe/arcgis/rest/services/Servicios_GeoPERU/ServicioSitiosRAMSAR_MINAM/MapServer", (0,),
        "Perú; sitios Ramsar designados", "Vector; escala no declarada", PUBLIC_LICENSE_NOTE,
    ),
    "ana-water-bodies": OfficialLayer(
        "ana-water-bodies", "ANA · SNIRH", "Cuerpos de agua con categoría de Estándar de Calidad Ambiental (ECA)",
        "https://geosnirh.ana.gob.pe/server/rest/services/ws_Rios_Quebradas/MapServer", (37,),
        "Perú; ríos y quebradas categorizados por la ANA", "Vector; red hidrográfica codificada Pfafstetter", PUBLIC_LICENSE_NOTE,
        ("La categoría ECA indica el uso asignado al cuerpo de agua, no su calidad medida.",),
    ),
    "ana-hydro-units": OfficialLayer(
        "ana-hydro-units", "ANA · SNIRH", "Unidades hidrográficas (Pfafstetter)",
        "https://geosnirh.ana.gob.pe/server/rest/services/ws_UnidadesHidro/MapServer", (1,),
        "Perú; cuencas e intercuencas codificadas", "Vector; codificación Pfafstetter hasta nivel 7", PUBLIC_LICENSE_NOTE,
    ),
    # Módulo 3 · amenazas naturales (Claude, 25-oct-2026). Las capas 1 y 2 del servicio FEN de CENEPRED
    # (susceptibilidad) no admiten consultas por área (400): no se agregan.
    "ana-critical-points": OfficialLayer(
        "ana-critical-points", "ANA · SNIRH", "Puntos críticos por riesgo de inundación en ríos y quebradas (2022)",
        "https://geosnirh.ana.gob.pe/server/rest/services/Puntos_Criticos/PuntosCriticos2022/MapServer", (57,),
        "Perú; puntos críticos identificados por las Autoridades Administrativas del Agua", "Puntos; ubicación aproximada del tramo crítico",
        PUBLIC_LICENSE_NOTE,
        ("Inventario de 2022: un punto crítico no estima probabilidad de inundación ni reemplaza un estudio hidráulico.",
         "El servidor de la ANA responde de forma intermitente; una falla se informa como no disponible."),
    ),
    "ana-imminent-danger": OfficialLayer(
        "ana-imminent-danger", "ANA · SNIRH", "Distritos declarados en peligro inminente por intensas precipitaciones (D.U. 015-2023)",
        "https://geosnirh.ana.gob.pe/server/rest/services/Puntos_Criticos/Distritos_en_peligro_inminente_por_intensas_precipitaciones/MapServer", (1,),
        "Perú; distritos incluidos en la declaratoria de 2023", "Polígonos distritales", PUBLIC_LICENSE_NOTE,
        ("Es una declaratoria administrativa de 2023, no un mapa de amenaza vigente.",),
    ),
    "ingemmet-geohazards": OfficialLayer(
        "ingemmet-geohazards", "INGEMMET · GEOCATMIN", "Peligros geológicos",
        "https://geocatminapp.ingemmet.gob.pe/arcgis/rest/services", (), "Perú",
        "Pendiente de lectura segura de metadatos",
        "INGEMMET declara GEOCATMIN público y de uso gratuito; falta validar la capa concreta.",
        # 26-oct-2026: el TLS se resuelve agregando el intermedio Sectigo OV R36 (ver identify_layers.py), pero el servicio
        # del inventario nacional (SERV_PERUALERTA) figura detenido; los mapas volcánicos sí se leen por identify.
        unavailable_reason="El inventario nacional de peligros geológicos (SERV_PERUALERTA) no está publicado en el servidor de INGEMMET (detenido al 26-oct-2026).",
    ),
    "senamhi-idesep": OfficialLayer(
        "senamhi-idesep", "SENAMHI · IDESEP", "Catálogo oficial WFS meteorológico y climático",
        "https://idesep.senamhi.gob.pe/geoserver/g_05_01/ows", (), "Perú; depende de cada feature type WFS",
        "Depende del producto; catálogo WFS 2.0 accesible", PUBLIC_LICENSE_NOTE,
        unavailable_reason="El catálogo está verificado, pero aún no se seleccionó una capa territorial de amenaza para este contrato.",
    ),
}


def _cache_max_age(source: OfficialLayer, default_hours: int) -> timedelta:
    """Use a courteous longer TTL for rate-sensitive Ministerio de Cultura SIGDA layers."""
    if source.source_id.startswith("cultura-"):
        return CULTURA_CACHE_TTL
    return timedelta(hours=default_hours)


def _esri_geometry(geojson: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    kind, coords = geojson["type"], geojson["coordinates"]
    sr = {"wkid": 4326}
    if kind == "Point":
        return "esriGeometryPoint", {"x": coords[0], "y": coords[1], "spatialReference": sr}
    if kind == "LineString":
        return "esriGeometryPolyline", {"paths": [coords], "spatialReference": sr}
    rings = [ring for polygon in coords for ring in polygon] if kind == "MultiPolygon" else coords
    return "esriGeometryPolygon", {"rings": rings, "spatialReference": sr}


def _safe_attributes(attributes: dict[str, Any]) -> dict[str, Any]:
    cleaned: dict[str, Any] = {}
    for key, value in attributes.items():
        if isinstance(value, (str, int, float, bool)) or value is None:
            cleaned[str(key)] = value[:1000] if isinstance(value, str) else value
    return cleaned


class TerritoryConnector:
    def __init__(self, *, settings: Settings | None = None, transport: httpx.AsyncBaseTransport | None = None):
        self.settings = settings or get_settings()
        self.transport = transport
        self.cache = RawPayloadCache(self.settings.cache_dir, "territory")

    async def _layer_query(self, source: OfficialLayer, layer_id: int, geometry_type: str, geometry: dict[str, Any]):
        descriptor = {"source": source.source_id, "layer": layer_id, "type": geometry_type, "geometry": geometry, "v": 1}
        cache_key = self.cache.request_key(descriptor)
        cached = self.cache.get(cache_key, max_age=_cache_max_age(source, self.settings.cache_ttl_hours))
        if cached:
            return json.loads(cached.content), cached.downloaded_at, Provenance.CACHED, None
        endpoint = f"{source.base_url}/{layer_id}/query"
        parsed = urlparse(endpoint)
        if parsed.scheme != "https" or parsed.hostname is None:
            raise TerritoryConnectorError("La capa territorial no usa un endpoint HTTPS válido.")
        form = {
            "f": "json", "where": "1=1", "geometry": json.dumps(geometry, separators=(",", ":")),
            "geometryType": geometry_type, "inSR": "4326", "outSR": "4326",
            "spatialRel": "esriSpatialRelIntersects", "outFields": "*", "returnGeometry": "false",
            "resultRecordCount": "100",
        }
        try:
            async with httpx.AsyncClient(timeout=TIMEOUT, transport=self.transport, follow_redirects=False) as client:
                response = await client.post(endpoint, data=form)
                response.raise_for_status()
            payload = response.json()
            if payload.get("error"):
                raise TerritoryConnectorError(str(payload["error"].get("message", "ArcGIS devolvió un error")))
        except (httpx.HTTPError, ValueError, TerritoryConnectorError) as exc:
            # El proveedor falló: si hay una copia válida anterior de la misma consulta se muestra, con su fecha y el motivo.
            stale = self.cache.last_valid(cache_key)
            if stale is None:
                raise
            return json.loads(stale.content), stale.downloaded_at, Provenance.CACHED, str(exc) or type(exc).__name__
        raw = self.cache.put(cache_key, response.content, suffix=".json")
        return payload, raw.downloaded_at, Provenance.REAL, None

    async def _source_query(self, source: OfficialLayer, geometry_type: str, geometry: dict[str, Any]):
        limitations = [*source.limitations,
            "Cero intersecciones significa solo que el servicio no devolvió objetos; no demuestra ausencia de riesgo o restricción."]
        common = dict(source_id=source.source_id, organization=source.organization, dataset=source.dataset,
            source_url=source.base_url, crs="EPSG:4326 en la solicitud", coverage=source.coverage,
            scale_or_resolution=source.scale_or_resolution, license=source.license)
        if source.unavailable_reason:
            return TerritorialSourceResult(status="DATA_UNAVAILABLE", provenance=Provenance.UNAVAILABLE,
                limitations=[source.unavailable_reason, *limitations], **common)
        try:
            payloads = await asyncio.gather(
                *(self._layer_query(source, layer_id, geometry_type, geometry) for layer_id in source.layer_ids))
        except (httpx.HTTPError, ValueError, TerritoryConnectorError) as exc:
            return TerritorialSourceResult(status="DATA_UNAVAILABLE", provenance=Provenance.UNAVAILABLE,
                limitations=[f"El servicio oficial no respondió con datos utilizables: {exc}", *limitations], **common)
        features, timestamps, provenances, stale = [], [], [], []
        exceeded = False
        for layer_id, (payload, downloaded_at, provenance, stale_reason) in zip(source.layer_ids, payloads, strict=True):
            timestamps.append(downloaded_at); provenances.append(provenance)
            if stale_reason:
                stale.append((downloaded_at, stale_reason))
            exceeded = exceeded or bool(payload.get("exceededTransferLimit"))
            layer_name = payload.get("name") or f"layer-{layer_id}"
            for feature in payload.get("features", []):
                features.append(TerritorialFeature(layer_id=layer_id, layer_name=str(layer_name),
                    attributes=_safe_attributes(feature.get("attributes", {}))))
        if exceeded:
            limitations.append("La respuesta superó 100 objetos; el detalle se truncó y no es un conteo exhaustivo.")
        # Con alguna capa servida de su última copia válida, la fecha que se informa es la de la copia más antigua.
        note = stale_copy_note(stale[0][1], min(stamp for stamp, _ in stale)) if stale else None
        if note:
            limitations.insert(0, note)
        latest = min(stamp for stamp, _ in stale) if stale else (max(timestamps) if timestamps else None)
        return TerritorialSourceResult(status="READY", intersection_count=len(features), features=features,
            provenance=Provenance.CACHED if provenances and all(p == Provenance.CACHED for p in provenances) else Provenance.REAL,
            downloaded_at=latest.astimezone(timezone.utc) if latest else None,
            limitations=limitations, stale_note=note, **common)

    async def query(self, request: TerritorialQueryRequest) -> TerritorialQueryResponse:
        try:
            inspected = inspect_geometry(request.geometry)
            shape(request.geometry)
        except (GeometryValidationError, ValueError) as exc:
            raise TerritoryConnectorError(str(exc)) from exc
        geometry_type, geometry = _esri_geometry(request.geometry)
        source_ids = request.source_ids or list(LAYERS)
        unknown = sorted(set(source_ids) - set(LAYERS))
        if unknown:
            raise TerritoryConnectorError(f"Fuentes territoriales desconocidas: {', '.join(unknown)}")
        sources = await asyncio.gather(*(self._source_query(LAYERS[item], geometry_type, geometry) for item in source_ids))
        return TerritorialQueryResponse(generated_at=datetime.now(timezone.utc), geometry_type=inspected.geometry_type,
            sources=list(sources), note="Intersecciones WGS84 contra servicios oficiales; una respuesta vacía no prueba ausencia de amenaza o restricción.")
