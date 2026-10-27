"""Deslizamientos de NASA (susceptibilidad global, LHASA del día, COOLR) y su cruce con CENEPRED, sin red."""

import asyncio
import json
from datetime import datetime, timezone
from urllib.parse import parse_qs

import httpx

from backend.app.connectors.nasa import landslides
from backend.app.core.config import Settings
from backend.app.geospatial.sampling import sample_points
from backend.app.orchestration.discoveries import landslide_discoveries
from backend.app.schemas.analysis import Provenance
from backend.app.schemas.data_sources import TerritorialFeature, TerritorialSourceResult
from backend.app.schemas.screening import DiscoveryKind
from backend.app.sectors.baseline_layers import summarize_layer

SQUARE = {"type": "Polygon", "coordinates": [[[-76.75, -11.98], [-76.65, -11.98], [-76.65, -11.90], [-76.75, -11.90], [-76.75, -11.98]]]}
CENTER = (-76.70, -11.94)
POINTS = sample_points(SQUARE, CENTER)


def _transport(values_for, coolr=None, status=200):
    """getSamples devuelve `values_for(i)` por punto (texto, como ArcGIS; "" = nodata); query devuelve `coolr`."""
    def handler(request: httpx.Request) -> httpx.Response:
        if status != 200:
            return httpx.Response(status, text="caído")
        form = {k: v[0] for k, v in parse_qs(request.content.decode()).items()}
        if request.url.path.endswith("/getSamples"):
            points = json.loads(form["geometry"])["points"]
            return httpx.Response(200, json={"samples": [{"locationId": i, "value": values_for(i)} for i in range(len(points))]})
        return httpx.Response(200, json=coolr or {"features": []})
    return httpx.MockTransport(handler)


def _connector(tmp_path, transport):
    return landslides.NasaLandslidesConnector(settings=Settings(_env_file=None, cache_dir=tmp_path), transport=transport)


def test_susceptibility_reads_classes_and_never_turns_zero_into_low(tmp_path):
    values = lambda i: "4.000000000" if i == 0 else "0.000000000" if i == 1 else "127" if i == 2 else "2"
    result = asyncio.run(_connector(tmp_path, _transport(values)).susceptibility(SQUARE, CENTER))
    assert result.status == "READY" and result.provenance == Provenance.REAL
    assert result.intersection_count == len(POINTS) - 2                          # el 0 (agua) y el nodata 127 no se cuentan
    assert result.features[0].attributes == {"clase": 4, "nivel": "Alta", "lon": CENTER[0], "lat": CENTER[1]}
    assert any("2 punto(s) sin clase" in note and "no se cuentan como susceptibilidad baja" in note for note in result.limitations)
    layer = summarize_layer(result, "amenazas")
    assert {h.label for h in layer.highlights} == {"Susceptibilidad NASA: alta", "Susceptibilidad NASA: baja"}
    again = asyncio.run(_connector(tmp_path, _transport(lambda i: "5")).susceptibility(SQUARE, CENTER))
    assert again.provenance == Provenance.CACHED and again.features[0].attributes["clase"] == 4   # caché: no rejuvenece ni cambia


def test_nowcast_keeps_missing_points_out_and_reports_the_maximum(tmp_path):
    values = lambda i: "0.0123" if i == 0 else "-9999" if i == 1 else "" if i == 2 else "0.0004"
    result = asyncio.run(_connector(tmp_path, _transport(values)).nowcast(SQUARE, CENTER))
    assert result.intersection_count == len(POINTS) - 2
    assert result.limitations[0] == f"Máximo en el área: 0.0123 en {CENTER[1]:.3f}, {CENTER[0]:.3f}."
    assert any(f"2 de {len(POINTS)} punto(s) sin valor" in note and "no se leen como cero" in note for note in result.limitations)
    labels = {h.label for h in summarize_layer(result, "amenazas").highlights}
    assert labels == {"Probabilidad LHASA entre 0.01 y 0.1", "Probabilidad LHASA menor que 0.001"}


def test_coolr_reports_are_translated_with_date_fatalities_and_precision(tmp_path):
    coolr = {"features": [{"attributes": {"event_date": 1486080000000, "event_title": "Mud Avalanche near Santiago de Tuna Kills Two",
                                          "landslide_category": "mudslide", "landslide_trigger": "continuous_rain", "fatality_count": 2,
                                          "location_accuracy": "10km", "event_import_source": "GLC", "source_link": "https://peru21.pe/x"}}]}
    result = asyncio.run(_connector(tmp_path, _transport(lambda i: "", coolr)).reports(SQUARE))
    highlight = summarize_layer(result, "amenazas").highlights[0]
    assert highlight.label == "Mud Avalanche near Santiago de Tuna Kills Two"
    assert highlight.detail == "2017-02-03 · flujo de lodo · lluvia continua · 2 fallecido(s) · precisión 10km"
    assert highlight.link == "https://peru21.pe/x"


def test_a_failed_service_is_unavailable_not_zero(tmp_path):
    result = asyncio.run(_connector(tmp_path, _transport(lambda i: "", status=503)).susceptibility(SQUARE, CENTER))
    assert result.status == "DATA_UNAVAILABLE" and result.intersection_count is None
    assert result.limitations[0].startswith("El servicio oficial no respondió")   # activa el reintento de la línea base


def _result(source_id, features):
    return TerritorialSourceResult(source_id=source_id, organization="Prueba", dataset=source_id, status="READY", intersection_count=len(features),
                                   features=features, provenance=Provenance.REAL, downloaded_at=datetime(2026, 10, 27, tzinfo=timezone.utc),
                                   source_url="https://example.org", crs="EPSG:4326", coverage="—", scale_or_resolution="—", license="—", limitations=[])


def _maps(national: list[str], nasa: list[int]):
    keys = [(-76.7 + i / 100, -11.9) for i in range(len(national))]
    cenepred = [TerritorialFeature(layer_id=2, layer_name="m", attributes={"capa": "Susceptibilidad a movimientos en masa", "nivel": level, "lon": x, "lat": y})
                for level, (x, y) in zip(national, keys)]
    cenepred.append(TerritorialFeature(layer_id=1, layer_name="i", attributes={"capa": "Susceptibilidad por inundaciones", "nivel": "Muy alto", "lon": keys[0][0], "lat": keys[0][1]}))
    global_ = [TerritorialFeature(layer_id=0, layer_name="g", attributes={"clase": value, "nivel": "x", "lon": x, "lat": y}) for value, (x, y) in zip(nasa, keys)]
    return {"cenepred-susceptibility": _result("cenepred-susceptibility", cenepred), "nasa-landslide-susceptibility": _result("nasa-landslide-susceptibility", global_)}


def test_national_and_global_maps_agree_point_by_point():
    found = landslide_discoveries("Chosica", _maps(["Alto", "Muy alto", "Medio"], [4, 4, 5]))   # el tercero difiere en dos clases
    assert [d.kind for d in found] == [DiscoveryKind.AGREEMENT]
    assert found[0].detail.startswith("En 2 de 3 puntos de muestreo") and "en 2 ambos marcan alta" in found[0].detail
    assert "CENEPRED: muy alto ×1, alto ×1, medio ×1." in found[0].detail          # la capa de inundaciones no entra


def test_maps_that_disagree_and_reports_where_maps_say_low():
    maps = _maps(["Muy alto", "Alto", "Bajo"], [1, 2, 2])
    found = landslide_discoveries("Ilo", maps)
    assert found[0].kind == DiscoveryKind.CONTRADICTION and "CENEPRED marca más alto en 2 y NASA en 0" in found[0].detail
    half = landslide_discoveries("Moquegua", _maps(["Alto", "Alto", "Alto", "Medio"], [2, 2, 4, 3]))   # la mitad no basta: hacen falta dos tercios
    assert half[0].kind == DiscoveryKind.CONTRADICTION and half[0].detail.startswith("Solo 2 de 4 puntos")
    low = _maps(["Bajo", "Medio"], [2, 3])
    low["nasa-coolr-reports"] = _result("nasa-coolr-reports", [TerritorialFeature(layer_id=0, layer_name="r", attributes={
        "titulo": "Huaico en la quebrada", "fecha": 1486080000000, "precision": "25km"})])
    found = landslide_discoveries("Valle", low)
    assert [d.kind for d in found] == [DiscoveryKind.AGREEMENT, DiscoveryKind.CONTRADICTION]
    assert "no marcan susceptibilidad alta" in found[1].title and "precisión de 25km" in found[1].detail and "en 2017" in found[1].detail


def test_reports_confirm_a_high_susceptibility_map():
    maps = _maps(["Alto"], [5])
    maps["nasa-coolr-reports"] = _result("nasa-coolr-reports", [TerritorialFeature(layer_id=0, layer_name="r", attributes={"titulo": t, "fecha": f})
                                                                for t, f in (("Chosica", 1427155200000), ("Ricardo Palma", 1234742400000))])
    found = landslide_discoveries("Chosica", maps)
    confirmed = next(d for d in found if d.kind == DiscoveryKind.CONFIRMED)
    assert "2 deslizamiento(s) reportado(s) entre 2009 y 2015 (Chosica; Ricardo Palma)" in confirmed.detail
    assert "CENEPRED y NASA marcan" in confirmed.detail and confirmed.sources == ["NASA COOLR", "CENEPRED", "NASA"]
