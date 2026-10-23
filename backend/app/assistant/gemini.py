"""Cliente mínimo de la API REST de Gemini (sin SDK: httpx ya es dependencia auditada del proyecto)."""

import asyncio
import re

import httpx

API = "https://generativelanguage.googleapis.com/v1beta"
PREFERRED_ALIAS = "gemini-flash-latest"
FLASH_VERSION = re.compile(r"gemini-(\d+(?:\.\d+)*)-flash")
TIMEOUT_SECONDS = 30
RETRY_STATUSES = {429, 500, 503}  # Gemini devuelve 503 en picos de demanda: un reintento corto
SYSTEM_PROMPT = (
    "Eres el asistente de Los Causas Espaciales, una consola de screening territorial con datos NASA. "
    "Responde en español, en un máximo de 160 palabras, usando EXCLUSIVAMENTE el CONTEXTO JSON del análisis. "
    "Reglas: 1) No inventes cifras, fuentes ni lugares; copia los números del contexto (puedes redondearlos). "
    "2) Si el contexto no tiene el dato, dilo: «El análisis no contiene ese dato». "
    "3) No des recomendaciones de inversión: el análisis es un screening preliminar. "
    "4) Si una tendencia no es significativa o un puntaje es empate práctico, dilo así. "
    "5) Termina con una línea «Fuentes:» que liste las claves del contexto que usaste, por ejemplo preguntas_nasa.what, puntaje, sensibilidad_van."
)


class GeminiError(RuntimeError):
    pass


_model_cache: dict[str, str] = {}


async def pick_model(client: httpx.AsyncClient, api_key: str, preferred: str | None) -> str:
    """Usa el modelo configurado o descubre uno «flash» con generateContent; nunca asume un nombre."""
    if preferred:
        return preferred
    if "auto" in _model_cache:
        return _model_cache["auto"]
    response = await client.get(f"{API}/models", headers={"x-goog-api-key": api_key}, params={"pageSize": 200})
    if response.status_code != 200:
        raise GeminiError(f"ListModels respondió {response.status_code}.")
    names = {m["name"].removeprefix("models/") for m in response.json().get("models", []) if "generateContent" in m.get("supportedGenerationMethods", [])}
    # El alias estable que mantiene Google; si no existe, el «gemini-X-flash» de versión más alta sin variantes.
    if PREFERRED_ALIAS in names:
        _model_cache["auto"] = PREFERRED_ALIAS
        return PREFERRED_ALIAS
    versioned = [(tuple(int(part) for part in match.group(1).split(".")), name) for name in names if (match := FLASH_VERSION.fullmatch(name))]
    if not versioned:
        raise GeminiError("No hay un modelo «flash» estable disponible para esta clave.")
    _model_cache["auto"] = max(versioned)[1]
    return _model_cache["auto"]


async def generate(api_key: str, model_hint: str | None, question: str, context_json: str) -> tuple[str, str]:
    async with httpx.AsyncClient(timeout=TIMEOUT_SECONDS) as client:
        model = await pick_model(client, api_key, model_hint)
        body = {
            "systemInstruction": {"parts": [{"text": SYSTEM_PROMPT}]},
            "contents": [{"role": "user", "parts": [{"text": f"CONTEXTO JSON:\n{context_json}\n\nPREGUNTA: {question}"}]}],
            "generationConfig": {"temperature": 0.2, "maxOutputTokens": 600},
        }
        for attempt in range(2):
            response = await client.post(f"{API}/models/{model}:generateContent", headers={"x-goog-api-key": api_key}, json=body)
            if response.status_code in RETRY_STATUSES and attempt == 0:
                await asyncio.sleep(1.5)
                continue
            break
        if response.status_code != 200:
            raise GeminiError(f"Gemini respondió {response.status_code}.")
        candidates = response.json().get("candidates", [])
        parts = candidates[0].get("content", {}).get("parts", []) if candidates else []
        text = "".join(part.get("text", "") for part in parts).strip()
        if not text:
            raise GeminiError("Gemini no devolvió texto (posible bloqueo de seguridad).")
        return text, model
