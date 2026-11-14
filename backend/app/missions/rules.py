"""Reglas que el modo jugador hereda de la plataforma: funciones puras, sin I/O.

El juego no tiene reglas propias sobre los datos. «Artefacto probable» es la regla de ADR-036 tal como la aplica
`rainfall_discoveries`, y el respaldo de la temperatura sale del código `agreement` del contraste con la segunda fuente.
El contrato (schemas/missions.py) las aplica al validar: lo que diga el archivo sobre estos campos no se usa.
"""

from collections.abc import Mapping

from ..orchestration.discoveries import ARTIFACT_RATIO
from ..schemas.pipeline import Agreement

# La misma condición de unidad que `rainfall_discoveries`: la razón entre fuentes solo se compara en índices de lluvia
# en mm; en un índice en días (CDD, R10MM) no dice nada sobre un evento.
ARTIFACT_UNIT = "mm"


def is_probable_artifact(unit: str | None, value: float | None, countercheck_values: Mapping[str, float | None]) -> bool:
    """Verdadero si el reanálisis supera al menos ARTIFACT_RATIO veces a cada producto de contraste, en un índice en mm.

    Un valor que falta nunca prueba un artefacto: sin unidad, sin valor, sin contraste o con un contraste vacío, es falso.
    """
    if unit != ARTIFACT_UNIT or value is None or not countercheck_values:
        return False
    return all(other is not None and other * ARTIFACT_RATIO < value for other in countercheck_values.values())


def heat_support(heat: str, agreement: str | None) -> str | None:
    """Qué dice la segunda fuente de la clase de temperatura del lugar; None si el lugar no tiene evidencia suficiente.

    Solo «coincide» confirma. «sin_respaldo», «solo_contraste» y «sin_tendencia» quedan como «una_fuente»: en los años
    comunes las dos fuentes no son significativas a la vez, así que la clase se apoya solo en la serie de NASA POWER.
    """
    if heat == "sin_evidencia":
        return None
    if agreement is None:
        return "sin_segunda_fuente"
    if agreement == Agreement.COINCIDE:
        return "confirmada"
    if agreement == Agreement.CONTRADICE:
        return "contradicha"
    return "una_fuente"
