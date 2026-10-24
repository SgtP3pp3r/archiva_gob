"""Crea app/templates/ficha_base.docx a partir de una ficha de ejemplo ya elaborada.

Conserva: membrete (encabezados), pie de página, márgenes, estilos y fuentes.
Elimina: todo el contenido del cuerpo, incluidas las imágenes y datos personales,
para que la plantilla no arrastre información de la persona del ejemplo.

Uso:
    python scripts/build_template.py "ruta/a/ficha_ejemplo.docx"
"""
from __future__ import annotations

import sys
from pathlib import Path

from docx import Document
from docx.oxml.ns import qn

DESTINO = Path(__file__).resolve().parent.parent / "app" / "templates" / "ficha_base.docx"


def construir(origen: Path, destino: Path = DESTINO) -> None:
    doc = Document(str(origen))
    cuerpo = doc.element.body

    # Borra todo el contenido salvo la configuración de página (sectPr, siempre al final).
    for hijo in list(cuerpo):
        if hijo.tag != qn("w:sectPr"):
            cuerpo.remove(hijo)

    # Las imágenes del cuerpo siguen "relacionadas" aunque ya no se usen:
    # se sueltan para que no viajen dentro de la plantilla. Las del membrete se conservan.
    for rel_id, rel in list(doc.part.rels.items()):
        if rel.reltype.endswith("/image") and rel_id not in doc.part._element.xml:
            doc.part.drop_rel(rel_id)

    destino.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(destino))
    print(f"Plantilla creada: {destino}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    construir(Path(sys.argv[1]))
