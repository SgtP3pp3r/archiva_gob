"""PDF sintético con datos FICTICIOS que imita el formato de una ficha."""
from __future__ import annotations

import random

import pymupdf
import pytest

LINEAS = [
    "NUC 19-2019-12345",
    "FICHA DE IDENTIFICACIÓN PERSONAL",
    "",
    "DATOS PERSONALES",
    "Nombre: Juan Carlos Pérez Ramírez",
    "Fecha de Nacimiento: 11 de septiembre de 1993",
    "Lugar de nacimiento: Ciudad Ejemplo, Chihuahua.",
    "Domicilio:",
    "• Calle Hidalgo 100, colonia Centro, Ciudad Ejemplo,",
    "Chihuahua.",
    "• Avenida Reforma 250, colonia Norte, C.P. 31000.",
    "Teléfono:",
    "• 656 123 4567",
    "Ocupación: Comerciante.",
    "Estado Civil: Unión Libre",
    "Edad: 33 años.",
    'Alias: "El Ejemplo"',
    "",
    "DATOS DE FAMILIARES",
    "Madre: María López Soto.",
    "Padre: José Pérez Duarte.",
    "Hermanos:",
    "• Luis Pérez Ramírez (fecha de nacimiento",
    "21/05/1986).",
    "• Pedro Pérez Ramírez (fecha de nacimiento 07/04/1985).",
    "Hermanas: Sin dato",
    "Pareja: Ana Torres Gil (Posible pareja)",
    "Hijas: Sin dato",
    "Hijos:",
    "Mateo Pérez Torres (fecha de nacimiento 27/10/2015)",
    "",
    "CARPETAS DE INVESTIGACIÓN Y AVERIGUACIONES PREVIAS",
    "NUC: 19-2019-12345",
    "FECHA INICIO: 13/10/2019",
    "DELITO: Delito de ejemplo.",
    "CALIDAD: Imputado",
    "HECHOS: Narración de hechos ficticia que ocupa",
    "varias líneas dentro de la carpeta.",
    "UNIDAD: Unidad de Ejemplo.",
    "",
    "DATOS VEHICULARES",
    "Sin dato",
    "",
    "REGISTRO PÚBLICO DE LA PROPIEDAD",
    "• Sin dato",
    "",
    "FUENTES ABIERTAS",
    "• Posible página de Facebook de Juan Carlos Pérez Ramírez.",
    "Fecha y hora de consulta: 09/10/2026 13:27 hrs.",
    "Link: https://www.facebook.com/ejemplo.perez",
    "",
    "FOTOGRAFÍAS",
    "• Registro de Ejemplo",
    "Fecha: 27/04/2023",
    "Nombre: Juan Carlos Pérez Ramírez.",
    "Número de causa: 25/2019.",
    "",
    "OBSERVACIONES",
    "Solicitud por medio de oficio FGE-000/2026.",
]


def _ruido(ancho: int, alto: int, semilla: int) -> pymupdf.Pixmap:
    """Imagen con textura (como una foto): no comprime a casi nada, a diferencia de una plana."""
    muestras = random.Random(semilla).randbytes(ancho * alto * 3)
    return pymupdf.Pixmap(pymupdf.csRGB, ancho, alto, muestras, False)


def _plana(ancho: int, alto: int) -> pymupdf.Pixmap:
    pix = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, ancho, alto), False)
    pix.set_rect(pix.irect, (190, 190, 190))
    return pix


def crear_pdf(lineas=LINEAS, con_foto=True) -> bytes:
    """Dos páginas de texto + imágenes de contenido y de decoración (que deben descartarse)."""
    doc = pymupdf.open()
    pagina = doc.new_page()
    marca_xref = None
    if con_foto:
        R = pymupdf.Rect
        pagina.insert_image(R(0, 0, 595, 842), pixmap=_ruido(100, 100, 1))  # fondo de página
        pagina.insert_image(R(40, 10, 220, 46), pixmap=_ruido(300, 100, 2))  # membrete (zona superior)
        pagina.insert_image(R(480, 800, 540, 830), pixmap=_ruido(100, 100, 3))  # pie (zona inferior)
        pagina.insert_image(R(395, 95, 525, 255), pixmap=_plana(160, 200))  # sombra plana de la foto
        pagina.insert_image(R(400, 100, 520, 250), pixmap=_ruido(160, 200, 4))  # ← LA FOTO (vertical)
        pagina.insert_image(R(300, 400, 540, 500), pixmap=_ruido(400, 150, 5))  # captura apaisada
        marca_xref = pagina.insert_image(R(450, 600, 540, 690), pixmap=_ruido(100, 100, 6))  # marca de agua
    y = 50
    for linea in lineas:
        if y > 790:
            pagina, y = doc.new_page(), 50
        pagina.insert_text((50, y), linea, fontsize=10)
        y += 14
    if marca_xref and len(doc) > 1:  # misma imagen en todas las páginas → decoración
        doc[1].insert_image(pymupdf.Rect(450, 600, 540, 690), xref=marca_xref)
    return doc.tobytes()


@pytest.fixture
def pdf_bytes() -> bytes:
    return crear_pdf()
