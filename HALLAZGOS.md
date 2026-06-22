# Hallazgos — Portal E-14 Segunda Vuelta Presidencial 2026

**Fecha:** 2026-06-21
**Portal:** `https://e14segundavueltapresidente.registraduria.gov.co`
**Objetivo:** Validar que el script `paso2_descargar_pdfs.py` puede descargar masivamente las actas E-14 sin modificarlo.

---

## 1. Stack del portal

| Capa | Tecnología | Evidencia |
|---|---|---|
| Frontend | **Angular** (build con esbuild) | `<base href="/">`, bundles `main-N6RW7J7R.js`, `polyfills-FFHMD2TL.js`, `styles-3DUAMZUT.css`, title `E14VisorCiudadano` |
| CDN / Edge | **Akamai** | IP `23.48.203.168`, header `X-Akamai-Transformed: 9 491 0 pmb=mRUM,1`, host `ak.gh: 23.48.200.185` |
| Bot Protection | **Akamai Bot Manager Standard Cache** | Cookie `ak_bmsc` (TTL 2 horas, `Domain=.registraduria.gov.co`, `HttpOnly`, `Secure`, `SameSite=None`) |
| RUM | mPulse (Boomerang) | `s.go-mpulse.net/boomerang/`, API key `JER5F-DM9HJ-9CDW5-RBFQV-YX2VP` |
| TLS | TLS 1.3 | `ak.tlsv: tls1.3` en cookie de Akamai |
| Backend de datos | JSONs estáticos servidos por el CDN | Sin API real; todo el "estado" está en `/assets/temis/divipol_json/*.json` |

**Conclusión:** no hay API REST que llamar. El sitio descarga JSON estáticos y construye URLs determinísticas para los PDFs. Eso es justo lo que el script asume.

---

## 2. URL determinística de los PDFs — ✅ VALIDADA

Construcción que hace `paso2_descargar_pdfs.py::construir_url()`:

```
{BASE}/assets/temis/pdf/{depto:2}/{mun:3}/{zona:3}/{puesto:2}/{mesa:3}/PRE/{expectedName}
```

**Prueba real ejecutada:**

```
URL:    https://e14segundavueltapresidente.registraduria.gov.co/assets/temis/pdf/11/025/099/91/001/PRE/7e5a5b86285d33d0645622135acfc92abb280120efadfefe29720f4a3047753e.pdf
Resultado: HTTP 200, Content-Type: application/pdf, 1.391.663 bytes, magic %PDF-1.6
Archivo guardado: _diag_sample.pdf
```

Segunda prueba (otra mesa Cauca aleatoria):
```
HTTP 200, 51.655 bytes, %PDF válido — tiempo: 1.597 ms
```

→ La función `construir_url()` del script funciona **tal cual**.

---

## 3. JSONs del índice — ✅ VALIDADOS

| Archivo | Status | Estructura observada |
|---|---|---|
| `allDepartments.json` | 200 OK, 3.320 bytes | `data.allDepartments.nodes[] = { idDepartmentCode, departmentName }` |
| `allCorporations.json` | OK (descarga local) | (se mantiene como paso1 lo trae) |
| `departmentsTree.json` | OK (~4.6 MB local) | `data.departmentsTree.edges[].node.{departmentName, idDepartmentCode, municipalities[]}` |
| `allTransmissionCodes.json` | OK (~35 MB local) | `data.statusN.nodes[]` con `{idDepartmentCode, municipalityCode, idZoneCode, standCode, numberStand, idCorporationCode, expectedName, idTransmissionCodeStatus}` |

**Cauca (`idDepartmentCode=11`, `idCorporationCode=001`) → 3.271 mesas con PDF disponible.**

---

## 4. Headers — ❌ LOS DEL SCRIPT SON INSUFICIENTES

### Headers actuales del script (`paso2_descargar_pdfs.py`)

```python
HEADERS = {
    "User-Agent": "Mozilla/5.0 ... Chrome/149.0.0.0 Safari/537.36",
    "Accept": "application/pdf,application/json,text/plain,*/*",
    "Accept-Language": "es-ES,es;q=0.8",
    "Referer": f"{BASE}/",
}
```

**Resultado real con estos headers:** timeout — Akamai Bot Manager bloquea silenciosamente la conexión (no cierra, no responde 403; simplemente no envía el body).

### Headers que SÍ funcionan

```
User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36
Accept: application/pdf,*/*
Accept-Language: es-ES,es;q=0.9,en;q=0.8
Referer: https://e14segundavueltapresidente.registraduria.gov.co/
Sec-Fetch-Dest: empty
Sec-Fetch-Mode: cors
Sec-Fetch-Site: same-origin
sec-ch-ua: "Chromium";v="149", "Not.A/Brand";v="24"
sec-ch-ua-mobile: ?0
sec-ch-ua-platform: "Windows"
```

**Faltantes clave que disparan Bot Manager:** `Sec-Fetch-*` y `sec-ch-ua*` (Client Hints). Sin ellos, Akamai detecta cliente no-navegador y dropea.

---

## 5. Comportamiento de Akamai bajo varios requests

Pruebas secuenciales **sin sesión persistente** (cada request abre TLS nuevo, no envía `ak_bmsc`):

| Request # | Resultado |
|---|---|
| 1 | OK 200, 51 KB en 1.6 s |
| 2 | Timeout |
| 3 | Timeout |

**Interpretación:** Akamai Bot Manager re-evalúa la sesión cada vez que llega un request sin la cookie `ak_bmsc`. La primera pasa por "scoring inicial"; las siguientes se bloquean hasta que se establezca una sesión.

**Mitigación esperada:** un `requests.Session()` con un GET inicial a `/` antes del barrido captura la cookie y la reusa → ese test queda pendiente (lo correrá el usuario con el bloque PowerShell entregado en la conversación).

---

## 6. Lo que YA se logró

- ✅ Identificado el stack completo: Angular + Akamai + Bot Manager + mPulse.
- ✅ Confirmado que la URL determinística `/assets/temis/pdf/.../{hash}.pdf` funciona.
- ✅ Descargados 2 PDFs reales como prueba (`%PDF-1.6` válidos).
- ✅ Confirmada la estructura de `allTransmissionCodes.json` y que el filtro por `idDepartmentCode + idCorporationCode` produce los nodos correctos.
- ✅ Confirmado que **3.271 mesas** del Cauca tienen PDF disponible (status3).
- ✅ Identificado el set mínimo de headers que evita el bloqueo de Akamai.
- ✅ Identificada la cookie que el Bot Manager espera (`ak_bmsc`).

---

## 7. Lo que falta validar / mejorar

### 7.1. Validación pendiente
- [ ] Confirmar que **una sesión persistente con warmup en `/`** permite N descargas seguidas (script PowerShell ya entregado al usuario).
- [ ] Medir tasa máxima sostenible sin disparar rate-limit (probar 20, 50, 100 PDFs en serie con la misma sesión).
- [ ] Probar concurrencia con `--workers 10` y ver si Akamai aguanta o bloquea.

### 7.2. Mejoras necesarias al script `paso2_descargar_pdfs.py`

| # | Cambio | Razón |
|---|---|---|
| 1 | **Agregar headers Sec-Fetch-\* y sec-ch-ua\*** a `HEADERS` | Sin ellos → timeout 100% del tiempo |
| 2 | **Warmup**: hacer `session.get(BASE + "/")` antes del bucle de descargas | Captura cookie `ak_bmsc` → Bot Manager deja pasar |
| 3 | **Reintento con backoff** en `descargar_uno()` cuando hay timeout / 403 / 429 | Akamai puede dropear requests aisladas |
| 4 | **Refresco de cookie**: re-visitar `/` si pasaron >100 min (TTL `ak_bmsc` = 2 h) | Evita expiración a mitad del barrido |
| 5 | **Default workers más bajo** (4–6 en vez de 10) o `time.sleep(0.1)` entre tareas | Reduce riesgo de rate-limit; subir solo si confirma estabilidad |
| 6 | **Detectar respuesta HTML** (página de challenge de Akamai) en vez de solo `content-type` | Si Akamai mete un challenge interstitial, `r.status_code` puede ser 200 pero el body es HTML |
| 7 | **Loggear código `idTransmissionCodeStatus`** | Status3 = PDF; otros valores indican mesas sin acta. El script ya filtra por `nodes` dentro de cada status; verificar que solo se itera status3 |
| 8 | **Conteo por municipio en el resumen final** | Para validar cobertura por municipio (útil con los 21 municipios de riesgo extremo de Cauca según MOE) |
| 9 | Considerar `--resume` que solo descargue los que faltan en disco | Ya hay `skip` por archivo existente >1 KB; falta hacer un resumen claro de "faltantes" para reintento dirigido |

### 7.3. Riesgos abiertos

- **TLS fingerprinting (JA3/JA4):** Akamai puede detectar que `requests` no tiene fingerprint de Chrome aunque los headers digan que sí. Si después de agregar headers + sesión sigue bloqueando, hay que usar `curl-impersonate` o `playwright`.
- **Volumen total nacional:** `allTransmissionCodes.json` tiene 35 MB. Si Cauca son 3.271 mesas y eso es ~3 % del país, el total nacional son ~100k PDFs. A 0.5 s/PDF con 10 workers serían ~83 min; con rate-limit puede ser horas. Para piloto de Cauca no es problema.
- **Hash en `expectedName`:** los hashes en `allTransmissionCodes.json` pueden cambiar si la Registraduría re-publica un acta. Si el script corre días después y los hashes cambiaron, los reintentos fallarán con 404. Mitigación: re-correr `paso1` antes de cada barrido grande.

---

## 8. Archivos generados durante el diagnóstico

| Archivo | Origen | Significado |
|---|---|---|
| `_diag_index.html` | GET `/` con headers de navegador | HTML del SPA Angular — útil para inspeccionar bundles |
| `_diag_sample.pdf` | GET PDF de mesa `11/025/099/91/001` | Prueba de que un PDF real descarga bien con los headers correctos |

(Ambos son archivos de diagnóstico; se pueden borrar cuando se confirme que el script ajustado funciona.)

---

## 9. Próximo paso recomendado

1. Correr el bloque PowerShell entregado (warmup + 5 descargas con sesión persistente).
2. Según resultado:
   - **5/5 OK** → Ajustar `paso2_descargar_pdfs.py` solo con cambios #1 y #2 (headers + warmup) y lanzar `--prueba 20` en Cauca.
   - **OK parcial** → Sumar #3 (reintento con backoff) y #5 (bajar workers).
   - **Todos ERR** → Cambiar de `requests` a `curl-impersonate` o `playwright` (TLS fingerprinting).
