"""Empaqueta el menu interactivo como ejecutable Windows (.exe).

Uso:
    pip install pyinstaller
    python build_exe.py

Resultado: dist/votaciones.exe (~30-50 MB) — corre en cualquier Windows
sin requerir Python instalado.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ENTRY = ROOT / "votaciones" / "menu.py"


def main() -> int:
    if not ENTRY.exists():
        print(f"No se encuentra {ENTRY}")
        return 1

    # Limpiar builds previos
    for d in ("build", "dist"):
        p = ROOT / d
        if p.exists():
            shutil.rmtree(p)
    for sp in ROOT.glob("*.spec"):
        sp.unlink()

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--onefile",
        "--name", "votaciones",
        "--console",
        "--clean",
        "--noconfirm",
        # incluir dependencias que PyInstaller a veces no detecta
        "--hidden-import", "questionary",
        "--hidden-import", "openpyxl",
        "--hidden-import", "fitz",
        "--hidden-import", "PIL",
        str(ENTRY),
    ]
    print("Ejecutando:", " ".join(cmd))
    rc = subprocess.call(cmd, cwd=ROOT)
    if rc != 0:
        print(f"\nPyInstaller fallo con codigo {rc}")
        return rc

    exe = ROOT / "dist" / "votaciones.exe"
    if exe.exists():
        print(f"\nOK -> {exe}  ({exe.stat().st_size / 1024 / 1024:.1f} MB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
