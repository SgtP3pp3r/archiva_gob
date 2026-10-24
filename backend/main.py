from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import documents
from app.config import CORS_ORIGINS

app = FastAPI(
    title="API de Fichas de Identificación",
    description="Lee un PDF, extrae los datos y genera la ficha en Word.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition", "X-Errores", "X-Advertencias"],
)

app.include_router(documents.router, prefix="/api")


@app.get("/health", tags=["health"])
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/hello")
def init():
    return {
        "message" : "La API funciona correctamente"
    }
