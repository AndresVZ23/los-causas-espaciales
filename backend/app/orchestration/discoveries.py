"""Descubrimientos: lo que aparece al cruzar fuentes independientes.

Reglas explícitas y deterministas; ninguna consulta externa. Un descubrimiento no es una conclusión: señala un
artefacto probable, una tendencia confirmada o sin respaldo, o una coincidencia entre instituciones distintas.
"""

from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from datetime import datetime, timezone

from ..schemas.analysis import Provenance
from ..schemas.baseline import BaselineLayer, SubjectBaseline
from ..schemas.climate import Agreement, ExtremeIndexSummary
from ..schemas.data_sources import TerritorialSourceResult
from ..schemas.pipeline import VariableSummary
from ..schemas.screening import Discovery, DiscoveryKind, PipelineStage, StageEvidence
from ..schemas.terrain import TerrainResponse

PRIMARY = "NASA POWER (MERRA-2)"
ARTIFACT_RATIO = 5.0         # el reanálisis supera al menos 5 veces a cada fuente de observación
STEEP_SLOPE_DEGREES = 15.0
HIGH_LEVELS = ("riesgo alto", "riesgo muy alto")
GROWING_COVER = {"Pastizal", "Matorral abierto", "Matorral cerrado", "Sabana", "Sabana arbolada", "Humedal permanente"}
# Susceptibilidad a deslizamientos en la misma escala 1–5: CENEPRED (capa 2 del servicio FEN) y NASA (Stanley y Kirschbaum 2017).
CENEPRED_CLASS = {"Muy bajo": 1, "Bajo": 2, "Medio": 3, "Alto": 4, "Muy alto": 5}
CENEPRED_MASS_MOVEMENT_LAYER = 2
NASA_NAMES = {1: "muy baja", 2: "baja", 3: "moderada", 4: "alta", 5: "muy alta"}
CENEPRED_NAMES = {value: name.lower() for name, value in CENEPRED_CLASS.items()}
HIGH_CLASS = 4
# Recurso solar: CERES y ERA5 «coinciden» si difieren menos de 5 % en la media común; desde 10 % la diferencia mueve el VAN.
SOLAR_CLOSE_PERCENT = 5.0
SOLAR_APART_PERCENT = 10.0
# Temperatura: desde 2 °C de diferencia en la media común, el nivel de una de las dos fuentes no representa el sitio.
TEMPERATURE_APART_DEGREES = 2.0
# Viento: dos reanálisis de celda gruesa difieren a menudo; desde 30 % en la media común, el nivel no sirve para diseño.
WIND_APART_PERCENT = 30.0
PRIMARY_BY_VARIABLE = {"T2M": "MERRA-2", "ALLSKY_SFC_SW_DWN": "CERES", "WS10M": "MERRA-2"}
CLOSE_CLASSES = 1            # dos fuentes «coinciden» en un punto si difieren a lo sumo en una clase,
                             # y en el área si coinciden en al menos dos tercios de los puntos


def short(source: str) -> str:
    return "IMERG" if "IMERG" in source else "CHIRPS" if "CHIRPS" in source else "ERA5" if "ERA5" in source else source


def _order(name: str) -> int:
    # El mismo orden que la tabla de extremos: IMERG, luego CHIRPS.
    return {"IMERG": 0, "CHIRPS": 1}.get(name, 2)


def rainfall_discoveries(sites: Sequence[tuple[str, Sequence[ExtremeIndexSummary]]]) -> list[Discovery]:
    out: list[Discovery] = []
    for label, extremes in sites:
        # 1) Artefactos probables: un evento anual que solo registra el reanálisis (agrupado por año, no por índice).
        by_year: dict[int, list[tuple[ExtremeIndexSummary, object]]] = defaultdict(list)
        for item in extremes:
            if item.unit != "mm":
                continue
            for year in item.atypical_years:
                others = year.countercheck_values
                if others and all(value * ARTIFACT_RATIO < year.value for value in others.values()):
                    by_year[year.year].append((item, year))
        for year_number, entries in sorted(by_year.items()):
            sources = sorted({short(source) for _, year in entries for source in year.countercheck_values}, key=_order)
            parts = [f"{item.variable} {year.value:.0f} mm en MERRA-2 frente a "
                     + ", ".join(f"{value:.0f} mm en {short(source)}" for source, value in sorted(year.countercheck_values.items(), key=lambda kv: _order(short(kv[0]))))
                     for item, year in entries]
            out.append(Discovery(
                kind=DiscoveryKind.PROBABLE_ARTIFACT, title=f"{label}: el evento de {year_number} solo aparece en el reanálisis",
                detail=f"{'; '.join(parts)}. {' y '.join(sources)} no lo {'registran' if len(sources) > 1 else 'registra'}: probable artefacto de MERRA-2; no se usa como evidencia de amenaza.",
                subjects=[label], sources=[PRIMARY, *sources],
            ))
        # 2) Tendencias significativas: cuántas fuentes independientes las repiten.
        for item in extremes:
            if not item.significant_after_bh or not item.counterchecks:
                continue
            agree = [short(c.source) for c in item.counterchecks if c.agreement == Agreement.COINCIDE]
            contradict = [short(c.source) for c in item.counterchecks if c.agreement == Agreement.CONTRADICE]
            checked = [short(c.source) for c in item.counterchecks]
            change = f"{label}: cambio en {item.label.lower()}"
            if contradict:
                kind, title = DiscoveryKind.CONTRADICTION, f"{change} de signo opuesto según la fuente"
            elif len(agree) == len(checked):
                kind, title = DiscoveryKind.CONFIRMED, f"{change} confirmado por todas las fuentes"
            elif not agree:
                kind, title = DiscoveryKind.UNBACKED, f"{change} solo en el reanálisis"
            else:
                kind, title = DiscoveryKind.AGREEMENT, f"{change} respaldado por {len(agree)} de {len(checked)} fuentes"
            out.append(Discovery(
                kind=kind, title=title, subjects=[label], sources=[PRIMARY, *checked],
                detail=f"Pendiente de Sen {item.trend.slope_per_year:+.3f} {item.display_unit}/año (p BH {item.adjusted_p_value:.3f}). "
                       f"Coinciden: {', '.join(agree) or 'ninguna'}; contradicen: {', '.join(contradict) or 'ninguna'}; "
                       f"sin tendencia: {', '.join(s for s in checked if s not in agree and s not in contradict) or 'ninguna'}.",
            ))
        # 3) Al revés: un cambio que ven las observaciones satelitales y no el reanálisis.
        for item in extremes:
            seen = sorted((c for c in item.counterchecks if c.agreement == Agreement.SOLO_CONTRASTE), key=lambda c: _order(short(c.source)))
            if item.significant_after_bh or not seen:
                continue
            names = [short(c.source) for c in seen]
            slopes = "; ".join(f"{short(c.source)} {c.slope_per_year:+.3f} {item.display_unit}/año (p BH {c.adjusted_p_value:.3f})"
                               for c in seen if c.slope_per_year is not None and c.adjusted_p_value is not None)
            both = len(seen) > 1
            out.append(Discovery(
                kind=DiscoveryKind.AGREEMENT if both else DiscoveryKind.UNBACKED,
                title=f"{label}: cambio en {item.label.lower()} según {' y '.join(names)}, no según el reanálisis",
                detail=f"{slopes}. MERRA-2 no muestra tendencia significativa. "
                       + ("Dos observaciones independientes coinciden: conviene revisarlo con estaciones." if both
                          else "Una sola fuente lo ve: es una pista para contrastar con estaciones, no una tendencia establecida."),
                subjects=[label], sources=[PRIMARY, *names],
            ))
    return out


def _signed(value: float | None, unit: str) -> str:
    return "sin pendiente" if value is None else f"{value:+.3f} {unit}/año"


def variable_discoveries(sites: Sequence[tuple[str, Sequence[VariableSummary]]]) -> list[Discovery]:
    """Temperatura, radiación y viento frente a una segunda fuente (ERA5): tendencia en los años comunes y nivel de cada variable."""
    out: list[Discovery] = []
    for label, variables in sites:
        for item in variables:
            primary = PRIMARY_BY_VARIABLE.get(item.variable, "NASA POWER")
            for check in item.counterchecks:
                other, unit, years = short(check.source), item.display_unit, check.period or f"{check.valid_years} años"
                change = f"{label}: {item.label.lower()}"
                p = f", p BH {check.adjusted_p_value:.3f}" if check.adjusted_p_value is not None else ""
                slopes = f"En {years}: {primary} {_signed(check.primary_slope_per_year, unit)}; {other} {_signed(check.slope_per_year, unit)}{p}."
                sources = [f"NASA POWER ({primary})", other]
                if check.agreement == Agreement.COINCIDE:
                    out.append(Discovery(kind=DiscoveryKind.CONFIRMED, title=f"{change}: la tendencia se confirma con {other}",
                                         detail=f"{slopes} Dos reanálisis independientes coinciden en significancia y dirección.", subjects=[label], sources=sources))
                elif check.agreement == Agreement.CONTRADICE:
                    out.append(Discovery(kind=DiscoveryKind.CONTRADICTION, title=f"{change}: tendencia de signo opuesto en {other}",
                                         detail=f"{slopes} Ninguna de las dos se usa sola: hace falta una estación.", subjects=[label], sources=sources))
                elif check.agreement == Agreement.SIN_RESPALDO:
                    same_sign = (check.slope_per_year or 0) * (check.primary_slope_per_year or 0) > 0
                    out.append(Discovery(
                        kind=DiscoveryKind.UNBACKED,
                        title=f"{change}: {other} apunta igual que {primary} pero sin significancia" if same_sign
                              else f"{change}: la tendencia de {primary} no se repite en {other}",
                        detail=f"{slopes} " + ("Misma dirección, sin llegar a la significancia tras BH: respaldo débil, no confirmación." if same_sign
                                               else "Se lee como indicio, no como cambio establecido."),
                        subjects=[label], sources=sources))
                elif check.agreement == Agreement.SOLO_CONTRASTE:
                    out.append(Discovery(kind=DiscoveryKind.UNBACKED, title=f"{change}: cambio según {other}, no según {primary}",
                                         detail=f"{slopes} Una sola fuente lo ve: es una pista para contrastar con estaciones.", subjects=[label], sources=sources))
                elif item.significant_after_bh:
                    out.append(Discovery(kind=DiscoveryKind.UNBACKED, title=f"{change}: la tendencia de {primary} no se sostiene en {years}",
                                         detail=f"{slopes} Ni {primary} ni {other} son significativas en esos años: la tendencia del período completo "
                                                f"depende de los años fuera de esa ventana.", subjects=[label], sources=sources))
                primary_by_year = {point.year: point.value for point in item.annual_series}
                pairs = [(primary_by_year[point.year], point.value) for point in check.annual_series if point.year in primary_by_year]
                if not pairs:
                    continue
                mine, theirs = sum(a for a, _ in pairs) / len(pairs), sum(b for _, b in pairs) / len(pairs)
                if item.variable == "T2M" and abs(theirs - mine) >= TEMPERATURE_APART_DEGREES:
                    # Una celda de MERRA-2 (0.5° × 0.625°) en los Andes mezcla altitudes muy distintas; ERA5 tiene celdas de 0.25°.
                    out.append(Discovery(
                        kind=DiscoveryKind.CONTRADICTION, title=f"{label}: la temperatura media difiere {abs(theirs - mine):.1f} °C entre {primary} y {other}",
                        detail=f"Media {years}: {primary} {mine:.1f} °C; {other} {theirs:.1f} °C. Las tendencias pueden coincidir aunque el nivel no: "
                               f"las celdas de cada reanálisis representan altitudes distintas. Para pérdidas térmicas, confort o heladas, "
                               f"el nivel absoluto se toma de una estación cercana o se mide en sitio.",
                        subjects=[label], sources=sources))
                if item.variable == "WS10M" and mine and abs(theirs - mine) / mine * 100 >= WIND_APART_PERCENT:
                    out.append(Discovery(
                        kind=DiscoveryKind.CONTRADICTION, title=f"{label}: el viento medio difiere {abs(theirs - mine) / mine * 100:.0f} % entre {primary} y {other}",
                        detail=f"Media {years}: {primary} {mine:.2f} m/s; {other} {theirs:.2f} m/s. Ninguna celda de reanálisis resuelve el viento "
                               f"de un valle o una ladera: para cargas de diseño, erosión eólica o recurso eólico, se mide en sitio.",
                        subjects=[label], sources=sources))
                if item.variable != "ALLSKY_SFC_SW_DWN":
                    continue
                # Nivel del recurso solar en los mismos años: la energía y el VAN se mueven en la misma proporción.
                gap = (theirs - mine) / mine * 100 if mine else 0.0
                levels = f"Media {years}: CERES (NASA POWER) {mine:.2f} {unit}; {other} {theirs:.2f} {unit} ({gap:+.1f} %)."
                if abs(gap) >= SOLAR_APART_PERCENT:
                    out.append(Discovery(kind=DiscoveryKind.CONTRADICTION, title=f"{label}: el recurso solar difiere {abs(gap):.0f} % entre CERES y {other}",
                                         detail=f"{levels} La energía estimada y el VAN cambian en la misma proporción: medir el recurso en sitio antes de comprometer.",
                                         subjects=[label], sources=["NASA POWER (CERES)", other]))
                elif abs(gap) < SOLAR_CLOSE_PERCENT:
                    out.append(Discovery(kind=DiscoveryKind.AGREEMENT, title=f"{label}: CERES y {other} coinciden en el recurso solar",
                                         detail=f"{levels} Dos fuentes independientes dan el mismo recurso dentro de ±{SOLAR_CLOSE_PERCENT:.0f} %.",
                                         subjects=[label], sources=["NASA POWER (CERES)", other]))
    return out


def record_in_pipeline(pipeline: list[PipelineStage], discoveries: Sequence[Discovery]) -> None:
    """Los descubrimientos entran a la etapa «Resultados» del pipeline como evidencia propia."""
    results = next((item for item in pipeline if item.key == "results"), None)
    if results is None:
        return
    by_kind = defaultdict(int)
    for item in discoveries:
        by_kind[item.kind] += 1
    labels = {DiscoveryKind.PROBABLE_ARTIFACT: "artefactos probables", DiscoveryKind.CONFIRMED: "confirmados", DiscoveryKind.UNBACKED: "sin respaldo",
              DiscoveryKind.AGREEMENT: "coincidencias", DiscoveryKind.CONTRADICTION: "contradicciones"}
    value = " · ".join(f"{count} {labels[kind]}" for kind, count in by_kind.items()) or "Ninguno: las fuentes cruzadas no muestran discrepancias ni coincidencias destacables"
    results.evidence.append(StageEvidence(label="Descubrimientos al cruzar fuentes", value=value, provenance=Provenance.MODEL))
    if discoveries:
        results.summary = f"{results.summary} {len(discoveries)} descubrimiento(s) al cruzar fuentes independientes."


def _layer(baseline: SubjectBaseline, source_id: str) -> BaselineLayer | None:
    return next((layer for layer in baseline.layers if layer.source_id == source_id and layer.status == "READY"), None)


def _high(layer: BaselineLayer | None) -> list[str]:
    if layer is None:
        return []
    return [f"{h.label} ({h.detail})" for h in layer.highlights if h.detail and any(level in h.detail for level in HIGH_LEVELS)]


def layer_discoveries(baselines: Sequence[SubjectBaseline], terrain: TerrainResponse | None) -> list[Discovery]:
    out: list[Discovery] = []
    slopes = {site.location.label: site.metrics.slope_degrees for site in (terrain.sites if terrain else []) if site.metrics.slope_degrees is not None}
    for baseline in baselines:
        flood_high = _high(_layer(baseline, "cenepred-flood-risk"))
        critical = _layer(baseline, "ana-critical-points")
        if flood_high and critical and critical.intersection_count:
            points = ", ".join(h.label for h in critical.highlights[:3])
            out.append(Discovery(
                kind=DiscoveryKind.AGREEMENT, title=f"{baseline.subject}: dos instituciones coinciden en riesgo de inundación",
                detail=f"CENEPRED (escenario El Niño): {'; '.join(flood_high[:2])}. La ANA registra {critical.intersection_count} punto(s) crítico(s): {points}.",
                subjects=[baseline.subject], sources=["CENEPRED", "ANA"],
            ))
        mass_high = _high(_layer(baseline, "cenepred-mass-movement-risk"))
        slope = slopes.get(baseline.subject)
        if mass_high and slope is not None and slope >= STEEP_SLOPE_DEGREES:
            out.append(Discovery(
                kind=DiscoveryKind.AGREEMENT, title=f"{baseline.subject}: riesgo de movimientos en masa y pendiente fuerte",
                detail=f"CENEPRED: {'; '.join(mass_high[:2])}. NASADEM mide {slope:.1f}° de pendiente en el punto representativo (umbral {STEEP_SLOPE_DEGREES:.0f}°).",
                subjects=[baseline.subject], sources=["CENEPRED", "NASADEM"],
            ))
        greening = next((v for v in baseline.vegetation if v.variable == "VCF_NONTREE" and v.significant_after_bh and (v.trend.slope_per_year or 0) > 0), None)
        cover = baseline.land_cover
        gained = [c for c in (cover.classes if cover else []) if c.label in GROWING_COVER and c.last_percent > c.first_percent]
        lomas = _layer(baseline, "minam-coastal-lomas")
        if greening and gained:
            context = f" El MINAM registra lomas costeras en el área ({lomas.intersection_count})." if lomas and lomas.intersection_count else ""
            out.append(Discovery(
                kind=DiscoveryKind.AGREEMENT, title=f"{baseline.subject}: dos productos MODIS coinciden en más vegetación",
                detail=f"MOD44B: vegetación no arbórea {greening.trend.slope_per_year:+.2f} puntos/año (p BH {greening.adjusted_p_value:.3f}). "
                       f"MCD12Q1 {cover.first_year}→{cover.last_year}: " + ", ".join(f"{c.label.lower()} {c.first_percent:.1f} → {c.last_percent:.1f} %" for c in gained) + f".{context}",
                subjects=[baseline.subject], sources=["MODIS MOD44B", "MODIS MCD12Q1", *(["MINAM"] if context else [])],
            ))
    return out


def _ready(results: Mapping[str, TerritorialSourceResult], source_id: str) -> TerritorialSourceResult | None:
    result = results.get(source_id)
    return result if result is not None and result.status == "READY" else None


def _tally(classes: Mapping[tuple[float, float], int], keys: Sequence[tuple[float, float]], names: Mapping[int, str]) -> str:
    counts = Counter(classes[key] for key in keys)
    return ", ".join(f"{names[value]} ×{count}" for value, count in sorted(counts.items(), reverse=True))


def _year(value: object) -> int | None:
    return datetime.fromtimestamp(value / 1000, tz=timezone.utc).year if isinstance(value, (int, float)) else None


def landslide_discoveries(subject: str, results: Mapping[str, TerritorialSourceResult]) -> list[Discovery]:
    """Deslizamientos: el mapa nacional (CENEPRED) frente al global (NASA) en los mismos puntos, y los reportes COOLR
    de deslizamientos ocurridos frente a ambos mapas."""
    out: list[Discovery] = []
    cenepred, nasa, coolr = (_ready(results, key) for key in ("cenepred-susceptibility", "nasa-landslide-susceptibility", "nasa-coolr-reports"))
    national = {(f.attributes["lon"], f.attributes["lat"]): CENEPRED_CLASS[f.attributes["nivel"]] for f in (cenepred.features if cenepred else [])
                if f.layer_id == CENEPRED_MASS_MOVEMENT_LAYER and f.attributes.get("nivel") in CENEPRED_CLASS and "lon" in f.attributes}
    global_ = {(f.attributes["lon"], f.attributes["lat"]): int(f.attributes["clase"]) for f in (nasa.features if nasa else []) if "clase" in f.attributes}
    shared = [key for key in national if key in global_]
    if shared:
        close = [key for key in shared if abs(national[key] - global_[key]) <= CLOSE_CLASSES]
        both_high = sum(1 for key in shared if national[key] >= HIGH_CLASS and global_[key] >= HIGH_CLASS)
        levels = f"CENEPRED: {_tally(national, shared, CENEPRED_NAMES)}. NASA: {_tally(global_, shared, NASA_NAMES)}."
        if len(close) * 3 >= len(shared) * 2:
            out.append(Discovery(
                kind=DiscoveryKind.AGREEMENT, title=f"{subject}: CENEPRED y NASA coinciden en la susceptibilidad a deslizamientos",
                detail=f"En {len(close)} de {len(shared)} puntos de muestreo los niveles difieren a lo sumo en una clase; "
                       f"{f'en {both_high}' if both_high else 'en ninguno'} ambos marcan alta o muy alta. {levels}",
                subjects=[subject], sources=["CENEPRED", "NASA susceptibilidad global"],
            ))
        else:
            national_higher = sum(1 for key in shared if national[key] - global_[key] > CLOSE_CLASSES)
            out.append(Discovery(
                kind=DiscoveryKind.CONTRADICTION, title=f"{subject}: CENEPRED y NASA discrepan en la susceptibilidad a deslizamientos",
                detail=f"Solo {len(close)} de {len(shared)} puntos coinciden (±1 clase): CENEPRED marca más alto en {national_higher} y NASA en "
                       f"{len(shared) - len(close) - national_higher}. {levels} El mapa nacional tiene más detalle; la diferencia se resuelve en campo.",
                subjects=[subject], sources=["CENEPRED", "NASA susceptibilidad global"],
            ))
    if coolr and coolr.features:
        reports = coolr.features
        years = sorted(year for year in (_year(f.attributes.get("fecha")) for f in reports) if year)
        span = (f" entre {years[0]} y {years[-1]}" if years[0] != years[-1] else f" en {years[0]}") if years else ""
        examples = "; ".join(str(f.attributes.get("titulo")) for f in reports[:2] if f.attributes.get("titulo"))
        said = f"NASA COOLR registra {len(reports)} deslizamiento(s) reportado(s){span}" + (f" ({examples})" if examples else "") + "."
        high = [name for name, classes in (("CENEPRED", national), ("NASA", global_)) if any(value >= HIGH_CLASS for value in classes.values())]
        if high:
            out.append(Discovery(
                kind=DiscoveryKind.CONFIRMED, title=f"{subject}: deslizamientos reportados donde los mapas marcan susceptibilidad alta",
                detail=f"{said} {' y '.join(high)} {'marcan' if len(high) > 1 else 'marca'} susceptibilidad alta o muy alta en el área: lo ocurrido respalda el mapa.",
                subjects=[subject], sources=["NASA COOLR", *high],
            ))
        elif national or global_:
            precision = ", ".join(sorted({str(f.attributes.get("precision")) for f in reports if f.attributes.get("precision")}))
            out.append(Discovery(
                kind=DiscoveryKind.CONTRADICTION, title=f"{subject}: deslizamientos reportados donde los mapas no marcan susceptibilidad alta",
                detail=f"{said} Ningún punto de muestreo llega a alta en {' ni en '.join(n for n, c in (('CENEPRED', national), ('NASA', global_)) if c)}. "
                       f"La ubicación del reporte tiene precisión de {precision or 'valor no declarado'}: puede caer en una quebrada vecina; no descartar la amenaza.",
                subjects=[subject], sources=["NASA COOLR", *(n for n, c in (("CENEPRED", national), ("NASA", global_)) if c)],
            ))
    return out
