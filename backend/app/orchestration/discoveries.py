"""Descubrimientos: lo que aparece al cruzar fuentes independientes.

Reglas explícitas y deterministas; ninguna consulta externa. Un descubrimiento no es una conclusión: señala un
artefacto probable, una tendencia confirmada o sin respaldo, o una coincidencia entre instituciones distintas.
"""

from collections import defaultdict
from collections.abc import Sequence

from ..schemas.analysis import Provenance
from ..schemas.baseline import BaselineLayer, SubjectBaseline
from ..schemas.climate import Agreement, ExtremeIndexSummary
from ..schemas.screening import Discovery, DiscoveryKind, PipelineStage, StageEvidence
from ..schemas.terrain import TerrainResponse

PRIMARY = "NASA POWER (MERRA-2)"
ARTIFACT_RATIO = 5.0         # el reanálisis supera al menos 5 veces a cada fuente de observación
STEEP_SLOPE_DEGREES = 15.0
HIGH_LEVELS = ("riesgo alto", "riesgo muy alto")
GROWING_COVER = {"Pastizal", "Matorral abierto", "Matorral cerrado", "Sabana", "Sabana arbolada", "Humedal permanente"}


def short(source: str) -> str:
    return "IMERG" if "IMERG" in source else "CHIRPS" if "CHIRPS" in source else source


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
