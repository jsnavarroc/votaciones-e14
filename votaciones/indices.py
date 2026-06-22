"""Descarga los JSON estaticos del portal E-14 (paso 1)."""
from __future__ import annotations

import json
from pathlib import Path

import requests

from votaciones.config import ASSETS_JSON, HEADERS_JSON, INDICES_DIR

ARCHIVOS = [
    "allDepartments.json",
    "allCorporations.json",
    "departmentsTree.json",
    "allTransmissionCodes.json",
]


def _descargar(nombre: str) -> Path:
    url = f"{ASSETS_JSON}/{nombre}"
    destino = INDICES_DIR / nombre
    print(f"  -> {url}")
    r = requests.get(url, headers=HEADERS_JSON, timeout=120)
    r.raise_for_status()
    destino.write_bytes(r.content)
    print(f"     OK  {len(r.content):>10,} bytes")
    return destino


def _inspeccionar(path: Path) -> None:
    print(f"\n--- {path.name} ---")
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict):
        print(f"Claves raiz ({len(data)}): {list(data.keys())[:20]}")


def ejecutar() -> int:
    """Descarga los 4 JSON y los guarda en indices/. Devuelve exit code."""
    INDICES_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Carpeta de salida: {INDICES_DIR}\n")
    print("Descargando JSONs base...")
    rutas: list[Path] = []
    for nombre in ARCHIVOS:
        try:
            rutas.append(_descargar(nombre))
        except requests.HTTPError as e:
            print(f"     FAIL {nombre}: HTTP {e.response.status_code}")
        except requests.RequestException as e:
            print(f"     FAIL {nombre}: {e}")
    print("\n--- Inspeccion ---")
    for r in rutas:
        try:
            _inspeccionar(r)
        except json.JSONDecodeError as e:
            print(f"  {r.name}: no es JSON valido ({e})")
    return 0 if rutas else 1


def indices_disponibles() -> bool:
    """True si el archivo maestro esta presente."""
    return (INDICES_DIR / "allTransmissionCodes.json").exists()


if __name__ == "__main__":
    raise SystemExit(ejecutar())
