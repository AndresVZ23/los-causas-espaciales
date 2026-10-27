"""Contexto del asistente: resumen compacto del análisis (sin series diarias) y respuestas por reglas.

El asistente nunca consulta fuentes: todo lo que dice sale de este contexto, que a su vez sale del sobre C2.
"""

import json
import re
import unicodedata
from typing import Any

MAX_CONTEXT_CHARS = 40_000


def _pick(item: dict[str, Any], *keys: str) -> dict[str, Any]:
    return {key: item.get(key) for key in keys if item.get(key) is not None}


def build_context(envelope: dict[str, Any]) -> dict[str, Any]:
    context: dict[str, Any] = {
        "analisis": _pick(envelope, "analysis_id", "title", "sector", "sector_label", "period", "disclaimer"),
        "sujetos": [{"nombre": s.get("label"), "tipo": s.get("kind"), "punto": s.get("representative_point")} for s in envelope.get("subjects", [])],
        "preguntas_nasa": [_pick(q, "key", "question_es", "status", "answer") for q in envelope.get("nasa_questions", [])],
        "tendencias_significativas": [
            _pick(t, "site", "label", "unit", "slope_per_year", "change_over_period", "change_percent_of_mean", "first_year", "last_year", "adjusted_p_value")
            for t in envelope.get("trend_findings", [])
        ],
        "brechas": [_pick(g, "dataset", "impact", "next_action") for g in envelope.get("data_gaps", [])],
        "descubrimientos": [_pick(d, "kind", "title", "detail", "sources") for d in envelope.get("discoveries", [])],
        "supuestos": [_pick(a, "label", "value", "unit") for a in envelope.get("assumption_items", [])],
        "pipeline": [_pick(s, "name", "status", "summary") for s in envelope.get("pipeline", [])],
    }
    card = envelope.get("scorecard")
    if card:
        context["puntaje"] = {
            **_pick(card, "leader", "margin", "tie", "stability_draws"),
            "sujetos": [_pick(s, "subject", "score", "rank", "first_place_share", "coverage") for s in card.get("subjects", [])],
            "criterios": [_pick(c, "label", "weight", "unit", "worst", "best", "basis") for c in card.get("criteria", [])],
            "pesos_que_cambian_el_primer_lugar": [s["key"] for s in card.get("weight_sensitivity", []) if s.get("changes_leader")],
        }
    sensitivity = envelope.get("financial_sensitivity") or []
    if sensitivity:
        context["sensibilidad_van"] = [{
            "sujeto": item.get("subject"), "van_base_usd": item.get("base_npv"),
            "escenarios": [_pick(s, "label", "npv", "changes") for s in item.get("scenarios", [])],
            "factores_principales": [_pick(b, "label", "low_value", "high_value", "npv_at_low", "npv_at_high", "provenance") for b in item.get("tornado", [])[:4]],
            "equilibrios": [b.get("note") for b in item.get("break_evens", [])],
        } for item in sensitivity]
    sites = []
    for site in envelope.get("sites", []):
        entry: dict[str, Any] = {"sujeto": (site.get("location") or {}).get("label") or site.get("label")}
        if site.get("area_km2") is not None:  # terrenos del piloto inmobiliario
            entry["terreno"] = {
                **_pick(site, "area_km2", "terrain_slope_degrees"),
                "lluvia_p99_mm_dia": (site.get("spatial_exposure") or {}).get("p99_precipitation_mm_day"),
                "alertas_territoriales": {key: value for key, value in (site.get("territorial_intersections") or {}).items() if value},
            }
        entry["variables"] = [{
            **_pick(v, "label", "mean", "display_unit", "annual_variability_percent", "last_valid_date"),
            "año_en_curso": _pick(v.get("current_period") or {}, "year", "through", "anomaly", "anomaly_percent", "rank", "years_compared"),
        } for v in site.get("variables", [])]
        if site.get("extremes"):
            entry["extremos_etccdi"] = [{
                **_pick(e, "variable", "label", "mean", "display_unit", "adjusted_p_value", "significant_after_bh"),
                "contraste_imerg": _pick(e.get("countercheck") or {}, "agreement", "slope_per_year", "adjusted_p_value"),
                "contrastes": [_pick(c, "source", "agreement", "slope_per_year", "adjusted_p_value") for c in e.get("counterchecks", [])],
                "años_atipicos": [_pick(a, "year", "value", "countercheck_value", "countercheck_values") for a in e.get("atypical_years", [])],
            } for e in site["extremes"]]
        if site.get("finance"):
            entry["finanzas"] = _pick(site["finance"], "annual_energy_mwh", "annual_revenue_usd", "npv_usd")
        sites.append(entry)
    if sites:
        context["sitios"] = sites
    segments = envelope.get("segments") or []
    if segments:
        context["tramos"] = [{
            **_pick(s, "label", "length_km", "heavy_rain_days_per_year", "terrain_slope_degrees"),
            "lluvia_max_diaria_celdas_mm": (s.get("spatial_exposure") or {}).get("rx1day_mm"),
            "van_usd": (s.get("finance") or {}).get("npv_usd"),
            "alertas_territoriales": {key: value for key, value in (s.get("territorial_intersections") or {}).items() if value},
        } for s in segments]
        context["corredor"] = _pick(envelope.get("corridor_source") or {}, "name", "source", "license")
    terrain = envelope.get("terrain")
    if terrain:
        context["relieve"] = [{"sujeto": (s.get("location") or {}).get("label"), "estado": s.get("status"), **(s.get("metrics") or {})} for s in terrain.get("sites", [])]
    return context


def context_text(context: dict[str, Any]) -> str:
    text = json.dumps(context, ensure_ascii=False, separators=(",", ":"))
    return text[:MAX_CONTEXT_CHARS]


def _plain(text: str) -> str:
    return "".join(ch for ch in unicodedata.normalize("NFD", text.lower()) if unicodedata.category(ch) != "Mn")


# Reglas: palabras clave → sección del contexto. El orden importa: lo más específico primero.
RULES: list[tuple[tuple[str, ...], str]] = [
    (("empate", "puntaje", "ranking", "score", "mejor sitio", "cual conviene", "priorizar", "multicriterio", "peso"), "puntaje"),
    (("van", "escenario", "sensibil", "precio", "capex", "opex", "equilibrio", "rentab", "tornado"), "sensibilidad_van"),
    (("tramo", "corredor", "carretera", "via ", "vial", "interrup"), "tramos"),
    (("terreno", "lote", "inmobiliar", "parcela", "area de analisis"), "terrenos"),
    (("imerg", "chirps", "atipic", "artefacto", "contraste", "satelit", "descubr", "cruzar fuentes", "coinciden",
      "deslizamiento", "lhasa", "coolr", "susceptib", "movimientos en masa", "discrepan"), "contraste"),
    (("extrem", "lluvia max", "lluvias max", "huaico", "rx1day", "rx5day", "racha seca", "sequia"), "extremos"),
    (("brecha", "falta", "pendiente", "no se sabe", "limitacion"), "brechas"),
    (("donde",), "where"),
    (("cuanto", "magnitud"), "how_much"),
    (("significativ", "confian", "p-value", "p valor", "estadistic"), "significant"),
    (("invertir", "inversion", "significa", "implica", "riesgo"), "so_what"),
    (("cambia", "tendencia", "que pasa"), "what"),
    (("fuente", "procedencia", "dato", "nasa"), "fuentes"),
]


def _question(context: dict[str, Any], key: str) -> str | None:
    return next((q.get("answer") for q in context.get("preguntas_nasa", []) if q.get("key") == key), None)


# Variable por palabra clave → fragmento de su etiqueta en el análisis.
VARIABLES = {"temperatura": "temperatura", "calor": "temperatura", "lluvia": "precipitaci", "precipit": "precipitaci",
             "viento": "viento", "radiacion": "irradiancia", "irradiancia": "irradiancia", "sol": "irradiancia"}
# Nombres legibles de las capas territoriales de Codex (claves de `territorial_intersections`).
LAYER_NAMES = {
    "cenepred-flood-risk": "riesgo de inundación (CENEPRED)", "cenepred-mass-movement-risk": "movimientos en masa (CENEPRED)",
    "sernanp-anp": "áreas protegidas (SERNANP)", "cultura-archaeology": "patrimonio arqueológico (SIGDA)",
    "cultura-archaeology-declared": "patrimonio declarado (SIGDA)", "ingemmet-geohazards": "peligros geológicos (INGEMMET)",
}
CURRENT_YEAR_WORDS = ("este ano", "ano en curso", "en lo que va", "actual", "hoy", "2026")
RELIEF_WORDS = ("relieve", "elevacion", "altitud", "pendiente del terreno", "orientacion", "nasadem")


def _musd(value: float) -> str:
    return f"{'−' if value < 0 else ''}USD {abs(value) / 1e6:,.2f} M"


def _lower_first(text: str) -> str:
    """Minúscula inicial dentro de una frase, salvo siglas (CAPEX, OPEX, VAN)."""
    return text if text[:2].isupper() else text[:1].lower() + text[1:]


def _fmt(value: Any, digits: int = 2) -> str:
    return f"{value:,.{digits}f}" if isinstance(value, (int, float)) else str(value)


def _sites_named(plain: str, context: dict[str, Any]) -> list[str]:
    names = [s.get("nombre") or "" for s in context.get("sujetos", [])]
    named = [name for name in names if name and _plain(name) in plain]
    return named or names


def _variable_answer(plain: str, context: dict[str, Any]) -> tuple[str, list[str]] | None:
    fragment = next((target for word, target in VARIABLES.items() if re.search(rf"\b{word}", plain)), None)
    if not fragment:
        return None
    sites = _sites_named(plain, context)
    if any(word in plain for word in CURRENT_YEAR_WORDS):
        lines = []
        for site in context.get("sitios", []):
            if site["sujeto"] not in sites:
                continue
            for variable in site.get("variables", []):
                current = variable.get("año_en_curso") or {}
                if fragment in _plain(variable.get("label", "")) and current:
                    change = f"{current['anomaly_percent']:+.1f} %" if current.get("anomaly_percent") is not None else f"{current.get('anomaly', 0):+.2f} {variable.get('display_unit', '')}"
                    lines.append(f"{site['sujeto']}: {change} frente a la misma ventana de los años completos, puesto {current.get('rank')} de {current.get('years_compared')} (hasta {current.get('through')})")
        if lines:
            return f"{variable_label(fragment)} en {current_year(context)}: " + "; ".join(lines) + ". El año en curso no entra en la tendencia.", ["sites.variables.current_period"]
    findings = [t for t in context.get("tendencias_significativas", []) if fragment in _plain(t.get("label", "")) and t.get("site") in sites]
    if findings:
        return " ".join(
            f"{t['label']} en {t['site']}: {_fmt(t['change_over_period'])} {t['unit']} entre {t['first_year']} y {t['last_year']} "
            f"({_fmt(t['slope_per_year'], 4)} {t['unit']}/año, p BH {_fmt(t['adjusted_p_value'], 3)})." for t in findings
        ), ["trend_findings"]
    return f"{variable_label(fragment)}: sin tendencia significativa tras el ajuste Benjamini–Hochberg en {', '.join(sites)}. Eso es evidencia insuficiente, no prueba de que no cambie.", ["trend_findings"]


def variable_label(fragment: str) -> str:
    return {"temperatura": "Temperatura", "precipitaci": "Precipitación", "viento": "Viento", "irradiancia": "Radiación solar"}[fragment]


def current_year(context: dict[str, Any]) -> str:
    for site in context.get("sitios", []):
        for variable in site.get("variables", []):
            if (variable.get("año_en_curso") or {}).get("year"):
                return str(variable["año_en_curso"]["year"])
    return "el año en curso"


def answer_by_rules(question: str, context: dict[str, Any]) -> tuple[str, list[str]]:
    """Respuesta determinista armada con textos y cifras del propio análisis."""
    plain = _plain(question)
    if any(word in plain for word in RELIEF_WORDS) and context.get("relieve"):
        parts = [f"{r['sujeto']}: elevación {_fmt(r.get('elevation_m'), 0)} m, pendiente {_fmt(r.get('slope_degrees'))}°, orientación {r.get('aspect_cardinal') or 'N/D'}"
                 if r.get("estado") == "READY" else f"{r['sujeto']}: relieve {r.get('estado', 'no disponible').lower()}"
                 for r in context["relieve"]]
        return "Relieve NASADEM (1 arc-second): " + "; ".join(parts) + ".", ["terrain"]
    section = next((target for words, target in RULES if any(word in plain for word in words)), None)
    if section == "extremos" and any(site.get("extremos_etccdi") for site in context.get("sitios", [])):
        sites = _sites_named(plain, context)
        agreement = {"coincide": "IMERG coincide", "contradice": "IMERG contradice", "sin_respaldo": "IMERG no la respalda",
                     "solo_contraste": "solo IMERG la ve", "sin_tendencia": "sin tendencia en ninguna fuente"}
        lines = [f"{e['label']} en {site['sujeto']}: tendencia significativa (p BH {_fmt(e.get('adjusted_p_value'), 3)}); {agreement.get(e.get('contraste_imerg', {}).get('agreement'), 'sin contraste')}"
                 for site in context["sitios"] if site["sujeto"] in sites for e in site["extremos_etccdi"] if e.get("significant_after_bh")]
        return ("; ".join(lines) + "." if lines else "Ningún índice de extremos de lluvia tiene tendencia significativa tras Benjamini–Hochberg en "
                + ", ".join(sites) + "."), ["sites.extremes"]
    if section not in {"puntaje", "sensibilidad_van", "contraste", "brechas"}:
        by_variable = _variable_answer(plain, context)
        if by_variable:
            return by_variable
    if section in {"what", "where", "how_much", "significant", "so_what"}:
        text = _question(context, section)
        if text:
            return text, [f"nasa_questions.{section}"]
    sites = _sites_named(plain, context)
    if section == "tramos" and context.get("tramos"):
        named = [t for t in context["tramos"] if _plain(t["label"]) in plain] or context["tramos"]
        lines = [
            f"{t['label']}: {_fmt(t.get('length_km'), 1)} km, {_fmt(t.get('heavy_rain_days_per_year'))} días/año de lluvia fuerte, "
            f"VAN de mitigación {_musd(t['van_usd']) if t.get('van_usd') is not None else 'N/D'}"
            + (f", alertas: {', '.join(f'{LAYER_NAMES.get(k, k)} {v}' for k, v in t['alertas_territoriales'].items())}" if t.get("alertas_territoriales") else ", sin alertas territoriales devueltas")
            for t in named
        ]
        return f"{context.get('corredor', {}).get('name', 'Corredor')}. " + "; ".join(lines) + ".", ["segments", "territorial_evidence"]
    parcels = [site for site in context.get("sitios", []) if "terreno" in site]
    if section == "terrenos" and parcels:
        named = [site for site in parcels if site["sujeto"] and _plain(site["sujeto"]) in plain] or parcels
        lines = []
        for site in named:
            info = site["terreno"]
            van = (site.get("finanzas") or {}).get("npv_usd")
            alerts = info.get("alertas_territoriales") or {}
            lines.append(
                f"{site['sujeto']}: {_fmt(info.get('area_km2'), 3)} km², pendiente {_fmt(info.get('terrain_slope_degrees'), 1)}°, "
                f"VAN {_musd(van) if van is not None else 'N/D'}"
                + (f", alertas: {', '.join(f'{LAYER_NAMES.get(k, k)} {v}' for k, v in alerts.items())}" if alerts else ", sin alertas territoriales devueltas")
            )
        return "; ".join(lines) + ".", ["sites", "territorial_evidence"]
    if section == "puntaje" and "puntaje" in context:
        card = context["puntaje"]
        parts = [f"{s['subject']}: {s.get('score', 'N/D')}/100, primero en {round(s.get('first_place_share', 0) * 100)} % de las combinaciones de pesos" for s in card["sujetos"]]
        verdict = "Empate práctico: el puntaje no separa los sitios." if card.get("tie") else f"Lidera {card.get('leader')}."
        return f"{verdict} {'; '.join(parts)}.", ["scorecard"]
    if section == "sensibilidad_van" and "sensibilidad_van" in context:
        lines = []
        for item in context["sensibilidad_van"]:
            if item["sujeto"] not in sites:
                continue
            scenarios = ", ".join(f"{s['label'].lower()} {_musd(s['npv'])}" for s in item["escenarios"])
            top = _lower_first(item["factores_principales"][0]["label"]) if item["factores_principales"] else "N/D"
            lines.append(f"{item['sujeto']}: {scenarios}; el factor que más mueve el VAN es el {top}.")
        return " ".join(lines), ["financial_sensitivity"]
    if section == "contraste":
        notes = [f"{e['label']} {site['sujeto']} {a['year']}: MERRA-2 {a['value']} {e.get('display_unit', '')}"
                 + "".join(f", {source.split(' ')[0]} {value}" for source, value in (a.get("countercheck_values") or {}).items())
                 for site in context.get("sitios", []) for e in site.get("extremos_etccdi", []) for a in e.get("años_atipicos", [])]
        significant = _question(context, "significant") or ""
        contrast = significant[significant.find("Contraste satelital"):] if "Contraste satelital" in significant else ""
        found = [f"{d['title']}: {d['detail']}" for d in context.get("descubrimientos", [])]
        if notes or contrast or found:
            return (contrast + (" Años atípicos: " + "; ".join(notes) + "." if notes else "")
                    + (" Descubrimientos al cruzar fuentes: " + " ".join(found) if found else "")).strip(), ["sites.extremes.counterchecks", "discoveries"]
    if section == "brechas" and context.get("brechas"):
        return "Brechas abiertas: " + "; ".join(f"{g['dataset']}: {g['impact']}" for g in context["brechas"]) + ".", ["data_gaps"]
    if section == "fuentes":
        stages = next((s.get("summary") for s in context.get("pipeline", []) if s.get("name") == "Extracción"), None)
        return (stages or "Los datos provienen de NASA POWER y NASADEM con procedencia registrada por variable.") + " " + context["analisis"].get("disclaimer", ""), ["pipeline.extraction", "disclaimer"]
    topics = "qué cambia, dónde, cuánto, si es significativo, qué significa para invertir, escenarios del VAN, puntaje, contraste IMERG, brechas y fuentes"
    return f"En modo reglas puedo responder sobre: {topics}. Reformule la pregunta con alguno de esos temas.", []


NUMBER = re.compile(r"(?<![\w.])[-−]?\d[\d.,]*")


def _numbers(text: str) -> list[float]:
    values = []
    for raw in NUMBER.findall(text):
        cleaned = raw.replace("−", "-").rstrip(".,")
        # Formato es-PE y en: 1,234.5 o 1.234,5; se prueba la lectura con punto decimal y luego con coma.
        for candidate in (cleaned.replace(",", ""), cleaned.replace(".", "").replace(",", ".")):
            try:
                values.append(float(candidate))
                break
            except ValueError:
                continue
    return values


def ungrounded_numbers(answer: str, context: str) -> list[float]:
    """Cifras de la respuesta que no salen del contexto (redondeadas, en %, en millones o en miles)."""
    known = _numbers(context)
    missing = []
    for value in _numbers(answer):
        if abs(value) <= 10 and float(value).is_integer():
            continue  # conteos pequeños («2 sitios», «5 de 20») y ordinales
        decimals = 0 if float(value).is_integer() else len(str(value).split(".")[1])
        tolerance = 0.5 * 10 ** (-decimals) + 1e-9  # la cifra debe ser un redondeo de un valor del contexto
        # Escalas admitidas: igual, fracción → %, USD → millones o miles, y pendiente por año → por década.
        scales = (1, 100, 1e-6, 1e-3, 10)
        # Sin signo: «−USD 3.08 M» se lee como 3.08 porque el signo va antes de la moneda.
        if not any(abs(abs(known_value * scale) - abs(value)) <= tolerance for known_value in known for scale in scales):
            missing.append(value)
    return missing
