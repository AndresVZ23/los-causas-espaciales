"""Arma el demo de 30 segundos de TERRA 2045 para NASA Space Apps 2026.

    python build.py --lang es                    # español con subtítulos en inglés, voz libre de Piper (sin internet)
    python build.py --lang en                    # inglés
    python build.py --lang es --voz edge         # la voz neuronal del tráiler (envía el guion al servicio de Edge)

Pasos: 1) voces; 2) línea de tiempo y datos para overlay.html; 3) video de base: las cinemáticas en 3D (cine/, con la
tarjeta gráfica) y el cierre; 4) cuadros de la capa de textos y capturas (frames.cjs); 5) música con atenuación bajo
la voz; 6) unión, subtítulos (.srt) y comprobación de que el archivo dura exactamente lo que dice guion.json (30 s: el
límite de la guía de entrega).

Necesita ffmpeg (FFMPEG=ruta, o el paquete imageio-ffmpeg) y Node con Playwright (PLAYWRIGHT_DIR=carpeta node_modules).
Voces: --voz piper (por defecto) usa Piper con voces de licencia abierta; PIPER_PYTHON es el Python que tiene piper-tts y
PIPER_VOICES la carpeta de los modelos (por defecto .herramientas/voz y .herramientas/piper-voces: la ruta debe ser
corta, espeak-ng no admite más de 160 caracteres). --voz edge necesita edge-tts e internet. --voz mac sirve solo para
ensayar: la licencia de macOS no permite publicar sus voces. Las tomas fijas se generan con tomas.cjs.
"""
import argparse
import json
import os
import re
import subprocess
import sys
import wave
from pathlib import Path

HERE = Path(__file__).resolve().parent
GUION = json.loads((HERE / "guion.json").read_text(encoding="utf-8"))
FPS = GUION["fps"]
N = GUION["cuadros"]
TOTAL = N / FPS

# Voz por motor e idioma. «piper»: voces de licencia abierta, sin internet (es_MX-claude-high, Apache-2.0;
# en_US-ljspeech-high, datos de dominio público); el segundo valor es la duración relativa (menos de 1 = más rápido).
# «edge»: las del tráiler (ADR-050). «mac»: solo para ensayar, su licencia no permite publicar el audio.
VOICES = {
    "piper": {"es": ("es_MX-claude-high", "0.81"), "en": ("en_US-ljspeech-high", "0.8")},
    "mac": {"es": ("Paulina", "192"), "en": ("Samantha", "186")},
    "edge": {"es": ("es-PE-CamilaNeural", "+9%", "+0Hz"), "en": ("en-US-AvaNeural", "+7%", "+0Hz")},
}
def ffmpeg_path():
    if os.environ.get("FFMPEG"):
        return os.environ["FFMPEG"]
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except ImportError:
        return "ffmpeg"


FF = ffmpeg_path()


def run(cmd, **kw):
    result = subprocess.run([str(c) for c in cmd], capture_output=True, text=True, **kw)
    if result.returncode != 0:
        raise RuntimeError(" ".join(str(c) for c in cmd)[:400] + "\n" + result.stderr[-1800:])
    return result


def ff(args):
    return run([FF, "-hide_banner", "-loglevel", "error", "-y", *args])


def wav_seconds(path):
    with wave.open(str(path)) as handle:
        return handle.getnframes() / handle.getframerate()


# --- 1. Voces ---------------------------------------------------------------------------------------------------------
def synth(text, lang, engine, raw):
    if engine == "piper":
        voice, scale = VOICES["piper"][lang]
        tools = HERE.parents[2] / ".herramientas"
        python = os.environ.get("PIPER_PYTHON", str(tools / "voz" / "bin" / "python"))
        models = os.environ.get("PIPER_VOICES", str(tools / "piper-voces"))
        run([python, "-m", "piper", "-m", voice, "--data-dir", models, "--length-scale", scale, "-f", raw, "--", text])
    elif engine == "mac":
        voice, rate = VOICES["mac"][lang]
        run(["say", "-v", voice, "-r", rate, "-o", raw, text])
    else:
        import asyncio
        import edge_tts
        voice, rate, pitch = VOICES["edge"][lang]
        asyncio.run(edge_tts.Communicate(text, voice, rate=rate, pitch=pitch).save(str(raw)))


def voices(lang, engine, work):
    folder = work / "voz" / f"{engine}_{lang}"
    folder.mkdir(parents=True, exist_ok=True)
    trim = "silenceremove=start_periods=1:start_threshold=-45dB:start_silence=0.03"
    out = []
    for line in GUION["voz"]:
        raw = folder / f"{line['id']}.crudo.{ {'mac': 'aiff', 'edge': 'mp3'}.get(engine, 'wav') }"
        clean = folder / f"{line['id']}.wav"
        stamp = folder / f"{line['id']}.txt"
        # «<idioma>_voz»: cómo se le escribe la frase al sintetizador cuando un nombre propio no es de su idioma.
        spoken = line.get(f"{lang}_voz", line[lang])
        signature = f"{VOICES[engine][lang]}|{spoken}"
        if not clean.exists() or not stamp.exists() or stamp.read_text(encoding="utf-8") != signature:
            synth(spoken, lang, engine, raw)
            ff(["-i", raw, "-af", f"{trim},areverse,{trim},areverse,loudnorm=I=-17:TP=-2:LRA=7,aresample=48000", "-ac", "1", clean])
            stamp.write_text(signature, encoding="utf-8")
        out.append({"id": line["id"], "wav": clean, "dur": wav_seconds(clean), "wanted": line["en_s"], "text": line[lang], "sub": line.get("sub", line["en"])})
    # Cada frase empieza donde pide el guion o, si la anterior se alargó, un respiro después.
    cursor = 0.0
    for item in out:
        item["inicio"] = round(max(item["wanted"], cursor + 0.16), 3)
        item["fin"] = round(item["inicio"] + item["dur"], 3)
        cursor = item["fin"]
    if out[-1]["fin"] > TOTAL - 0.35:
        detail = "\n".join(f"  {v['id']} {v['inicio']:5.2f}–{v['fin']:5.2f} s ({v['dur']:.2f}) pedía {v['wanted']:.2f}: {v['text']}" for v in out)
        raise SystemExit(f"La voz termina en {out[-1]['fin']:.2f} s y el video dura {TOTAL:.2f} s: hay que acortar el guion o subir la velocidad.\n{detail}")
    return out


# --- 2. Línea de tiempo de la base y datos para la capa de textos ------------------------------------------------------
def segments():
    """Tramos del video de base, en orden: cinemática en 3D, clip de video o negro (ahí van las capturas de la capa)."""
    out, frame = [], 0
    for item in GUION["base"]:
        out.append((item, frame, frame + item["cuadros"]))
        frame += item["cuadros"]
    if frame != N:
        raise SystemExit(f"Los tramos de la base suman {frame} cuadros y el video tiene {N}.")
    return out


def spec(lang, vo, tomas):
    return {
        "lang": lang, "fps": FPS, "cuadros": N, "tomas": tomas.resolve().as_uri() + "/",
        "textos": GUION["textos"][lang],
        "planos": {p["id"]: [p["desde"] / FPS, p["hasta"] / FPS] for p in GUION["planos"]},
        "voz": {v["id"]: {"inicio": v["inicio"], "fin": v["fin"], "sub": v["sub"]} for v in vo},
        "subtitulos": lang != "en",
        "segmentos": [{"inicio": a / FPS, "fin": b / FPS, "plano": s["plano"], "escena": s.get("escena"), "desde_s": s.get("desde_s", 0),
                       **{k: s[k][lang] for k in ("titulo", "lugar", "paso") if k in s}} for s, a, b in segments()],
        "cortes": GUION["cortes"][lang],
    }


# --- 3. Video de base: cinemáticas en 3D, el cierre del tráiler y negro bajo las capturas ------------------------------
def cinematics(work):
    """Dibuja las cinemáticas (cine/cine_frames.cjs) una sola vez: son las mismas en los dos idiomas."""
    plan = [{"escena": s["escena"], "cuadros": s["cuadros"], "fps": FPS, "desde_s": s.get("desde_s", 0)} for s, _, _ in segments() if s["tipo"] == "cine"]
    folder = work / "cine"
    stamp = folder / "hecho.json"
    signature = json.dumps(plan, sort_keys=True) + str((HERE / "cine" / "cine.js").stat().st_mtime_ns)
    done = stamp.exists() and stamp.read_text(encoding="utf-8") == signature and all(len(list((folder / p["escena"]).glob("*.jpg"))) == p["cuadros"] for p in plan)
    if not done:
        folder.mkdir(parents=True, exist_ok=True)
        for scene in {p["escena"] for p in plan}:          # sin cuadros de una versión anterior más larga
            for old in (folder / scene).glob("*.jpg"):
                old.unlink()
        plan_path = folder / "plan.json"
        plan_path.write_text(json.dumps(plan), encoding="utf-8")
        result = subprocess.run(["node", str(HERE / "cine" / "cine_frames.cjs"), "serie", str(plan_path), str(folder)], text=True, capture_output=True)
        print(result.stdout.strip())
        if result.returncode != 0:
            raise SystemExit("No se dibujaron las cinemáticas:\n" + result.stdout[-800:] + result.stderr[-800:])
        stamp.write_text(signature, encoding="utf-8")
    return folder


def base_video(lang, videos, work):
    folder = work / f"base_{lang}"
    folder.mkdir(parents=True, exist_ok=True)
    cine = cinematics(work)
    enc = ["-c:v", "libx264", "-preset", "medium", "-crf", "12", "-pix_fmt", "yuv420p", "-r", str(FPS), "-an"]
    parts = []
    for index, (item, _, _) in enumerate(segments()):
        out = folder / f"tramo{index:02d}.mp4"
        if item["tipo"] == "negro":
            ff(["-f", "lavfi", "-i", f"color=c=black:s=1920x1080:r={FPS}", "-frames:v", item["cuadros"], *enc, out])
        elif item["tipo"] == "cine":
            ff(["-framerate", str(FPS), "-i", cine / item["escena"] / "%04d.jpg", "-frames:v", item["cuadros"], *enc, out])
        else:
            src = videos / item["src"].format(lang=lang)
            if not src.exists():
                raise SystemExit(f"Falta la toma {src}")
            speed = item.get("velocidad", 1.0)
            length = item.get("dura_s", item["cuadros"] / FPS * speed + 0.5)
            # El tramo se recorta dentro del filtro y recién después se cambia la velocidad: así «desde_s» siempre es
            # tiempo del archivo original (las capturas .webm del navegador, además, no traen índice para buscar).
            chain = [f"trim=start={item['desde_s']}:duration={length}", f"setpts=(PTS-STARTPTS)/{speed}", f"fps={FPS}"]
            if item.get("recorte"):
                chain.append(item["recorte"])
            chain += ["scale=1920:1080:flags=lanczos", "setsar=1"]
            ff(["-i", src, "-vf", ",".join(chain), "-frames:v", item["cuadros"], *enc, out])
        made = frame_count(out)
        if made != item["cuadros"]:
            raise SystemExit(f"El tramo {index} ({item.get('escena', item.get('src', 'negro'))}) dio {made} cuadros y se pedían {item['cuadros']}.")
        parts.append(out)
    listing = folder / "lista.txt"
    listing.write_text("".join(f"file '{p}'\n" for p in parts), encoding="utf-8")
    base = folder / "base.mp4"
    ff(["-f", "concat", "-safe", "0", "-i", listing, "-c", "copy", base])
    return base


# --- 4. Cuadros de la capa (Playwright) -------------------------------------------------------------------------------
def frames(spec_path, folder, workers):
    if folder.exists():
        for old in folder.glob("*.png"):
            old.unlink()
    result = subprocess.run(["node", str(HERE / "frames.cjs"), str(spec_path), str(folder), "0", str(N), str(workers)], text=True, capture_output=True)
    print(result.stdout.strip())
    if result.returncode != 0 or len(list(folder.glob("*.png"))) != N:
        raise SystemExit("No se dibujaron todos los cuadros:\n" + result.stderr[-1500:])
    # Todos los cuadros deben ser PNG con transparencia (tipo de color 6, byte 25 del archivo). Si alguno sale sin ella,
    # ffmpeg rehace el montaje al cambiar de formato y uno o dos cuadros del video quedan sin la capa de textos.
    opaque = [png.name for png in sorted(folder.glob("*.png")) if png.read_bytes()[25] != 6]
    if opaque:
        raise SystemExit(f"{len(opaque)} cuadros de la capa salieron sin transparencia (el primero, {opaque[0]}): revisar la fila transparente de frames.cjs.")


# --- 5. Sonido: música con atenuación bajo la voz ---------------------------------------------------------------------
def audio(vo, videos, work, lang):
    music = GUION["musica"]
    track = videos / music["pista"]
    start = music["termina_s"] - TOTAL          # el último acorde coincide con el final del video
    inputs, graph, labels = ["-i", track], [], []
    for index, item in enumerate(vo, start=1):
        inputs += ["-i", item["wav"]]
        delay = int(item["inicio"] * 1000)
        graph.append(f"[{index}:a]adelay={delay}|{delay}[v{index}]")
        labels.append(f"[v{index}]")
    graph.append(f"{''.join(labels)}amix=inputs={len(vo)}:normalize=0,apad=whole_dur={TOTAL}[vo]")
    graph.append("[vo]asplit[voa][vob]")
    graph.append(f"[0:a]atrim=start={start}:end={start + TOTAL},asetpts=PTS-STARTPTS,afade=t=in:d=0.5,afade=t=out:st={TOTAL - 0.3}:d=0.3,volume=0.62[m]")
    graph.append("[m][voa]sidechaincompress=threshold=0.015:ratio=7:attack=12:release=420[md]")
    graph.append(f"[md][vob]amix=inputs=2:normalize=0:duration=first,loudnorm=I=-15:TP=-1.5:LRA=11,aresample=48000,atrim=end={TOTAL - 0.05}[out]")
    out = work / f"audio_{lang}.wav"
    ff([*inputs, "-filter_complex", ";".join(graph), "-map", "[out]", "-ac", "2", out])
    return out


# --- 6. Unión y comprobación ------------------------------------------------------------------------------------------
def srt(vo, key, path):
    def stamp(seconds):
        ms = int(round(seconds * 1000))
        return f"{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}"
    path.write_text("".join(f"{i}\n{stamp(v['inicio'])} --> {stamp(v['fin'] + 0.15)}\n{v[key]}\n\n" for i, v in enumerate(vo, start=1)), encoding="utf-8")


def final(base, frames_dir, sound, out, lang, engine):
    voice = VOICES[engine][lang][0]
    meta = {
        "title": "TERRA 2045 · 30-second demo · Los Causas Espaciales · NASA Space Apps Challenge 2026",
        "artist": "Los Causas Espaciales (Moquegua, Peru)",
        "comment": (f"SI/AI disclosure: narration is a synthetic text-to-speech voice ({engine}: {voice}); script, 3D animation code, edit and on-screen "
                    "text made with AI assistance (Claude) and reviewed by the team. Footage: 3D animation made for this video (three.js; NASA Blue "
                    "Marble and Black Marble imagery; terrain from Copernicus DEM and ESA WorldCover; simulated events, labelled on screen), real "
                    f"screen captures of the team's app, and a closing shot from the team's game trailer. Music: {GUION['musica']['credito']}."),
        "description": ("Challenge: Be An Earth System Trend Detective! Data shown: NASA POWER (MERRA-2), NASA GIBS, GPM IMERG, ERA5, CHIRPS, "
                        "Copernicus DEM, ESA WorldCover."),
        "language": "spa" if lang == "es" else "eng",
    }
    args = ["-i", base, "-framerate", str(FPS), "-i", frames_dir / "%04d.png", "-i", sound,
            "-filter_complex", f"[1:v]crop=1920:1080:0:0[capa];[0:v][capa]overlay=format=auto,fade=t=in:st=0:d=0.25,fade=t=out:st={TOTAL - 0.3}:d=0.3,format=yuv420p[v]",
            "-map", "[v]", "-map", "2:a", "-frames:v", N, "-c:v", "libx264", "-preset", "slow", "-crf", "19", "-profile:v", "high", "-pix_fmt", "yuv420p",
            "-r", str(FPS), "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart"]
    for key, value in meta.items():
        args += ["-metadata", f"{key}={value}"]
    ff([*args, out])


def probe(path):
    """Duración en segundos y número de cuadros de un video (ffmpeg solo; no hace falta ffprobe)."""
    info = subprocess.run([FF, "-hide_banner", "-i", str(path), "-map", "0:v", "-f", "null", "-"], capture_output=True, text=True).stderr
    duration = re.search(r"Duration: (\d+):(\d+):([\d.]+)", info)
    seconds = int(duration.group(1)) * 3600 + int(duration.group(2)) * 60 + float(duration.group(3))
    frames_seen = re.findall(r"frame=\s*(\d+)", info)
    return seconds, int(frames_seen[-1]) if frames_seen else 0


def frame_count(path):
    return probe(path)[1]


def dark_frames(path):
    """Tramos de uno a tres cuadros mucho más oscuros que los cuadros de antes y de después: es un fallo del dibujo o del montaje."""
    info = subprocess.run([FF, "-hide_banner", "-i", str(path), "-vf", "signalstats,metadata=print:key=lavfi.signalstats.YAVG:file=-",
                           "-an", "-f", "null", "-"], capture_output=True, text=True).stdout
    level = [float(x) for x in re.findall(r"YAVG=([\d.]+)", info)]
    found = []
    for width in (1, 2, 3):                                  # el fallo puede durar más de un cuadro
        for i in range(1, len(level) - width):
            around, worst = min(level[i - 1], level[i + width]), max(level[i:i + width])
            if worst < 0.65 * around and around - worst > 4:
                found.append(i)
    return sorted(set(found))


def check(path):
    seconds, count = probe(path)
    print(f"{path.name}: {seconds:.2f} s · {count} cuadros · {path.stat().st_size / 1e6:.1f} MB")
    if count != N or seconds > TOTAL + 0.005:
        raise SystemExit(f"El archivo no mide {TOTAL:.2f} s exactos ({count} cuadros, {seconds:.3f} s).")
    dark = dark_frames(path)
    if dark:
        raise SystemExit(f"Hay cuadros negros sueltos en el video (cuadros {dark[:12]}): revisar las cinemáticas.")


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--lang", choices=["es", "en"], default="es")
    parser.add_argument("--voz", choices=["piper", "edge", "mac"], default="piper")
    parser.add_argument("--videos", type=Path, default=HERE.parents[2] / "videos", help="carpeta videos/ del repositorio (capturas, tráiler y música)")
    parser.add_argument("--tomas", type=Path, default=None, help="tomas fijas de la aplicación (por defecto videos/demo30/tomas)")
    parser.add_argument("--work", type=Path, default=None, help="carpeta de trabajo (por defecto videos/render/demo30)")
    parser.add_argument("--out", type=Path, default=None, help="carpeta del video final (por defecto videos/)")
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--solo-plan", action="store_true", help="solo voces y línea de tiempo")
    args = parser.parse_args()
    tomas = args.tomas or args.videos / "demo30" / "tomas"
    work = args.work or args.videos / "render" / "demo30"
    out_dir = args.out or args.videos
    work.mkdir(parents=True, exist_ok=True)

    vo = voices(args.lang, args.voz, work)
    for v in vo:
        print(f"  {v['id']} {v['inicio']:5.2f}–{v['fin']:5.2f} s ({v['dur']:.2f}) {v['text']}")
    data = spec(args.lang, vo, tomas)
    spec_path = work / f"spec_{args.lang}.json"
    spec_path.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    if args.solo_plan:
        return
    base = base_video(args.lang, args.videos, work)
    frames_dir = work / f"cuadros_{args.lang}"
    frames(spec_path, frames_dir, args.workers)
    sound = audio(vo, args.videos, work, args.lang)
    out = out_dir / f"terra2045_demo30_{args.lang}.mp4"
    final(base, frames_dir, sound, out, args.lang, args.voz)
    srt(vo, "text", out.with_suffix(".srt"))
    if args.lang != "en":
        srt(vo, "sub", out.with_name(out.stem + ".en.srt"))
    check(out)


if __name__ == "__main__":
    main()
