"""Verifica el token de Earthdata sin imprimirlo: fechas del JWT y una lectura autenticada de 1 byte.

Uso desde la raíz del repo: .venv\\Scripts\\python.exe scripts\\qa\\token_check.py  (lee EARTHDATA_TOKEN del .env local)
"""
import base64
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from backend.app.core.config import get_settings  # noqa: E402

token = get_settings().earthdata_token or ""
if not token:
    raise SystemExit("EARTHDATA_TOKEN no está configurado en .env")
payload = token.split(".")[1]
claims = json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
for key in ("iat", "exp"):
    if key in claims:
        print(key, datetime.fromtimestamp(claims[key], timezone.utc).strftime("%Y-%m-%d %H:%M UTC"))

cmr = httpx.get(
    "https://cmr.earthdata.nasa.gov/search/granules.json",
    params={"short_name": "NASADEM_HGT", "version": "001", "point": "-70.934,-17.193", "page_size": "1"},
    timeout=30,
).json()
url = next(link["href"] for link in cmr["feed"]["entry"][0]["links"] if "data#" in link.get("rel", "") and link["href"].startswith("https://"))
response = httpx.get(url, headers={"Authorization": f"Bearer {token}", "Range": "bytes=0-0"}, follow_redirects=True, timeout=60)
print("lectura autenticada:", response.status_code, len(response.content), "byte(s)")
