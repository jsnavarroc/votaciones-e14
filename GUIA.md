# Guía de uso — Pipeline E-14 Segunda Vuelta Presidencial 2026

Pipeline en Python para descargar masivamente las **actas E-14** (escrutinio de jurados) de la Registraduría Nacional, validar integridad contra el servidor y prepararlas para análisis (detección de enmendaduras con visión IA, etc.).

**Portal:** `https://e14segundavueltapresidente.registraduria.gov.co`
**Stack:** Angular SPA + Akamai CDN + Amazon S3 (versionado).

---

## Setup (una sola vez)

```bash
pip install -r requirements.txt
```

Dependencias:
- `requests` — descargas HTTP
- `openpyxl` — generación de Excel
- `pymupdf` — render PDF → imagen
- `Pillow` — manipulación de imágenes

---

## Flujo recomendado

```bash
# 1. Bajar índices JSON (catálogo de mesas)
python paso1_descargar_indices.py

# 2. Bajar todos los PDFs de un departamento (ej. Cauca = 11)
python paso2_descargar_pdfs.py 11

# 3. Generar Excel + manifest con hashes del servidor
python paso3_generar_excel.py 11

# 4. (Opcional) Convertir PDFs a imágenes para mandar a IA
python paso4_pdf_a_imagenes.py 11 --stitch --horizontal --jpg --rotar 90 --dpi 250

# 5. Re-correr paso3 días después y luego detectar cambios
python paso3_generar_excel.py 11        # segunda observación
python paso5_detectar_cambios.py 11     # compara las observaciones
```

---

## paso1 — Descargar índices

```bash
python paso1_descargar_indices.py
```

**Qué hace:** baja 4 JSONs estáticos del portal y los guarda en `indices/`:
- `allDepartments.json` — lista de departamentos
- `allCorporations.json` — corporaciones (PRE, SEN, CAM, etc.)
- `departmentsTree.json` — árbol depto → municipios
- `allTransmissionCodes.json` — **catálogo maestro de mesas con sus hashes** (~35 MB)

**Cuándo correrlo:** la primera vez, y **antes de cada barrido grande** durante la jornada electoral (la Registraduría publica más actas progresivamente).

---

## paso2 — Descargar PDFs

```bash
# Lista departamentos disponibles
python paso2_descargar_pdfs.py

# Descargar un departamento completo
python paso2_descargar_pdfs.py 11             # Cauca

# Modo prueba: solo N mesas
python paso2_descargar_pdfs.py 11 --prueba 20

# Más velocidad
python paso2_descargar_pdfs.py 11 --workers 16
```

**Qué hace:**
1. Lee el catálogo y filtra mesas del departamento + corporación PRE.
2. Hace warmup en `/` para obtener cookie `ak_bmsc` (necesaria para pasar el Bot Manager de Akamai).
3. Descarga en paralelo cada PDF a `pdfs/<DEPTO>/<MUN>/zNN_pNN_mNNN.pdf`.
4. Salta archivos ya descargados (idempotente).
5. Valida magic `%PDF-` y `Content-Type` antes de guardar.

**Flags:**
| Flag | Default | Para qué |
|---|---|---|
| `--prueba N` | (todas) | Limitar a N mesas |
| `--workers K` | `10` | Hilos paralelos |

**Cuánto tarda:** Cauca (3.271 mesas) ≈ 21 min a 2-3 PDFs/s.

---

## paso3 — Validar y generar Excel

```bash
python paso3_generar_excel.py 11
python paso3_generar_excel.py 11 --workers 16
python paso3_generar_excel.py 11 --sin-red    # solo validación local, sin consultar al servidor
python paso3_generar_excel.py 11 -o otro_nombre.xlsx
```

**Qué hace:**
1. Para cada mesa del departamento:
   - Verifica que el PDF exista en disco.
   - Valida magic `%PDF-` y tamaño > 1 KB.
   - Calcula **MD5 + SHA-256** del archivo local.
   - Hace `HEAD` al servidor y captura **ETag, Last-Modified, x-amz-version-id, Content-Length**.
2. Compara MD5 local vs ETag del servidor (`etag_coincide` → True/False).
3. Genera `inventario_<DEPTO>.xlsx` con 2 hojas:
   - **Hoja del departamento** — 25 columnas con todo el detalle por mesa, filas rojas para `estado != OK`.
   - **Hoja `resumen`** — conteos, total MB, # de archivos con ETag capturado.
4. **Append-only** al `manifest_<DEPTO>.jsonl` con timestamp UTC de cada corrida.

**Columnas clave del Excel:**
| Columna | Qué dice |
|---|---|
| `estado` | `OK / FALTA / VACIO / NO_PDF / ERROR` |
| `md5_archivo` | MD5 del PDF local |
| `sha256_archivo` | SHA-256 del PDF local (huella propia) |
| `servidor_etag` | MD5 oficial del servidor (S3) |
| `etag_coincide` | True/False — si False, tu archivo local difiere de lo que sirve hoy el servidor |
| `servidor_last_modified` | Cuándo subió el archivo |
| `servidor_version_id` | ID de versión S3 — cambia si re-subieron |
| `verificado_utc` | Cuándo capturaste estos datos |

**Cuándo correrlo:**
- Una vez después de cada `paso2`.
- **Periódicamente** para detectar si la Registraduría modificó archivos.

---

## paso4 — PDF → Imagen

```bash
# Default: PNG 200 DPI, una imagen por página
python paso4_pdf_a_imagenes.py 11

# Recomendado para mandar a IA: JPG 250 DPI, todas las páginas en una sola imagen horizontal, rotadas a la izquierda
python paso4_pdf_a_imagenes.py 11 --stitch --horizontal --jpg --rotar 90 --dpi 250 --workers 16

# Solo primera página
python paso4_pdf_a_imagenes.py 11 --solo-pagina 1

# Modo prueba
python paso4_pdf_a_imagenes.py 11 --prueba 5 --stitch --jpg
```

**Qué hace:** lee cada PDF en `pdfs/<DEPTO>/...` y genera imágenes en `imagenes/<DEPTO>/...` con la **misma estructura de carpetas**.

**Flags:**
| Flag | Default | Para qué |
|---|---|---|
| `--dpi N` | `200` | Resolución de render. **250 es el sweet spot** para OCR de manuscrito |
| `--jpg` / `--png` | `png` | Formato (JPG pesa ~4× menos) |
| `--workers K` | `4` | Hilos paralelos |
| `--stitch` | off | **Todas las páginas en una sola imagen** por PDF |
| `--horizontal` | off | Con `--stitch`: páginas al lado (en vez de apiladas) |
| `--rotar N` | `0` | Gira `90`/`180`/`270` grados antihorario |
| `--solo-pagina N` | (todas) | Genera solo esa página |
| `--prueba N` | (todos) | Procesa solo los primeros N PDFs |

**Notas:**
- Cauca con `--dpi 250 --stitch --horizontal --jpg --rotar 90` ≈ 7-8 GB total.
- Para `--dpi 200` sin `--horizontal` ≈ 5 GB.
- Sin `--jpg` (PNG) los archivos pesan 4× más.

---

## paso5 — Detectar cambios

```bash
# Reporta TODO (cambios + sin cambios + solo 1 observación)
python paso5_detectar_cambios.py 11

# Solo lo que cambió
python paso5_detectar_cambios.py 11 --solo-cambios
```

**Qué hace:**
1. Lee `manifest_<DEPTO>.jsonl` (escrito por paso3).
2. Agrupa observaciones por URL y las ordena por timestamp.
3. Compara primera vs última observación por cada URL.
4. Reporta cambios en: `ETag`, `Last-Modified`, `version_id`, `Content-Length`.
5. Genera `cambios_<DEPTO>.xlsx` con filas rojas para archivos modificados.

**Exit codes (útiles para automatización):**
- `0` → sin cambios
- `2` → **se detectaron cambios** (útil para conectar a cron/alerta)

**Requisito:** necesita **al menos 2 corridas del paso3** separadas en el tiempo. Con una sola corrida, todas las URLs aparecen como "Solo 1 observación".

---

## Archivos que genera el pipeline

```
Votaciones/
├── indices/                          ← paso1
│   ├── allDepartments.json
│   ├── allCorporations.json
│   ├── departmentsTree.json
│   └── allTransmissionCodes.json
│
├── pdfs/                             ← paso2
│   └── CAUCA/
│       ├── 001_POPAYAN/
│       │   ├── z099_p13_m004.pdf
│       │   └── ...
│       └── 006_BALBOA/...
│
├── imagenes/                         ← paso4
│   └── CAUCA/
│       └── 001_POPAYAN/
│           ├── z099_p13_m004.jpg     (stitch horizontal rotado)
│           └── ...
│
├── inventario_CAUCA.xlsx             ← paso3 (sobreescribe)
├── manifest_CAUCA.jsonl              ← paso3 (append-only)
└── cambios_CAUCA.xlsx                ← paso5 (sobreescribe)
```

---

## Cómo verificar integridad (paso3 + paso5)

La Registraduría almacena los E-14 en **Amazon S3 con versionado**. En cada descarga, el CDN devuelve en los headers HTTP:

- `ETag` → MD5 oficial del archivo en S3.
- `Last-Modified` → fecha de subida.
- `x-amz-version-id` → ID de versión S3 (cambia si re-suben).

**El paso3 captura esos 3 valores cada vez que corres.** El paso5 los compara entre corridas y detecta cualquier modificación posterior a tu primera descarga.

**Limitaciones:**
- El CDN cachea ~7 días (`Cache-Control: max-age=600719`). Una modificación reciente puede tardar en propagarse al edge.
- `ETag` (MD5) y `sha256_archivo` no son comparables directamente — son algoritmos distintos. Por eso el paso3 también calcula MD5 local (`md5_archivo`) para poder hacer la comparación 1:1 en `etag_coincide`.

---

## Códigos de departamento útiles

(Sistema interno Registraduría, **no** DANE.)

| Code | Departamento | Code | Departamento |
|---|---|---|---|
| 01 | ANTIOQUIA | 11 | CAUCA |
| 03 | ATLANTICO | 13 | CESAR |
| 05 | BOGOTA D.C. | 17 | CORDOBA |
| 07 | BOLIVAR | 25 | CUNDINAMARCA |

Para ver la lista completa: `python paso2_descargar_pdfs.py` (sin argumentos).

---

## Solución de problemas

| Síntoma | Causa | Solución |
|---|---|---|
| Timeout silencioso en descargas | Akamai Bot Manager bloqueó | Verifica headers `Sec-Fetch-*` y `sec-ch-ua*` en el script |
| `PermissionError` al guardar Excel | Tienes el Excel abierto | Ciérralo o usa `-o otro_nombre.xlsx` |
| Muchos `FALTA` en el inventario | El servidor no tiene esas actas publicadas todavía | Re-corre `paso1` y vuelve a `paso2` |
| Imagen final muy grande | DPI alto + stitch | Baja a `--dpi 200` o sin `--horizontal` |
| `git bash` da timeout en HTTP | `curl` de MSYS2 tiene TLS fingerprint distinto a Chrome y Akamai bloquea | Usa los scripts Python en su lugar |

---

## Contexto

Este pipeline existe en el contexto de la polémica pública (junio 2026) sobre la integridad de los E-14 entre el gobierno y la Registraduría. El **`paso3 + paso5`** te da la garantía técnica de detectar si **un archivo cambia** en el servidor después de tu primera descarga, usando los propios mecanismos de S3/CloudFront (`ETag`, `version-id`, `Last-Modified`) sin depender de promesas institucionales.

Ver `HALLAZGOS.md` para los detalles técnicos completos del descubrimiento.
