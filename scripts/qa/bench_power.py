"""Mide la extracción NASA POWER (fría y con caché) y el parseo de un sitio. Uso: .venv\\Scripts\\python.exe scripts\\qa\\bench_power.py"""
import asyncio
import sys
import time
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from backend.app.connectors.nasa.power import PowerConnector  # noqa: E402

VARS = ["ALLSKY_SFC_SW_DWN", "T2M", "WS10M", "PRECTOTCORR"]
SITES = [(-17.193, -70.934), (-16.409, -71.537)]


async def main():
    connector = PowerConnector()
    for label in ("primera", "segunda"):
        start = time.perf_counter()
        results = await asyncio.gather(*(connector.daily_point_multi(lat, lon, VARS, date(2001, 1, 1), date(2024, 12, 31)) for lat, lon in SITES))
        provenance = {source.provenance for site in results for _, source in site.values()}
        print(label, f"{(time.perf_counter() - start) * 1000:.0f} ms", provenance)
    payload, *_ = await connector._request({"parameters": ",".join(VARS), "community": "RE", "longitude": SITES[0][1], "latitude": SITES[0][0], "start": "20010101", "end": "20241231", "format": "JSON", "time-standard": "UTC"})
    start = time.perf_counter()
    PowerConnector._parse_multi(payload, None or results[0]["T2M"][1].provenance, results[0]["T2M"][1].downloaded_at, VARS)
    print("parse síncrono 1 sitio", f"{(time.perf_counter() - start) * 1000:.0f} ms")


asyncio.run(main())
