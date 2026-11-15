"""Texturas de apoyo de las cinemáticas (ADR-050), en videos/assets/:

- landmask.png: tierra firme (Natural Earth 110 m del repositorio) en equirectangular; separa tierra y mar en el shader.
- earth_fallback.jpg: una Tierra de respaldo si no se bajó NASA Blue Marble.
- noise.png: ruido esférico (nubes, humo y fuego) precalculado; el shader lo lee en vez de calcularlo por píxel.
- lroc_color_2k.jpg: la Luna de LRO que ya usa el juego.

    python scripts/video/texturas.py
"""
import json
import shutil

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

from common import ASSETS, REPO


def landmask(w=2048, h=1024):
    g = json.loads((REPO / "backend/data/world/countries_110m.geojson").read_text(encoding="utf-8"))
    mask = Image.new("L", (w, h), 0); d = ImageDraw.Draw(mask)
    for f in g["features"]:
        geom = f["geometry"]; polys = geom["coordinates"] if geom["type"] == "MultiPolygon" else [geom["coordinates"]]
        for poly in polys: d.polygon([((x + 180) / 360 * w, (90 - y) / 180 * h) for x, y in poly[0]], fill=255)
    return mask.filter(ImageFilter.GaussianBlur(1.2))


def fallback_earth(mask):
    w, h = mask.size; m = np.array(mask) / 255.0
    lat = np.linspace(90, -90, h)[:, None] * np.ones((1, w)); one = np.ones((h, w))
    rng = np.random.default_rng(3); noise = np.array(Image.fromarray((rng.random((h // 8, w // 8)) * 255).astype("uint8")).resize((w, h), Image.BICUBIC)) / 255.0
    green = np.stack([0.18 * one + 0.1 * noise, 0.32 * one + 0.12 * noise, 0.14 * one], -1); desert = np.stack([0.62 * one, 0.52 * one, 0.36 * one], -1)
    dry = np.clip((np.abs(np.abs(lat) - 24) < 10) * 0.8 + noise * 0.3 - 0.2, 0, 1)[..., None]
    land = np.where((np.abs(lat) > 66)[..., None], np.ones((h, w, 3)) * 0.92, green * (1 - dry) + desert * dry)
    ocean = np.stack([0.03 * one, 0.10 * one + 0.04 * noise, 0.25 * one + 0.05 * noise], -1)
    return Image.fromarray(((land * m[..., None] + ocean * (1 - m[..., None])) * 255).astype("uint8"))


def sphere_noise(w=1024, h=512):
    lon = (np.arange(w) + 0.5) / w * 2 * np.pi - np.pi; lat = np.pi / 2 - (np.arange(h) + 0.5) / h * np.pi
    LON, LAT = np.meshgrid(lon, lat)
    P = np.stack([np.cos(LAT) * np.sin(LON), np.sin(LAT), np.cos(LAT) * np.cos(LON)], -1)
    rng = np.random.default_rng(7); perm = np.concatenate([rng.permutation(256)] * 2)
    grad = rng.normal(size=(256, 3)); grad /= np.linalg.norm(grad, axis=1, keepdims=True)

    def pnoise(p):
        i = np.floor(p).astype(int); f = p - i; u = f * f * f * (f * (f * 6 - 15) + 10)
        def g(ix, iy, iz, fx, fy, fz):
            hsh = perm[(perm[(perm[ix & 255] + iy) & 511] + iz) & 511] & 255; gg = grad[hsh]
            return gg[..., 0] * fx + gg[..., 1] * fy + gg[..., 2] * fz
        ix, iy, iz = i[..., 0], i[..., 1], i[..., 2]; fx, fy, fz = f[..., 0], f[..., 1], f[..., 2]
        c = [g(ix + a, iy + b, iz + c_, fx - a, fy - b, fz - c_) for c_ in (0, 1) for b in (0, 1) for a in (0, 1)]
        ux, uy, uz = u[..., 0], u[..., 1], u[..., 2]
        x00, x10, x01, x11 = c[0] + ux * (c[1] - c[0]), c[2] + ux * (c[3] - c[2]), c[4] + ux * (c[5] - c[4]), c[6] + ux * (c[7] - c[6])
        y0, y1 = x00 + uy * (x10 - x00), x01 + uy * (x11 - x01); return y0 + uz * (y1 - y0)

    def fbm(p, octaves):
        s, a = 0, 0.5
        for _ in range(octaves): s = s + a * pnoise(p); p = p * 2.03 + np.array([1.7, 9.2, 3.1]); a *= 0.5
        return (s - s.min()) / (s.max() - s.min())

    return Image.fromarray((np.stack([fbm(P * 2.5, 6), fbm(P * 2.0 + [5, 1, 2], 5), fbm(P * 9.0 + [3, 7, 1], 4)], -1) * 255).astype("uint8"))


def main():
    ASSETS.mkdir(parents=True, exist_ok=True)
    mask = landmask(); mask.save(ASSETS / "landmask.png")
    fallback_earth(mask).save(ASSETS / "earth_fallback.jpg", quality=90)
    sphere_noise().save(ASSETS / "noise.png")
    shutil.copy(REPO / "frontend/public/textures/moon/lroc_color_2k.jpg", ASSETS / "lroc_color_2k.jpg")
    print("Texturas en", ASSETS)


if __name__ == "__main__":
    main()
