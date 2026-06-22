"""
Validacion de la mesa: ANTIOQUIA / TURBO / zona 03 / puesto 01 / mesa 003.

La imagen ciudadana muestra dos versiones del MISMO acta (DELEGADOS y CLAVEROS)
con diferencias visibles entre ellas (Pacto Historico: 38 vs 138).

Este script:
  1. Confirma cual version publica el portal en /assets/temis/pdf/.../PRE/<hash>.pdf
  2. Renderiza la pagina 1 a JPG para que tu compares visualmente con la imagen
  3. Calcula MD5/SHA-256 locales y los huellas oficiales del servidor (ETag, etc.)
  4. Sondea rutas alternativas plausibles para la SEGUNDA version
     (DELEGADOS vs CLAVEROS) y reporta cual responde 200 y cual 403/404.

Uso:
    python validar_dos_mesas.py
"""
from __future__ import annotations
import hashlib
import json
import time
from pathlib import Path

import requests

from votaciones.config import BASE, HEADERS_PDF, HEADERS_WARMUP

VAL_DIR = Path(__file__).parent / "validacion"

# Datos de la mesa que vamos a validar (con padding como hace construir_url)
DEPTO = "01".zfill(2)    # ANTIOQUIA
MUN   = "280".zfill(3)   # TURBO
ZONA  = "03".zfill(3)    # -> "003"  (importante: la zona usa 3 digitos)
PUEST = "01".zfill(2)
MESA  = "003".zfill(3)
HASH  = "09686f1885b0bf01fe7722350fb63f7acb620a0aa36dd78fe240c003a56a0b76"

URL_OFICIAL = f"{BASE}/assets/temis/pdf/{DEPTO}/{MUN}/{ZONA}/{PUEST}/{MESA}/PRE/{HASH}.pdf"

# Variantes a sondear para encontrar la otra version (DELEGADOS vs CLAVEROS)
VARIANTES = [
    f"{BASE}/assets/temis/pdf/{DEPTO}/{MUN}/{ZONA}/{PUEST}/{MESA}/PRE/DELEGADOS/{HASH}.pdf",
    f"{BASE}/assets/temis/pdf/{DEPTO}/{MUN}/{ZONA}/{PUEST}/{MESA}/PRE/CLAVEROS/{HASH}.pdf",
    f"{BASE}/assets/temis/pdf/{DEPTO}/{MUN}/{ZONA}/{PUEST}/{MESA}/PRE_DELEGADOS/{HASH}.pdf",
    f"{BASE}/assets/temis/pdf/{DEPTO}/{MUN}/{ZONA}/{PUEST}/{MESA}/PRE_CLAVEROS/{HASH}.pdf",
    f"{BASE}/assets/temis/pdf/{DEPTO}/{MUN}/{ZONA}/{PUEST}/{MESA}/DEL/{HASH}.pdf",
    f"{BASE}/assets/temis/pdf/{DEPTO}/{MUN}/{ZONA}/{PUEST}/{MESA}/CLA/{HASH}.pdf",
    # versiones con tipo concatenado al hash
    f"{BASE}/assets/temis/pdf/{DEPTO}/{MUN}/{ZONA}/{PUEST}/{MESA}/PRE/{HASH}_D.pdf",
    f"{BASE}/assets/temis/pdf/{DEPTO}/{MUN}/{ZONA}/{PUEST}/{MESA}/PRE/{HASH}_C.pdf",
    f"{BASE}/assets/temis/pdf/{DEPTO}/{MUN}/{ZONA}/{PUEST}/{MESA}/PRE/D_{HASH}.pdf",
    f"{BASE}/assets/temis/pdf/{DEPTO}/{MUN}/{ZONA}/{PUEST}/{MESA}/PRE/C_{HASH}.pdf",
]


def calcular_hashes(p: Path) -> tuple[str, str]:
    md5 = hashlib.md5()
    sha = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            md5.update(chunk)
            sha.update(chunk)
    return md5.hexdigest(), sha.hexdigest()


def main() -> int:
    VAL_DIR.mkdir(exist_ok=True)

    print("Warmup en /...")
    s = requests.Session()
    try:
        rw = s.get(f"{BASE}/", headers=HEADERS_WARMUP, timeout=60)
        print(f"  HTTP {rw.status_code}  cookies={[c.name for c in s.cookies]}")
    except requests.RequestException as e:
        print(f"  WARMUP FAIL: {e}")
        return 1
    time.sleep(1)

    # 1) Descargar la URL oficial del catalogo
    print(f"\n[1/3] Descargando version del catalogo oficial...")
    print(f"      URL: {URL_OFICIAL[-100:]}")
    dest = VAL_DIR / "antioquia_TURBO_z03_p01_m003.pdf"
    r = s.get(URL_OFICIAL, headers=HEADERS_PDF, timeout=60)
    if not r.content.startswith(b"%PDF-"):
        print(f"      FAIL: HTTP={r.status_code}  no es PDF (size={len(r.content)})")
        return 2
    dest.write_bytes(r.content)
    md5, sha = calcular_hashes(dest)
    etag = (r.headers.get("ETag") or "").strip('"').lstrip("W/").strip('"')
    print(f"      OK  {dest.stat().st_size:,} bytes")
    print(f"      MD5 local      : {md5}")
    print(f"      ETag servidor  : {etag}")
    print(f"      MD5 == ETag    : {md5.lower() == etag.lower() if etag else 'N/A'}")
    print(f"      Last-Modified  : {r.headers.get('Last-Modified', '')}")
    print(f"      version-id S3  : {r.headers.get('x-amz-version-id', '')}")

    # 2) Renderizar pagina 1 para comparacion visual
    print(f"\n[2/3] Renderizando pagina 1 para comparacion visual...")
    try:
        import fitz
        from PIL import Image
        doc = fitz.open(dest)
        pix = doc.load_page(0).get_pixmap(matrix=fitz.Matrix(1.5, 1.5),
                                           alpha=False, colorspace=fitz.csRGB)
        Image.frombytes("RGB", (pix.width, pix.height), pix.samples).save(
            VAL_DIR / "antioquia_TURBO_pag1.jpg", "JPEG", quality=88)
        doc.close()
        print(f"      OK -> validacion/antioquia_TURBO_pag1.jpg")
        print(f"      Abrelo y compara contra tu imagen para identificar si es")
        print(f"      la version DELEGADOS o la version CLAVEROS.")
    except ImportError:
        print(f"      (saltado: pymupdf/Pillow no disponible)")

    # 3) Sondear rutas alternativas (con verificacion de magic %PDF para descartar falsos positivos)
    print(f"\n[3/3] Sondeando rutas alternativas para la OTRA version...")
    print(f"      (verifica magic %PDF para descartar paginas HTML default del CDN)")
    time.sleep(1)
    encontradas = []
    fp_etag = None  # etag del falso positivo (HTML default)
    for variante in VARIANTES:
        try:
            # GET parcial (primeros 8 bytes) para verificar magic
            rh = s.get(variante, headers={**HEADERS_PDF, "Range": "bytes=0-7"},
                       timeout=15, allow_redirects=True, stream=False)
            status = rh.status_code
            etag_v = (rh.headers.get("ETag") or "").strip('"').lstrip("W/").strip('"')
            es_pdf = rh.content[:5] == b"%PDF-"
        except requests.RequestException as e:
            status = f"ERR:{type(e).__name__}"; etag_v = ""; es_pdf = False

        if status in (200, 206) and es_pdf and etag_v and etag_v.lower() != etag.lower():
            marca = " <-- PDF distinto al oficial!"
            encontradas.append((variante, etag_v))
        elif status in (200, 206) and not es_pdf:
            if fp_etag is None: fp_etag = etag_v
            marca = " (HTML default, no es PDF real)"
        elif status in (200, 206) and etag_v.lower() == etag.lower():
            marca = " (mismo hash que la oficial)"
        else:
            marca = ""
        print(f"      {status:>6}  {variante[len(BASE)+len('/assets/temis/pdf/'):]}{marca}")
        time.sleep(0.3)

    if fp_etag and not encontradas:
        print(f"\n      (Todas las rutas alternativas devuelven el mismo HTML default")
        print(f"       con ETag {fp_etag}. El portal solo publica UNA version por mesa.)")

    resultado = {
        "mesa": f"Antioquia/Turbo/z{ZONA}/p{PUEST}/m{MESA}",
        "url_catalogo": URL_OFICIAL,
        "archivo_local": str(dest),
        "md5_local": md5,
        "sha256_local": sha,
        "etag_servidor": etag,
        "md5_coincide_etag": md5.lower() == etag.lower() if etag else None,
        "last_modified": r.headers.get("Last-Modified", ""),
        "version_id": r.headers.get("x-amz-version-id", ""),
        "otras_versiones_encontradas": [
            {"url": u, "etag": e} for u, e in encontradas
        ],
        "nota": (
            "Si 'otras_versiones_encontradas' esta vacio, el portal solo "
            "publica UNA version por mesa. Las versiones DELEGADOS y CLAVEROS "
            "son copias fisicas del mismo escrutinio; solo una termina "
            "digitalizada en el portal publico."
        ),
    }
    out_json = VAL_DIR / "RESUMEN.json"
    out_json.write_text(json.dumps(resultado, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nResumen guardado en {out_json}")
    if encontradas:
        print(f"\nHALLAZGO REAL: se encontro otra version PDF distinta en:")
        for u, e in encontradas:
            print(f"  {u}  (ETag {e})")
    else:
        print(f"\nResultado: el portal SOLO publica UNA version por mesa.")
        print(f"Las copias DELEGADOS y CLAVEROS del E-14 son fisicas; solo una se digitaliza.")
        print(f"")
        print(f"Compara visualmente:")
        print(f"  Tu imagen (las dos versiones lado a lado)")
        print(f"  vs   validacion/antioquia_TURBO_pag1.jpg  (la que el portal publica)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
