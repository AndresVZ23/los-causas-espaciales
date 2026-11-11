"""Alcance global: país de un punto, alertas del mundo (GDACS con NASA EONET) y búsqueda de lugares. Sin red."""

import asyncio
import json
from datetime import date, datetime, timedelta, timezone

import httpx
import pytest
from fastapi.testclient import TestClient

from backend.app.connectors.cache import RawPayloadCache
from backend.app.connectors.gdacs import events as gdacs
from backend.app.connectors.http_json import JsonSourceError, cached_json
from backend.app.connectors.nasa import eonet
from backend.app.connectors.openmeteo import geocoding
from backend.app.geospatial.countries import country_at, touches_peru
from backend.app.main import app
from backend.app.orchestration import world_alerts as world
from backend.app.schemas.analysis import Provenance

TODAY = date(2026, 11, 10)


def _gdacs(event_type, event_id, level, name, country, start, end, lon, lat, current="false", severity="Magnitude 0 "):
    return {"type": "Feature", "geometry": {"type": "Point", "coordinates": [lon, lat]},
            "properties": {"eventtype": event_type, "eventid": event_id, "alertlevel": level, "name": name, "country": country, "fromdate": f"{start}T00:00:00",
                           "todate": f"{end}T00:00:00", "iscurrent": current, "severitydata": {"severitytext": severity},
                           "url": {"report": f"https://www.gdacs.org/report.aspx?eventid={event_id}"}}}


GDACS_PAYLOAD = {"features": [
    _gdacs("TC", 1001, "Red", "Tropical Cyclone MURASU-26", "India", "2026-11-01", "2026-11-03", 80.2, 15.8, severity="Hurricane/Typhoon > 74 mph"),
    _gdacs("FL", 2002, "Green", "Flood in Peru", "Peru", "2026-10-26", "2026-11-06", -81.0, -4.16),
    _gdacs("FL", 2003, "Green", "Flood in Chile", "Chile", "2026-10-26", "2026-11-06", -71.0, -33.0),
    _gdacs("DR", 3003, "Orange", "Drought in A, B, C, D, E", "Belize, Costa Rica, Cuba, Honduras, Haiti", "2026-04-21", "2026-11-08", -95.4, 18.6,
           severity="Medium impact for agricultural drought in 1012801 km2"),
    {"type": "Feature", "geometry": None, "properties": {"eventtype": "EQ", "eventid": 9, "alertlevel": "Red"}},     # sin punto: se descarta
    _gdacs("XX", 4004, "Red", "Tipo desconocido", "Nowhere", "2026-11-01", "2026-11-02", 0, 0),                      # tipo desconocido: se descarta
]}
EONET_PAYLOAD = {"events": [
    {"id": "EONET_1", "title": "Tropical Cyclone Murasu", "categories": [{"id": "severeStorms"}], "sources": [{"url": "https://example.org/jtwc"}],
     "geometry": [{"date": "2026-10-31T00:00:00Z", "type": "Point", "coordinates": [84.0, 13.0]},
                  {"date": "2026-11-03T06:00:00Z", "type": "Point", "coordinates": [80.9, 15.5], "magnitudeValue": 85.0, "magnitudeUnit": "kts"}]},
    {"id": "EONET_2", "title": "Typhoon Cempaka", "categories": [{"id": "severeStorms"}], "sources": [],
     "geometry": [{"date": "2026-11-09T00:00:00Z", "type": "Point", "coordinates": [135.0, 18.0]}]},
    {"id": "EONET_3", "title": "Some Fire", "categories": [{"id": "wildfires"}], "geometry": [{"date": "2026-11-09T00:00:00Z", "type": "Point", "coordinates": [-120.0, 40.0]}]},
    {"id": "EONET_4", "title": "Iceberg", "categories": [{"id": "seaLakeIce"}], "geometry": [{"date": "2026-11-09T00:00:00Z", "type": "Point", "coordinates": [0, -70]}]},
]}


def test_country_lookup_tolerates_simplified_coasts_and_refuses_open_sea():
    assert country_at(-70.934, -17.193).iso3 == "PER"          # Moquegua
    assert country_at(-71.34, -17.64).iso3 == "PER"            # Ilo, sobre la costa simplificada
    assert country_at(36.82, -1.28).iso3 == "KEN" and country_at(-5.99, 37.39).iso3 == "ESP"
    assert country_at(-140.0, 0.0) is None                      # mar abierto: sin país adivinado
    assert touches_peru({"type": "Point", "coordinates": [-71.34, -17.64]})
    assert not touches_peru({"type": "Point", "coordinates": [36.82, -1.28]})
    assert not touches_peru({"type": "LineString", "coordinates": [[-78.5, -0.2], [-78.4, -0.1]]})   # Quito


def test_gdacs_and_eonet_parsers_keep_only_complete_known_events():
    parsed = gdacs.parse_events(GDACS_PAYLOAD)
    assert [item["id"] for item in parsed] == ["gdacs-TC-1001", "gdacs-FL-2002", "gdacs-FL-2003", "gdacs-DR-3003"]
    flood = parsed[1]
    assert flood["level"] == "green" and flood["severity"] is None and flood["current"] is False     # «Magnitude 0» no es un dato
    assert flood["started"] == date(2026, 10, 26) and flood["url"].endswith("eventid=2002")
    events = eonet.parse_events(EONET_PAYLOAD)
    assert [item["id"] for item in events] == ["eonet-EONET_1", "eonet-EONET_2", "eonet-EONET_3"]    # el hielo marino no es un tipo listado
    assert events[0]["latitude"] == 15.5 and events[0]["severity"] == "85 kts" and events[0]["url"] == "https://example.org/jtwc"


def test_gdacs_combined_response_is_cached_when_either_query_is_cached():
    connector = object.__new__(gdacs.GdacsConnector)
    newer = datetime(2026, 11, 10, 12, tzinfo=timezone.utc)
    older = datetime(2026, 11, 10, 11, tzinfo=timezone.utc)
    responses = iter([
        (gdacs.parse_events({"features": [GDACS_PAYLOAD["features"][0]]}), Provenance.REAL, newer, None),
        (gdacs.parse_events({"features": [GDACS_PAYLOAD["features"][1]]}), Provenance.CACHED, older, None),
    ])

    async def search(_params):
        return next(responses)

    connector._search = search
    events, provenance, downloaded_at, stale = asyncio.run(connector.events(TODAY, 60))

    assert len(events) == 2
    assert provenance == Provenance.CACHED
    assert downloaded_at == older
    assert stale is None


def test_merge_marks_the_second_witness_and_lists_unmatched_nasa_events():
    alerts = world.merge_alerts(gdacs.parse_events(GDACS_PAYLOAD), eonet.parse_events(EONET_PAYLOAD))
    by_id = {alert.id: alert for alert in alerts}
    cyclone = by_id["gdacs-TC-1001"]
    assert cyclone.also_seen_by == ["NASA EONET"] and cyclone.title == "Tropical Cyclone MURASU-26" and cyclone.level == "red"
    assert "eonet-EONET_1" not in by_id                                   # ya está representado por su pareja de GDACS
    assert by_id["eonet-EONET_2"].level == "none" and by_id["eonet-EONET_2"].current
    assert "eonet-EONET_3" not in by_id                                   # los incendios de EONET solo sirven para el cruce
    peru = by_id["gdacs-FL-2002"]
    assert peru.in_peru and peru.title == "Inundación" and peru.place == "Peru"
    assert "gdacs-FL-2003" not in by_id                                   # una alerta verde fuera del Perú no se lista
    drought = by_id["gdacs-DR-3003"]
    assert drought.title == "Sequía" and drought.place == "Belize, Costa Rica, Cuba y 2 países más" and drought.also_seen_by == []
    assert alerts[0].current                                              # primero lo vigente


def test_same_event_needs_kind_distance_and_dates():
    base = {"kind": "flood", "started": date(2026, 11, 1), "updated": date(2026, 11, 5), "latitude": -5.0, "longitude": -80.6}
    near = {"kind": "flood", "started": date(2026, 11, 2), "updated": date(2026, 11, 6), "latitude": -5.2, "longitude": -80.7}
    assert world.same_event(base, near)
    assert not world.same_event(base, {**near, "kind": "wildfire"})
    assert not world.same_event(base, {**near, "latitude": -12.0})                                               # ~750 km
    assert not world.same_event(base, {**near, "started": date(2026, 12, 20), "updated": date(2026, 12, 25)})


def test_cached_json_serves_last_valid_copy_and_fails_without_one(tmp_path):
    calls = {"n": 0, "down": False}

    def handler(request: httpx.Request):
        calls["n"] += 1
        return httpx.Response(503) if calls["down"] else httpx.Response(200, json={"ok": True})

    cache = RawPayloadCache(tmp_path, "prueba")
    transport = httpx.MockTransport(handler)
    run = lambda url: asyncio.run(cached_json(cache, url, {"a": "1"}, max_age=timedelta(hours=1), transport=transport))  # noqa: E731
    first = run("https://example.org/a")
    again = run("https://example.org/a")
    assert first[1] == Provenance.REAL and again[1] == Provenance.CACHED and calls["n"] == 1 and again[3] is None
    for path in (tmp_path / "prueba" / "manifests").glob("*.json"):            # la copia vence para el uso normal
        manifest = json.loads(path.read_text(encoding="utf-8"))
        manifest["downloaded_at"] = (datetime.now(timezone.utc) - timedelta(days=2)).isoformat()
        path.write_text(json.dumps(manifest), encoding="utf-8")
    calls["down"] = True
    stale = run("https://example.org/a")
    assert stale[0] == {"ok": True} and stale[1] == Provenance.CACHED and "última copia válida" in stale[3]
    with pytest.raises(JsonSourceError):
        run("https://example.org/sin-copia")


def test_world_alerts_declares_a_source_that_is_down(monkeypatch):
    class Gdacs:
        async def events(self, today, window_days):
            return gdacs.parse_events(GDACS_PAYLOAD), Provenance.REAL, datetime(2026, 11, 10, tzinfo=timezone.utc), None

    class EonetDown:
        async def open_events(self, window_days):
            raise JsonSourceError("503")

    monkeypatch.setattr(world, "GdacsConnector", Gdacs)
    monkeypatch.setattr(world, "EonetConnector", EonetDown)
    response = asyncio.run(world.world_alerts(TODAY))
    assert [source.provenance for source in response.sources] == [Provenance.REAL, Provenance.UNAVAILABLE]
    assert "segundo testigo" in response.sources[1].note
    assert all(alert.source == "GDACS" and alert.also_seen_by == [] for alert in response.alerts) and len(response.alerts) == 3


def test_places_endpoint_returns_coordinates_and_rejects_short_queries(monkeypatch):
    class Geocoder:
        async def search(self, query):
            payload = {"results": [{"name": "Nairobi", "admin1": "Nairobi", "country": "Kenia", "country_code": "KE", "latitude": -1.28333, "longitude": 36.81667, "population": 4397073},
                                   {"name": "Sin coordenadas", "country": "X"}]}
            return geocoding.parse_places(payload), Provenance.REAL, datetime(2026, 11, 10, tzinfo=timezone.utc), None

    monkeypatch.setattr("backend.app.api.world.GeocodingConnector", Geocoder)
    client = TestClient(app)
    response = client.get("/api/v1/world/places", params={"q": "Nairobi"})
    assert response.status_code == 200
    places = response.json()["places"]
    assert len(places) == 1 and places[0]["detail"] == "Kenia" and places[0]["latitude"] == -1.28333      # la región repite el nombre: no se duplica
    assert client.get("/api/v1/world/places", params={"q": "N"}).status_code == 422
