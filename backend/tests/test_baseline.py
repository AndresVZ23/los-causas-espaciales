"""Línea base ambiental y patrimonial (módulos 4 y 5) con fuentes sintéticas: sin red, contrato C2, MODIS y capas."""

import asyncio
from datetime import date, datetime, timezone
from math import pi

import pytest
from pydantic import ValidationError
from shapely.geometry import shape

from backend.app.connectors.nasa.modis_subsets import ModisBand, ModisDate, ModisGrid, ModisSubsetError
from backend.app.geospatial.buffers import buffer_km
from backend.app.geospatial.geometry import GEOD
from backend.app.geospatial.modis_grid import pixel_centers, pixels_inside
from backend.app.orchestration.conformance import envelope_violations
from backend.app.schemas.analysis import Point, Provenance
from backend.app.schemas.baseline import BaselineGeometry, BaselineRequest
from backend.app.schemas.data_sources import TerritorialFeature, TerritorialQueryResponse, TerritorialSourceResult
from backend.app.schemas.screening import PipelineStatus, QuestionStatus, Sector
from backend.app.sectors import baseline, baseline_vegetation
from backend.app.sectors.baseline_layers import summarize_layer

# Ventana 9×9 real del ORNL alrededor de Moquegua (-17.193, -70.934), verificada el 2026-10-24.
GRID = ModisGrid(xllcorner=-7536012.97, yllcorner=-1912786.51, cellsize=231.656358264, nrows=9, ncols=9)
STAMP = datetime(2026, 10, 24, tzinfo=timezone.utc)


def _band(product: str, band: str, value_for_year) -> ModisBand:
    years = range(2000, 2026) if product != "MCD12Q1" else range(2001, 2025)
    return ModisBand(product=product, band=band, units="", scale=None, grid=GRID,
                     dates=[ModisDate(date(year, 3, 1), [value_for_year(year)] * 81) for year in years],
                     provenance=Provenance.CACHED, downloaded_at=STAMP, source_url=f"https://modis.ornl.gov/rst/api/v1/{product}/subset")


class FakeModis:
    """Suelo sin vegetación que sube 0.5 puntos por año; vegetación que baja; NPP de relleno (desierto); cobertura que cambia en 2024."""

    def __init__(self, *args, **kwargs):
        pass

    async def band(self, product, band, latitude, longitude, km):
        if band == "Percent_NonVegetated":
            return _band(product, band, lambda y: 70 + (y - 2000) // 2)
        if band == "Percent_NonTree_Vegetation":
            return _band(product, band, lambda y: 30 - (y - 2000) // 2)
        if band == "Percent_Tree_Cover":
            return _band(product, band, lambda y: 0)
        if band == "Npp_500m":
            return _band(product, band, lambda y: 32766)
        if band == "LC_Type1":
            return _band(product, band, lambda y: 16 if y < 2024 else 13)
        raise ModisSubsetError("banda inesperada")


FEATURES = {
    "cultura-das": [{"proyecto": "Diagnóstico Arqueológico Superficial del Proyecto X", "cod_das_informe": "DAS-2025-0000020", "categoria": "Electrificación",
                     "fecha_informe": 1752624000000, "enlace": "https://sigda.cultura.gob.pe/cirasdsfl/das/2025-0082264.pdf"}],
    "cultura-archaeology": [{"nombre": "S.A. ALGARROBAL 1", "clasificac": "Sitio Arqueológico", "distrito": "ILO"}] * 2,
    "minam-coastal-lomas": [{"nombdist": "ILO", "nombprov": "ILO", "nombdep": "MOQUEGUA"}],
    "ana-water-bodies": [{"NOMBRE_CA": "Río Ilo", "CATEGORIA": "Categoría 3", "NOMBRE_UH": "Cuenca Ilo - Moquegua"}],
    "cenepred-flood-risk": [{"nombdist": "ILO", "nombprov": "ILO", "nriesgo_in": "Alto", "niv_sinu": "Medio", "nvuln_in": "Alto"}],
    "ana-critical-points": [{"RIO_QDA": "Ilo", "SECTOR": "Valle de Ilo", "CUENCA": "Ilo-Moquegua", "DISTRITO": "Ilo, Pacocha y El Algarrobal"}],
}


class FakeTerritory:
    """Capas sintéticas: registros en cuatro fuentes, una fuente caída y el resto sin intersecciones."""

    def __init__(self, *args, **kwargs):
        pass

    async def query(self, request):
        results = []
        for source_id in request.source_ids:
            common = dict(source_id=source_id, organization="Prueba", dataset=f"Capa {source_id}", source_url="https://example.gob.pe",
                          crs="EPSG:4326", coverage="Perú", scale_or_resolution="—", license="—")
            if source_id == "cultura-world-heritage":
                results.append(TerritorialSourceResult(status="DATA_UNAVAILABLE", provenance=Provenance.UNAVAILABLE,
                                                       limitations=["El servicio oficial no respondió con datos utilizables: prueba"], **common))
                continue
            features = [TerritorialFeature(layer_id=0, layer_name="capa", attributes=a) for a in FEATURES.get(source_id, [])]
            results.append(TerritorialSourceResult(status="READY", intersection_count=len(features), features=features, provenance=Provenance.REAL,
                                                   downloaded_at=STAMP, limitations=["Cero intersecciones no prueba ausencia."], **common))
        return TerritorialQueryResponse(generated_at=STAMP, geometry_type="Polygon", sources=results, note="prueba")


class FakeIdentify:
    """Susceptibilidad muestreada (dos puntos: alto y muy alto) y una zona de peligro volcánico, sin red."""

    def __init__(self, *args, **kwargs):
        pass

    @staticmethod
    def _result(source_id, features):
        return TerritorialSourceResult(source_id=source_id, organization="Prueba", dataset=f"Capa {source_id}", status="READY",
                                       intersection_count=len(features), features=features, provenance=Provenance.REAL, downloaded_at=STAMP,
                                       source_url="https://example.gob.pe", crs="EPSG:4326", coverage="Perú", scale_or_resolution="—", license="—",
                                       limitations=["Muestreo de 2 punto(s) dentro del área."])

    async def cenepred_susceptibility(self, geometry, representative):
        return self._result("cenepred-susceptibility", [
            TerritorialFeature(layer_id=2, layer_name="Susceptibilidad a movimientos en masa", attributes={"capa": "Susceptibilidad a movimientos en masa", "nivel": level})
            for level in ("Alto", "Muy alto")])

    async def volcanic_hazards(self, geometry):
        return self._result("ingemmet-volcanic-hazards", [TerritorialFeature(layer_id=2, layer_name="Peligro alto",
                                                                             attributes={"volcan": "Misti", "zona": "Peligro alto", "descripcion": "Zona severamente afectada."})])


async def _no_terrain(points):
    return None, "NASADEM sin red en la prueba.", 0.0


@pytest.fixture
def patched(monkeypatch):
    monkeypatch.setattr(baseline_vegetation, "ModisSubsetConnector", FakeModis)
    monkeypatch.setattr(baseline, "TerritoryConnector", FakeTerritory)
    monkeypatch.setattr(baseline, "IdentifyLayersConnector", FakeIdentify)
    monkeypatch.setattr(baseline, "extract_terrain", _no_terrain)
    monkeypatch.setattr(baseline, "RETRY_SECONDS", 0)
    monkeypatch.setattr(baseline, "PACE_SECONDS", 0)


def _request(**overrides):
    data = dict(sites=[Point(latitude=-17.193, longitude=-70.934, label="Moquegua")],
                geometries=[BaselineGeometry(id="via", label="Vía de acceso", geometry={"type": "LineString", "coordinates": [[-70.94, -17.20], [-70.93, -17.19]]})])
    data.update(overrides)
    return BaselineRequest(**data)


def test_pixel_centers_match_the_requested_point():
    lon, lat = pixel_centers(GRID)[40]          # celda central de una ventana 9×9
    assert lon == pytest.approx(-70.934, abs=0.002) and lat == pytest.approx(-17.193, abs=0.002)


def test_buffer_is_geodesic_and_selects_the_pixels_inside():
    circle = buffer_km({"type": "Point", "coordinates": [-70.934, -17.193]}, 1.0)
    area_km2 = abs(GEOD.geometry_area_perimeter(shape(circle))[0]) / 1e6
    assert area_km2 == pytest.approx(pi, rel=0.01)
    inside, fallback = pixels_inside(GRID, circle, -70.934, -17.193)
    assert not fallback and 55 <= len(inside) <= 63   # π km² / 0.0537 km² por píxel ≈ 58.5


def test_tiny_area_falls_back_to_the_nearest_pixel():
    tiny = buffer_km({"type": "Point", "coordinates": [-70.934, -17.193]}, 0.02)
    inside, fallback = pixels_inside(GRID, tiny, -70.934, -17.193)
    assert fallback and len(inside) == 1


def test_environment_baseline_detects_vegetation_loss_and_conforms(patched):
    result = asyncio.run(baseline.run_baseline_screening(_request(), Sector.ENVIRONMENT))
    assert envelope_violations(result) == []
    site = result.baselines[0]
    assert site.subject == "Moquegua (radio 1 km)" and site.area_km2 == pytest.approx(pi, rel=0.01)
    bare = next(item for item in site.vegetation if item.variable == "VCF_BARE")
    assert bare.trend.direction == "increasing" and bare.significant_after_bh
    assert bare.trend.slope_per_year == pytest.approx(0.5, abs=0.01)
    assert all(item.variable != "NPP" for item in site.vegetation)          # relleno MODIS: no se inventa una serie
    assert any("ningún año" in note for note in site.vegetation_notes)
    assert site.land_cover.changed_percent == 100.0 and site.land_cover.classes[0].label.startswith("Suelo desnudo")
    groups = {group.variable: group for group in site.land_cover_check.groups}            # WorldCover sintético: 80 % desnudo, 20 % pastizal
    assert (groups["VCF_BARE"].modis_percent, groups["VCF_BARE"].worldcover_percent) == (80.0, 80.0)
    assert any(d.title == "Moquegua (radio 1 km): MODIS y ESA WorldCover coinciden en la cobertura" for d in result.discoveries)
    corridor = result.subjects[1]
    assert corridor.geometry["type"] == "Polygon"                            # la línea se amplía con el buffer
    assert result.nasa_questions[0].status == QuestionStatus.ANSWERED
    assert "ventana MODIS" in result.nasa_questions[1].evidence[0]
    assert "capa minam-coastal-lomas (1)" in result.nasa_questions[4].answer.lower()   # lo que las capas registran entra a la quinta pregunta
    assert any(gap.dataset.startswith("SENACE") for gap in result.data_gaps)
    assert next(s for s in result.pipeline if s.key == "finance").status == PipelineStatus.UNAVAILABLE


def test_heritage_baseline_reports_records_without_inventing_trends(patched):
    result = asyncio.run(baseline.run_baseline_screening(_request(), Sector.HERITAGE))
    assert envelope_violations(result) == []
    assert result.trend_findings == [] and result.baselines[0].vegetation == []
    assert all(q.status == QuestionStatus.INSUFFICIENT for q in result.nasa_questions[:4])
    das = next(layer for layer in result.baselines[0].layers if layer.source_id == "cultura-das")
    assert das.highlights[0].link.endswith(".pdf") and "2025-07-16" in das.highlights[0].detail
    archaeology = next(layer for layer in result.baselines[0].layers if layer.source_id == "cultura-archaeology")
    assert archaeology.highlights[0].count == 2                              # registros iguales se agrupan
    assert any(gap.dataset == "Capa cultura-world-heritage" for gap in result.data_gaps)
    down = next(layer for layer in result.baselines[0].layers if layer.source_id == "cultura-world-heritage")
    assert down.status == "DATA_UNAVAILABLE" and down.intersection_count is None      # caída: nunca un cero
    assert next(s for s in result.pipeline if s.key == "analysis").status == PipelineStatus.UNAVAILABLE


def _pdf_text(pdf: bytes) -> str:
    from io import BytesIO

    from pypdf import PdfReader
    return " ".join(page.extract_text() for page in PdfReader(BytesIO(pdf)).pages)


def test_heritage_pdf_carries_records_links_and_honest_footer(patched):
    from fastapi.testclient import TestClient

    from backend.app.main import app
    result = asyncio.run(baseline.run_baseline_screening(_request(), Sector.HERITAGE))
    response = TestClient(app).post("/api/v1/reports/executive-pdf", json=result.model_dump(mode="json"))
    assert response.status_code == 200 and response.headers["content-type"] == "application/pdf"
    text = _pdf_text(response.content)
    assert "Línea base por área de estudio" in text and "Moquegua (radio 1 km)" in text
    assert "Diagnóstico Arqueológico Superficial del Proyecto X" in text and "S.A. ALGARROBAL 1" in text
    assert "No disponible" in text                                                 # la capa caída no se lee como cero
    assert "no sustituye el CIRA ni una opinión legal" in text and "NASA POWER, API" not in text   # pie propio de Patrimonio
    assert b"/URI" in response.content and b"2025-0082264.pdf" in response.content  # enlace al PDF del DAS


def test_environment_pdf_lists_modis_series_and_sources(patched):
    from backend.app.reports.executive_pdf import render_executive_pdf
    result = asyncio.run(baseline.run_baseline_screening(_request(), Sector.ENVIRONMENT))
    text = _pdf_text(render_executive_pdf(result))
    assert "Suelo sin vegetación" in text and "MOD44B" in text and "Cobertura IGBP" in text
    assert "ORNL DAAC" in text and "NASA POWER, API" not in text
    assert "ningún año" in text                                                    # productividad sin serie, declarada


def test_hazards_module_reads_rainfall_extremes_and_risk_levels(patched, monkeypatch):
    from backend.app.orchestration import extraction
    from backend.app.reports.executive_pdf import render_executive_pdf
    from backend.tests.test_solar import FakePowerConnector
    monkeypatch.setattr(extraction, "PowerConnector", FakePowerConnector)
    result = asyncio.run(baseline.run_baseline_screening(_request(), Sector.HAZARDS))
    assert envelope_violations(result) == []
    area = result.baselines[0]
    assert [item.variable for item in area.climate] == ["PRECTOTCORR"]
    assert {item.variable for item in area.extremes} >= {"RX1DAY", "RX5DAY", "CDD"}
    assert all(item.countercheck is not None for item in area.extremes)               # contraste IMERG adjunto
    flood = next(layer for layer in area.layers if layer.source_id == "cenepred-flood-risk")
    assert flood.highlights[0].label == "Ilo (Ilo)" and flood.highlights[0].detail == "riesgo alto · susceptibilidad medio · vulnerabilidad alto"
    assert not any("LHASA" in gap.dataset for gap in result.data_gaps)                 # LHASA ya no es brecha: entra como capa
    nasa = {layer.source_id: layer for layer in area.layers if layer.source_id.startswith("nasa-")}
    assert set(nasa) == {"nasa-landslide-susceptibility", "nasa-lhasa-nowcast", "nasa-coolr-reports"} and all(l.status == "READY" for l in nasa.values())
    susceptibility = next(layer for layer in area.layers if layer.source_id == "cenepred-susceptibility")
    assert {h.label for h in susceptibility.highlights} == {"Susceptibilidad a movimientos en masa: alto", "Susceptibilidad a movimientos en masa: muy alto"}
    volcanic = next(layer for layer in area.layers if layer.source_id == "ingemmet-volcanic-hazards")
    assert volcanic.highlights[0].label == "Volcán Misti: peligro alto"
    assert result.period.startswith("2001-01-01/")
    assert next(s for s in result.pipeline if s.key == "analysis").status != PipelineStatus.UNAVAILABLE
    text = _pdf_text(render_executive_pdf(result))
    assert "Amenazas por área de estudio" in text and "Índice ETCCDI" in text and "GPM IMERG" in text and "Valle de Ilo" in text


def test_layer_served_from_its_last_valid_copy_is_declared_everywhere(patched, monkeypatch):
    from backend.app.orchestration import extraction
    from backend.app.reports.executive_pdf import render_executive_pdf
    from backend.tests.test_solar import FakePowerConnector
    note = "El servicio oficial no respondió hoy (Token Required); se muestra la última copia válida, del 27-oct-2026."

    class ClosedCenepred(FakeTerritory):
        """CENEPRED exige token: su capa de inundación llega de la última copia válida, con la nota del conector."""

        async def query(self, request):
            response = await super().query(request)
            for source in response.sources:
                if source.source_id == "cenepred-flood-risk":
                    source.provenance, source.stale_note = Provenance.CACHED, note
                    source.limitations.insert(0, note)
            return response

    monkeypatch.setattr(extraction, "PowerConnector", FakePowerConnector)
    monkeypatch.setattr(baseline, "TerritoryConnector", ClosedCenepred)
    result = asyncio.run(baseline.run_baseline_screening(_request(), Sector.HAZARDS))

    assert envelope_violations(result) == []
    flood = next(layer for layer in result.baselines[0].layers if layer.source_id == "cenepred-flood-risk")
    assert flood.status == "READY" and flood.stale_note == note and flood.intersection_count == 1      # el dato se usa, con su advertencia
    gap = next(item for item in result.data_gaps if item.dataset.endswith("última copia válida"))
    assert gap.status == Provenance.CACHED and gap.impact == note and "credenciales" in gap.next_action
    assert sum(item.dataset.endswith("última copia válida") for item in result.data_gaps) == 1          # una vez, aunque haya dos áreas
    agreement = next(item for item in result.discoveries if "coinciden en riesgo de inundación" in item.title)
    assert "se muestra la última copia válida, del 27-oct-2026" in agreement.detail
    text = _pdf_text(render_executive_pdf(result))
    assert "última copia válida" in text and "Token Required" in text


def test_area_outside_peru_skips_peruvian_layers_and_declares_it(patched, monkeypatch):
    from backend.app.orchestration import extraction
    from backend.tests.test_solar import FakePowerConnector
    asked: list[str] = []

    class Spy(FakeTerritory):
        async def query(self, request):
            asked.extend(request.source_ids)
            return await super().query(request)

    monkeypatch.setattr(extraction, "PowerConnector", FakePowerConnector)
    monkeypatch.setattr(baseline, "TerritoryConnector", Spy)
    request = BaselineRequest(sites=[Point(latitude=-1.2833, longitude=36.8167, label="Nairobi")])
    result = asyncio.run(baseline.run_baseline_screening(request, Sector.HAZARDS))

    assert envelope_violations(result) == []
    assert asked == []                                                         # ningún servicio peruano se consultó para Kenia
    assert {layer.source_id for layer in result.baselines[0].layers} == {"nasa-landslide-susceptibility", "nasa-coolr-reports", "nasa-lhasa-nowcast"}
    gap = next(item for item in result.data_gaps if item.dataset == "Capas oficiales nacionales fuera del Perú")
    assert "Kenia" in gap.impact and "Nairobi" in gap.impact
    assert not any("SINPAD" in item.dataset or "SENAMHI" in item.dataset for item in result.data_gaps)   # las brechas peruanas no aplican


def test_hazards_without_power_series_declares_the_gap(patched, monkeypatch):
    from backend.app.connectors.nasa.power import PowerConnectorError
    from backend.app.orchestration import extraction

    class Down:
        async def daily_point_multi(self, *args, **kwargs):
            raise PowerConnectorError("caída controlada")

    monkeypatch.setattr(extraction, "PowerConnector", Down)
    result = asyncio.run(baseline.run_baseline_screening(_request(), Sector.HAZARDS))
    assert envelope_violations(result) == []
    assert result.baselines[0].extremes == [] and result.trend_findings == []
    assert result.data_gaps[0].dataset == "NASA POWER · lluvia diaria" and "caída controlada" in result.data_gaps[0].impact


def test_rainfall_artifact_and_unbacked_trend_become_discoveries():
    from backend.app.orchestration.discoveries import rainfall_discoveries
    from backend.app.schemas.analysis import TrendResult
    from backend.app.schemas.climate import AtypicalYear, ExtremeCountercheck, ExtremeIndexSummary
    trend = TrendResult(method="MK", direction="increasing", slope_per_year=0.2, p_value=0.01, confidence_interval=None, significant=True,
                        valid_observations=25, interpretation="", limitations=[])
    check = lambda source, agreement: ExtremeCountercheck(source=source, valid_years=25, direction="no_trend", slope_per_year=0.0, adjusted_p_value=0.5,  # noqa: E731
                                                          significant_after_bh=False, agreement=agreement, annual_series=[])
    index = lambda code: ExtremeIndexSummary(  # noqa: E731
        variable=code, label="Lluvia máxima en 1 día" if code == "RX1DAY" else "Lluvia máxima en 5 días", description="", unit="mm", display_unit="mm",
        mean=22.6, minimum=1, maximum=300, valid_years=25, discarded_years=0, trend=trend, adjusted_p_value=0.02, significant_after_bh=code == "RX1DAY",
        annual_series=[], atypical_years=[AtypicalYear(year=2022, value=300.2, robust_z=89, countercheck_values={"GPM IMERG": 12.1, "CHIRPS (UCSB · NASA SERVIR)": 0.0})],
        counterchecks=[check("GPM IMERG", "sin_respaldo"), check("CHIRPS (UCSB · NASA SERVIR)", "sin_respaldo")])
    found = rainfall_discoveries([("Moquegua", [index("RX1DAY"), index("RX5DAY")])])
    artifact = [d for d in found if d.kind == "artefacto_probable"]
    assert len(artifact) == 1 and "2022" in artifact[0].title                     # un evento, aunque aparezca en dos índices
    assert "12 mm en IMERG" in artifact[0].detail and "0 mm en CHIRPS" in artifact[0].detail
    assert [d.kind for d in found if d.kind != "artefacto_probable"] == ["sin_respaldo"]
    # Al revés: CHIRPS e IMERG ven un cambio que MERRA-2 no.
    seen = check("CHIRPS (UCSB · NASA SERVIR)", "solo_contraste").model_copy(update={"slope_per_year": 0.4, "adjusted_p_value": 0.01})
    quiet = index("RX5DAY").model_copy(update={"atypical_years": [], "counterchecks": [seen, seen.model_copy(update={"source": "GPM IMERG"})]})
    only_satellites = rainfall_discoveries([("Ica", [quiet])])
    assert [d.kind for d in only_satellites] == ["coincidencia"] and "IMERG y CHIRPS" in only_satellites[0].title   # mismo orden que la tabla


def test_layer_summary_flags_truncated_responses():
    result = TerritorialSourceResult(source_id="cultura-qhapaq-nan", organization="Cultura", dataset="Qhapaq Ñan", status="READY", intersection_count=100,
                                     features=[TerritorialFeature(layer_id=1, layer_name="Proyección", attributes={"tramnomb": "Quilca - Sama"})] * 100,
                                     provenance=Provenance.REAL, source_url="https://sigda.cultura.gob.pe", crs="EPSG:4326", coverage="Perú",
                                     scale_or_resolution="—", license="—", limitations=["La respuesta superó 100 objetos; el detalle se truncó y no es un conteo exhaustivo."])
    layer = summarize_layer(result, "sociocultural")
    assert layer.truncated and layer.highlights[0].label == "Proyección de camino: Quilca - Sama" and layer.highlights[0].count == 100


def test_request_validation():
    with pytest.raises(ValidationError, match="entre 1 y 4"):
        BaselineRequest(sites=[])
    with pytest.raises(ValidationError):
        BaselineRequest(sites=[Point(latitude=-17.2, longitude=-70.9)], buffer_km=50)
    with pytest.raises(baseline.BaselineScreeningError, match="nombre distinto"):
        baseline.resolve_areas(BaselineRequest(sites=[Point(latitude=-17.2, longitude=-70.9, label="A"), Point(latitude=-17.3, longitude=-70.8, label="A")]))
