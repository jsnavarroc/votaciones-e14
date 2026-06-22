"""
Verifica si tu IP esta bloqueada por Akamai en el portal de la Registraduria.
Hace UN solo GET a / y reporta:
  - HTTP status
  - Si recibio cookie ak_bmsc
  - Si el body es PDF, HTML de error, o pagina real del SPA Angular

Uso:
    python diagnosticar_akamai.py
"""
from __future__ import annotations
import requests
from votaciones.config import BASE, HEADERS_WARMUP


def main() -> int:
    print(f"GET {BASE}/")
    s = requests.Session()
    try:
        r = s.get(f"{BASE}/", headers=HEADERS_WARMUP, timeout=60)
    except requests.RequestException as e:
        print(f"FAIL: {e}")
        return 1

    print(f"\nHTTP status:      {r.status_code}")
    print(f"Bytes recibidos:  {len(r.content)}")
    print(f"Content-Type:     {r.headers.get('Content-Type', '?')}")
    print(f"Cookies recibidas: {[c.name for c in s.cookies]}")

    body = r.text
    if "Access Denied" in body:
        veredicto = "BLOQUEADO por Akamai (HTML de 'Access Denied')"
        diag = "tu IP esta en la lista de bot detection"
    elif "E14VisorCiudadano" in body or "<app-root" in body or "main-" in body:
        veredicto = "OK - SPA Angular real"
        diag = "Akamai te esta dejando pasar; el portal responde bien"
    elif r.status_code == 200 and len(r.content) < 2000:
        veredicto = "SOSPECHOSO - HTML pequeno sin marcadores conocidos"
        diag = "probablemente bloqueado, abre el body manualmente para verificar"
    else:
        veredicto = "DESCONOCIDO"
        diag = "respuesta inusual"

    print(f"\nVEREDICTO:        {veredicto}")
    print(f"Diagnostico:      {diag}")

    if "Access Denied" in body:
        print(f"\nReference de Akamai: " + (body.split("Reference")[1][:60] if "Reference" in body else "?"))
        print(f"\n>>> QUE HACER:")
        print(f"  1. ESPERAR 15-60 minutos. El bot-score de Akamai baja con el tiempo.")
        print(f"     Vuelve a ejecutar este script para ver si ya pasaste.")
        print(f"  2. Cambiar de red: usa datos moviles desde el celular como hotspot.")
        print(f"     IP nueva = score limpio.")
        print(f"  3. Usar VPN con ubicacion Colombia/Mexico/USA.")
        print(f"  4. Como ultimo recurso, instalar curl-cffi para impersonar Chrome")
        print(f"     a nivel TLS (mas dificil de detectar):")
        print(f"         pip install curl-cffi")
        print(f"     (requiere modificar el codigo para usarlo en lugar de requests)")
    else:
        print(f"\nPuedes continuar con el inventario.")
        print(f"  python -m votaciones.inventario 01 --prueba 5 --workers 4")
    print(f"\n--- Primeros 500 bytes del body ---")
    print(body[:500])
    return 0 if "Access Denied" not in body else 2


if __name__ == "__main__":
    raise SystemExit(main())
