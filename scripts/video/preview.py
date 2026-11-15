"""Vista previa de las cinemáticas: un cuadro de cada escena en una hoja de contacto (/tmp/sheet.jpg).

    python scripts/video/preview.py [escena ...]
"""
import asyncio, base64, json, sys
from playwright.async_api import async_playwright
from PIL import Image
import io
from common import BROWSER_ARGS, CHROME, ENGINE, boot_options
W, H = 1280, 720
SHOTS = [("negro_titulo", {"caption": "2045"}), ("tierra_desde_luna", {"health": 0}), ("colonia", {"health": 0}), ("ventana", {"who": ["mario", "andres", "viajero"], "health": 0}),
         ("ventana_cerca", {"who": ["viajero", "andres"], "health": 0}), ("genesis", {}), ("genesis_cerca", {"who": ["viajero", "nikol", "mario"]}), ("cuaderno", {}),
         ("satelites", {}), ("foto", {}), ("activacion", {}), ("tunel", {}), ("llegada", {}), ("tierra_datos", {}), ("terreno", {"place": "chosica", "label": "Chosica, Perú"}),
         ("terreno", {"place": "huascaran", "label": "Huascarán y Yungay, Perú", "alt": 0.85, "radius": 0.6}), ("terreno", {"place": "piura", "label": "Piura, Perú"}), ("terreno", {"place": "chamonix", "label": "Chamonix, Mont Blanc, Francia"}), ("terreno", {"place": "mocoa", "label": "Mocoa, Colombia"}), ("datos", {"place": "chosica"}), ("decision", {}), ("aviso", {"place": "chosica"}), ("planeta_cambia", {}),
         ("titulo", {}), ("ventana_revela", {"who": ["mario", "andres", "viajero"], "from": 0.15, "to": 1}), ("montaje_mixto", {"places": ["chosica", "huascaran"]}), ("cuaderno_salvado", {}),
         ("tierra_amanecer", {}), ("tierra_orbita", {}), ("colapso", {}), ("alarma", {}), ("creditos", {}), ("colonia_calma", {})]
async def main():
    sel = sys.argv[1:] 
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path=CHROME, args=BROWSER_ARGS)
        pg = await b.new_page(viewport={"width": W, "height": H})
        pg.on("console", lambda m: print("console:", m.text) if "GPU stall" not in m.text else None)
        pg.on("pageerror", lambda e: print("PAGEERROR", e))
        await pg.goto((ENGINE / "index.html").as_uri())
        await pg.evaluate("([w,h,o]) => boot(w,h,o)", [W, H, boot_options()])
        cdp = await pg.context.new_cdp_session(pg)
        tiles = []
        for name, params in SHOTS:
            if sel and name not in sel: continue
            dur = 8.0; t = params.pop("_t", dur * 0.62)
            await pg.evaluate("([n,t,d,p]) => drawShot(n,t,d,p)", [name, t, dur, {**params, "lang": "es", "fadeIn": 0, "fadeOut": 0}])
            r = await cdp.send("Page.captureScreenshot", {"format": "jpeg", "quality": 85})
            img = Image.open(io.BytesIO(base64.b64decode(r["data"])))
            img.save(f"/tmp/prev_{name}.jpg"); tiles.append((name, img))
        cols = 3; tw, th = 640, 360
        sheet = Image.new("RGB", (cols * tw, ((len(tiles) + cols - 1) // cols) * th))
        for i, (n, im) in enumerate(tiles): sheet.paste(im.resize((tw, th)), ((i % cols) * tw, (i // cols) * th))
        sheet.save("/tmp/sheet.jpg", quality=85); print(len(tiles), "cuadros")
        await b.close()
asyncio.run(main())
