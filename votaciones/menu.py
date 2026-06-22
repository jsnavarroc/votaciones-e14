"""Menu interactivo del pipeline E-14.

Flujo:
1. Pregunta departamento (si no hay indices, ofrece descargarlos)
2. Loop de acciones para ese departamento
3. Opcion 'Cambiar departamento' o 'Salir' rompen el loop
"""
from __future__ import annotations

import os
import sys
import traceback

import questionary
from questionary import Choice

from votaciones import cambios, descargar, imagenes, indices, inventario
from votaciones.config import PDFS_DIR, REPORTES_DIR, safe_dir
from votaciones.datos import cargar_indices, listar_departamentos


def _banner() -> None:
    print()
    print("=" * 50)
    print("  Pipeline E-14 - Segunda Vuelta Presidencial 2026")
    print("  Registraduria Nacional - Colombia")
    print("=" * 50)


def _asegurar_indices() -> bool:
    """Si no hay indices, ofrece descargarlos. Devuelve True si quedan listos."""
    if indices.indices_disponibles():
        return True
    print("\nNo encuentro los indices (catalogo de mesas).")
    ok = questionary.confirm("Descargarlos ahora? (~36 MB)").ask()
    if not ok:
        return False
    return indices.ejecutar() == 0 and indices.indices_disponibles()


def _elegir_departamento() -> tuple[str, str] | None:
    tree, _ = cargar_indices()
    lista = listar_departamentos(tree)
    choices = []
    # Opciones especiales nacionales al inicio
    choices.append(Choice(
        title="  *** TODOS - Inventario nacional (linea base de los 34 territorios) ***",
        value=("__ALL_INVENTARIO__", "TODOS"),
    ))
    choices.append(Choice(
        title="  *** TOP 4 - Solo grandes: Bogota, Antioquia, Valle, Cundinamarca ***",
        value=("__TOP4_INVENTARIO__", "TOP4"),
    ))
    choices.append(Choice(title="  -----", value=("__SEP__", "")))
    for d in lista:
        folder = PDFS_DIR / safe_dir(d["name"])
        n_pdfs = sum(1 for _ in folder.rglob("*.pdf")) if folder.exists() else 0
        marca = f"  ({n_pdfs} PDFs descargados)" if n_pdfs else "  (sin descargar)"
        choices.append(Choice(
            title=f"  {d['code']}  {d['name']:<25} mun={d['municipios']:>3}{marca}",
            value=(d["code"], d["name"]),
        ))
    seleccion = questionary.select(
        "Departamento:",
        choices=choices,
        instruction="(flechas + enter)",
    ).ask()
    # Si eligieron el separador, ignorar
    if seleccion and seleccion[0] == "__SEP__":
        return _elegir_departamento()
    return seleccion


def _menu_acciones(dept_code: str, dept_name: str) -> str:
    """Devuelve: 'cambiar', 'salir' o ejecuta la accion y devuelve 'continuar'."""
    folder = PDFS_DIR / safe_dir(dept_name)
    n_pdfs = sum(1 for _ in folder.rglob("*.pdf")) if folder.exists() else 0
    manifest = REPORTES_DIR / f"manifest_{safe_dir(dept_name)}.jsonl"
    n_obs = sum(1 for _ in manifest.open(encoding="utf-8")) if manifest.exists() else 0

    accion = questionary.select(
        f"\nAccion para {dept_name} ({dept_code}):",
        choices=[
            Choice(title=f"  1) Descargar PDFs                ({n_pdfs} en disco)",
                   value="descargar"),
            Choice(title=f"  2) Generar Excel + integridad    (manifest: {n_obs} lineas)",
                   value="inventario"),
            Choice(title="  3) Convertir PDFs a imagenes",
                   value="imagenes"),
            Choice(title=f"  4) Detectar cambios              (necesita >=2 obs en manifest)",
                   value="cambios"),
            Choice(title="  5) Cambiar departamento", value="cambiar"),
            Choice(title="  0) Salir", value="salir"),
        ],
    ).ask()
    if accion in (None, "salir"):
        return "salir"
    if accion == "cambiar":
        return "cambiar"

    try:
        if accion == "descargar":
            _accion_descargar(dept_code)
        elif accion == "inventario":
            _accion_inventario(dept_code)
        elif accion == "imagenes":
            _accion_imagenes(dept_code)
        elif accion == "cambios":
            _accion_cambios(dept_code)
    except KeyboardInterrupt:
        print("\nInterrumpido por el usuario.")
    except Exception:
        traceback.print_exc()
        questionary.press_any_key_to_continue("Presiona una tecla para volver al menu...").ask()
    return "continuar"


def _workers_sugeridos(tipo: str) -> tuple[int, int, int]:
    """Devuelve (recomendado, maximo_seguro, cores). Si tipo='io' (red, no CPU
    intensivo) puede usar mas hilos que cores. Si tipo='cpu' (render PDF, etc.)
    deja al menos 1 nucleo libre para que el sistema responda."""
    cores = os.cpu_count() or 4
    if tipo == "io":
        recom = min(cores * 2, 16)       # bloqueo en red, hilos extra ayudan
        maximo = min(cores * 4, 32)
    else:  # cpu
        recom = max(1, cores - 1)        # deja 1 libre para no congelar PC
        maximo = cores                   # no pasar de fisicos
    return recom, maximo, cores


def _preguntar_workers(tipo: str = "io") -> int:
    recom, maximo, cores = _workers_sugeridos(tipo)
    descripcion = "I/O (red)" if tipo == "io" else "CPU (procesamiento)"
    print(f"\n  Tu PC tiene {cores} nucleos.  Tarea: {descripcion}.")
    sel = questionary.select(
        "Workers paralelos:",
        choices=[
            Choice(f"Recomendado: {recom}  (rapido y seguro)", recom),
            Choice(f"Maximo seguro: {maximo}", maximo),
            Choice("Personalizado...", None),
        ],
    ).ask()
    if sel is None:
        sel_str = questionary.text(
            f"Cuantos workers? (1-{maximo * 2})",
            default=str(recom),
            validate=lambda x: x.isdigit() and 1 <= int(x) <= maximo * 2,
        ).ask()
        sel = int(sel_str)
    return int(sel)


def _preguntar_modo(default_prueba: str = "5") -> int | None:
    """Pregunta si correr modo prueba (N) o todo. Devuelve None=todo, int=N."""
    modo = questionary.select(
        "Como quieres correrlo?",
        choices=[
            Choice("Probar primero con unos pocos (recomendado la primera vez)", "prueba"),
            Choice("Procesar TODO", "todo"),
        ],
    ).ask()
    if modo != "prueba":
        return None
    n = questionary.text(
        "Cuantos?",
        default=default_prueba,
        validate=lambda x: x.isdigit() and int(x) > 0,
    ).ask()
    return int(n)


def _accion_descargar(dept_code: str) -> None:
    prueba = _preguntar_modo(default_prueba="5")
    workers = _preguntar_workers("io")
    descargar.ejecutar(dept_code, workers=workers, prueba=prueba)


def _accion_inventario(dept_code: str) -> None:
    con_red = questionary.confirm(
        "Consultar al servidor para capturar ETag/version-id? (recomendado)",
        default=True,
    ).ask()
    workers = 10
    if con_red:
        workers = _preguntar_workers("io")
    inventario.ejecutar(dept_code, workers=workers, sin_red=not con_red)


def _accion_imagenes(dept_code: str) -> None:
    prueba = _preguntar_modo(default_prueba="3")
    fmt = questionary.select("Formato:", choices=[
        Choice("JPG (mas liviano, recomendado)", "jpg"),
        Choice("PNG (sin perdida, pesa 4x mas)", "png"),
    ]).ask()
    dpi = int(questionary.select("DPI:", choices=[
        Choice("200 (default)", "200"),
        Choice("250 (recomendado para OCR)", "250"),
        Choice("300 (maxima calidad)", "300"),
    ]).ask())
    stitch = questionary.confirm(
        "Stitch (todas las paginas en UNA imagen por PDF)?", default=True,
    ).ask()
    horizontal = False
    if stitch:
        horizontal = questionary.confirm(
            "Stitch HORIZONTAL (paginas al lado)? Si=al lado, No=apiladas verticalmente",
            default=True,
        ).ask()
    rotar = int(questionary.select("Rotar?", choices=[
        Choice("Sin rotar", "0"),
        Choice("90 grados a la izquierda (recomendado, queda apaisado)", "90"),
        Choice("180 grados", "180"),
        Choice("270 grados", "270"),
    ]).ask())
    workers = _preguntar_workers("cpu")
    imagenes.ejecutar(
        dept_code, dpi=dpi, fmt=fmt, workers=workers, prueba=prueba,
        stitch=stitch, rotar=rotar, horizontal=horizontal,
    )


def _accion_cambios(dept_code: str) -> None:
    solo = questionary.confirm("Mostrar solo los archivos que cambiaron?", default=False).ask()
    cambios.ejecutar(dept_code, solo_cambios=solo)


# IDs de departamento Bogota, Antioquia, Valle, Cundinamarca (los 4 grandes)
_TOP4 = ["16", "01", "31", "15"]


def _inventario_bulk(codes: list[str], titulo: str) -> None:
    """Ejecuta paso3 sobre una lista de departamentos secuencialmente."""
    import time
    tree, _ = cargar_indices()
    lista = listar_departamentos(tree)
    deptos = [d for d in lista if d["code"] in codes]
    total_mesas = "?"  # informativo no se calcula a priori

    print(f"\n>>> {titulo}")
    print(f"    Departamentos a procesar: {len(deptos)}")
    for d in deptos:
        print(f"      {d['code']}  {d['name']}  ({d['municipios']} mun)")
    print(f"\n    El inventario NO descarga PDFs; solo captura ETag/version-id")
    print(f"    del servidor para tener linea base de integridad.")

    workers = _preguntar_workers("io")
    if not questionary.confirm(f"\nConfirmas ejecutar inventario sobre los {len(deptos)} departamentos?",
                                default=True).ask():
        print("Cancelado.")
        return

    t_total = time.time()
    fallidos: list[str] = []
    for i, d in enumerate(deptos, 1):
        print(f"\n{'='*70}")
        print(f"[{i}/{len(deptos)}]  {d['name']}  (codigo {d['code']})")
        print(f"{'='*70}")
        t0 = time.time()
        try:
            rc = inventario.ejecutar(d["code"], workers=workers, sin_red=False)
            if rc != 0:
                fallidos.append(f"{d['code']} {d['name']} (rc={rc})")
        except KeyboardInterrupt:
            print(f"\nInterrumpido por usuario en {d['name']}.")
            print(f"Procesados: {i-1}/{len(deptos)}.")
            break
        except Exception as e:
            print(f"\nERROR en {d['name']}: {e}")
            fallidos.append(f"{d['code']} {d['name']}: {e!s:.80}")
        print(f"\n[{i}/{len(deptos)}] {d['name']} - tomo {time.time()-t0:.0f}s")

    dt = time.time() - t_total
    print(f"\n{'#'*70}")
    print(f"TERMINADO: {len(deptos)} departamentos en {dt:.0f}s ({dt/60:.1f} min)")
    print(f"{'#'*70}")
    if fallidos:
        print(f"\nFallos ({len(fallidos)}):")
        for f in fallidos:
            print(f"  - {f}")
    else:
        print(f"\nTodos los departamentos procesados correctamente.")
    questionary.press_any_key_to_continue("\nPresiona una tecla para volver al menu...").ask()


def main() -> int:
    _banner()
    if not _asegurar_indices():
        print("\nNo se pueden continuar sin indices. Saliendo.")
        return 1
    while True:
        sel = _elegir_departamento()
        if sel is None:
            return 0
        dept_code, dept_name = sel

        # Opciones especiales de inventario bulk
        if dept_code == "__ALL_INVENTARIO__":
            tree, _ = cargar_indices()
            all_codes = [d["code"] for d in listar_departamentos(tree)]
            _inventario_bulk(all_codes, "INVENTARIO NACIONAL (34 territorios)")
            continue
        if dept_code == "__TOP4_INVENTARIO__":
            _inventario_bulk(_TOP4, "INVENTARIO TOP 4 (Bogota, Antioquia, Valle, Cundinamarca)")
            continue

        while True:
            r = _menu_acciones(dept_code, dept_name)
            if r == "salir":
                print("\nHasta luego.")
                return 0
            if r == "cambiar":
                break


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\nInterrumpido.")
        sys.exit(130)
