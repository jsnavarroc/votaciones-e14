"""Descarga masiva de PDFs E-14 de un departamento (paso 2)."""
from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import requests

from votaciones.config import (
    BASE, CORP_MAP, HEADERS_PDF, HEADERS_WARMUP, PDFS_DIR, safe_dir,
)
from votaciones.datos import (
    buscar_departamento, cargar_indices, transmisiones_del_depto,
)


def construir_url(t: dict) -> str:
    dpto = t["idDepartmentCode"].zfill(2)
    mun = t["municipalityCode"].zfill(3)
    zona = t["idZoneCode"].zfill(3)
    puesto = t["standCode"].zfill(2)
    mesa = t["numberStand"].zfill(3)
    corp = CORP_MAP.get(t["idCorporationCode"], t["idCorporationCode"])
    return f"{BASE}/assets/temis/pdf/{dpto}/{mun}/{zona}/{puesto}/{mesa}/{corp}/{t['expectedName']}"


def _descargar_uno(session: requests.Session, t: dict, base_dir: Path,
                   mun_map: dict, dept_name: str):
    url = construir_url(t)
    mun_name = mun_map.get(t["municipalityCode"], t["municipalityCode"])
    dest_dir = base_dir / safe_dir(dept_name) / safe_dir(f"{t['municipalityCode']}_{mun_name}")
    dest_dir.mkdir(parents=True, exist_ok=True)
    fname = f"z{t['idZoneCode']}_p{t['standCode']}_m{t['numberStand']}.pdf"
    dest = dest_dir / fname

    if dest.exists() and dest.stat().st_size > 1000:
        return "skip", url, str(dest)
    try:
        r = session.get(url, headers=HEADERS_PDF, timeout=60)
    except requests.RequestException as e:
        return "error", url, str(e)
    if r.status_code != 200:
        return "fail", url, f"HTTP {r.status_code}"
    ct = r.headers.get("content-type", "")
    if "pdf" not in ct.lower() and not r.content.startswith(b"%PDF"):
        return "fail", url, f"Content-Type inesperado: {ct}"
    dest.write_bytes(r.content)
    return "ok", url, str(dest)


def ejecutar(dept_code: str, *, workers: int = 10, prueba: int | None = None) -> int:
    """Descarga los PDFs del departamento. Devuelve exit code."""
    tree, codes = cargar_indices()
    dept_name, mun_map = buscar_departamento(tree, dept_code)
    transmisiones = transmisiones_del_depto(codes, dept_code)

    print(f"\n>>> {dept_name} (codigo {dept_code})")
    print(f"    Total mesas con PDF disponible: {len(transmisiones)}")
    print(f"    Municipios: {len(mun_map)}")
    if not transmisiones:
        print("\nNo hay transmisiones para este departamento.")
        return 2
    if prueba is not None:
        transmisiones = transmisiones[:prueba]
        print(f"    MODO PRUEBA: solo {len(transmisiones)} mesas")

    print(f"\nGuardando en {PDFS_DIR}\n")
    PDFS_DIR.mkdir(parents=True, exist_ok=True)
    session = requests.Session()

    try:
        rw = session.get(f"{BASE}/", headers=HEADERS_WARMUP, timeout=60)
        cookies = ",".join(c.name for c in session.cookies) or "(ninguna)"
        print(f"  warmup HTTP {rw.status_code}  cookies={cookies}")
    except requests.RequestException as e:
        print(f"  WARMUP FAIL: {e}  -- abortando")
        return 3

    ok = fail = skip = err = 0
    t0 = time.time()
    primeros_fail: list[str] = []
    pool = ThreadPoolExecutor(max_workers=workers)
    try:
        futures = [
            pool.submit(_descargar_uno, session, t, PDFS_DIR, mun_map, dept_name)
            for t in transmisiones
        ]
        total = len(futures)
        for i, fut in enumerate(as_completed(futures), 1):
            status, url, info = fut.result()
            if status == "ok":
                ok += 1
            elif status == "skip":
                skip += 1
            elif status == "fail":
                fail += 1
                if len(primeros_fail) < 5:
                    primeros_fail.append(f"  {info}  ->  {url}")
            else:
                err += 1
                if len(primeros_fail) < 5:
                    primeros_fail.append(f"  ERROR {info}  ->  {url}")
            if i % 25 == 0 or i == total:
                dt = time.time() - t0
                vel = i / dt if dt else 0
                print(f"  {i}/{total}  ok={ok} skip={skip} fail={fail} err={err}  ({vel:.1f}/s)")
    except KeyboardInterrupt:
        print(f"\n[!] Cancelado por usuario. Deteniendo descargas...")
        pool.shutdown(wait=False, cancel_futures=True)
        print(f"[!] Procesados: {ok+skip+fail+err}/{total}.")
    finally:
        pool.shutdown(wait=False, cancel_futures=True)

    print(f"\nTerminado en {time.time() - t0:.1f}s.")
    print(f"  ok={ok}  skip={skip}  fail={fail}  err={err}")
    if primeros_fail:
        print("\nPrimeros fallos (para depurar la URL):")
        for f in primeros_fail:
            print(f)
    return 0


def cuenta_pdfs_locales(dept_name: str) -> int:
    """Cuenta PDFs ya descargados para mostrar en el menu."""
    folder = PDFS_DIR / safe_dir(dept_name)
    if not folder.exists():
        return 0
    return sum(1 for _ in folder.rglob("*.pdf"))


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Uso: python -m votaciones.descargar <CODE> [--prueba N] [--workers K]")
        raise SystemExit(0)
    code = sys.argv[1].zfill(2)
    kw = {}
    i = 2
    while i < len(sys.argv):
        if sys.argv[i] == "--prueba": kw["prueba"] = int(sys.argv[i+1]); i += 2
        elif sys.argv[i] == "--workers": kw["workers"] = int(sys.argv[i+1]); i += 2
        else: i += 1
    raise SystemExit(ejecutar(code, **kw))
