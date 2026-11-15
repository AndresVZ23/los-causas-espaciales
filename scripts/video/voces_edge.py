"""Voces de las cinemáticas de TERRA 2045 con las voces neuronales de Microsoft Edge (edge-tts). ADR-050.

    .venv\\Scripts\\python.exe scripts/video/voces_edge.py      (lo corre VOCES.bat)

Lee scripts/video/guion.json y escribe videos/voz/es/<id>.mp3 y videos/voz/en/<id>.mp3, más videos/voz/voces_edge.json
con la voz de cada línea. render.py usa estos mp3 cuando existen (si no, los .wav de voces.ps1 y voces_ingles.ps1).
Las voces de niño (Mario, Killa) se logran subiendo el tono en la propia síntesis; por eso render.py no les vuelve a
cambiar el tono. Necesita internet: el texto va al servicio de lectura en voz alta de Edge. Licencia: ese servicio no da
una licencia explícita para publicar el audio; vale para la demo del hackatón (ver DATA_SOURCES.md).
"""
import asyncio
import json
import sys
from pathlib import Path

import edge_tts

ROOT = Path(__file__).resolve().parents[2]
GUION = json.loads((Path(__file__).with_name("guion.json")).read_text(encoding="utf-8"))
OUT = ROOT / "videos" / "voz"

# Rol → (voz, velocidad, tono) por idioma. Nikol y Andrés con acento peruano; Killa con acento andino (Bolivia).
ROLES = {
    "es": {
        "narrador": ("es-MX-JorgeNeural", "+2%", "-2Hz"),
        "nikol": ("es-PE-CamilaNeural", "+0%", "+0Hz"),
        "radio": ("es-PE-CamilaNeural", "+4%", "+0Hz"),
        "andres": ("es-PE-AlexNeural", "+0%", "+0Hz"),
        "viajero": ("es-MX-DaliaNeural", "+2%", "+0Hz"),
        "mario": ("es-CO-SalomeNeural", "+6%", "+38Hz"),
        "killa": ("es-BO-SofiaNeural", "-2%", "+45Hz"),
    },
    "en": {
        "narrador": ("en-US-ChristopherNeural", "+0%", "-2Hz"),
        "nikol": ("en-US-AvaNeural", "+0%", "+0Hz"),
        "radio": ("en-US-AvaNeural", "+4%", "+0Hz"),
        "andres": ("en-US-BrianNeural", "+0%", "+0Hz"),
        "viajero": ("en-US-EmmaNeural", "+2%", "+0Hz"),
        "mario": ("en-US-AnaNeural", "+4%", "-14Hz"),
        "killa": ("en-US-AnaNeural", "-4%", "+4Hz"),
    },
}


async def speak(text: str, voice: str, rate: str, pitch: str, out: Path) -> None:
    tmp = out.with_suffix(".tmp.mp3")
    for attempt in range(4):
        try:
            await edge_tts.Communicate(text, voice, rate=rate, pitch=pitch).save(str(tmp))
            if tmp.stat().st_size > 2000:
                tmp.replace(out)
                return
        except Exception as error:  # red o servicio: se reintenta con espera creciente
            print(f"    reintento {attempt + 1}: {error}", flush=True)
        await asyncio.sleep(2 + attempt * 3)
    raise RuntimeError(f"No se pudo generar {out.name} con {voice}")


async def main() -> None:
    only = set(sys.argv[1:])
    for lang in ("es", "en"):
        (OUT / lang).mkdir(parents=True, exist_ok=True)
    # Solo se vuelven a generar las líneas nuevas o cambiadas (texto, voz, velocidad o tono distintos al último informe).
    report_path = OUT / "voces_edge.json"
    before = {}
    if report_path.exists():
        for item in json.loads(report_path.read_text(encoding="utf-8")):
            before[(item["id"], item["lang"])] = item
    report, made = [], 0
    for line in GUION["lines"]:
        for lang in ("es", "en"):
            voice, rate, pitch = ROLES[lang].get(line["who"], ROLES[lang]["narrador"])
            item = {"id": line["id"], "lang": lang, "who": line["who"], "voice": voice, "rate": rate, "pitch": pitch, "text": line[lang]}
            out = OUT / lang / f"{line['id']}.mp3"
            same = before.get((line["id"], lang)) == item and out.exists()
            if (not only and not same) or line["id"] in only:
                await speak(line[lang], voice, rate, pitch, out)
                made += 1
                print(f"  {line['id']} {lang} ({line['who']})", flush=True)
            report.append(item)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"Listo: {made} audios nuevos o cambiados ({len(report)} en total) en {OUT}")


if __name__ == "__main__":
    asyncio.run(main())
