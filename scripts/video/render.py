"""Montaje de las cinemáticas de TERRA 2045 (ADR-050).

    python scripts/video/texturas.py                 # una vez: texturas de apoyo en videos/assets
    python scripts/video/render.py [video ...] [--dry] [--plan]

Requiere Playwright para Python con Chromium (o TERRA_CHROME con la ruta de Chrome) y ffmpeg con libass y rubberband.
Carpeta de trabajo: videos/ (variable TERRA_VIDEOS para otra): assets/, voz/<lang>/, musica/, render/ y los mp4 finales.

1. Procesa las voces (videos/voz/<lang>/<id>.wav): tono de niño para Mario y Killa, filtro de radio, volumen parejo.
2. Arma la línea de tiempo: cada plano dura lo que pide la versión más larga (español o inglés) más sus pausas, así el
   video es el mismo en los dos idiomas; solo cambian la voz, los subtítulos y los planos con texto en pantalla.
3. Dibuja cada plano en Chrome (engine/) y lo codifica en un mp4 por plano; luego los une sin recodificar.
4. Mezcla voz, música (Kevin MacLeod, CC BY 4.0) con atenuación bajo la voz y efectos sintetizados.
5. Escribe los subtítulos (.srt) y la versión final con subtítulos quemados, en español y en inglés.
6. Escribe la versión para el juego en web/: mp4 de 1280×720 más liviano, sin subtítulos quemados, con su .vtt aparte
   (el juego los muestra y deja apagarlos o cambiar de idioma). Se copia a frontend/public/cine/.
--dry: sin voces reales, con duraciones estimadas (para probar el montaje).
--plan: solo la línea de tiempo. --subs: solo los subtítulos (.srt y .vtt), sin volver a dibujar; con --queme también
vuelve a quemarlos en la versión final.
"""
import asyncio, base64, json, math, os, re, shutil, subprocess, sys, wave
from pathlib import Path
import numpy as np
from playwright.async_api import async_playwright
from common import BROWSER_ARGS, CHROME, ENGINE, REPO, VIDEOS, boot_options

ROOT = VIDEOS
GUION = json.loads((Path(__file__).with_name("guion.json")).read_text(encoding="utf-8"))
VOZ = ROOT / "voz"            # voces crudas staged desde el equipo: voz/es/*.wav, voz/en/*.wav
MUSIC = ROOT / "musica"
OUT = ROOT; WORK = ROOT / "render"
FPS = 30
SR = 48000
LEAD, TAIL = 0.35, 0.3
PAUSE_SCALE = 0.65        # las pausas del guion, más cortas: ritmo más fluido (pedido de Andrés, 14-nov)
# Imágenes reales del juego (grabadas del navegador en videos/captura/): no se dibujan en el motor, se recortan y
# codifican con ffmpeg. «clip»: un tramo de video; «pantalla»: una captura fija con un acercamiento lento.
FOOTAGE = {"clip", "pantalla"}
FONT_FILE = "/usr/share/fonts/opentype/inter/Inter-SemiBold.otf"
TEXT_SCENES = {"clip", "pantalla", "negro_radio", "tierra_datos", "datos", "decision", "planeta_cambia", "titulo", "cuaderno", "cuaderno_salvado", "creditos"}
MIN_DUR = {"ventana_revela": 15.0, "montaje_lugares": 15.0, "montaje_mixto": 12.0, "tierra_orbita": 8.0, "tierra_amanecer": 9.0, "planeta_cambia": 6.5, "satelites": 8.0, "decision": 6.5, "datos": 8.0, "aviso": 5.5, "colonia": 6.0}
RES = {"trailer": (1920, 1080)}
DEFAULT_RES = (1280, 720)


def sh(cmd, **kw):
    r = subprocess.run(cmd, capture_output=True, text=True, **kw)
    if r.returncode != 0: raise RuntimeError(" ".join(map(str, cmd))[:300] + "\n" + r.stderr[-1500:])
    return r.stdout


def duration(path):
    return float(sh(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=nk=1:nw=1", str(path)]).strip())


# --- voces --------------------------------------------------------------------------------------------------------
def process_voice(line, lang, dry):
    out = WORK / "voz" / lang / f"{line['id']}.wav"
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists(): return out
    # Voces neuronales de Edge (voces_edge.py, mp3) si están; si no, las de Windows o Piper (wav).
    edge = VOZ / lang / f"{line['id']}.mp3"
    src = edge if edge.exists() else VOZ / lang / f"{line['id']}.wav"
    if dry or not src.exists():
        words = len(line[lang].split()); secs = max(1.0, words / 2.6)
        sh(["ffmpeg", "-y", "-f", "lavfi", "-i", f"anoisesrc=d={secs}:c=pink:a=0.02", "-ar", str(SR), "-ac", "1", str(out)])
        return out
    who = line["who"]
    chain = []
    if src.suffix == ".wav":  # las voces de Edge ya traen el tono de niño desde la síntesis
        if who == "mario": chain.append("rubberband=pitch=1.24:tempo=1.04:formant=preserved")
        if who == "killa": chain.append("rubberband=pitch=1.3:tempo=0.97:formant=preserved")
        if who == "andres": chain.append("rubberband=pitch=0.94")
    if who == "radio": chain += ["highpass=f=320", "lowpass=f=3300", "acrusher=bits=10:mix=0.25", "aecho=0.6:0.3:18:0.18"]
    if who == "narrador": chain.append("equalizer=f=140:t=q:w=1:g=2.5")
    # Silencio solo al principio y al final (dando vuelta el audio): las pausas entre frases se conservan.
    trim = "silenceremove=start_periods=1:start_threshold=-45dB:start_silence=0.05"
    chain = [trim, "areverse", trim, "areverse"] + chain + ["loudnorm=I=-17:TP=-2:LRA=7", f"aresample={SR}"]
    sh(["ffmpeg", "-y", "-i", str(src), "-af", ",".join(chain), "-ac", "1", str(out)])
    return out


# --- línea de tiempo ------------------------------------------------------------------------------------------------
def timeline(video, dry):
    spec = GUION["videos"][video]
    lines = {l["id"]: l for l in GUION["lines"] if l["video"] == video}
    shots, t = [], 0.0
    for index, shot in enumerate(spec["shots"]):
        clips = {lang: [] for lang in ("es", "en")}
        need = 0.0
        for lang in ("es", "en"):
            cursor = LEAD
            for lid in shot["lines"]:
                path = process_voice(lines[lid], lang, dry); d = duration(path)
                clips[lang].append({"id": lid, "path": path, "start": cursor, "dur": d, "text": lines[lid][lang], "who": lines[lid]["who"]})
                cursor += d + lines[lid]["pause"] * PAUSE_SCALE
            need = max(need, cursor + (TAIL if shot["lines"] else 0))
        dur = max(need, shot.get("hold", 0), MIN_DUR.get(shot["scene"], 0) if shot["lines"] else shot.get("hold", 2.0))
        shots.append({"index": index, "scene": shot["scene"], "start": t, "dur": round(dur * FPS) / FPS, "params": params_for(video, index, shot), "clips": clips})
        t += shots[-1]["dur"]
    return shots, t


def params_for(video, index, shot):
    p = {k: v for k, v in shot.items() if k not in ("scene", "lines", "hold")}
    nxt = GUION["videos"][video]["shots"][index + 1]["scene"] if index + 1 < len(GUION["videos"][video]["shots"]) else None
    if shot["scene"] == "activacion" and nxt in ("tunel", "titulo", "colonia_calma"): p["flashEnd"] = True
    if nxt == "tunel" or shot["scene"] == "tunel": p["fadeOut"] = 0.0 if shot["scene"] != "tunel" else 0.4
    if video == "trailer" and shot["scene"] == "negro_titulo": p["caption"] = "2045"
    if video == "trailer": p.setdefault("fadeIn", 0.25); p.setdefault("fadeOut", 0.25)
    if shot["scene"] in ("datos", "decision", "titulo", "creditos"): p["noBars"] = True
    if shot["scene"] == "terreno" and p.get("place") == "huascaran": p.update({"alt": 0.85, "radius": 0.95})
    return p


# --- render de planos -------------------------------------------------------------------------------------------------
async def render_video(video, shots, res):
    W, H = res
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(executable_path=CHROME, args=BROWSER_ARGS)
        page = await browser.new_page(viewport={"width": W, "height": H})
        page.on("pageerror", lambda e: print("PAGEERROR", e, flush=True))
        await page.goto((ENGINE / "index.html").as_uri())
        await page.evaluate("([w,h,o]) => boot(w,h,o)", [W, H, boot_options()])
        cdp = await page.context.new_cdp_session(page)
        only = next((a.split("=", 1)[1].split(",") for a in sys.argv if a.startswith("--only=")), None)
        for shot in shots:
            if only and shot["scene"] not in only: continue
            langs = ("es", "en") if shot["scene"] in TEXT_SCENES else ("xx",)
            for lang in langs:
                target = WORK / video / f"{shot['index']:02d}_{lang}.mp4"
                target.parent.mkdir(parents=True, exist_ok=True)
                if shot["scene"] in FOOTAGE:  # se vuelve a cortar siempre: es rápido y así sigue a la captura
                    render_footage(shot, lang, target, res); continue
                if target.exists() and abs(duration(target) - shot["dur"]) < 0.05: continue
                tmp = target.with_suffix(".tmp.mp4")
                enc = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "image2pipe", "-vcodec", "mjpeg", "-framerate", str(FPS), "-i", "-",
                                        "-c:v", "libx264", "-preset", "veryfast", "-crf", "19", "-pix_fmt", "yuv420p", "-r", str(FPS), str(tmp)], stdin=subprocess.PIPE)
                frames = int(round(shot["dur"] * FPS))
                params = {**shot["params"], "lang": "es" if lang == "xx" else lang}
                pj = json.dumps(params, ensure_ascii=False)
                for f in range(frames):
                    t = f / FPS
                    r = await cdp.send("Runtime.evaluate", {"expression": f"drawShot({json.dumps(shot['scene'])},{t:.4f},{shot['dur']:.4f},{pj})", "awaitPromise": False})
                    if "exceptionDetails" in r: raise RuntimeError(json.dumps(r["exceptionDetails"])[:600])
                    img = await cdp.send("Page.captureScreenshot", {"format": "jpeg", "quality": 92})
                    enc.stdin.write(base64.b64decode(img["data"]))
                enc.stdin.close(); enc.wait()
                if enc.returncode != 0: raise RuntimeError(f"ffmpeg falló en {target}")
                tmp.rename(target)
                print(f"  {video} plano {shot['index']:02d} {shot['scene']} {lang} · {frames} cuadros", flush=True)
        await browser.close()


def esc(text):
    return text.replace("\\", "\\\\").replace(":", "\\:").replace("'", "\u2019").replace("%", "\\%")


def render_footage(shot, lang, target, res):
    """Plano con imágenes reales del juego: recorte a 16:9, franjas de cine, fundidos y la marca «Imágenes reales del
    juego». Un «clip» puede encadenar varios tramos («srcs»: src, from, dur, label) con cortes secos entre ellos."""
    W, H = res; p = shot["params"]; dur = shot["dur"]; frames = int(round(dur * FPS))
    bar = round(H * 0.075); size = round(H * 0.019)
    tag = {"es": "IMÁGENES REALES DEL JUEGO", "en": "REAL IN-GAME FOOTAGE"}[lang]
    pick = lambda value: value.get(lang) if isinstance(value, dict) else value
    inputs, graph, labels = [], [], []
    if shot["scene"] == "clip":
        pieces = p.get("srcs") or [{"src": p["src"], "from": p.get("from", 0), "label": p.get("label")}]
        fixed = sum(piece.get("dur", 0) for piece in pieces[:-1])
        t = 0.0
        for k, piece in enumerate(pieces):
            d = piece.get("dur", 0) if k < len(pieces) - 1 else max(0.5, dur - fixed)
            src = ROOT / "captura" / piece["src"]
            if not src.exists(): raise RuntimeError(f"Falta la captura {src}")
            inputs += ["-ss", f"{piece.get('from', 0)}", "-t", f"{d + 1:.2f}", "-i", str(src)]
            graph.append(f"[{k}:v]fps={FPS},scale={W}:{H}:force_original_aspect_ratio=increase:flags=lanczos,"
                         f"crop={W}:{H}:(iw-{W})*{piece.get('cx', 0.5)}:(ih-{H})*{piece.get('cy', 0.5)},"
                         f"tpad=stop_mode=clone:stop_duration={d:.2f},trim=duration={d:.3f},setpts=PTS-STARTPTS,setsar=1[p{k}]")
            if pick(piece.get("label")): labels.append((t, t + d, pick(piece["label"])))
            t += d
        graph.append("".join(f"[p{k}]" for k in range(len(pieces))) + f"concat=n={len(pieces)}:v=1:a=0[base]")
    else:
        src = ROOT / "captura" / p["src"]
        if not src.exists(): raise RuntimeError(f"Falta la captura {src}")
        z0, z1 = p.get("zoom", [1.0, 1.1]); cx, cy = p.get("cx", 0.5), p.get("cy", 0.5)
        inputs = ["-loop", "1", "-framerate", str(FPS), "-i", str(src)]
        graph.append(f"[0:v]scale={W * 2}:{H * 2}:force_original_aspect_ratio=increase:flags=lanczos,crop={W * 2}:{H * 2},"
                     f"zoompan=z='{z0}+({z1}-{z0})*on/{frames}':x='(iw-iw/zoom)*{cx}':y='(ih-ih/zoom)*{cy}':d=1:s={W}x{H}:fps={FPS}[base]")
        if pick(p.get("label")): labels.append((0, dur, pick(p["label"])))
    chain = [f"eq=saturation={p.get('sat', 1.1)}:contrast=1.05",
             f"drawbox=x=0:y=0:w=iw:h={bar}:color=black:t=fill", f"drawbox=x=0:y=ih-{bar}:w=iw:h={bar}:color=black:t=fill",
             f"drawtext=fontfile={FONT_FILE}:text='{esc(tag)}':fontsize={size}:fontcolor=white@0.62:x={round(W * 0.035)}:y=({bar}-th)/2"]
    for a, b, text in labels:
        chain.append(f"drawtext=fontfile={FONT_FILE}:text='{esc(text)}':fontsize={round(size * 1.15)}:fontcolor=white@0.85:"
                     f"x=w-tw-{round(W * 0.035)}:y=({bar}-th)/2:enable='between(t,{a:.3f},{b - 0.001:.3f})'")
    fi, fo = p.get("fadeIn", 0.2), p.get("fadeOut", 0.2)
    if fi > 0: chain.append(f"fade=t=in:st=0:d={fi}")
    if fo > 0: chain.append(f"fade=t=out:st={max(0, dur - fo):.3f}:d={fo}")
    graph.append("[base]" + ",".join(chain) + "[out]")
    tmp = target.with_suffix(".tmp.mp4")
    sh(["ffmpeg", "-y", "-loglevel", "error", *inputs, "-filter_complex", ";".join(graph), "-map", "[out]", "-frames:v", str(frames), "-an",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "19", "-pix_fmt", "yuv420p", "-r", str(FPS), str(tmp)])
    tmp.replace(target)
    print(f"  plano {shot['index']:02d} {shot['scene']} {lang} · {frames} cuadros", flush=True)


def concat(video, shots, lang):
    parts = []
    for shot in shots:
        part = WORK / video / f"{shot['index']:02d}_{lang if shot['scene'] in TEXT_SCENES else 'xx'}.mp4"
        parts.append(f"file '{part}'")
    listfile = WORK / video / f"lista_{lang}.txt"; listfile.write_text("\n".join(parts))
    out = WORK / video / f"imagen_{lang}.mp4"
    sh(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(listfile), "-c", "copy", str(out)])
    return out


# --- efectos de sonido sintetizados ---------------------------------------------------------------------------------
def write_wav(path, x):
    x = np.clip(x, -1, 1); data = (x * 32767).astype(np.int16)
    with wave.open(str(path), "wb") as w: w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR); w.writeframes(data.tobytes())


def sfx_for(shot):
    d = shot["dur"]; n = int(d * SR); t = np.arange(n) / SR; s = shot["scene"]; rng = np.random.default_rng(shot["index"])
    env = np.minimum(1, np.minimum(t / 0.5, (d - t) / 0.5)).clip(0, 1)
    x = np.zeros(n)
    if s in ("genesis", "genesis_cerca", "colonia_calma", "activacion", "activacion_debil"):
        rise = (t / d) ** 2 if s == "activacion" else 0
        f = 55 * (1 + 1.5 * rise)
        x += 0.10 * np.sin(2 * np.pi * f * t) + 0.05 * np.sin(2 * np.pi * 2 * f * t) + 0.03 * np.sin(2 * np.pi * 3.01 * f * t)
        x *= 0.7 + 0.3 * np.sin(2 * np.pi * 0.5 * t)
        if s == "activacion": x += 0.08 * rng.normal(size=n) * (t / d) ** 3
        if s == "activacion_debil": x *= (np.sin(2 * np.pi * 1.1 * t) > -0.2)
    if s == "tunel":
        noise = rng.normal(size=n); k = np.exp(-np.arange(400) / 60); noise = np.convolve(noise, k / k.sum(), "same")
        x += 0.35 * noise * np.sin(np.pi * t / d) + 0.08 * np.sin(2 * np.pi * (80 + 300 * t / d) * t)
    if s in ("negro_radio", "llegada"):
        x += 0.025 * rng.normal(size=n) * (0.6 + 0.4 * np.sin(2 * np.pi * 0.7 * t))
    if s == "alarma":
        beep = ((t % 0.9) < 0.35) * np.sin(2 * np.pi * np.where((t % 1.8) < 0.9, 880, 660) * t)
        x += 0.12 * beep
    if s == "colapso":
        rum = rng.normal(size=n); k = np.exp(-np.arange(2000) / 500); rum = np.convolve(rum, k / k.sum(), "same")
        x += 0.6 * rum * (t / d) + 0.1 * np.sin(2 * np.pi * 38 * t) * (t / d)
    hit = np.zeros(n)
    if s in FOOTAGE:  # golpe de aire en el corte (fuera de la envolvente, que empieza en silencio)
        m = min(n, int(0.45 * SR)); w = rng.normal(size=m); k = np.exp(-np.arange(200) / 25); w = np.convolve(w, k / k.sum(), "same")
        hit[:m] = 0.5 * w * np.exp(-np.arange(m) / SR / 0.12)
    if s in ("tierra_desde_luna", "colonia", "ventana", "ventana_cerca", "ventana_revela", "ventana_oscura"):
        hum = rng.normal(size=n); k = np.exp(-np.arange(3000) / 900); hum = np.convolve(hum, k / k.sum(), "same")
        x += 0.25 * hum
    return x * env + hit


def music_end(path):
    """Dónde termina de verdad la música: último segundo con sonido (> -45 dB) más dos de cola; muchas pistas traen
    silencio al final, y alinear con el largo del archivo dejaba el cierre del video sin música."""
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-ac", "1", "-ar", "8000", "-f", "s16le", "-"], capture_output=True).stdout
    d = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32767
    loud = [i for i in range(0, len(d) // 8000) if 20 * np.log10(np.sqrt((d[i * 8000:(i + 1) * 8000] ** 2).mean()) + 1e-9) > -45]
    return min(len(d) / 8000, (loud[-1] + 2) if loud else len(d) / 8000)


def music_bed(video, shots, total, tracks):
    """Música de todo el video. Por defecto una pista; con «music_cues» varias, cada una desde un plano, con fundido
    cruzado. «align_end»: la pista termina justo con el video (su final cae en el título); si es más corta que lo que
    queda, entra más tarde y la anterior sigue sonando hasta entonces. Escribe musica.wav (una vez por video)."""
    spec = GUION["videos"][video]
    cues = spec.get("music_cues") or [{"track": spec["music"], "shot": 0}]
    cues = [c for c in cues if (MUSIC / f"{c['track']}.mp3").exists()]
    if not cues: return None
    XF = 1.5
    lengths = [music_end(MUSIC / f"{c['track']}.mp3") for c in cues]
    starts = [shots[c["shot"]]["start"] for c in cues]
    for i, c in enumerate(cues):
        if c.get("align_end") and lengths[i] < total - starts[i]: starts[i] = total - lengths[i]
    parts, inputs = [], []
    for i, c in enumerate(cues):
        end = starts[i + 1] + XF if i + 1 < len(cues) else total
        seg = end - starts[i]
        off = lengths[i] - (total - starts[i]) if c.get("align_end") else c.get("offset", 0.0)
        fin = 2.0 if i == 0 else XF
        fout = XF if i + 1 < len(cues) else (1.2 if c.get("align_end") else 4.0)
        inputs += ["-i", str(MUSIC / f"{c['track']}.mp3")]
        ms = int(round(starts[i] * 1000))
        parts.append(f"[{i}:a]atrim={max(0, off):.3f}:{max(0, off) + seg:.3f},asetpts=N/SR/TB,aresample={SR},aformat=channel_layouts=stereo,"
                     f"afade=t=in:d={fin},afade=t=out:st={max(0, seg - fout):.3f}:d={fout},adelay=delays={ms}:all=1[c{i}]")
    mix = "".join(f"[c{i}]" for i in range(len(cues)))
    out = tracks / "musica.wav"
    sh(["ffmpeg", "-y", "-loglevel", "error", *inputs, "-filter_complex", ";".join(parts) + f";{mix}amix=inputs={len(cues)}:normalize=0[m]",
        "-map", "[m]", "-t", f"{total}", str(out)])
    return out


def mix_audio(video, shots, total, lang):
    tracks = WORK / video / "audio"; tracks.mkdir(parents=True, exist_ok=True)
    n = int(math.ceil(total * SR)) + SR
    voice = np.zeros(n); fx = np.zeros(n)
    for shot in shots:
        for clip in shot["clips"][lang]:
            with wave.open(str(clip["path"])) as w:
                data = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32767
            a = int((shot["start"] + clip["start"]) * SR); voice[a:a + len(data)] += data[: max(0, n - a)]
        s = sfx_for(shot); a = int(shot["start"] * SR); fx[a:a + len(s)] += s[: max(0, n - a)]
    write_wav(tracks / f"voz_{lang}.wav", voice[: int(total * SR)])
    write_wav(tracks / "fx.wav", fx[: int(total * SR)])
    out = tracks / f"mezcla_{lang}.m4a"
    bed = music_bed(video, shots, total, tracks)
    if bed:
        sh(["ffmpeg", "-y", "-loglevel", "error", "-i", str(tracks / f"voz_{lang}.wav"), "-i", str(bed), "-i", str(tracks / "fx.wav"), "-filter_complex",
            f"[1:a]volume=0.55,aresample={SR}[m];"
            f"[0:a]asplit=2[v][sc];[m][sc]sidechaincompress=threshold=0.03:ratio=6:attack=40:release=500[md];"
            f"[v][md][2:a]amix=inputs=3:normalize=0:weights=1 1 0.8,alimiter=limit=0.95[a]",
            "-map", "[a]", "-c:a", "aac", "-b:a", "192k", "-t", f"{total}", str(out)])
    else:
        sh(["ffmpeg", "-y", "-loglevel", "error", "-i", str(tracks / f"voz_{lang}.wav"), "-i", str(tracks / "fx.wav"), "-filter_complex", "[0:a][1:a]amix=inputs=2:normalize=0[a]",
            "-map", "[a]", "-c:a", "aac", "-b:a", "192k", str(out)])
    return out


# --- subtítulos -----------------------------------------------------------------------------------------------------------
def wrap(text, width=46):
    words, lines, cur = text.split(), [], ""
    for w in words:
        if len(cur) + len(w) + 1 > width and cur: lines.append(cur); cur = w
        else: cur = (cur + " " + w).strip()
    if cur: lines.append(cur)
    return lines


def chunks(text, start, dur):
    """Parte una línea larga en subtítulos de hasta dos renglones, repartiendo el tiempo según el largo."""
    lines = wrap(text); groups = [lines[i:i + 2] for i in range(0, len(lines), 2)]
    # Una cola corta («2026.») no queda sola en pantalla una fracción de segundo: se suma al subtítulo anterior.
    if len(groups) > 1 and len(groups[-1]) == 1 and len(groups[-1][0]) < 20:
        tail = groups.pop()[0]; prev = groups[-1]
        if len(prev[-1]) + len(tail) + 1 <= 56: prev[-1] = f"{prev[-1]} {tail}"
        else: prev.append(tail)
    total = sum(len(" ".join(g)) for g in groups); t = start; out = []
    for g in groups:
        d = dur * len(" ".join(g)) / total; out.append((t, t + d, "\n".join(g))); t += d
    return out


def srt_time(x):
    h, m = int(x // 3600), int(x % 3600 // 60); s = x % 60
    return f"{h:02d}:{m:02d}:{int(s):02d},{int(round((s - int(s)) * 1000)):03d}"


def write_srt(video, shots, lang):
    items = []
    for shot in shots:
        for clip in shot["clips"][lang]:
            items += chunks(clip["text"], shot["start"] + clip["start"], clip["dur"] + 0.25)
    # Ningún subtítulo se queda en pantalla cuando ya empezó el siguiente.
    items = [(a, min(b, items[i + 1][0] - 0.02) if i + 1 < len(items) else b, txt) for i, (a, b, txt) in enumerate(items)]
    out = OUT / f"terra2045_{video}_{lang}.srt"
    out.write_text("\n".join(f"{i + 1}\n{srt_time(a)} --> {srt_time(b)}\n{txt}\n" for i, (a, b, txt) in enumerate(items)), encoding="utf-8")
    return out


def finalize(video, image, audio, srt, lang, res):
    out = OUT / f"terra2045_{video}_{lang}.mp4"; tmp = OUT / f"terra2045_{video}_{lang}.tmp.mp4"
    # libass mide letra y márgenes sobre una pantalla virtual de 288 líneas y escala solo: valores fijos para cualquier
    # resolución (antes crecían con ella y en 1080p el subtítulo salía enorme y partido en tres renglones).
    style = "FontName=Inter,FontSize=18,PrimaryColour=&H00F5F5F5,OutlineColour=&H90000000,BorderStyle=1,Outline=1.4,Shadow=0,MarginV=18,Bold=0"
    sh(["ffmpeg", "-y", "-loglevel", "error", "-i", str(image), "-i", str(audio), "-vf", f"subtitles={srt}:force_style='{style}'",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "19", "-pix_fmt", "yuv420p", "-c:a", "copy", "-movflags", "+faststart", "-shortest", str(tmp)])
    tmp.replace(out)
    return out


def web_version(video, image, audio, srt, lang):
    """Versión del juego: sin subtítulos quemados, 1280×720, más liviana; subtítulos en WebVTT aparte."""
    web = ROOT / "web"; web.mkdir(exist_ok=True)
    out = web / f"{video}_{lang}.mp4"; tmp = web / f"{video}_{lang}.tmp.mp4"
    sh(["ffmpeg", "-y", "-loglevel", "error", "-i", str(image), "-i", str(audio), "-vf", "scale=1280:720:flags=lanczos",
        "-c:v", "libx264", "-preset", "medium", "-crf", "27", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "128k",
        "-movflags", "+faststart", "-shortest", str(tmp)])
    tmp.replace(out)
    write_vtt(video, srt, lang)
    return out


def write_vtt(video, srt, lang):
    web = ROOT / "web"; web.mkdir(exist_ok=True)
    body = srt.read_text(encoding="utf-8").strip()
    vtt = "WEBVTT\n\n" + re.sub(r"(\d{2}:\d{2}:\d{2}),(\d{3})", r"\1.\2", body) + "\n"
    (web / f"{video}_{lang}.vtt").write_text(vtt, encoding="utf-8")


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    dry = "--dry" in sys.argv
    videos = args or list(GUION["videos"])
    OUT.mkdir(exist_ok=True)
    for video in videos:
        res = RES.get(video, DEFAULT_RES)
        shots, total = timeline(video, dry)
        print(f"{video}: {len(shots)} planos, {total:.1f} s (máx. {GUION['videos'][video]['max_s']} s) a {res[0]}×{res[1]}", flush=True)
        (WORK / video).mkdir(parents=True, exist_ok=True)
        (WORK / video / "linea.json").write_text(json.dumps([{k: (v if k != "clips" else {lg: [{**c, "path": str(c["path"])} for c in cs] for lg, cs in v.items()}) for k, v in s.items()} for s in shots], ensure_ascii=False, indent=1))
        if "--plan" in sys.argv: continue
        if "--subs" in sys.argv:  # solo subtítulos (.srt y .vtt del juego), sin volver a dibujar el video
            for lang in ("es", "en"):
                srt = write_srt(video, shots, lang); write_vtt(video, srt, lang)
                # Con --queme, vuelve a quemar los subtítulos en la versión final usando la imagen y la mezcla ya hechas.
                image, audio = WORK / video / f"imagen_{lang}.mp4", WORK / video / "audio" / f"mezcla_{lang}.m4a"
                if "--queme" in sys.argv and image.exists() and audio.exists(): print("  →", finalize(video, image, audio, srt, lang, res), flush=True)
            continue
        asyncio.run(render_video(video, shots, res))
        if any(a.startswith("--only=") for a in sys.argv): continue
        for lang in ("es", "en"):
            image = concat(video, shots, lang)
            audio = mix_audio(video, shots, total, lang)
            srt = write_srt(video, shots, lang)
            print("  →", finalize(video, image, audio, srt, lang, res), flush=True)
            print("  →", web_version(video, image, audio, srt, lang), flush=True)


if __name__ == "__main__":
    main()
