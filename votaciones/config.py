"""Configuracion compartida del pipeline E-14."""
from __future__ import annotations

from pathlib import Path

# Raiz del proyecto: la carpeta que CONTIENE el paquete votaciones/
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Carpetas de datos (NO se versionan en git)
INDICES_DIR = PROJECT_ROOT / "indices"
PDFS_DIR = PROJECT_ROOT / "pdfs"
IMG_DIR = PROJECT_ROOT / "imagenes"
REPORTES_DIR = PROJECT_ROOT / "reportes"

# Portal de la Registraduria - Segunda vuelta presidencial 2026
BASE = "https://e14segundavueltapresidente.registraduria.gov.co"
ASSETS_JSON = f"{BASE}/assets/temis/divipol_json"

# idCorporationCode -> sufijo en la ruta del PDF
CORP_MAP = {"001": "PRE"}

# User-Agent y client hints de Chrome 149 - necesarios para pasar Akamai Bot Manager
_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/149.0.0.0 Safari/537.36"
)

HEADERS_WARMUP = {
    "User-Agent": _UA,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Upgrade-Insecure-Requests": "1",
}

HEADERS_PDF = {
    "User-Agent": _UA,
    "Accept": "application/pdf,*/*",
    "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
    "Referer": f"{BASE}/",
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-origin",
    "sec-ch-ua": '"Chromium";v="149", "Not.A/Brand";v="24"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Windows"',
}

HEADERS_JSON = {
    **HEADERS_PDF,
    "Accept": "application/json, text/plain, */*",
}


def safe_dir(s: str) -> str:
    """Normaliza un string a nombre de carpeta filesystem-safe."""
    return "".join(c if c.isalnum() or c in "-_." else "_" for c in s).strip("._") or "SIN_NOMBRE"
