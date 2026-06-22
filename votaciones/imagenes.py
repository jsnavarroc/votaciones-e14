"""Convierte PDFs descargados a imagenes (paso 4)."""
from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import fitz  # pymupdf
from PIL import Image

from votaciones.config import IMG_DIR, PDFS_DIR, safe_dir
from votaciones.datos import cargar_indices, buscar_departamento  # noqa: F401


def _pixmap_a_pil(pix: fitz.Pixmap) -> Image.Image:
    return Image.frombytes("RGB", (pix.width, pix.height), pix.samples)


def _stitch_vertical(imgs: list[Image.Image]) -> Image.Image:
    base_w = imgs[0].width
    escaladas = []
    for im in imgs:
        if im.width != base_w:
            ratio = base_w / im.width
            im = im.resize((base_w, int(im.height * ratio)), Image.LANCZOS)
        escaladas.append(im)
    total_h = sum(im.height for im in escaladas)
    salida = Image.new("RGB", (base_w, total_h), "white")
    y = 0
    for im in escaladas:
        salida.paste(im, (0, y))
        y += im.height
    return salida


def _stitch_horizontal(imgs: list[Image.Image]) -> Image.Image:
    base_h = imgs[0].height
    escaladas = []
    for im in imgs:
        if im.height != base_h:
            ratio = base_h / im.height
            im = im.resize((int(im.width * ratio), base_h), Image.LANCZOS)
        escaladas.append(im)
    total_w = sum(im.width for im in escaladas)
    salida = Image.new("RGB", (total_w, base_h), "white")
    x = 0
    for im in escaladas:
        salida.paste(im, (x, 0))
        x += im.width
    return salida


def _convertir_pdf(pdf_path: Path, base_in: Path, base_out: Path,
                   dpi: int, fmt: str, solo_pagina: int | None,
                   stitch: bool, rotar: int, horizontal: bool) -> tuple[str, str, int]:
    try:
        rel = pdf_path.relative_to(base_in)
    except ValueError:
        rel = Path(pdf_path.name)
    out_dir = base_out / rel.parent
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = pdf_path.stem
    sufijo = "jpg" if fmt == "jpg" else "png"

    try:
        with pdf_path.open("rb") as f:
            if f.read(5) != b"%PDF-":
                return "pdf_invalido", str(pdf_path), 0
    except OSError as e:
        return "fail", f"{pdf_path}: {e}", 0
    try:
        doc = fitz.open(pdf_path)
    except Exception as e:
        return "fail", f"{pdf_path}: {e}", 0

    try:
        zoom = dpi / 72.0
        mat = fitz.Matrix(zoom, zoom)
        if stitch:
            out_path = out_dir / f"{stem}.{sufijo}"
            if out_path.exists() and out_path.stat().st_size > 1000:
                return "skip", str(pdf_path), 1
            pils = []
            for i in range(doc.page_count):
                pix = doc.load_page(i).get_pixmap(matrix=mat, alpha=False)
                im = _pixmap_a_pil(pix)
                if rotar:
                    im = im.rotate(rotar, expand=True)
                pils.append(im)
            if not pils:
                return "pdf_invalido", str(pdf_path), 0
            final = _stitch_horizontal(pils) if horizontal else _stitch_vertical(pils)
            if fmt == "jpg":
                final.save(out_path, "JPEG", quality=85)
            else:
                final.save(out_path, "PNG", compress_level=1)
            return "ok", str(pdf_path), 1

        paginas = [solo_pagina - 1] if solo_pagina else range(doc.page_count)
        generadas = salteadas = 0
        for i in paginas:
            if i < 0 or i >= doc.page_count:
                continue
            out_path = out_dir / f"{stem}_p{i + 1:02d}.{sufijo}"
            if out_path.exists() and out_path.stat().st_size > 1000:
                salteadas += 1
                continue
            pix = doc.load_page(i).get_pixmap(matrix=mat, alpha=False)
            if rotar:
                im = _pixmap_a_pil(pix).rotate(rotar, expand=True)
                if fmt == "jpg":
                    im.save(out_path, "JPEG", quality=85)
                else:
                    im.save(out_path, "PNG", compress_level=1)
            else:
                if fmt == "jpg":
                    pix.save(out_path, jpg_quality=85)
                else:
                    pix.save(out_path)
            generadas += 1
    finally:
        doc.close()
    if generadas == 0 and salteadas > 0:
        return "skip", str(pdf_path), salteadas
    return "ok", str(pdf_path), generadas


def ejecutar(dept_code: str, *, dpi: int = 200, fmt: str = "png",
             workers: int = 4, prueba: int | None = None,
             solo_pagina: int | None = None,
             stitch: bool = False, rotar: int = 0,
             horizontal: bool = False) -> int:
    tree, _ = cargar_indices()
    dept_name, _ = buscar_departamento(tree, dept_code)

    pdf_root = PDFS_DIR / safe_dir(dept_name)
    out_root = IMG_DIR / safe_dir(dept_name)
    if not pdf_root.exists():
        print(f"No existe {pdf_root}. Corre primero la descarga de PDFs.")
        return 1

    pdfs = sorted(pdf_root.rglob("*.pdf"))
    print(f"\n>>> {dept_name} (codigo {dept_code})")
    print(f"    PDFs encontrados: {len(pdfs)}")
    print(f"    Formato: {fmt.upper()}  DPI: {dpi}  Workers: {workers}")
    if rotar:
        print(f"    Rotacion: {rotar} grados (antihorario)")
    if stitch:
        direccion = "HORIZONTAL (al lado)" if horizontal else "VERTICAL (apiladas)"
        print(f"    Modo: STITCH {direccion}")
    elif solo_pagina:
        print(f"    Solo pagina: {solo_pagina}")
    if prueba:
        pdfs = pdfs[:prueba]
        print(f"    MODO PRUEBA: solo {len(pdfs)} PDFs")
    print(f"    Salida: {out_root}\n")
    if not pdfs:
        print("Nada que procesar.")
        return 0

    out_root.mkdir(parents=True, exist_ok=True)
    ok = skip = fail = inv = 0
    paginas_total = 0
    primeros_fail: list[str] = []
    t0 = time.time()
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [
            pool.submit(_convertir_pdf, p, pdf_root, out_root, dpi, fmt,
                        solo_pagina, stitch, rotar, horizontal)
            for p in pdfs
        ]
        total = len(futures)
        for i, fut in enumerate(as_completed(futures), 1):
            estado, info, npages = fut.result()
            if estado == "ok": ok += 1; paginas_total += npages
            elif estado == "skip": skip += 1
            elif estado == "pdf_invalido": inv += 1
            else:
                fail += 1
                if len(primeros_fail) < 5:
                    primeros_fail.append(info)
            if i % 50 == 0 or i == total:
                dt = time.time() - t0
                vel = i / dt if dt else 0
                print(f"  {i}/{total}  ok={ok} skip={skip} pdf_invalido={inv} fail={fail}  ({vel:.1f}/s)")

    print(f"\nTerminado en {time.time() - t0:.1f}s.")
    print(f"  ok={ok}  skip={skip}  pdf_invalido={inv}  fail={fail}")
    print(f"  imagenes generadas: {paginas_total}")
    if primeros_fail:
        print("\nPrimeros fallos:")
        for f in primeros_fail:
            print(f"  {f}")
    return 0


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Uso: python -m votaciones.imagenes <CODE> [--dpi N] [--jpg] [--stitch] [--horizontal] [--rotar N] [--workers K] [--prueba N]")
        raise SystemExit(0)
    code = sys.argv[1].zfill(2)
    kw = {}
    i = 2
    while i < len(sys.argv):
        a = sys.argv[i]
        if a == "--dpi": kw["dpi"] = int(sys.argv[i+1]); i += 2
        elif a == "--jpg": kw["fmt"] = "jpg"; i += 1
        elif a == "--png": kw["fmt"] = "png"; i += 1
        elif a == "--workers": kw["workers"] = int(sys.argv[i+1]); i += 2
        elif a == "--prueba": kw["prueba"] = int(sys.argv[i+1]); i += 2
        elif a == "--solo-pagina": kw["solo_pagina"] = int(sys.argv[i+1]); i += 2
        elif a == "--stitch": kw["stitch"] = True; i += 1
        elif a == "--horizontal": kw["horizontal"] = True; i += 1
        elif a == "--rotar": kw["rotar"] = int(sys.argv[i+1]) % 360; i += 2
        else: i += 1
    raise SystemExit(ejecutar(code, **kw))
