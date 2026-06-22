"""Utilidades para leer los JSON de indice (compartido por varios pasos)."""
from __future__ import annotations

import json

from votaciones.config import INDICES_DIR


def cargar_indices() -> tuple[dict, dict]:
    """Carga departmentsTree.json y allTransmissionCodes.json."""
    tree = json.loads((INDICES_DIR / "departmentsTree.json").read_text(encoding="utf-8"))
    codes = json.loads((INDICES_DIR / "allTransmissionCodes.json").read_text(encoding="utf-8"))
    return tree, codes


def listar_departamentos(tree: dict) -> list[dict]:
    """Devuelve lista de dicts {code, name, municipios} ordenada por code."""
    out = []
    for edge in tree["data"]["departmentsTree"]["edges"]:
        n = edge["node"]
        out.append({
            "code": n["idDepartmentCode"],
            "name": n["departmentName"],
            "municipios": len(n["municipalities"]),
        })
    return sorted(out, key=lambda d: d["code"])


def buscar_departamento(tree: dict, dept_code: str) -> tuple[str, dict[str, str]]:
    """Devuelve (nombre_depto, {municipalityCode: nombre})."""
    for edge in tree["data"]["departmentsTree"]["edges"]:
        n = edge["node"]
        if n["idDepartmentCode"] == dept_code:
            mun_map = {m["municipalityCode"]: m["municipalityName"] for m in n["municipalities"]}
            return n["departmentName"], mun_map
    raise ValueError(f"Departamento con codigo {dept_code!r} no encontrado")


def transmisiones_del_depto(codes_json: dict, dept_code: str,
                            corporation: str = "001") -> list[dict]:
    """Devuelve todos los nodos del depto+corporacion en cualquier bucket.

    El bucket (status3 / status11) NO determina si hay PDF. Algunos status11
    tambien tienen acta publicada. La unica forma confiable de saber si hay PDF
    es intentar el GET y revisar el magic %PDF de la respuesta.
    """
    todas: list[dict] = []
    for v in codes_json["data"].values():
        if isinstance(v, dict) and "nodes" in v:
            todas.extend(v["nodes"])
    return [
        n for n in todas
        if n.get("idDepartmentCode") == dept_code
        and n.get("idCorporationCode") == corporation
    ]
