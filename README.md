# 🗳️ votaciones-e14

**🌐 Sitio web:** <https://jsnavarroc.github.io/votaciones-e14/>
**🎥 Video demo:** <https://youtu.be/Ol7KC50mpjs>

Pipeline en Python para descargar, validar y procesar masivamente las **actas E-14** (escrutinio de jurados de votación) publicadas por la Registraduría Nacional de Colombia — Segunda Vuelta Presidencial 2026.

Pensado para **auditoría ciudadana**: descarga todas las actas de un departamento, captura las huellas criptográficas oficiales del servidor (S3 ETag + version-id + Last-Modified) en cada corrida y detecta automáticamente si la Registraduría modifica un archivo después de tu primera descarga.

---

## 🎥 Video demo

[![Demo del pipeline votaciones-e14](https://img.youtube.com/vi/Ol7KC50mpjs/maxresdefault.jpg)](https://youtu.be/Ol7KC50mpjs)

> Click en la imagen para ver cómo funciona el menú interactivo paso por paso en YouTube.

---

## ✨ Qué hace

| Paso | Acción |
|---|---|
| 1 | Descarga los JSONs del catálogo maestro (~36 MB) |
| 2 | Descarga en paralelo todos los PDFs E-14 de un departamento |
| 3 | Genera Excel con inventario + calcula MD5/SHA-256 locales + consulta integridad oficial al servidor |
| 4 | Convierte PDFs a imágenes (PNG/JPG, varios layouts) para mandar a OCR / IA de visión |
| 5 | Compara dos corridas del paso 3 y reporta archivos que el servidor cambió |

Todo accesible desde un **menú interactivo** con flechas:

```
==================================================
  Pipeline E-14 - Segunda Vuelta Presidencial 2026
==================================================

? Departamento:
  ❯ 11  CAUCA                    mun= 42  (2486 PDFs descargados)
    01  ANTIOQUIA                mun=125  (sin descargar)
    03  ATLANTICO                mun= 23  (sin descargar)
    ...

? Acción para CAUCA (11):
  ❯ 1) Descargar PDFs                (2486 en disco)
    2) Generar Excel + integridad    (manifest: 0 lineas)
    3) Convertir PDFs a imagenes
    4) Detectar cambios              (necesita >=2 obs en manifest)
    5) Cambiar departamento
    0) Salir
```

---

## 🚀 Instalación

### Opción A — Como script de Python

Requiere Python 3.10+.

```bash
git clone https://github.com/jsnavarroc/votaciones-e14.git
cd votaciones-e14
pip install -r requirements.txt
python -m votaciones.menu
```

### Opción B — Como ejecutable Windows (.exe)

```bash
pip install pyinstaller
python build_exe.py
# Genera dist/votaciones.exe (~30-50 MB)
```

Doble clic en `votaciones.exe` y listo — funciona sin Python instalado.

---

## 🗂️ Estructura del repo

```
votaciones-e14/
├── README.md            ← este archivo
├── GUIA.md              ← guía detallada de uso por paso
├── HALLAZGOS.md         ← bitácora técnica de descubrimientos (Akamai, S3, etc.)
├── LICENSE              ← MIT
├── requirements.txt
├── pyproject.toml
├── build_exe.py         ← empaquetador PyInstaller
│
├── votaciones/          ← paquete Python
│   ├── __init__.py
│   ├── config.py        ← URLs, headers, paths
│   ├── datos.py         ← lectura de los JSON de índice
│   ├── menu.py          ← launcher interactivo (entry point)
│   ├── indices.py       ← paso 1: descarga catálogo
│   ├── descargar.py     ← paso 2: PDFs paralelos
│   ├── inventario.py    ← paso 3: Excel + integridad
│   ├── imagenes.py      ← paso 4: PDF → imagen
│   └── cambios.py       ← paso 5: detecta cambios
│
└── (datos locales, gitignored)
    ├── indices/         ← JSONs descargados
    ├── pdfs/<DEPTO>/<MUN>/zNN_pNN_mNNN.pdf
    ├── imagenes/<DEPTO>/<MUN>/zNN_pNN_mNNN.jpg
    └── reportes/
        ├── inventario_<DEPTO>.xlsx
        ├── manifest_<DEPTO>.jsonl   ← histórico append-only
        └── cambios_<DEPTO>.xlsx
```

---

## 🔍 Verificación de integridad

La Registraduría almacena los E-14 en **Amazon S3 con versionado**. Cada descarga devuelve en headers HTTP:

- `ETag` — MD5 oficial del archivo (se compara con el MD5 local que calculamos).
- `Last-Modified` — fecha de subida al bucket.
- `x-amz-version-id` — ID de versión S3 (cambia si re-suben el archivo).

El **paso 3** captura los 3 valores cada vez que corres y los guarda en `reportes/manifest_<DEPTO>.jsonl` (append-only). El **paso 5** compara las observaciones entre corridas y reporta archivos que cambiaron en el servidor.

> **Caveat:** el CDN cachea ~7 días (`Cache-Control: max-age=600719`). Una modificación reciente puede tardar en propagarse al edge node.

Ver `HALLAZGOS.md` para el detalle técnico completo.

---

## 📊 Cuánto pesa

| Departamento | Mesas (Cauca) | PDFs (~60 KB c/u) | Imágenes JPG 250 DPI |
|---|---|---|---|
| Cauca (piloto) | 3.271 | ~150 MB | ~7-8 GB |
| Nacional (estimado) | ~110.000 | ~6 GB | ~280 GB |

---

## 🤝 Contexto

Este pipeline existe en el contexto de la polémica pública (junio 2026) sobre la integridad de los E-14 entre el gobierno y la Registraduría. Sin depender de promesas institucionales, `paso 3 + paso 5` te dan la **garantía técnica** de detectar si un archivo cambia en el servidor después de tu primera descarga, usando los propios mecanismos de S3/CloudFront.

---

## 📄 Licencia

MIT — ver `LICENSE`.

## 🙋 Soporte

Issues: <https://github.com/jsnavarroc/votaciones-e14/issues>
