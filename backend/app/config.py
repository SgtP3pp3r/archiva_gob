"""Configuración central. Todo se puede sobreescribir con variables de entorno."""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
TEMPLATE_PATH = BASE_DIR / "templates" / "ficha_base.docx"

MAX_UPLOAD_MB = int(os.getenv("MAX_UPLOAD_MB", "20"))
MAX_UPLOAD_BYTES = MAX_UPLOAD_MB * 1024 * 1024

# Orígenes del frontend permitidos (separados por coma).
CORS_ORIGINS = [
    o.strip()
    for o in os.getenv(
        "CORS_ORIGINS",
        "http://localhost:3000,http://localhost:5173, https://archiva-gob.vercel.app",
    ).split(",")
    if o.strip()
]
