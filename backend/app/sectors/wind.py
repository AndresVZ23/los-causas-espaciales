"""Piloto eólico: screening comparativo de sitios sobre el contrato común C2.

La tendencia del viento sale de NASA POWER diario (MERRA-2, 50 y 10 m) y se contrasta con ERA5. La energía sale de
la serie horaria de NASA POWER llevada a la altura del buje y escalada al nivel medio del Atlas Eólico Global (250 m):
la celda de MERRA-2 no ve la aceleración local del viento. Validado el 30-oct-2026 con la producción COES 2024 de
Tres Hermanas (97.15 MW, 56.5 %) y Marcona (32.1 MW, 57.7 %): con el nivel del atlas el modelo da ~47 % neto y con
el de MERRA-2, 14 %. El nivel de NASA POWER queda como extremo adverso del recurso. Lo que una fuente no entrega
queda declarado, nunca en cero.
"""

import asyncio
import hashlib
import json
import math
from collections.abc import Mapping
from datetime import date, datetime, timezone
from time import perf_counter

import numpy as np

from ..connectors.gwa.wind_atlas import LICENSE as ATLAS_LICENSE
from ..connectors.gwa.wind_atlas import SOURCE as ATLAS_SOURCE
from ..connectors.gwa.wind_atlas import AtlasPoint, WindAtlasConnector, WindAtlasError
from ..connectors.nasa.power_hourly import SOURCE_URL as HOURLY_URL
from ..connectors.nasa.power_hourly import HourlyWind, PowerHourlyConnector
from ..finance.sensitivity import Driver, break_even_item, tornado
from ..orchestration.analysis import analyze_subjects
from ..orchestration.discoveries import record_in_pipeline, terrain_discoveries, variable_discoveries, wind_atlas_discoveries
from ..orchestration.era5_crosscheck import attach_era5, era5_gaps, era5_series
from ..orchestration.extraction import elapsed_ms, extract_power, extract_terrain, max_separation_km
from ..orchestration.nasa_questions import SectorLens, SubjectSummaries, answer_nasa_questions, collect_trend_findings, millions_usd
from ..orchestration.slope_check import scorecard_with_slope_check
from ..orchestration.stages import (
    StageTimings,
    analysis_stage,
    assemble_pipeline,
    configuration_stage,
    export_stage,
    extraction_stage,
    results_stage,
    selection_stage,
    stage,
    territorial_stage,
    unique,
)
from ..schemas.analysis import Provenance
from ..schemas.pipeline import AnnualObservation, DataGap, VariableSummary
from ..schemas.scoring import Criterion, Direction, Scorecard, ScorecardRequest, SubjectValues
from ..schemas.screening import AssumptionItem, FinanceScenario, PipelineStatus, StageEvidence, StudySubject, SubjectKind, SubjectSensitivity
from ..schemas.terrain import TerrainResponse
from ..schemas.wind import WindAssumptions, WindAtlasCheck, WindResource, WindScreeningRequest, WindScreeningResponse, WindSiteResult
from .energy_common import BREAK_EVEN_SPAN, break_even_note, fmt_value, lower_first, scenario_npv
from .wind_energy import (
    SHEAR_LIMITS,
    air_density,
    annual_energy_mwh,
    calculate_wind_projection,
    capacity_factor,
    hub_speeds,
    shear_exponent,
)

WIND_VARIABLES = ["WS50M", "WS10M", "T2M", "PRECTOTCORR"]
WIND_50M = "WS50M"
SECTOR_LABEL = "Eólico"
HOURLY_YEARS = 10          # la energía usa los diez últimos años completos de la serie horaria
ATLAS_TIMEOUT_SECONDS = 60
RESOURCE_LOW_PERCENTILE, RESOURCE_HIGH_PERCENTILE = 10, 90
ADVERSE_KEYS = {"capacity_factor", "energy_price_usd_mwh", "initial_capex_usd", "annual_opex_usd"}

WIND_READINGS: dict[tuple[str, str], str] = {
    (WIND_50M, "decreasing"): "el viento a 50 m cae: la media histórica sobrestima el recurso futuro y la energía debe sensibilizarse a la baja",
    (WIND_50M, "increasing"): "el viento a 50 m sube: la media histórica es conservadora para el recurso; revisar cargas extremas",
    ("WS10M", "decreasing"): "el viento a 10 m cae: confirma una caída del recurso si también la muestra el viento a 50 m",
    ("WS10M", "increasing"): "el viento a 10 m sube: revisar erosión y cargas sobre accesos y estructuras bajas",
    ("T2M", "increasing"): "la temperatura sube: el aire menos denso reduce levemente la potencia de cada turbina",
    ("T2M", "decreasing"): "la temperatura baja: el aire más denso aumenta levemente la potencia de cada turbina",
    ("PRECTOTCORR", "increasing"): "la precipitación aumenta: revisar accesos, drenaje y cimentaciones",
    ("PRECTOTCORR", "decreasing"): "la precipitación disminuye: más polvo en accesos; sin efecto directo en el recurso",
}
WIND_STABLE_NOTES = {
    WIND_50M: "El viento a 50 m no muestra deriva significativa en ningún sitio: no hay evidencia para castigar la media histórica por tendencia, lo que no prueba que sea constante.",
}
ASSUMPTION_LABELS = {
    "capacity_mw": ("Capacidad", "MW"), "hub_height_m": ("Altura del buje", "m"), "cut_in_ms": ("Velocidad de arranque", "m/s"),
    "rated_ms": ("Velocidad nominal", "m/s"), "cut_out_ms": ("Velocidad de parada", "m/s"), "losses": ("Pérdidas totales", "fracción"),
    "initial_capex_usd": ("CAPEX inicial", "USD"), "annual_opex_usd": ("OPEX anual", "USD/año"), "energy_price_usd_mwh": ("Precio de energía", "USD/MWh"),
    "mitigation_capex_usd": ("CAPEX de mitigación", "USD"), "discount_rate": ("Tasa de descuento", "fracción"), "horizon_years": ("Horizonte", "años"),
    "price_sensitivity": ("Rango del precio (±)", "fracción"), "capex_sensitivity": ("Rango del CAPEX (±)", "fracción"),
    "opex_sensitivity": ("Rango del OPEX (±)", "fracción"), "losses_sensitivity": ("Rango de las pérdidas (±)", "puntos"),
    "discount_rate_sensitivity": ("Rango de la tasa (±)", "puntos"),
}
WIND_CRITERIA = [
    ("hub_speed", "Viento a la altura del buje", "m/s", Direction.HIGHER_IS_BETTER, 0.25, 4.0, 9.0,
     "Media al buje con el nivel del Atlas Eólico Global (o de NASA POWER si el atlas no respondió). Escala: 4 m/s (insuficiente) a 9 m/s (excelente)."),
    ("variability", "Estabilidad del recurso", "%", Direction.LOWER_IS_BETTER, 0.10, 10.0, 2.0,
     "Variación interanual del factor de planta en la serie horaria. Escala 10 % a 2 %."),
    ("resource_drift", "Deriva del viento a 50 m", "m/s por década", Direction.HIGHER_IS_BETTER, 0.10, -0.3, 0.3,
     "Pendiente de Sen × 10 solo si es significativa tras BH; sin evidencia de cambio cuenta como 0."),
    ("atlas_gap", "Confianza del recurso", "%", Direction.LOWER_IS_BETTER, 0.15, 40.0, 0.0,
     "Diferencia absoluta entre NASA POWER y el Atlas Eólico Global a la altura del buje: cuanto menor, más confiable el nivel."),
    ("terrain_slope", "Pendiente del terreno", "°", Direction.LOWER_IS_BETTER, 0.10, 20.0, 0.0,
     "NASADEM en el punto. Escala 20° (accesos y plataformas costosos) a 0°."),
    ("npv_ratio", "VAN / CAPEX", "fracción", Direction.HIGHER_IS_BETTER, 0.30, -0.5, 0.5,
     "VAN base sobre CAPEX inicial con los supuestos del usuario. Escala −50 % a +50 %."),
]
SCORE_NOTES = [
    "Ordena prioridades de estudio entre sitios; no es una recomendación de inversión ni un índice de factibilidad.",
    "Escalas de referencia y pesos son supuestos editables; el resultado debe leerse junto con su estabilidad.",
]


def hourly_years(start: date, end: date) -> range:
    """Los diez últimos años completos dentro del período (un año termina el 31 de diciembre)."""
    last = end.year if (end.month, end.day) == (12, 31) else end.year - 1
    return range(max(start.year, last - HOURLY_YEARS + 1), last + 1)


def _subjects(request: WindScreeningRequest) -> list[StudySubject]:
    return [
        StudySubject(id=f"sitio-{index + 1}", label=site.label or f"Sitio {index + 1}", kind=SubjectKind.POINT,
                     geometry={"type": "Point", "coordinates": [site.longitude, site.latitude]}, representative_point=site)
        for index, site in enumerate(request.sites)
    ]


async def _atlas(latitude: float, longitude: float) -> AtlasPoint | str:
    try:
        return await asyncio.wait_for(WindAtlasConnector().point(latitude, longitude), timeout=ATLAS_TIMEOUT_SECONDS)
    except WindAtlasError as exc:
        return str(exc)
    except TimeoutError:
        return f"El Atlas Eólico Global no respondió en {ATLAS_TIMEOUT_SECONDS} s."


async def _hourly(points, years: range) -> tuple[list[HourlyWind], float]:
    start = perf_counter()
    connector = PowerHourlyConnector()
    series = await asyncio.gather(*(connector.wind(point.latitude, point.longitude, years) for point in points))
    return list(series), elapsed_ms(start)


def _elevation(terrain: TerrainResponse | None, index: int, count: int) -> tuple[float | None, str]:
    if terrain is None or len(terrain.sites) != count:
        return None, "sin elevación del sitio"
    site = terrain.sites[index]
    if site.metrics.elevation_m is not None:
        return site.metrics.elevation_m, f"NASADEM {site.metrics.elevation_m:,.0f} m"
    if site.crosscheck is not None and site.crosscheck.elevation_m is not None:
        return site.crosscheck.elevation_m, f"Copernicus GLO-30 {site.crosscheck.elevation_m:,.0f} m"
    return None, "sin elevación del sitio"


def build_resource(hourly: HourlyWind, temperature_c: float, elevation_m: float | None, elevation_basis: str,
                   assumptions: WindAssumptions) -> tuple[WindResource, np.ndarray, float, float]:
    years = sorted(hourly.by_year)
    high = np.concatenate([hourly.by_year[year][0] for year in years])
    low = np.concatenate([hourly.by_year[year][1] for year in years])
    shear, shear_basis = shear_exponent(float(high.mean()), float(low.mean()))
    density = air_density(elevation_m if elevation_m is not None else 0.0, temperature_c)
    density_basis = (f"Atmósfera estándar a {elevation_basis} y {temperature_c:.1f} °C (T2M media)" if elevation_m is not None
                     else f"Sin elevación del sitio: atmósfera estándar a nivel del mar y {temperature_c:.1f} °C; sobrestima la densidad en altura")
    gross = capacity_factor(high, assumptions, shear, density)
    annual = [AnnualObservation(year=year, value=round(capacity_factor(hourly.by_year[year][0], assumptions, shear, density), 4)) for year in years]
    mean_hub = round(float(hub_speeds(high, assumptions.hub_height_m, shear).mean()), 3)
    resource = WindResource(
        years=f"{years[0]}–{years[-1]}" if len(years) > 1 else str(years[0]), hours=int(high.size),
        mean_speed_10m=round(float(low.mean()), 3), mean_speed_50m=round(float(high.mean()), 3), shear_exponent=round(shear, 4), shear_basis=shear_basis,
        hub_height_m=assumptions.hub_height_m, mean_speed_hub=mean_hub, mean_speed_hub_used=mean_hub,
        air_density_kg_m3=round(density, 4), density_basis=density_basis, capacity_factor_gross=round(gross, 4), annual_capacity_factors=annual,
        capacity_factor_gross_nasa_level=round(gross, 4),
        provenance=hourly.provenance, downloaded_at=hourly.downloaded_at, source_url=HOURLY_URL, version=hourly.version,
    )
    return resource, high, shear, density


def apply_atlas_level(resource: WindResource, hourly: HourlyWind, check: WindAtlasCheck | None, shear: float, density: float,
                      assumptions: WindAssumptions) -> WindResource:
    """Lleva cada hora de MERRA-2 al nivel medio del atlas al buje; sin atlas, el recurso queda con el nivel de NASA POWER."""
    if check is None or not check.speed_hub or not resource.mean_speed_hub:
        return resource
    level = check.speed_hub / resource.mean_speed_hub
    years = sorted(hourly.by_year)
    speeds = np.concatenate([hourly.by_year[year][0] for year in years])
    return resource.model_copy(update={
        "level_source": ATLAS_SOURCE, "level_factor": round(level, 4), "mean_speed_hub_used": round(resource.mean_speed_hub * level, 3),
        "capacity_factor_gross": round(capacity_factor(speeds, assumptions, shear, density, level), 4),
        "annual_capacity_factors": [AnnualObservation(year=year, value=round(capacity_factor(hourly.by_year[year][0], assumptions, shear, density, level), 4))
                                    for year in years],
    })


def build_atlas_check(atlas: AtlasPoint, resource: WindResource, speeds_50m: np.ndarray, shear: float, density: float,
                      assumptions: WindAssumptions) -> WindAtlasCheck:
    g50, g100 = atlas.speeds.get(50), atlas.speeds.get(100)
    hub = assumptions.hub_height_m
    if g50 and g100:
        atlas_shear = min(max(math.log(g100 / g50) / math.log(2), SHEAR_LIMITS[0]), SHEAR_LIMITS[1])
        g_hub = g100 * (hub / 100) ** atlas_shear
    else:
        g_hub = g100 * (hub / 100) ** shear if g100 else None
    gap50 = (g50 - resource.mean_speed_50m) / resource.mean_speed_50m * 100 if g50 and resource.mean_speed_50m else None
    gap_hub = (g_hub - resource.mean_speed_hub) / resource.mean_speed_hub * 100 if g_hub and resource.mean_speed_hub else None
    cf_atlas = capacity_factor(speeds_50m, assumptions, shear, density, level=g_hub / resource.mean_speed_hub) if g_hub and resource.mean_speed_hub else None
    return WindAtlasCheck(
        source=ATLAS_SOURCE, speed_50m=g50, speed_100m=g100, speed_hub=round(g_hub, 2) if g_hub else None, power_speed_50m=resource.mean_speed_50m,
        gap_percent_50m=round(gap50, 1) if gap50 is not None else None, gap_percent_hub=round(gap_hub, 1) if gap_hub is not None else None,
        capacity_factor_gross_at_atlas=round(cf_atlas, 4) if cf_atlas is not None else None,
        annual_energy_mwh_at_atlas=round(annual_energy_mwh(cf_atlas, assumptions), 2) if cf_atlas is not None else None,
        provenance=atlas.provenance, downloaded_at=atlas.downloaded_at, urls=atlas.urls, license=ATLAS_LICENSE,
        limitations=[*atlas.limitations, "La energía «al nivel del atlas» escala cada hora de MERRA-2 por la razón de medias: conserva la forma de la serie, no la del atlas."],
    )


def wind_npv(inputs: Mapping[str, float], assumptions: WindAssumptions) -> float:
    """VAN eólico con factores sobrescritos; reutiliza la proyección para no duplicar fórmulas."""
    updated = assumptions.model_copy(update={key: value for key, value in inputs.items() if key not in ("capacity_factor", "atlas_ratio")})
    return calculate_wind_projection(inputs["capacity_factor"] * inputs.get("atlas_ratio", 1.0), updated).npv_usd


def _capacity_factor_note(value: float | None, observed: list[float]) -> str:
    if value is None:
        return "El VAN no cruza cero en el rango de factor de planta buscado."
    best = max(observed) if observed else None
    if best is None:
        return f"Factor de planta bruto mínimo para VAN ≥ 0: {value * 100:.1f} %."
    reach = "ningún año observado lo alcanza" if value > best else f"{sum(1 for item in observed if item >= value)} de {len(observed)} años observados lo superan"
    return f"Factor de planta bruto mínimo para VAN ≥ 0: {value * 100:.1f} %; {reach} (mejor año: {best * 100:.1f} %)."


def wind_sensitivity(label: str, resource: WindResource, atlas: WindAtlasCheck | None, assumptions: WindAssumptions) -> SubjectSensitivity:
    a = assumptions
    base = {"capacity_factor": resource.capacity_factor_gross, "atlas_ratio": 1.0, "energy_price_usd_mwh": a.energy_price_usd_mwh,
            "initial_capex_usd": a.initial_capex_usd, "annual_opex_usd": a.annual_opex_usd, "losses": a.losses, "discount_rate": a.discount_rate}

    def model(inputs: Mapping[str, float]) -> float:
        return wind_npv(inputs, a)

    user = "Supuesto del usuario"
    drivers = [
        Driver("energy_price_usd_mwh", "Precio de energía", "USD/MWh", a.energy_price_usd_mwh * (1 - a.price_sensitivity),
               a.energy_price_usd_mwh * (1 + a.price_sensitivity), Provenance.ASSUMPTION, f"{user}: ±{a.price_sensitivity:.0%}."),
        Driver("initial_capex_usd", "CAPEX inicial", "USD", a.initial_capex_usd * (1 + a.capex_sensitivity),
               a.initial_capex_usd * (1 - a.capex_sensitivity), Provenance.ASSUMPTION, f"{user}: ±{a.capex_sensitivity:.0%}."),
        Driver("annual_opex_usd", "OPEX anual", "USD/año", a.annual_opex_usd * (1 + a.opex_sensitivity),
               a.annual_opex_usd * (1 - a.opex_sensitivity), Provenance.ASSUMPTION, f"{user}: ±{a.opex_sensitivity:.0%}."),
        Driver("losses", "Pérdidas totales", "fracción", min(0.95, a.losses + a.losses_sensitivity), max(0.0, a.losses - a.losses_sensitivity),
               Provenance.ASSUMPTION, f"{user}: ±{a.losses_sensitivity * 100:.0f} puntos."),
        Driver("discount_rate", "Tasa de descuento", "fracción", a.discount_rate + a.discount_rate_sensitivity,
               max(0.0, a.discount_rate - a.discount_rate_sensitivity), Provenance.ASSUMPTION, f"{user}: ±{a.discount_rate_sensitivity * 100:.1f} puntos."),
    ]
    observed = [item.value for item in resource.annual_capacity_factors]
    if len(observed) >= 5:
        low, high = (float(np.percentile(observed, q)) for q in (RESOURCE_LOW_PERCENTILE, RESOURCE_HIGH_PERCENTILE))
        drivers.insert(0, Driver("capacity_factor", "Recurso eólico (año bajo / alto)", "fracción", low, high, Provenance.MODEL,
                                 f"Percentiles {RESOURCE_LOW_PERCENTILE} y {RESOURCE_HIGH_PERCENTILE} del factor de planta de {len(observed)} años "
                                 f"({resource.years}), NASA POWER horario."))
    # El nivel que no se usó en el caso base es el otro extremo del recurso: con atlas, el nivel propio de NASA POWER.
    if resource.capacity_factor_gross and resource.level_factor != 1.0:
        ratio = resource.capacity_factor_gross_nasa_level / resource.capacity_factor_gross
        if abs(ratio - 1) > 1e-3:
            drivers.insert(1, Driver("atlas_ratio", "Nivel del recurso (Atlas Eólico ↔ NASA POWER)", "×", min(1.0, ratio), max(1.0, ratio), Provenance.MODEL,
                                     f"Si el nivel fuera el de la celda de NASA POWER, la energía sería {ratio:.2f} veces la del caso base."))
    adverse = {driver.key: driver.low for driver in drivers if driver.key in ADVERSE_KEYS}
    favorable = {driver.key: driver.high for driver in drivers if driver.key in ADVERSE_KEYS}
    moved = [driver for driver in drivers if driver.key in ADVERSE_KEYS]
    shown = lambda driver, value: f"{value * 100:.1f} %" if driver.key == "capacity_factor" else fmt_value(value, driver.unit)  # noqa: E731
    scenarios = [
        FinanceScenario(key="base", label="Base", npv=round(model(base), 2), changes=["Todos los supuestos en su valor declarado; recurso = serie horaria completa."]),
        FinanceScenario(key="adverso", label="Adverso", npv=round(model({**base, **adverse}), 2), changes=[f"{d.label}: {shown(d, d.low)}" for d in moved]),
        FinanceScenario(key="favorable", label="Favorable", npv=round(model({**base, **favorable}), 2), changes=[f"{d.label}: {shown(d, d.high)}" for d in moved]),
    ]
    break_evens = [
        break_even_item(model, base, "energy_price_usd_mwh", "Precio de equilibrio", "USD/MWh", 0.0, BREAK_EVEN_SPAN * max(a.energy_price_usd_mwh, 1.0),
                        lambda value: break_even_note(value, base["energy_price_usd_mwh"], "USD/MWh", "precio mínimo", higher_is_better=True)),
        break_even_item(model, base, "initial_capex_usd", "CAPEX máximo", "USD", 1.0, BREAK_EVEN_SPAN * a.initial_capex_usd,
                        lambda value: break_even_note(value, base["initial_capex_usd"], "USD", "CAPEX máximo", higher_is_better=False)),
        break_even_item(model, base, "capacity_factor", "Factor de planta de equilibrio", "fracción", 0.0, 1.0,
                        lambda value: _capacity_factor_note(value, observed)),
    ]
    return SubjectSensitivity(subject=label, base_npv=scenarios[0].npv, scenarios=scenarios, tornado=tornado(model, base, drivers), break_evens=break_evens)


def _site_result(site, summaries: list[VariableSummary], resource: WindResource, atlas: WindAtlasCheck | None, position: int, total: int,
                 assumptions: WindAssumptions) -> WindSiteResult:
    wind = next(item for item in summaries if item.variable == WIND_50M)
    finance = calculate_wind_projection(resource.capacity_factor_gross, assumptions)
    level = ("nivel del Atlas Eólico Global con la forma horaria de NASA POWER" if resource.level_factor != 1.0 else "nivel de NASA POWER")
    opportunities = [
        f"Viento medio de {resource.mean_speed_hub_used:.2f} m/s a {resource.hub_height_m:g} m ({level}; {resource.hours:,} horas, {resource.years}); "
        f"factor de planta neto {finance.capacity_factor_net * 100:.1f} %.",
        f"Posición {position} de {total} entre las ubicaciones comparadas por factor de planta.",
    ]
    if wind.significant_after_bh and wind.trend.direction == "increasing":
        opportunities.append("El viento a 50 m tiene tendencia creciente que conserva significancia tras el ajuste BH.")
    cautions = [
        "NASA POWER representa una celda de reanálisis; la decisión de inversión exige medición en sitio (torre o LiDAR, al menos un año).",
        "El análisis no incluye conexión eléctrica, predios ni restricciones ambientales o sociales (ver módulos Ambiente y Territorio).",
    ]
    if wind.significant_after_bh and wind.trend.direction == "decreasing":
        cautions.append("El viento a 50 m presenta una tendencia decreciente significativa tras el ajuste BH.")
    if atlas and atlas.gap_percent_hub is not None and abs(atlas.gap_percent_hub) >= 20:
        cautions.append(f"La celda de NASA POWER da {resource.mean_speed_hub:.2f} m/s al buje y el atlas {atlas.speed_hub:.2f} m/s ({atlas.gap_percent_hub:+.0f} %): "
                        f"con el nivel de NASA POWER el factor de planta bruto sería {resource.capacity_factor_gross_nasa_level * 100:.1f} %.")
    elif atlas is None:
        cautions.append("Sin Atlas Eólico Global: la energía usa el nivel de la celda de NASA POWER, que en costa y relieve complejo puede subestimar el viento.")
    return WindSiteResult(location=site, relative_position=position, relative_position_text=f"{position} de {total} por factor de planta",
                          variables=summaries, resource=resource, atlas_check=atlas, finance=finance, opportunities=opportunities, cautions=cautions)


def wind_scorecard(subjects: list[StudySubject], results: list[WindSiteResult], terrain: TerrainResponse | None, assumptions: WindAssumptions) -> Scorecard:
    rows = []
    for index, (subject, result) in enumerate(zip(subjects, results, strict=True)):
        wind = next(item for item in result.variables if item.variable == WIND_50M)
        drift = wind.trend.slope_per_year * 10 if wind.significant_after_bh and wind.trend.slope_per_year is not None else 0.0
        site = terrain.sites[index] if terrain and len(terrain.sites) == len(results) else None
        factors = [item.value for item in result.resource.annual_capacity_factors]
        variability = float(np.std(factors) / np.mean(factors) * 100) if len(factors) >= 3 and np.mean(factors) > 0 else None
        gap = result.atlas_check.gap_percent_hub if result.atlas_check else None
        rows.append(SubjectValues(subject=subject.label, values={
            "hub_speed": result.resource.mean_speed_hub_used, "variability": variability, "resource_drift": drift,
            "atlas_gap": abs(gap) if gap is not None else None,
            "terrain_slope": site.metrics.slope_degrees if site and site.status == "READY" else None,
            "npv_ratio": result.finance.npv_usd / assumptions.initial_capex_usd,
        }))
    criteria = [Criterion(key=key, label=label, unit=unit, direction=direction, weight=weight, worst=worst, best=best,
                          provenance=Provenance.MODEL, basis=basis)
                for key, label, unit, direction, weight, worst, best, basis in WIND_CRITERIA]
    notes = list(SCORE_NOTES)
    for key, name in (("terrain_slope", "pendiente NASADEM"), ("atlas_gap", "contraste del Atlas Eólico Global")):
        missing = [row.subject for row in rows if row.values[key] is None]
        if missing:
            notes.append(f"Sin {name} para {', '.join(missing)}: ese criterio queda fuera y su peso se reparte (ver cobertura).")
    return scorecard_with_slope_check(ScorecardRequest(criteria=criteria, subjects=rows), notes, terrain)


def _data_gaps(terrain: TerrainResponse | None, atlas_errors: list[str]) -> list[DataGap]:
    gaps = []
    if terrain is None or any(site.metrics.elevation_m is None and (site.crosscheck is None or site.crosscheck.elevation_m is None) for site in terrain.sites):
        gaps.append(DataGap(dataset="Elevación del sitio (NASADEM o Copernicus)", impact="Sin elevación, la densidad del aire se toma a nivel del mar y la energía queda sobrestimada en altura.",
                            next_action="Volver a ejecutar cuando NASADEM o Copernicus respondan."))
    if atlas_errors:
        gaps.append(DataGap(dataset=ATLAS_SOURCE, impact="; ".join(atlas_errors)[:400], next_action="Reintentar; un sitio sin atlas queda sin contraste de nivel, no con ceros."))
    return gaps + [
        DataGap(dataset="Medición de viento en sitio (torre o LiDAR)", impact="El nivel del recurso proviene de reanálisis y de un atlas modelado; ninguno sustituye la campaña de medición.",
                next_action="Instalar una torre o LiDAR al menos un año y correlacionarla con la serie de largo plazo (MCP)."),
        DataGap(dataset="Curva de potencia del fabricante", impact="Se usa una curva genérica: la energía puede moverse ±10 % o más.",
                next_action="Reemplazar con la curva certificada de la turbina candidata."),
        DataGap(dataset="Red eléctrica y subestaciones", impact="No se estima distancia ni capacidad de conexión.", next_action="Validar servicios oficiales de MINEM y COES."),
        DataGap(dataset="Restricciones ambientales, sociales y aves", impact="Este módulo no cruza áreas protegidas, patrimonio ni rutas de aves migratorias.",
                next_action="Usar los módulos Ambiente y Territorio y un estudio de avifauna."),
    ]


def _evaluation_and_finance_stages(results: list[WindSiteResult], sensitivities: list[SubjectSensitivity], source_provenance: list[Provenance], finance_ms: float):
    ranked = sorted(results, key=lambda item: item.relative_position)
    delta = ranked[0].resource.capacity_factor_gross - ranked[-1].resource.capacity_factor_gross
    evidence = [StageEvidence(label=f"{index + 1}.º {item.location.label}",
                              value=f"factor de planta bruto {item.resource.capacity_factor_gross * 100:.1f} % · {item.resource.mean_speed_hub_used:.2f} m/s al buje")
                for index, item in enumerate(ranked)]
    evidence.append(StageEvidence(label="Criterio", value="Factor de planta: forma horaria de NASA POWER, nivel del Atlas Eólico Global y curva genérica"))
    evaluation = stage("evaluation", PipelineStatus.COMPLETED, f"Orden relativo por factor de planta; diferencia entre extremos de {delta * 100:.1f} puntos.",
                       source_provenance + [Provenance.MODEL], evidence, answers=["so_what"])
    npvs = [item.finance.npv_usd for item in results]
    finance_evidence = [StageEvidence(label=item.location.label or "Sitio", value=f"USD {item.finance.npv_usd:,.0f} · {item.finance.annual_energy_mwh:,.0f} MWh/año",
                                      provenance=Provenance.MODEL) for item in results]
    finance_evidence.append(StageEvidence(label="Fórmula", value="Energía = MW × 8,760 h × factor de planta × (1 − pérdidas); VAN a tasa del usuario"))
    adverse = [scenario_npv(item, "adverso") for item in sensitivities]
    finance_evidence += [StageEvidence(label=f"Adverso · {item.subject}", value=f"USD {value:,.0f}", provenance=Provenance.MODEL) for item, value in zip(sensitivities, adverse, strict=True)]
    finance_evidence += [StageEvidence(label=f"Factor dominante · {item.subject}", value=item.tornado[0].label, provenance=item.tornado[0].provenance) for item in sensitivities if item.tornado]
    finance = stage("finance", PipelineStatus.COMPLETED,
                    f"VAN positivo en {sum(1 for value in npvs if value >= 0)} de {len(npvs)} sitios con los supuestos del usuario "
                    f"y en {sum(1 for value in adverse if value >= 0)} de {len(adverse)} en el escenario adverso.",
                    [Provenance.MODEL, Provenance.ASSUMPTION], finance_evidence, finance_ms, ["so_what"])
    return evaluation, finance


async def run_wind_screening(request: WindScreeningRequest) -> WindScreeningResponse:
    timings = StageTimings()
    subjects = _subjects(request)
    points = [subject.representative_point for subject in subjects]
    years = hourly_years(request.start_date, request.end_date)
    (datasets, daily_ms), (terrain, terrain_error, timings.terrain_ms), era5, (hourly, hourly_ms), atlas_points = await asyncio.gather(
        extract_power(points, WIND_VARIABLES, request.start_date, request.end_date), extract_terrain(points),
        era5_series([(subject.label, subject.representative_point) for subject in subjects]),
        _hourly(points, years), asyncio.gather(*(_atlas(point.latitude, point.longitude) for point in points)),
    )
    timings.extraction_ms = max(daily_ms, hourly_ms)
    expected_days = (request.end_date - request.start_date).days + 1

    analysis_start = perf_counter()
    summaries_by_site = analyze_subjects(datasets, WIND_VARIABLES, expected_days)
    attach_era5(summaries_by_site, era5)
    timings.analysis_ms = elapsed_ms(analysis_start)

    finance_start = perf_counter()
    a = request.assumptions
    resources, atlas_checks, atlas_errors = [], [], []
    for index, (subject, summaries, series, atlas) in enumerate(zip(subjects, summaries_by_site, hourly, atlas_points, strict=True)):
        temperature = next(item for item in summaries if item.variable == "T2M").mean
        elevation, basis = _elevation(terrain, index, len(subjects))
        resource, speeds, shear, density = build_resource(series, temperature, elevation, basis, a)
        check = build_atlas_check(atlas, resource, speeds, shear, density, a) if isinstance(atlas, AtlasPoint) else None
        if check is None:
            atlas_errors.append(f"{subject.label}: {atlas}")
        resources.append(apply_atlas_level(resource, series, check, shear, density, a))
        atlas_checks.append(check)
    ordered = sorted(range(len(resources)), key=lambda index: resources[index].capacity_factor_gross, reverse=True)
    positions = {index: position + 1 for position, index in enumerate(ordered)}
    site_results = [_site_result(site, summaries, resource, check, positions[index], len(request.sites), a)
                    for index, (site, summaries, resource, check) in enumerate(zip(request.sites, summaries_by_site, resources, atlas_checks, strict=True))]
    sensitivities = [wind_sensitivity(subject.label, result.resource, result.atlas_check, a) for subject, result in zip(subjects, site_results, strict=True)]
    timings.finance_ms = elapsed_ms(finance_start)

    ranked = sorted(site_results, key=lambda item: item.relative_position)
    best, worst = ranked[0], ranked[-1]
    comparative = [
        f"{best.location.label} tiene el mayor factor de planta: {best.finance.capacity_factor_net * 100:.1f} % neto con {best.resource.mean_speed_hub_used:.2f} m/s a {a.hub_height_m:g} m.",
        f"La energía anual va de {worst.finance.annual_energy_mwh:,.0f} a {best.finance.annual_energy_mwh:,.0f} MWh con {a.capacity_mw:g} MW instalados.",
        "La posición relativa usa el nivel del Atlas Eólico Global, la forma horaria de NASA POWER y una curva genérica; no es una recomendación de inversión ni un score de factibilidad.",
    ]

    labelled = [SubjectSummaries(label=subject.label, summaries=summaries) for subject, summaries in zip(subjects, summaries_by_site, strict=True)]
    trend_findings = collect_trend_findings(labelled)
    gaps = _data_gaps(terrain, atlas_errors) + era5_gaps(era5)
    pending = sum(1 for gap in gaps if gap.status == Provenance.UNAVAILABLE)
    discoveries = variable_discoveries([(subject.label, summaries) for subject, summaries in zip(subjects, summaries_by_site, strict=True)]) \
        + wind_atlas_discoveries([(result.location.label, result.resource, result.atlas_check) for result in site_results]) \
        + terrain_discoveries(terrain)
    npvs = [result.finance.npv_usd for result in site_results]
    adverse = [scenario_npv(item, "adverso") for item in sensitivities]
    dominant = {item.tornado[0].label for item in sensitivities if item.tornado}
    lens = SectorLens(
        readings=WIND_READINGS, stable_notes=WIND_STABLE_NOTES,
        economics=(
            f"Con los supuestos del usuario, el VAN es positivo en {sum(1 for value in npvs if value >= 0)} de {len(npvs)} sitios "
            f"(de {millions_usd(min(npvs))} a {millions_usd(max(npvs))}); en el escenario adverso, en {sum(1 for value in adverse if value >= 0)} de {len(adverse)}. "
            + (f"El factor que más mueve el VAN es el {lower_first(next(iter(dominant)))}." if len(dominant) == 1
               else f"Los factores que más mueven el VAN son: {', '.join(lower_first(item) for item in sorted(dominant))}.")
        ),
    )
    nasa_questions = answer_nasa_questions(
        labelled, trend_findings, {subject.label: (subject.representative_point.latitude, subject.representative_point.longitude) for subject in subjects},
        pending, lens,
    )

    source_provenance = unique([item.source.provenance for summaries in summaries_by_site for item in summaries] + [item.provenance for item in resources])
    all_provenance = unique(source_provenance + [Provenance.MODEL, Provenance.ASSUMPTION] + ([Provenance.UNAVAILABLE] if pending else []))
    years_count = max(len(item.annual_series) for summaries in summaries_by_site for item in summaries)
    scorecard = wind_scorecard(subjects, site_results, terrain, a)
    evaluation, finance = _evaluation_and_finance_stages(site_results, sensitivities, source_provenance, timings.finance_ms)
    leader = next((item for item in scorecard.subjects if item.subject == scorecard.leader), None)
    if leader:
        evaluation.evidence.append(StageEvidence(
            label="Puntaje multicriterio", provenance=Provenance.MODEL,
            value=(f"Empate práctico: {leader.subject} {leader.score:.0f}/100 por {scorecard.margin:.1f} punto(s), primero en {leader.first_place_share:.0%} de las combinaciones de pesos"
                   if scorecard.tie else
                   f"{leader.subject} {leader.score:.0f}/100 · primero en {leader.first_place_share:.0%} de {scorecard.stability_draws} combinaciones de pesos"),
        ))
    extraction = extraction_stage(labelled, timings.extraction_ms)
    extraction.evidence.append(StageEvidence(label="NASA POWER horario (energía)", provenance=resources[0].provenance,
                                             value=f"WS50M y WS10M, {resources[0].years} · {sum(item.hours for item in resources):,} horas en {len(resources)} sitios"))
    for result in site_results:
        check = result.atlas_check
        extraction.evidence.append(StageEvidence(label=f"Atlas Eólico Global · {result.location.label}", provenance=check.provenance if check else Provenance.UNAVAILABLE,
                                                 value=f"{check.speed_50m} m/s a 50 m · {check.speed_100m} m/s a 100 m" if check else "Sin respuesta"))
    pipeline = assemble_pipeline([
        selection_stage(subjects, max_separation_km(points)),
        configuration_stage(SECTOR_LABEL, WIND_VARIABLES, request.start_date, request.end_date, years_count,
                            f"{a.capacity_mw:g} MW · buje {a.hub_height_m:g} m · tasa {a.discount_rate:.0%} · {a.horizon_years} años"),
        extraction,
        analysis_stage(labelled, trend_findings, timings.analysis_ms),
        territorial_stage(terrain, terrain_error, gaps, timings.terrain_ms),
        evaluation,
        finance,
        results_stage(trend_findings, gaps, all_provenance),
        export_stage(all_provenance),
    ])
    record_in_pipeline(pipeline, discoveries)
    fingerprint = hashlib.sha256(json.dumps(request.model_dump(mode="json"), sort_keys=True).encode()).hexdigest()[:16]
    return WindScreeningResponse(
        analysis_id=fingerprint, generated_at=datetime.now(timezone.utc), title="Screening eólico comparativo — Perú",
        period=f"{request.start_date.isoformat()}/{request.end_date.isoformat()}", subjects=subjects, pipeline=pipeline,
        nasa_questions=nasa_questions, trend_findings=trend_findings, sites=site_results, terrain=terrain, comparative_findings=comparative,
        data_gaps=gaps, assumptions=a,
        assumption_items=[AssumptionItem(key=key, label=label, value=float(getattr(a, key)), unit=unit) for key, (label, unit) in ASSUMPTION_LABELS.items()],
        financial_sensitivity=sensitivities, scorecard=scorecard, discoveries=discoveries,
        disclaimer="Screening preliminar basado en datos NASA, un atlas modelado y supuestos del usuario. No sustituye la campaña de medición de viento, "
                   "el estudio de conexión, la ingeniería, el impacto ambiental (incluida la avifauna), patrimonio, debida diligencia legal ni factibilidad financiera.",
    )
