"""Extrae el contenido crudo de un PDF (texto e imágenes) con PyMuPDF.

Este módulo NO interpreta el contenido: solo lo lee. Identificar los campos
es responsabilidad de `data_extractor.py`.
Todo se procesa en memoria; nada se escribe en disco.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import pymupdf

MIN_LADO_IMAGEN_PX = 80  # descarta íconos, viñetas y líneas decorativas
MIN_CHARS_POR_PAGINA = 20  # por debajo de esto se asume PDF escaneado

# False → texto en el orden del flujo del documento. Es lo correcto para PDFs exportados desde
# Word con tablas: cada celda sale completa (etiqueta, luego valor). True → ordena por posición
# en la página, que mezcla las celdas de una misma fila (útil solo para PDFs sin tablas
# o cuyo orden interno está desordenado).
ORDENAR_POR_POSICION = False

# Filtros para quedarse solo con imágenes de CONTENIDO (fotos, capturas) y descartar el
# membrete, el pie y los fondos decorativos que Word repite en todas las páginas.
ZONA_ENCABEZADO = 0.12  # imágenes cuyo centro está en el 12 % superior de la página
ZONA_PIE = 0.88  # …o en el 12 % inferior
MAX_FRACCION_PAGINA = 0.5  # una imagen que cubre más de la mitad de la página es un fondo
MAX_LADO_PX = 1000  # las fotos grandes se reducen para no inflar el JSON ni el Word
# Sombras, degradados y fondos de color son imágenes casi planas: su PNG pesa apenas
# 0.05–3 % de los bytes crudos RGB (ancho×alto×3), mientras que el de una fotografía real
# ronda 10–80 % (medido en PDFs exportados de Word: foto 42 %, sombra 0.05 %, fondo 0.15 %).
MIN_RAZON_PNG = 0.08


class PdfError(ValueError):
    """El PDF no se puede leer o no sirve para extraer texto."""


@dataclass
class ImagenPdf:
    png: bytes
    ancho: int  # píxeles
    alto: int
    pagina: int  # 1 = primera página
    area_mostrada: float  # tamaño real en la página (pt²), no el de píxeles


@dataclass
class ContenidoPdf:
    texto: str
    paginas: int
    imagenes: list[ImagenPdf] = field(default_factory=list)


def leer_pdf(datos: bytes) -> ContenidoPdf:
    """Devuelve el texto (en orden de lectura) y las imágenes embebidas del PDF."""
    if not datos.startswith(b"%PDF"):
        raise PdfError("El archivo no es un PDF válido.")

    try:
        doc = pymupdf.open(stream=datos, filetype="pdf")
    except Exception as exc:  # pymupdf lanza varios tipos según el daño del archivo
        raise PdfError("No se pudo abrir el PDF; puede estar dañado.") from exc

    with doc:
        if doc.needs_pass:
            raise PdfError("El PDF está protegido con contraseña.")

        textos: list[str] = []
        colocaciones: list[tuple[int, int, pymupdf.Rect, pymupdf.Rect]] = []  # (pág, xref, bbox, página)

        for n, pagina in enumerate(doc, 1):
            textos.append(pagina.get_text("text", sort=ORDENAR_POR_POSICION))
            for info in pagina.get_image_info(xrefs=True):
                if info["xref"]:  # 0 = imagen "inline" sin objeto propio; se ignora
                    colocaciones.append((n, info["xref"], pymupdf.Rect(info["bbox"]), pagina.rect))

        imagenes = _imagenes_de_contenido(doc, colocaciones)

    texto = "\n".join(textos)
    if len(texto.strip()) < MIN_CHARS_POR_PAGINA * len(textos):
        raise PdfError(
            "El PDF no contiene texto seleccionable (parece un documento escaneado). "
            "Se requiere OCR antes de procesarlo."
        )
    return ContenidoPdf(texto=texto, paginas=len(textos), imagenes=imagenes)


def _imagenes_de_contenido(doc: pymupdf.Document, colocaciones) -> list[ImagenPdf]:
    """Imágenes de contenido en orden de lectura (página, luego de arriba hacia abajo)."""
    paginas_por_xref: dict[int, set[int]] = {}
    for n, xref, _, _ in colocaciones:
        paginas_por_xref.setdefault(xref, set()).add(n)

    imagenes: list[ImagenPdf] = []
    convertidas: dict[int, ImagenPdf | None] = {}
    for n, xref, bbox, pag in sorted(colocaciones, key=lambda c: (c[0], c[2].y0, c[2].x0)):
        centro_y = ((bbox.y0 + bbox.y1) / 2 - pag.y0) / pag.height
        if bbox.get_area() > MAX_FRACCION_PAGINA * pag.get_area():
            continue  # fondo de página
        if centro_y < ZONA_ENCABEZADO or centro_y > ZONA_PIE:
            continue  # membrete / pie
        if len(doc) > 1 and len(paginas_por_xref[xref]) == len(doc):
            continue  # aparece en TODAS las páginas: es decoración, no contenido
        if xref not in convertidas:  # se convierte una sola vez por xref
            convertidas[xref] = _imagen_a_png(doc, xref)
        base = convertidas[xref]
        if base:
            imagenes.append(
                ImagenPdf(base.png, base.ancho, base.alto, pagina=n, area_mostrada=bbox.get_area())
            )
    return imagenes


def _imagen_a_png(doc: pymupdf.Document, xref: int) -> ImagenPdf | None:
    """Convierte cualquier imagen embebida (JPEG, JPX, CMYK…) a PNG compatible con Word."""
    try:
        pix = pymupdf.Pixmap(doc, xref)
        if pix.width < MIN_LADO_IMAGEN_PX or pix.height < MIN_LADO_IMAGEN_PX:
            return None
        if pix.colorspace is None or pix.colorspace.n > 3:  # CMYK u otros → RGB
            pix = pymupdf.Pixmap(pymupdf.csRGB, pix)
        if pix.alpha:
            pix = pymupdf.Pixmap(pix, 0)  # quita el canal alfa
        while max(pix.width, pix.height) > MAX_LADO_PX:
            pix.shrink(1)  # reduce a la mitad
        png = pix.tobytes("png")
        if len(png) / (pix.width * pix.height * 3) < MIN_RAZON_PNG:
            return None  # imagen plana: sombra o fondo, no una fotografía
        return ImagenPdf(png=png, ancho=pix.width, alto=pix.height, pagina=0, area_mostrada=0)
    except Exception:
        return None  # una imagen rara no debe tumbar todo el procesamiento
