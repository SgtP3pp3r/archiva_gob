"""Modelo de datos de la Ficha de Identificación Personal.

Refleja las secciones del formato Word:
encabezado · datos personales · datos de familiares · carpetas de investigación ·
datos vehiculares · registro público · fuentes abiertas · fotografías · observaciones.

Las fechas se guardan como `date` (se serializan ISO 8601 en el JSON) y el
generador de Word se encarga de mostrarlas en formato mexicano.
"""
from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field


class Familiar(BaseModel):
    nombre: str
    fecha_nacimiento: date | None = None


class DatosPersonales(BaseModel):
    nombre: str | None = None
    fecha_nacimiento: date | None = None
    lugar_nacimiento: str | None = None
    estado: str = "Chihuahua"
    domicilios: list[str] = Field(default_factory=list)
    telefonos: list[str] = Field(default_factory=list)
    telefono_emergencia: str | None = None
    ocupacion: str | None = None
    estado_civil: str | None = None
    edad: int | None = None
    alias: str | None = None


class DatosFamiliares(BaseModel):
    madre: str | None = None
    padre: str | None = None
    hermanos: list[Familiar] = Field(default_factory=list)
    hermanas: list[Familiar] = Field(default_factory=list)
    pareja: str | None = None
    hijas: list[Familiar] = Field(default_factory=list)
    hijos: list[Familiar] = Field(default_factory=list)


class CarpetaInvestigacion(BaseModel):
    nuc: str | None = None
    fecha_inicio: date | None = None
    delito: str | None = None
    calidad: str | None = None
    hechos: str | None = None
    unidad: str | None = None


class Vehiculo(BaseModel):
    alta: str | None = None
    marca: str | None = None
    linea: str | None = None
    modelo: str | None = None
    placa: str | None = None
    serie: str | None = None


class FuenteAbierta(BaseModel):
    descripcion: str
    fecha_consulta: str | None = None  # texto libre: "09/10/2026 13:27 hrs."
    link: str | None = None


class FuenteFotografia(BaseModel):
    """Origen de la fotografía (p. ej. un registro judicial con su fecha y causa)."""

    fuente: str | None = None
    fecha: date | None = None
    nombre: str | None = None
    numero_causa: str | None = None


class Ficha(BaseModel):
    fecha: date = Field(default_factory=date.today)  # fecha de elaboración de la ficha
    nuc: str | None = None  # NUC del encabezado
    datos_personales: DatosPersonales = Field(default_factory=DatosPersonales)
    datos_familiares: DatosFamiliares = Field(default_factory=DatosFamiliares)
    carpetas: list[CarpetaInvestigacion] = Field(default_factory=list)
    vehiculos: list[Vehiculo] = Field(default_factory=list)
    registro_publico: list[str] = Field(default_factory=list)
    fuentes_abiertas: list[FuenteAbierta] = Field(default_factory=list)
    fotografias: list[FuenteFotografia] = Field(default_factory=list)
    nota_fotografia: str | None = None
    observaciones: str | None = None
    # Foto principal en PNG codificado en base64: permite el ciclo extraer → editar → generar.
    foto_base64: str | None = None


# ── Validación y respuestas de la API ────────────────────────────────────────


class Incidencia(BaseModel):
    nivel: Literal["error", "advertencia"]
    campo: str
    mensaje: str


class ReporteValidacion(BaseModel):
    valido: bool  # True si no hay incidencias de nivel "error"
    incidencias: list[Incidencia] = Field(default_factory=list)

    @property
    def errores(self) -> list[Incidencia]:
        return [i for i in self.incidencias if i.nivel == "error"]

    @property
    def advertencias(self) -> list[Incidencia]:
        return [i for i in self.incidencias if i.nivel == "advertencia"]


class RespuestaExtraccion(BaseModel):
    ficha: Ficha
    validacion: ReporteValidacion
