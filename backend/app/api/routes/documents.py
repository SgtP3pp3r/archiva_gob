"""Endpoints de documentos.

Flujo recomendado para una interfaz con revisión humana:
    1. POST /documents/extract   (PDF)  → ficha en JSON + reporte de validación
    2. el usuario revisa/corrige la ficha en pantalla
    3. POST /documents/generate  (JSON) → .docx

Atajo sin revisión:
    POST /documents/ficha        (PDF)  → .docx directo
"""
from __future__ import annotations

import re
import unicodedata
from urllib.parse import quote

from fastapi import APIRouter, File, HTTPException, Query, UploadFile
from fastapi.responses import Response

from app.config import MAX_UPLOAD_BYTES, MAX_UPLOAD_MB
from app.schemas.ficha import Ficha, ReporteValidacion, RespuestaExtraccion
from app.services.data_extractor import extraer_ficha
from app.services.pdf_reader import PdfError, leer_pdf
from app.services.validator import normalizar, validar
from app.services.word_generator import generar_docx

router = APIRouter(prefix="/documents", tags=["documents"])

DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


# Las funciones son `def` (no `async def`): PyMuPDF y python-docx son síncronos y
# FastAPI ejecuta estos endpoints en un hilo aparte sin bloquear el servidor.


def _leer_subida(archivo: UploadFile) -> bytes:
    datos = archivo.file.read(MAX_UPLOAD_BYTES + 1)
    if len(datos) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, f"El archivo supera el máximo de {MAX_UPLOAD_MB} MB.")
    if not datos:
        raise HTTPException(400, "El archivo está vacío.")
    return datos


def _procesar_pdf(archivo: UploadFile) -> tuple[Ficha, ReporteValidacion]:
    datos = _leer_subida(archivo)
    try:
        contenido = leer_pdf(datos)
    except PdfError as exc:
        raise HTTPException(422, str(exc)) from exc
    ficha = normalizar(extraer_ficha(contenido))
    return ficha, validar(ficha)


def _respuesta_docx(ficha: Ficha, **cabeceras: str) -> Response:
    nombre = (ficha.datos_personales.nombre or "sin_nombre").strip(" .")  # sin el punto final del PDF
    ascii_ = unicodedata.normalize("NFKD", nombre).encode("ascii", "ignore").decode()
    base = re.sub(r"[^A-Za-z0-9]+", "_", ascii_).strip("_") or "ficha"
    return Response(
        content=generar_docx(ficha),
        media_type=DOCX_MIME,
        headers={
            "Content-Disposition": (
                f'attachment; filename="Ficha_{base}.docx"; '
                f"filename*=UTF-8''{quote('Ficha_' + nombre.replace(' ', '_'))}.docx"
            ),
            **cabeceras,
        },
    )


@router.post("/extract", response_model=RespuestaExtraccion, summary="PDF → ficha en JSON")
def extraer(archivo: UploadFile = File(..., description="PDF a procesar")) -> RespuestaExtraccion:
    ficha, validacion = _procesar_pdf(archivo)
    return RespuestaExtraccion(ficha=ficha, validacion=validacion)


@router.post(
    "/generate",
    response_class=Response,
    responses={200: {"content": {DOCX_MIME: {}}}},
    summary="Ficha en JSON → Word",
)
def generar(ficha: Ficha) -> Response:
    ficha = normalizar(ficha)
    reporte = validar(ficha)
    if not reporte.valido:
        raise HTTPException(422, {"mensaje": "La ficha tiene errores.", "incidencias": [i.model_dump() for i in reporte.errores]})
    return _respuesta_docx(ficha, **{"X-Advertencias": str(len(reporte.advertencias))})


@router.post(
    "/ficha",
    response_class=Response,
    responses={200: {"content": {DOCX_MIME: {}}}},
    summary="PDF → Word (todo el flujo en una llamada)",
)
def ficha_desde_pdf(
    archivo: UploadFile = File(..., description="PDF a procesar"),
    estricto: bool = Query(False, description="Si es true, rechaza el PDF cuando hay errores de validación"),
) -> Response:
    ficha, reporte = _procesar_pdf(archivo)
    if estricto and not reporte.valido:
        raise HTTPException(422, {"mensaje": "La ficha tiene errores.", "incidencias": [i.model_dump() for i in reporte.errores]})
    return _respuesta_docx(
        ficha,
        **{"X-Errores": str(len(reporte.errores)), "X-Advertencias": str(len(reporte.advertencias))},
    )
