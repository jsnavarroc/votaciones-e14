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


class _Volver(Exception):
    """Senalar que el usuario eligio volver al menu anterior."""
    pass


def _ask_or_back(question):
    """Ejecuta questionary.ask() y lanza _Volver si el usuario cancela (Ctrl+C/Esc)."""
    r = question.ask()
    if r is None:
        raise _Volver
    return r


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
    # Opciones especiales bulk al inicio
    choices.append(Choice(
        title="  *** TODOS - Procesar los 34 territorios ***",
        value=("__BULK_ALL__", "TODOS"),
    ))
    choices.append(Choice(
        title="  *** TOP 4 - Solo grandes (Bogota, Antioquia, Valle, Cundinamarca) ***",
        value=("__BULK_TOP4__", "TOP 4"),
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
    except _Volver:
        print("\n[<-] Volviendo al menu de acciones...")
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


_BACK = "__back__"


def _preguntar_workers(tipo: str = "io") -> int:
    recom, maximo, cores = _workers_sugeridos(tipo)
    descripcion = "I/O (red)" if tipo == "io" else "CPU (procesamiento)"
    print(f"\n  Tu PC tiene {cores} nucleos.  Tarea: {descripcion}.")
    sel = _ask_or_back(questionary.select(
        "Workers paralelos:",
        choices=[
            Choice(f"Recomendado: {recom}  (rapido y seguro)", recom),
            Choice(f"Maximo seguro: {maximo}", maximo),
            Choice("Personalizado...", "__custom__"),
            Choice("← Volver al menu anterior", _BACK),
        ],
    ))
    if sel == _BACK:
        raise _Volver
    if sel == "__custom__":
        sel_str = _ask_or_back(questionary.text(
            f"Cuantos workers? (1-{maximo * 2})",
            default=str(recom),
            validate=lambda x: x.isdigit() and 1 <= int(x) <= maximo * 2,
        ))
        sel = int(sel_str)
    return int(sel)


def _preguntar_modo(default_prueba: str = "5") -> int | None:
    """Pregunta si correr modo prueba (N) o todo. Devuelve None=todo, int=N.
    Lanza _Volver si el usuario elige volver."""
    modo = _ask_or_back(questionary.select(
        "Como quieres correrlo?",
        choices=[
            Choice("Probar primero con unos pocos (recomendado la primera vez)", "prueba"),
            Choice("Procesar TODO", "todo"),
            Choice("← Volver al menu anterior", _BACK),
        ],
    ))
    if modo == _BACK:
        raise _Volver
    if modo != "prueba":
        return None
    n = _ask_or_back(questionary.text(
        "Cuantos?",
        default=default_prueba,
        validate=lambda x: x.isdigit() and int(x) > 0,
    ))
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
    # respaldar_xlsx=True para no perder vistas anteriores al sobrescribir
    inventario.ejecutar(dept_code, workers=workers, sin_red=not con_red,
                        respaldar_xlsx=True)


def _accion_imagenes(dept_code: str) -> None:
    prueba = _preguntar_modo(default_prueba="3")
    fmt = _ask_or_back(questionary.select("Formato:", choices=[
        Choice("JPG (mas liviano, recomendado)", "jpg"),
        Choice("PNG (sin perdida, pesa 4x mas)", "png"),
        Choice("← Volver al menu anterior", _BACK),
    ]))
    if fmt == _BACK: raise _Volver
    dpi_str = _ask_or_back(questionary.select("DPI:", choices=[
        Choice("200 (default)", "200"),
        Choice("250 (recomendado para OCR)", "250"),
        Choice("300 (maxima calidad)", "300"),
        Choice("← Volver al menu anterior", _BACK),
    ]))
    if dpi_str == _BACK: raise _Volver
    dpi = int(dpi_str)
    stitch = _ask_or_back(questionary.confirm(
        "Stitch (todas las paginas en UNA imagen por PDF)?", default=True,
    ))
    horizontal = False
    if stitch:
        horizontal = _ask_or_back(questionary.confirm(
            "Stitch HORIZONTAL (paginas al lado)? Si=al lado, No=apiladas verticalmente",
            default=True,
        ))
    rotar_str = _ask_or_back(questionary.select("Rotar?", choices=[
        Choice("Sin rotar", "0"),
        Choice("90 grados a la izquierda (recomendado, queda apaisado)", "90"),
        Choice("180 grados", "180"),
        Choice("270 grados", "270"),
        Choice("← Volver al menu anterior", _BACK),
    ]))
    if rotar_str == _BACK: raise _Volver
    rotar = int(rotar_str)
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


def _seleccion_bulk(tipo: str) -> tuple[list[dict], str]:
    """Devuelve (deptos, titulo) para los modos bulk."""
    tree, _ = cargar_indices()
    lista = listar_departamentos(tree)
    if tipo == "ALL":
        return lista, "TODOS (34 territorios)"
    if tipo == "TOP4":
        return [d for d in lista if d["code"] in _TOP4], "TOP 4 grandes"
    return [], ""


def _confirmar_bulk(deptos: list[dict], accion_str: str) -> bool:
    print(f"\n>>> {accion_str.upper()} sobre {len(deptos)} departamentos:")
    for d in deptos:
        print(f"      {d['code']}  {d['name']:<25} ({d['municipios']:>3} mun)")
    return questionary.confirm("Confirmas?", default=True).ask()


def _ejecutar_sobre_deptos(deptos: list[dict], accion_str: str, fn_ejecutar) -> None:
    """Itera fn_ejecutar(depto) sobre cada departamento con feedback de progreso.
    Captura KeyboardInterrupt para no romper el menu si el usuario aborta."""
    import time
    t_total = time.time()
    fallidos: list[str] = []
    for i, d in enumerate(deptos, 1):
        print(f"\n{'='*70}")
        print(f"[{i}/{len(deptos)}]  {d['name']}  (codigo {d['code']})")
        print(f"{'='*70}")
        t0 = time.time()
        try:
            rc = fn_ejecutar(d)
            if rc not in (None, 0):
                fallidos.append(f"{d['code']} {d['name']} (rc={rc})")
        except KeyboardInterrupt:
            print(f"\n[!] Interrumpido en {d['name']}. Procesados: {i-1}/{len(deptos)}.")
            break
        except Exception as e:
            print(f"\nERROR en {d['name']}: {e}")
            fallidos.append(f"{d['code']} {d['name']}: {e!s:.80}")
        print(f"\n[{i}/{len(deptos)}] {d['name']} - tomo {time.time()-t0:.0f}s")

    dt = time.time() - t_total
    print(f"\n{'#'*70}")
    print(f"TERMINADO {accion_str}: {len(deptos)} deptos en {dt:.0f}s ({dt/60:.1f} min)")
    print(f"{'#'*70}")
    if fallidos:
        print(f"\nFallos ({len(fallidos)}):")
        for f in fallidos:
            print(f"  - {f}")
    else:
        print(f"\nTodos los departamentos completados.")
    questionary.press_any_key_to_continue("\nPresiona una tecla para volver al menu...").ask()


def _bulk_descargar(deptos: list[dict]) -> None:
    prueba = _preguntar_modo(default_prueba="5")
    workers = _preguntar_workers("io")
    if not _confirmar_bulk(deptos, "Descargar PDFs"):
        return
    _ejecutar_sobre_deptos(
        deptos, "DESCARGA DE PDFs",
        lambda d: descargar.ejecutar(d["code"], workers=workers, prueba=prueba),
    )


def _bulk_inventario(deptos: list[dict]) -> None:
    con_red = questionary.confirm(
        "Consultar al servidor para capturar ETag/version-id? (recomendado)",
        default=True,
    ).ask()
    workers = _preguntar_workers("io") if con_red else 10
    if not _confirmar_bulk(deptos, "Generar Excel + integridad"):
        return
    _ejecutar_sobre_deptos(
        deptos, "INVENTARIO + INTEGRIDAD",
        lambda d: inventario.ejecutar(d["code"], workers=workers,
                                       sin_red=not con_red, respaldar_xlsx=True),
    )


def _bulk_imagenes(deptos: list[dict]) -> None:
    prueba = _preguntar_modo(default_prueba="3")
    fmt = _ask_or_back(questionary.select("Formato:", choices=[
        Choice("JPG (mas liviano, recomendado)", "jpg"),
        Choice("PNG (sin perdida, pesa 4x mas)", "png"),
        Choice("← Volver al menu anterior", _BACK),
    ]))
    if fmt == _BACK: raise _Volver
    dpi_str = _ask_or_back(questionary.select("DPI:", choices=[
        Choice("200 (default)", "200"),
        Choice("250 (recomendado para OCR)", "250"),
        Choice("300 (maxima calidad)", "300"),
        Choice("← Volver al menu anterior", _BACK),
    ]))
    if dpi_str == _BACK: raise _Volver
    dpi = int(dpi_str)
    stitch = _ask_or_back(questionary.confirm(
        "Stitch (todas las paginas en UNA imagen por PDF)?", default=True,
    ))
    horizontal = False
    if stitch:
        horizontal = _ask_or_back(questionary.confirm(
            "Stitch HORIZONTAL (paginas al lado)? Si=al lado, No=apiladas verticalmente",
            default=True,
        ))
    rotar_str = _ask_or_back(questionary.select("Rotar?", choices=[
        Choice("Sin rotar", "0"),
        Choice("90 grados a la izquierda (queda apaisado)", "90"),
        Choice("180 grados", "180"),
        Choice("270 grados", "270"),
        Choice("← Volver al menu anterior", _BACK),
    ]))
    if rotar_str == _BACK: raise _Volver
    rotar = int(rotar_str)
    workers = _preguntar_workers("cpu")
    if not _confirmar_bulk(deptos, "PDFs a imagenes"):
        return
    _ejecutar_sobre_deptos(
        deptos, "PDF -> IMAGEN",
        lambda d: imagenes.ejecutar(
            d["code"], dpi=dpi, fmt=fmt, workers=workers, prueba=prueba,
            stitch=stitch, rotar=rotar, horizontal=horizontal),
    )


def _bulk_cambios(deptos: list[dict]) -> None:
    solo = questionary.confirm("Mostrar solo los archivos que cambiaron?", default=False).ask()
    if not _confirmar_bulk(deptos, "Detectar cambios"):
        return
    _ejecutar_sobre_deptos(
        deptos, "DETECCION DE CAMBIOS",
        lambda d: cambios.ejecutar(d["code"], solo_cambios=solo),
    )


def _menu_acciones_bulk(deptos: list[dict], titulo: str) -> str:
    """Menu de acciones para multiples departamentos. Devuelve 'salir' / 'cambiar' / 'continuar'."""
    accion = questionary.select(
        f"\nAccion sobre {titulo} ({len(deptos)} departamentos):",
        choices=[
            Choice(title="  1) Descargar PDFs                (pesado: muchos GB y horas)",
                   value="descargar"),
            Choice(title="  2) Generar Excel + integridad    (rapido y liviano)",
                   value="inventario"),
            Choice(title="  3) Convertir PDFs a imagenes",
                   value="imagenes"),
            Choice(title="  4) Detectar cambios              (compara corridas anteriores)",
                   value="cambios"),
            Choice(title="  5) Cambiar seleccion (otro depto o salir de bulk)",
                   value="cambiar"),
            Choice(title="  0) Salir", value="salir"),
        ],
    ).ask()
    if accion in (None, "salir"):
        return "salir"
    if accion == "cambiar":
        return "cambiar"
    try:
        if accion == "descargar":   _bulk_descargar(deptos)
        elif accion == "inventario": _bulk_inventario(deptos)
        elif accion == "imagenes":   _bulk_imagenes(deptos)
        elif accion == "cambios":    _bulk_cambios(deptos)
    except _Volver:
        print("\n[<-] Volviendo al menu de acciones...")
    except KeyboardInterrupt:
        print("\n[!] Cancelado.")
    except Exception:
        traceback.print_exc()
        questionary.press_any_key_to_continue("Presiona una tecla...").ask()
    return "continuar"


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

        # Opciones bulk: van al mismo menu de acciones, pero ejecutan sobre N deptos
        if dept_code in ("__BULK_ALL__", "__BULK_TOP4__"):
            tipo = "ALL" if dept_code == "__BULK_ALL__" else "TOP4"
            deptos, titulo = _seleccion_bulk(tipo)
            while True:
                r = _menu_acciones_bulk(deptos, titulo)
                if r == "salir":
                    print("\nHasta luego.")
                    return 0
                if r == "cambiar":
                    break
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
