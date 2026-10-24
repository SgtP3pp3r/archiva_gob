"""Normaliza y valida la información extraída antes de generar el Word.

- `normalizar`: completa datos derivables (edad) y limpia formatos.
- `validar`: devuelve un reporte con errores (bloquean en modo estricto)
  y advertencias (informativas, para revisión humana).
"""
from __future__ import annotations

import re
import unicodedata
from datetime import date

from app.schemas.ficha import Ficha, Incidencia, ReporteValidacion, Vehiculo

RE_NUC = re.compile(r"^\d{2}-\d{4}-\d{3,6}$")  # p. ej. 19-2019-26310
RE_DOMICILIO_INVALIDO = re.compile(
    r"\bsin\s+nombre\b|#\s*s\s*/\s*n\b|\bsin\s+n[uú]mero\b",
    re.IGNORECASE,
)
def _normalizar_componente(texto: str) -> str:
    plegado = unicodedata.normalize("NFKD", texto)
    sin_acentos = "".join(caracter for caracter in plegado if not unicodedata.combining(caracter))
    return re.sub(r"[^A-Z0-9]", "", sin_acentos.upper())


def _componentes_domicilio(domicilio: str) -> dict[str, str]:
    componentes = {clave: "" for clave in ("calle", "numero", "colonia", "cp", "municipio", "estado")}
    libres: list[str] = []
    for parte in domicilio.split(","):
        valor = parte.strip()
        if valor.lower().startswith("calle "):
            componentes["calle"] = _normalizar_componente(valor[6:])
        elif valor.startswith("#"):
            componentes["numero"] = _normalizar_componente(valor[1:])
        elif valor.lower().startswith("colonia "):
            componentes["colonia"] = _normalizar_componente(valor[8:])
        elif re.match(r"(?i)^c\.?\s*p\.?\s*", valor):
            componentes["cp"] = _normalizar_componente(re.sub(r"(?i)^c\.?\s*p\.?\s*", "", valor))
        elif valor:
            libres.append(_normalizar_componente(valor))
    if len(libres) > 1:
        componentes["municipio"], componentes["estado"] = libres[-2:]
    elif libres:
        componentes["municipio"] = libres[0]
    return componentes


def domicilios_sin_duplicados(domicilios: list[str]) -> list[str]:
    unicos: list[str] = []
    vistos: list[dict[str, str]] = []
    anclas = ("calle", "colonia")
    componentes_conflictivos = (*anclas, "municipio", "estado")
    for domicilio in domicilios:
        if RE_DOMICILIO_INVALIDO.search(domicilio):
            continue
        actual = _componentes_domicilio(domicilio)
        duplicado = any(
            all(
                not actual[clave] or not anterior[clave] or actual[clave] == anterior[clave]
                for clave in componentes_conflictivos
            )
            and (
                all(actual[clave] == anterior[clave] for clave in componentes_conflictivos)
                or any(actual[ancla] and actual[ancla] == anterior[ancla] for ancla in anclas)
            )
            for anterior in vistos
        )
        if not duplicado:
            unicos.append(domicilio)
            vistos.append(actual)
    return unicos


def vehiculos_sin_duplicados(vehiculos: list[Vehiculo]) -> list[Vehiculo]:
    unicos: list[Vehiculo] = []
    series_vistas: set[str] = set()
    for vehiculo in vehiculos:
        serie = _normalizar_componente(vehiculo.serie or "")
        if serie in {"NA", "SINDATO", "NOAPLICA", "NODISPONIBLE", "NONE", "NULL", "0"}:
            serie = ""
        if serie and serie in series_vistas:
            continue
        if serie:
            series_vistas.add(serie)
        unicos.append(vehiculo)
    return unicos


def calcular_edad(nacimiento: date, hoy: date | None = None) -> int:
    hoy = hoy or date.today()
    return hoy.year - nacimiento.year - ((hoy.month, hoy.day) < (nacimiento.month, nacimiento.day))


def normalizar(ficha: Ficha) -> Ficha:
    """Devuelve una copia con los datos derivables completados."""
    f = ficha.model_copy(deep=True)
    dp = f.datos_personales
    dp.estado = (dp.estado or "").strip() or "Chihuahua"
    if dp.edad is None and dp.fecha_nacimiento:
        dp.edad = calcular_edad(dp.fecha_nacimiento, f.fecha)
    dp.telefonos = [re.sub(r"\D", "", t) if re.sub(r"\D", "", t) else t for t in dp.telefonos]
    dp.domicilios = domicilios_sin_duplicados(dp.domicilios)
    f.vehiculos = vehiculos_sin_duplicados(f.vehiculos)
    return f


def validar(ficha: Ficha) -> ReporteValidacion:
    incidencias: list[Incidencia] = []

    def error(campo: str, msg: str) -> None:
        incidencias.append(Incidencia(nivel="error", campo=campo, mensaje=msg))

    def aviso(campo: str, msg: str) -> None:
        incidencias.append(Incidencia(nivel="advertencia", campo=campo, mensaje=msg))

    dp, fam = ficha.datos_personales, ficha.datos_familiares

    # ── Obligatorios ─────────────────────────────────────────────────────────
    if not dp.nombre:
        error("datos_personales.nombre", "No se encontró el nombre de la persona.")
    if not ficha.nuc:
        aviso("nuc", "No se encontró el NUC del encabezado.")
    elif not RE_NUC.match(ficha.nuc):
        error("nuc", f"El NUC '{ficha.nuc}' no tiene el formato esperado (NN-AAAA-NNNNN).")

    # ── Consistencia de NUC entre encabezado y carpetas ──────────────────────
    for i, c in enumerate(ficha.carpetas, 1):
        if c.nuc and not RE_NUC.match(c.nuc):
            error(f"carpetas[{i}].nuc", f"El NUC '{c.nuc}' no tiene el formato esperado.")
    nucs_carpetas = {c.nuc for c in ficha.carpetas if c.nuc}
    if ficha.nuc and nucs_carpetas and ficha.nuc not in nucs_carpetas:
        aviso(
            "nuc",
            f"El NUC del encabezado ({ficha.nuc}) no coincide con el de las carpetas "
            f"({', '.join(sorted(nucs_carpetas))}). Revisa que no haya un dígito transpuesto.",
        )

    # ── Fechas y edad ────────────────────────────────────────────────────────
    hoy = ficha.fecha
    if dp.fecha_nacimiento:
        if dp.fecha_nacimiento > hoy:
            error("datos_personales.fecha_nacimiento", "La fecha de nacimiento está en el futuro.")
        elif dp.edad is not None and abs(calcular_edad(dp.fecha_nacimiento, hoy) - dp.edad) > 1:
            aviso(
                "datos_personales.edad",
                f"La edad indicada ({dp.edad}) no corresponde con la fecha de nacimiento "
                f"(sería {calcular_edad(dp.fecha_nacimiento, hoy)}).",
            )
    else:
        aviso("datos_personales.fecha_nacimiento", "No se encontró la fecha de nacimiento.")

    for etiqueta, lista in (("hermanos", fam.hermanos), ("hermanas", fam.hermanas),
                            ("hijos", fam.hijos), ("hijas", fam.hijas)):  # fmt: skip
        for p in lista:
            if p.fecha_nacimiento and p.fecha_nacimiento > hoy:
                error(f"datos_familiares.{etiqueta}", f"Fecha de nacimiento futura para '{p.nombre}'.")

    for i, c in enumerate(ficha.carpetas, 1):
        if c.fecha_inicio and c.fecha_inicio > hoy:
            aviso(f"carpetas[{i}].fecha_inicio", "La fecha de inicio de la carpeta está en el futuro.")

    # ── Formatos ─────────────────────────────────────────────────────────────
    for t in dp.telefonos:
        if not (t.isdigit() and len(t) == 10):
            aviso("datos_personales.telefonos", f"El teléfono '{t}' no tiene 10 dígitos.")

    for i, fa in enumerate(ficha.fuentes_abiertas, 1):
        if fa.link and not re.match(r"^https?://", fa.link, re.I):
            aviso(f"fuentes_abiertas[{i}].link", "El enlace no empieza con http:// o https://.")

    # ── Datos recomendados ───────────────────────────────────────────────────
    if not ficha.foto_base64:
        aviso("foto_base64", "No se encontró una fotografía en el PDF.")
    if not ficha.carpetas:
        aviso("carpetas", "No se encontró ninguna carpeta de investigación.")

    return ReporteValidacion(
        valido=not any(i.nivel == "error" for i in incidencias), incidencias=incidencias
    )
