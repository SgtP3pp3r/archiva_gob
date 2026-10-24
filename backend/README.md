# API de Fichas de Identificación

Lee un PDF → extrae los datos → genera la ficha en Word (sobre `templates/ficha_base.docx`).

## Estructura

```
app/
├── config.py                  # rutas, límite de subida, CORS (variables de entorno)
├── api/routes/documents.py    # endpoints
├── schemas/ficha.py           # modelo de datos (Pydantic)
├── services/
│   ├── pdf_reader.py          # PyMuPDF: texto + imágenes de contenido
│   ├── data_extractor.py      # identifica los campos (tablas CAMPOS / SECCIONES)
│   ├── validator.py           # normaliza y valida
│   └── word_generator.py      # escribe el DOCX sobre la plantilla
└── templates/ficha_base.docx  # membrete + pie + estilos, sin contenido
main.py                         # punto de entrada FastAPI, CORS y /health
scripts/build_template.py      # regenera la plantilla desde una ficha ya hecha
tests/                         # pytest (PDF sintético con datos ficticios)
```

## Ejecutar

```bash
pip install -r requirements.txt
uvicorn main:app --reload
# Documentación interactiva: http://localhost:8000/docs
pytest
```

## Endpoints

| Método | Ruta | Entrada | Salida |
|---|---|---|---|
| POST | `/api/documents/extract` | PDF (`archivo`) | JSON: `ficha` + `validacion` |
| POST | `/api/documents/generate` | JSON `ficha` (ya revisada) | `.docx` |
| POST | `/api/documents/ficha?estricto=false` | PDF (`archivo`) | `.docx` directo |

Flujo con revisión humana: `extract` → el usuario corrige en pantalla → `generate`.
El atajo `ficha` devuelve las cabeceras `X-Errores` y `X-Advertencias`; con `estricto=true`
responde 422 si hay errores de validación.

Además del formato de ficha con secciones y etiquetas, `/extract` reconoce reportes PiWeb con
registros `FUENTE` y campos separados por comas. Agrupa los registros por nombre y apellidos,
prioriza la fecha de nacimiento del Registro Civil y completa los datos compatibles con la ficha.
Como estos reportes pueden contener datos contradictorios o registros de personas homónimas,
revisa la información extraída antes de generar el Word.
Los domicilios PiWeb se ordenan como calle, número (interior primero), colonia, código postal,
municipio y estado. Los componentes ausentes no se inventan y solo se conserva el primer teléfono encontrado.
La respuesta de extracción ya incluye la ficha normalizada que se muestra en `/editar`: elimina domicilios duplicados
(ignorando diferencias de mayúsculas, acentos y puntuación) y vehículos con número de serie repetido. Se aplica la
misma normalización a la ficha editada antes de generar el Word. El teléfono de emergencia se muestra como
`número (Contacto De Emergencia)` cuando se detecta, y la nota editable de la fotografía se imprime junto a la imagen.
El estado de nacimiento es editable, usa Chihuahua como valor predeterminado y se incluye junto al municipio en el Word.

```bash
curl -F "archivo=@entrada.pdf" http://localhost:8000/api/documents/ficha -o ficha.docx
```

## Adaptar al formato de tus PDF

Todo lo específico del formato vive en **dos tablas** de `data_extractor.py`:
`SECCIONES` (encabezados) y `CAMPOS` (etiquetas). Los patrones van en minúsculas y sin acentos.
Para un campo nuevo: agrégalo a `CAMPOS`, al esquema (`schemas/ficha.py`), a `extraer_ficha`
y a `word_generator.py`.

Para cambiar el diseño del Word: edita `templates/ficha_base.docx` (membrete, pie, márgenes) o
regénerala con `python scripts/build_template.py ficha_ejemplo.docx`.

## Notas

- **Privacidad:** todo se procesa en memoria; no se escribe nada a disco ni se registra el contenido.
  Los datos son sensibles: ponlo detrás de autenticación y HTTPS antes de desplegarlo.
- **PDF escaneados:** se rechazan con un mensaje claro (necesitan OCR, p. ej. `pymupdf` + Tesseract).
- **Lectura del PDF:** por defecto se lee en el orden del flujo del documento
  (`ORDENAR_POR_POSICION = False` en `pdf_reader.py`), lo correcto para PDFs exportados de Word con tablas.
- **Foto:** se elige la primera imagen vertical de contenido; se descartan membrete, pie, fondos,
  imágenes repetidas en todas las páginas y sombras (imágenes planas).

## Limitaciones conocidas

- Las capturas de pantalla de *Fuentes abiertas* no se copian al Word (solo texto, fecha y link).
- *Datos vehiculares* solo se extrae si viene como `Marca: …`, `Placa: …`; una fila de tabla horizontal no.
