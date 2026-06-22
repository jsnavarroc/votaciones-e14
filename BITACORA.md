# Bitácora de Sesiones — votaciones-e14

Registro cronológico de las sesiones de trabajo sobre el proyecto. Útil para que
cualquier agente IA o desarrollador que retome el repo en una nueva conversación
sepa de dónde viene y a dónde va sin tener que reconstruir todo desde cero.

---

## Sesión #1 — 21 al 22 de junio de 2026

**Inicio:** 2026-06-21
**Cierre:** 2026-06-22
**Estado:** ✅ Proyecto publicado en GitHub, pipeline funcional, sitio web vivo.

### Lo que se logró

#### Fase 1 — Descubrimiento y prototipo inicial
- Mapeo del portal `e14segundavueltapresidente.registraduria.gov.co`.
- Identificación del stack: **Angular SPA + Akamai CDN + Amazon S3 con versionado**.
- Descubrimiento de los JSON estáticos del catálogo en `/assets/temis/divipol_json/`.
- Validación de la fórmula determinística de URL del PDF:
  `/assets/temis/pdf/{depto:2}/{mun:3}/{zona:3}/{puesto:2}/{mesa:3}/PRE/{hash}.pdf`
- Diagnóstico del bloqueo silencioso de Akamai Bot Manager: requiere headers
  `Sec-Fetch-*`, `sec-ch-ua*` y warmup en `/` para obtener cookie `ak_bmsc`.

#### Fase 2 — Pipeline funcional
- 5 módulos en `votaciones/`:
  - `indices.py` (paso 1) — descarga catálogo nacional
  - `descargar.py` (paso 2) — descarga paralela de PDFs por departamento
  - `inventario.py` (paso 3) — Excel + captura ETag/version-id/Last-Modified
  - `imagenes.py` (paso 4) — PDF → JPG/PNG con stitch + rotación
  - `cambios.py` (paso 5) — compara observaciones del manifest entre corridas
- Menú interactivo (`votaciones/menu.py`) con `questionary`.
- Empaquetable a `.exe` con PyInstaller (`build_exe.py`).

#### Fase 3 — Publicación en GitHub
- Repo público en <https://github.com/jsnavarroc/votaciones-e14>.
- Sitio web en GitHub Pages: <https://jsnavarroc.github.io/votaciones-e14/>.
- Video demo en YouTube: <https://youtu.be/Ol7KC50mpjs>.
- Licencia MIT, 9 topics agregados, homepage configurado.

#### Fase 4 — Refinamiento (sesión continuación 2026-06-22)
- **Estructura por departamento**: `reportes/<DEPTO>/`, `indices/<DEPTO>/`.
- **Respaldo automático** de xlsx en `reportes/<DEPTO>/backups/` antes de sobrescribir.
- **Manifest append-only** garantiza historial completo de observaciones.
- **Fix de falsos positivos en cambios.py**: pasamos de 130 falsos a 7 cambios reales en Cauca.
- **Fix del bug Content-Length** en `_head_servidor` (HEAD vs Range).
- **Detección de bloqueo silencioso de Akamai** (HTTP 200 sin ETag → reintenta con Range, marca `BLOCKED_NO_ETAG`).
- **Ctrl+C cancela inmediatamente** los `ThreadPoolExecutor` con `cancel_futures=True`.
- **Opciones bulk en el menú**: `TODOS` (34 territorios) y `TOP 4` (Bogotá, Antioquia, Valle, Cundinamarca).
- Las opciones bulk llevan al **mismo menú de acciones** (descargar / inventario / imágenes / cambios) y ejecutan sobre N departamentos.

### Hallazgos técnicos importantes

1. **Akamai Bot Manager filtra por headers, no por TLS fingerprint** — `requests` sí funciona si tiene los headers correctos.
2. **`expectedName` en el JSON NO es el SHA-256 del PDF** — es un identificador opaco. La huella oficial está en el header HTTP `ETag` (MD5 de S3).
3. **Buckets `status3` vs `status11` NO indican publicado/no-publicado** — ambos contienen actas descargables. Solo se sabe intentando el GET.
4. **Akamai serve HTML genérico con HTTP 200 cuando bloquea** — no devuelve 403. Por eso el script tiene que verificar magic `%PDF-` o presencia de ETag.
5. **CloudFront pasa `?versionId=` al origen S3** — se pueden consultar versiones específicas si conocemos el version-id, pero **NO se puede LISTAR todas las versiones** (el bucket está bien protegido).
6. **Versiones anteriores a la primera corrida del paso 3 son inalcanzables** desde afuera. Por eso la línea base lo antes posible es crítica.

### Estado actual de los datos (22 de junio 2026 madrugada)

- **Cauca (`11`)**: 3.271 mesas en catálogo, 2.486 PDFs descargados, **7 cambios reales detectados** entre las corridas del paso 3.
- **Antioquia (`01`)**: inventario iniciado.
- **Caldas (`09`)**: inventario corrido pero **Akamai bloqueó silenciosamente** (capturado como `BLOCKED_NO_ETAG`); falta re-correr tras el fix.
- Resto del país: sin línea base todavía. **Pendiente correr inventario nacional**.

### Próximos pasos sugeridos para la siguiente sesión

1. **Capturar línea base nacional** corriendo el menú bulk `TODOS` con opción 2 (inventario).
   - Tiempo estimado: 3-4 horas con 16 workers.
   - Espacio: ~50 MB de manifests JSONL.
2. **Validar los 7 cambios reales del Cauca**:
   - Re-descargar las 7 mesas modificadas a `validacion/`.
   - Comparar contenido visualmente (DELEGADOS vs CLAVEROS, valores numéricos).
   - URLs en `reportes/CAUCA/cambios_CAUCA.xlsx`.
3. **Re-correr inventario de Caldas** después del cooldown de Akamai (con el fix de bloqueo silencioso).
4. **Crear el primer Release `v0.1.0`** con `votaciones.exe`:
   - `pip install pyinstaller`
   - `python build_exe.py`
   - `gh release create v0.1.0 dist/votaciones.exe`
5. **Crear `CONTRIBUTING.md`** y `.github/PULL_REQUEST_TEMPLATE.md` para abrir contribuciones de la comunidad.
6. **Branch protection en `main`** (requerir PR, no force push). Comando:
   ```bash
   gh api -X PUT repos/jsnavarroc/votaciones-e14/branches/main/protection \
     -F enforce_admins=false \
     -F required_pull_request_reviews[required_approving_review_count]=0 \
     -F allow_force_pushes=false \
     -F allow_deletions=false
   ```
7. **(Opcional)** Detección de enmendaduras con visión IA:
   - El usuario tiene Ollama instalado con `qwen3-vl:4b` (modelo de visión).
   - Diseño: para cada imagen JPG, prompt estructurado pidiendo JSON con votos por candidato + flag de enmendadura por celda.
   - Empezar con piloto de 5-10 actas de Cauca, comparar manual contra Excel.

### Archivos clave del repo

```
votaciones-e14/
├── README.md              # Portada del repo
├── GUIA.md                # Guía de uso detallada paso a paso
├── HALLAZGOS.md           # Bitácora técnica de descubrimientos
├── BITACORA.md            # Este archivo (sesiones de trabajo)
├── index.html             # Landing page (GitHub Pages)
├── build_exe.py           # Empaquetador PyInstaller
├── validar_dos_mesas.py   # Utilidad para auditar mesas específicas
├── pyproject.toml
├── requirements.txt
└── votaciones/            # Paquete Python
    ├── config.py          # BASE, HEADERS, paths
    ├── datos.py           # Lectura del catálogo
    ├── menu.py            # Launcher interactivo (entry point)
    ├── indices.py         # paso 1
    ├── descargar.py       # paso 2
    ├── inventario.py      # paso 3
    ├── imagenes.py        # paso 4
    └── cambios.py         # paso 5
```

### Decisiones de diseño durables (no las cambies sin razón)

- **Nada de firmas de IA en commits** (regla global del usuario).
- **Manifest jsonl es append-only** — preserva historial. Nunca lo trunques.
- **xlsx son derivados** del manifest; se respaldan en `backups/` antes de sobrescribir.
- **`indices/` mantiene los JSON nacionales en raíz**; las subcarpetas por depto solo guardan extractos específicos.
- **El usuario es `@jsnavarroc`**. Su nombre completo (Johan Sebastian Navarro Cano) NO debe aparecer en archivos del repo — solo el handle.
- **El proyecto se posiciona como neutral**: ni acusa ni absuelve. Solo provee evidencia técnica reproducible.

### Notas sensibles

- **No subir** carpetas `pdfs/`, `imagenes/`, `indices/` (extractos), `reportes/`, `validacion/`. Están en `.gitignore`.
- **No subir** scripts experimentales `sondear_versiones.py`, `listar_versiones.py` (también en `.gitignore`).
- **Sí subir** `validar_dos_mesas.py` (utilidad real).

---

## Sesión #N — fecha

(Plantilla para siguiente sesión. Copiar la estructura de arriba y completar.)
