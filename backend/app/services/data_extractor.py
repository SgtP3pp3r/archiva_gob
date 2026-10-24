"""Identifica los campos de la ficha dentro del texto extraído del PDF.

Estrategia (basada en etiquetas):
  1. Se buscan encabezados de sección ("DATOS PERSONALES", "FUENTES ABIERTAS"…)
     y etiquetas de campo ("Nombre:", "Fecha de nacimiento:"…) al inicio de línea.
  2. El valor de cada etiqueta es el texto que hay hasta la siguiente etiqueta
     o encabezado, de modo que funciona igual si el PDF trae "Etiqueta: valor"
     en una línea o la etiqueta y el valor en líneas separadas (celdas de tabla).
  3. Los valores se convierten a los tipos del esquema (fechas, listas, números).

PARA ADAPTAR AL FORMATO REAL DE TUS PDF: edita únicamente las tablas CAMPOS y
SECCIONES de abajo. Los patrones se escriben en minúsculas y SIN acentos
(el texto se normaliza igual antes de comparar).
"""
from __future__ import annotations

import base64
import re
from collections import Counter
from dataclasses import dataclass
from datetime import date

from app.schemas.ficha import (
    CarpetaInvestigacion,
    DatosFamiliares,
    DatosPersonales,
    Ficha,
    Familiar,
    FuenteAbierta,
    FuenteFotografia,
    Vehiculo,
)
from app.services.pdf_reader import ContenidoPdf, ImagenPdf

# ── Configuración: encabezados y etiquetas ───────────────────────────────────

# Encabezados de sección (línea completa). Clave → patrón.
SECCIONES: dict[str, str] = {
    "personales": r"datos\s+personales",
    "familiares": r"datos\s+(?:de\s+)?familiares",
    "carpetas": r"carpetas?\s+de\s+investigacion(?:\s+y\s+averiguaciones\s+previas)?",
    "vehiculos": r"datos\s+vehiculares",
    "registro": r"registro\s+publico\s+de\s+la\s+propiedad",
    "fuentes": r"fuentes\s+abiertas",
    "fotografias": r"fotografias?",
    "observaciones": r"observaciones",  # también es campo ("Observaciones: texto"), ver CAMPOS
}


@dataclass(frozen=True)
class Campo:
    clave: str  # a dónde va el valor; "prefijo.nombre" para campos de bloques repetibles
    patron: str  # etiqueta, minúsculas y sin acentos
    seccion: str | None = None  # si se indica, solo aplica dentro de esa sección
    dos_puntos: bool = True  # False → los ":" son opcionales


CAMPOS: list[Campo] = [
    # Datos personales
    Campo("nombre", r"nombre(?:\s+completo)?"),
    Campo("fecha_nacimiento", r"fecha\s+de\s+nacimiento"),
    Campo("lugar_nacimiento", r"lugar\s+de\s+nacimiento"),
    Campo("domicilio", r"domicilios?"),
    Campo(
        "telefono_emergencia",
        r"(?:telefono(?:\s+de)?|celular(?:\s+de)?|numero(?:\s+de(?:\s+telefono)?(?:\s+de)?)?|contacto(?:\s+de)?)\s+emergencia",
    ),
    Campo("telefono", r"(?:telefonos?|celulares?)"),
    Campo("ocupacion", r"ocupacion"),
    Campo("estado_civil", r"estado\s+civil"),
    Campo("edad", r"edad"),
    Campo("alias", r"alias"),
    # Datos de familiares
    Campo("madre", r"madre"),
    Campo("padre", r"padre"),
    Campo("hermanos", r"hermanos"),
    Campo("hermanas", r"hermanas"),
    Campo("pareja", r"pareja"),
    Campo("hijas", r"hijas"),
    Campo("hijos", r"hijos"),
    # Carpetas de investigación (bloque repetible)
    Campo("carpeta.nuc", r"nuc"),
    Campo("carpeta.fecha_inicio", r"fecha\s+(?:de\s+)?inicio"),
    Campo("carpeta.delito", r"delito"),
    Campo("carpeta.calidad", r"calidad"),
    Campo("carpeta.hechos", r"hechos"),
    Campo("carpeta.unidad", r"unidad"),
    # Datos vehiculares (bloque repetible)
    Campo("vehiculo.alta", r"alta"),
    Campo("vehiculo.marca", r"marca"),
    Campo("vehiculo.linea", r"linea"),
    Campo("vehiculo.modelo", r"modelo"),
    Campo("vehiculo.placa", r"placas?"),
    Campo("vehiculo.serie", r"serie"),
    # Fotografías (bloque repetible; "Nombre" y "Fecha" solo cuentan dentro de la sección)
    Campo("foto.fecha", r"fecha", seccion="fotografias"),
    Campo("foto.nombre", r"nombre", seccion="fotografias"),
    Campo("foto.causa", r"(?:numero|no\.?|num\.?)\s+de\s+(?:causa|casusa)", seccion="fotografias"),
    # Observaciones (texto libre hasta el final)
    Campo("observaciones", r"observaciones", dos_puntos=False),
]

# ── Utilidades de texto ──────────────────────────────────────────────────────

# Misma longitud que el original: así los índices del texto "plegado" valen para el original.
_PLEGAR = str.maketrans("áéíóúüñÁÉÍÓÚÜÑ", "aeiouunaeiouun")
_VINETAS = "•·▪◦●"
_RE_VINETA = re.compile(rf"^[ \t]*[{_VINETAS}\-–*][ \t]*")
_RE_VINETA_SOLA = re.compile(rf"(?m)^[ \t]*[{_VINETAS}][ \t]*\n[ \t]*")
_RE_SIN_DATO = re.compile(r"(?:sin\s+dato|n/?a|ninguno|no\s+aplica|-+)\.?", re.I)

MESES = {
    "enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6,
    "julio": 7, "agosto": 8, "septiembre": 9, "setiembre": 9, "octubre": 10,
    "noviembre": 11, "diciembre": 12,
}  # fmt: skip
_RE_FECHA_NUM = re.compile(r"(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{4})")
_RE_FECHA_ISO = re.compile(r"(\d{4})-(\d{2})-(\d{2})")
_RE_FECHA_LARGA = re.compile(r"(\d{1,2})\s+de\s+([a-z]+)\s+(?:de\s+|del\s+)?(\d{4})")
_RE_PIWEB_MARCA = re.compile(r"(?im)^[ \t]*fuente\s*:\s*")
_RE_PIWEB_CAMPO = re.compile(r"(?i)(?:^|[,;\n])[ \t]*([a-z][a-z0-9_]+)[ \t]*:[ \t]*")
_RE_PIWEB_PIE = re.compile(r"(?i)\s*(?:piweb[- ]confidencial|plataforma de integraci[oó]n tecnol[oó]gica)\b.*$")


def _plegar(texto: str) -> str:
    return texto.translate(_PLEGAR).lower()


def _normalizar(texto: str) -> str:
    texto = texto.replace("\xa0", " ").replace("\r", "")
    # Word exporta las viñetas con la fuente Symbol (p. ej. U+F0B7, área de uso privado de Unicode).
    texto = re.sub("[\ue000-\uf8ff]", "•", texto)
    # PyMuPDF suele dejar la viñeta sola en una línea: se une con su texto.
    return _RE_VINETA_SOLA.sub("• ", texto)


def parse_fecha(texto: str | None) -> date | None:
    """Acepta 21/05/1986, 21-05-1986, 1986-05-21 y '21 de mayo de 1986'."""
    if not texto:
        return None
    t = _plegar(texto)
    try:
        if m := _RE_FECHA_ISO.search(t):
            return date(int(m[1]), int(m[2]), int(m[3]))
        if m := _RE_FECHA_NUM.search(t):
            return date(int(m[3]), int(m[2]), int(m[1]))
        if (m := _RE_FECHA_LARGA.search(t)) and m[2] in MESES:
            return date(int(m[3]), MESES[m[2]], int(m[1]))
    except ValueError:  # fecha imposible (31/02/…)
        return None
    return None


def _sin_dato(valor: str) -> bool:
    return not valor or bool(_RE_SIN_DATO.fullmatch(_plegar(valor).strip()))


def _escalar(valor: str | None) -> str | None:
    """Une líneas y devuelve None si el campo viene vacío o dice 'Sin dato'."""
    if valor is None:
        return None
    limpio = " ".join(valor.split())
    return None if _sin_dato(limpio) else limpio


def _items(valor: str | None) -> list[str]:
    """Separa una lista en elementos (viñetas o líneas) y une los renglones cortados."""
    if not valor:
        return []
    lineas = [ln.strip() for ln in valor.splitlines() if ln.strip()]
    hay_vinetas = any(_RE_VINETA.match(ln) for ln in lineas)
    items: list[str] = []
    for ln in lineas:
        es_nuevo = bool(_RE_VINETA.match(ln))
        ln = _RE_VINETA.sub("", ln).strip()
        # Una línea continúa la anterior si hay viñetas y esta no trae, o si hay un "(" sin cerrar.
        continua = items and (
            (hay_vinetas and not es_nuevo) or items[-1].count("(") > items[-1].count(")")
        )
        if continua:
            items[-1] += " " + ln
        else:
            items.append(ln)
    return [i for i in items if not _sin_dato(i)]


def _familiares(valor: str | None) -> list[Familiar]:
    """'Nombre (fecha de nacimiento 21/05/1986)' → Familiar(nombre, fecha)."""
    resultado = []
    for item in _items(valor):
        fecha = parse_fecha(item)
        nombre = re.sub(r"\(.*?\)", "", item)
        if fecha and "(" not in item:
            for rx in (_RE_FECHA_NUM, _RE_FECHA_ISO):
                nombre = rx.sub("", nombre)
        nombre = re.sub(r"\s+", " ", nombre).strip(" .-–,;:")
        if nombre:
            resultado.append(Familiar(nombre=nombre, fecha_nacimiento=fecha))
    return resultado


def _telefonos(valor: str | None) -> list[str]:
    salida = []
    for item in _items(valor):
        for parte in re.split(r"[;,/]", item):
            digitos = re.sub(r"\D", "", parte)
            if digitos:
                salida.append(digitos)
            elif _escalar(parte):
                salida.append(parte.strip())
    return salida


def _sin_comillas(valor: str | None) -> str | None:
    """El generador de Word agrega las comillas del alias; aquí se guarda sin ellas."""
    return valor.strip("\"“”'") or None if valor else None


def _entero(valor: str | None) -> int | None:
    m = re.search(r"\d+", valor or "")
    return int(m[0]) if m else None


def _registros_piweb(texto: str) -> list[tuple[str, dict[str, str]]]:
    """Lee los registros FUENTE: CAMPO: valor de los reportes PiWeb."""
    marcas = list(_RE_PIWEB_MARCA.finditer(texto))
    registros = []
    for i, marca in enumerate(marcas):
        fin = marcas[i + 1].start() if i + 1 < len(marcas) else len(texto)
        contenido = texto[marca.start() : fin]
        campos = list(_RE_PIWEB_CAMPO.finditer(contenido))
        valores: dict[str, str] = {}
        for j, campo in enumerate(campos):
            siguiente = campos[j + 1].start() if j + 1 < len(campos) else len(contenido)
            clave = re.sub(r"\d+$", "", campo[1].upper())
            valor = " ".join(contenido[campo.end() : siguiente].split()).strip(" ,;")
            valor = _RE_PIWEB_PIE.sub("", valor).strip(" ,;")
            if not valor:
                continue
            valores.setdefault(clave, valor)
        fuente = valores.pop("FUENTE", "")
        if fuente and valores:
            registros.append((fuente, valores))
    return registros


def _valor_registro(campos: dict[str, str], *claves: str) -> str | None:
    for clave in claves:
        valor = _escalar(campos.get(clave))
        if valor:
            return valor
    return None


def _identidad_registro(campos: dict[str, str]) -> tuple[str, str, str] | None:
    nombre = _valor_registro(campos, "NOMBRE")
    paterno = _valor_registro(campos, "PATERNO")
    materno = _valor_registro(campos, "MATERNO")
    if nombre and (paterno or materno):
        return (_plegar(nombre), _plegar(paterno or ""), _plegar(materno or ""))
    return None


def _nombre_piweb(campos: dict[str, str]) -> str | None:
    nombre = _valor_registro(campos, "NOMBRE")
    if not nombre:
        return _valor_registro(campos, "NOMBRECOMPLETO", "NOMBRE_COMPLETO")
    return " ".join(
        parte for parte in (nombre, _valor_registro(campos, "PATERNO"), _valor_registro(campos, "MATERNO")) if parte
    )


def _nombre_familiar_piweb(campos: dict[str, str], parentesco: str) -> str | None:
    nombre = _valor_registro(campos, f"NOMBRE_{parentesco}")
    paterno = _valor_registro(campos, f"PATERNO_{parentesco}")
    materno = _valor_registro(campos, f"MATERNO_{parentesco}")
    if not nombre:
        return None
    partes = nombre.split()
    if paterno and not _plegar(nombre).endswith(_plegar(paterno)):
        partes.extend(paterno.split())
    nombre = " ".join(partes)
    if materno and not _plegar(nombre).endswith(_plegar(materno)):
        nombre = f"{nombre} {materno}"
    return nombre


def _estado_piweb(registros: list[tuple[str, dict[str, str]]]) -> str:
    for _, campos in registros:
        estado = _valor_registro(campos, "ESTADO", "ESTADO6")
        if estado and not estado.isdigit():
            return estado
    for _, campos in registros:
        entidad = _valor_registro(campos, "ENTIDAD_ORIGEN")
        if entidad and not entidad.isdigit():
            return entidad
    return "Chihuahua"


def _estado_lugar_nacimiento(lugar: str | None) -> str:
    if lugar and "," in lugar:
        estado = _escalar(lugar.rsplit(",", 1)[-1].strip(" ."))
        if estado:
            return estado
    return "Chihuahua"


def _partes_direccion_unicas(partes: list[tuple[str | None, str | None]]) -> list[str]:
    resultado: list[str] = []
    vistos: set[str] = set()
    for etiqueta, valor in partes:
        if not etiqueta or not valor:
            continue
        clave = re.sub(r"[^A-Z0-9]", "", _plegar(valor).upper())
        if clave and clave not in vistos:
            vistos.add(clave)
            resultado.append(etiqueta)
    return resultado


def _direccion_piweb(campos: dict[str, str], estado_default: str) -> str | None:
    calle = _valor_registro(campos, "CALLE")
    numero = _valor_registro(campos, "NUMERO_INTERIOR", "NUM_INT", "NUMERO_EXTERIOR")
    colonia = _valor_registro(campos, "COLONIA")
    codigo_postal = _valor_registro(campos, "CP", "CODIGO_POSTAL")
    municipio = _valor_registro(campos, "MUNICIPIO", "LOCALIDAD")
    estado = _valor_registro(campos, "ESTADO", "ESTADO6", "ENTIDAD_ORIGEN") or estado_default

    if municipio:
        colonia_embebida = re.search(r"(?:^|[,;])\s*COLONIA\s+([^,;]+)", municipio, re.I)
        if colonia_embebida:
            colonia = colonia or colonia_embebida[1].strip()
            municipio = (
                municipio[: colonia_embebida.start()] + municipio[colonia_embebida.end() :]
            ).strip(" ,;")

        cp_embebido = re.search(
            r"(?:^|[,;])\s*(?:C\.?P\.?|CP|CODIGO[ _]POSTAL)\s*[:#]?\s*(\d{5})",
            municipio,
            re.I,
        )
        if cp_embebido:
            codigo_postal = codigo_postal or cp_embebido[1]
            municipio = (
                municipio[: cp_embebido.start()] + municipio[cp_embebido.end() :]
            ).strip(" ,;")

    if not any((calle, numero, colonia, codigo_postal)):
        return None

    partes = _partes_direccion_unicas([
        (f"Calle {calle}" if calle else None, calle),
        (f"#{numero}" if numero else None, f"numero:{numero}" if numero else None),
        (f"Colonia {colonia}" if colonia else None, colonia),
        (f"C.P. {codigo_postal}" if codigo_postal else None, f"cp:{codigo_postal}" if codigo_postal else None),
        (municipio, municipio),
        (estado, estado),
    ])
    domicilio = ", ".join(partes)
    return domicilio or None


def _extraer_piweb(texto: str, imagenes: list[ImagenPdf]) -> Ficha:
    registros = _registros_piweb(texto)
    identidades = Counter(
        identidad
        for _, campos in registros
        if (identidad := _identidad_registro(campos)) is not None
    )
    if not identidades:
        return Ficha()

    identidad = identidades.most_common(1)[0][0]
    def coincide_sujeto(campos: dict[str, str]) -> bool:
        if _identidad_registro(campos) == identidad:
            return True
        nombre_completo = _plegar(_valor_registro(campos, "NOMBRECOMPLETO", "NOMBRE_COMPLETO") or "")
        nombre_objetivo = " ".join(parte for parte in identidad if parte)
        return bool(nombre_completo and nombre_objetivo in nombre_completo)

    relacionados = [(fuente, campos) for fuente, campos in registros if coincide_sujeto(campos)]
    civiles = [
        campos
        for fuente, campos in relacionados
        if "registro civil" in _plegar(fuente) and "nacimiento" in _plegar(fuente)
    ]
    nacimiento = next(
        (
            parse_fecha(_valor_registro(campos, "FECHA_NACIMIENTO", "FECHA"))
            for campos in civiles
            if parse_fecha(_valor_registro(campos, "FECHA_NACIMIENTO", "FECHA"))
        ),
        None,
    )
    if nacimiento is None:
        nacimiento = next(
            (
                fecha
                for _, campos in relacionados
                if (fecha := parse_fecha(_valor_registro(campos, "FECHA_NACIMIENTO"))) is not None
            ),
            None,
        )

    def es_del_sujeto(campos: dict[str, str]) -> bool:
        identidad_registro = _identidad_registro(campos)
        if identidad_registro is not None and identidad_registro != identidad:
            return False
        if identidad_registro is None and not coincide_sujeto(campos):
            return False
        fecha = parse_fecha(_valor_registro(campos, "FECHA_NACIMIENTO"))
        return fecha is None or fecha == nacimiento

    personales = [(fuente, campos) for fuente, campos in relacionados if es_del_sujeto(campos)]
    primero = personales[0][1]
    estado_default = _estado_piweb(personales)
    domicilios: list[str] = []
    telefonos: list[str] = []
    ocupaciones: list[str] = []
    estado_civil = None
    vehiculos: list[Vehiculo] = []
    carpetas: list[CarpetaInvestigacion] = []

    for fuente, campos in personales:
        domicilio = _direccion_piweb(campos, estado_default)
        if domicilio and domicilio not in domicilios:
            domicilios.append(domicilio)

        telefono = _valor_registro(campos, "TELEFONO", "TELEFONO_MOVIL", "CELULAR")
        if telefono and not telefonos:
            telefonos.extend(_telefonos(telefono))
        ocupacion = _valor_registro(campos, "OCUPACION")
        if ocupacion and ocupacion not in ocupaciones:
            ocupaciones.append(ocupacion)
        estado_civil = estado_civil or _valor_registro(campos, "ESTADO_CIVIL")

        if "vehicular" in _plegar(fuente) or _valor_registro(campos, "PLACA", "SERIE", "MARCA"):
            vehiculo = Vehiculo(
                alta=_valor_registro(campos, "FECHA", "FECHA_ALTA"),
                marca=_valor_registro(campos, "MARCA"),
                linea=_valor_registro(campos, "LINEA", "SUBLINEA"),
                modelo=_valor_registro(campos, "MODELO"),
                placa=_valor_registro(campos, "PLACA"),
                serie=_valor_registro(campos, "SERIE"),
            )
            if any((vehiculo.marca, vehiculo.linea, vehiculo.modelo, vehiculo.placa, vehiculo.serie)):
                if vehiculo not in vehiculos:
                    vehiculos.append(vehiculo)

        delito = _valor_registro(campos, "DELITO")
        if delito:
            carpeta = CarpetaInvestigacion(
                nuc=None,
                fecha_inicio=parse_fecha(_valor_registro(campos, "FECHA")),
                delito=delito,
                calidad=_valor_registro(campos, "TIPO_PERSONA", "CALIDAD"),
                hechos=_valor_registro(campos, "HECHOS", "DESCRIPCION_HECHOS"),
                unidad=fuente,
            )
            if carpeta not in carpetas:
                carpetas.append(carpeta)

    madre = next(
        (nombre for _, campos in personales if (nombre := _valor_registro(campos, "NOMBRE_MADRE"))),
        None,
    )
    padre = next(
        (nombre for _, campos in personales if (nombre := _valor_registro(campos, "NOMBRE_PADRE"))),
        None,
    )
    for campos in civiles:
        madre = _nombre_familiar_piweb(campos, "MADRE") or madre
        padre = _nombre_familiar_piweb(campos, "PADRE") or padre

    pareja = None
    for fuente, campos in registros:
        if "matrimonio" in _plegar(fuente) and _identidad_registro(campos) == identidad:
            pareja = _nombre_familiar_piweb(campos, "ESPOSA") or _nombre_familiar_piweb(campos, "ESPOSO")
            if pareja:
                break

    hijos: list[Familiar] = []
    for fuente, campos in registros:
        if "nacimiento" not in _plegar(fuente) or _identidad_registro(campos) in (None, identidad):
            continue
        padre_hijo = _nombre_familiar_piweb(campos, "PADRE")
        madre_hijo = _nombre_familiar_piweb(campos, "MADRE")
        es_hijo = padre_hijo and identidad[0] in _plegar(padre_hijo) and identidad[1] in _plegar(padre_hijo)
        es_hija = madre_hijo and identidad[0] in _plegar(madre_hijo) and identidad[1] in _plegar(madre_hijo)
        if es_hijo or es_hija:
            nombre = _nombre_piweb(campos)
            if nombre:
                familiar = Familiar(
                    nombre=nombre,
                    fecha_nacimiento=parse_fecha(_valor_registro(campos, "FECHA_NACIMIENTO", "FECHA")),
                )
                if familiar not in hijos:
                    hijos.append(familiar)
            pareja = pareja or (madre_hijo if es_hijo else padre_hijo)

    origen = next(
        (valor for _, campos in personales if (valor := _valor_registro(campos, "ORIGINARIO", "LUGAR_NACIMIENTO"))),
        None,
    )
    origen = origen or next(
        (valor for campos in civiles if (valor := _valor_registro(campos, "LOCALIDAD", "MUNICIPIO"))),
        None,
    )
    origen = origen or next(
        (
            valor
            for _, campos in personales
            if (valor := _valor_registro(campos, "LOCALIDAD", "MUNICIPIO"))
        ),
        None,
    )
    nombre = _nombre_piweb(primero)
    if not nombre:
        return Ficha()
    foto = _elegir_foto(imagenes)

    return Ficha(
        datos_personales=DatosPersonales(
            nombre=nombre,
            fecha_nacimiento=nacimiento,
            lugar_nacimiento=origen,
            estado=_estado_piweb(personales),
            domicilios=domicilios[:20],
            telefonos=telefonos[:1],
            telefono_emergencia=next(
                (
                    numeros[0]
                    for _, campos in personales
                    if (valor := _valor_registro(
                        campos,
                        "TELEFONO_EMERGENCIA",
                        "TELEFONO_CONTACTO_EMERGENCIA",
                        "NUMERO_TELEFONO_EMERGENCIA",
                        "NUMERO_EMERGENCIA",
                        "TEL_EMERGENCIA",
                        "TEL_CONTACTO_EMERGENCIA",
                        "CONTACTO_EMERGENCIA",
                        "EMERGENCIA",
                    ))
                    and (numeros := _telefonos(valor))
                ),
                None,
            ),
            ocupacion=", ".join(ocupaciones) if ocupaciones else None,
            estado_civil=estado_civil,
        ),
        datos_familiares=DatosFamiliares(
            madre=madre,
            padre=padre,
            pareja=pareja,
            hijos=hijos,
        ),
        carpetas=carpetas,
        vehiculos=vehiculos,
        foto_base64=base64.b64encode(foto.png).decode() if foto else None,
    )


# ── Segmentación del texto en (campo, valor) ─────────────────────────────────


@dataclass
class _Marca:
    inicio: int
    fin: int
    tipo: str  # "seccion" | "campo"
    clave: str
    seccion: str | None = None  # sección activa donde se encontró


def _segmentar(texto: str) -> tuple[list[tuple[str, str | None, str]], dict[str, str]]:
    """Devuelve ([(clave, sección, valor)], {sección: texto libre})."""
    plegado = _plegar(texto)
    marcas: list[_Marca] = []

    for nombre, patron in SECCIONES.items():
        rx = re.compile(rf"(?m)^[ \t]*(?:{patron})[ \t]*:?[ \t]*$")
        marcas += [_Marca(m.start(), m.end(), "seccion", nombre) for m in rx.finditer(plegado)]
    marcas.sort(key=lambda m: m.inicio)

    def seccion_en(pos: int) -> str | None:
        activa = None
        for m in marcas:
            if m.tipo == "seccion" and m.inicio < pos:
                activa = m.clave
        return activa

    candidatas: dict[int, tuple[bool, _Marca]] = {}
    for campo in CAMPOS:
        dp = ":" if campo.dos_puntos else ":?"
        rx = re.compile(rf"(?m)^[ \t]*(?:[{_VINETAS}\-–*][ \t]*)?(?:{campo.patron})[ \t]*{dp}")
        for m in rx.finditer(plegado):
            activa = seccion_en(m.start())
            if campo.seccion and campo.seccion != activa:
                continue
            especifico = campo.seccion is not None
            previa = candidatas.get(m.start())
            if previa is None or (especifico and not previa[0]):  # lo específico gana
                candidatas[m.start()] = (especifico, _Marca(m.start(), m.end(), "campo", campo.clave, activa))

    marcas += [m for _, m in candidatas.values()]
    marcas.sort(key=lambda m: m.inicio)

    pares: list[tuple[str, str | None, str]] = []
    libres: dict[str, str] = {}
    for i, m in enumerate(marcas):
        siguiente = marcas[i + 1].inicio if i + 1 < len(marcas) else len(texto)
        if m.tipo == "campo":
            pares.append((m.clave, m.seccion, texto[m.fin : siguiente].strip()))

    # Texto libre de cada sección: hasta el siguiente ENCABEZADO (ignora etiquetas).
    encabezados = [m for m in marcas if m.tipo == "seccion"]
    for i, m in enumerate(encabezados):
        fin = encabezados[i + 1].inicio if i + 1 < len(encabezados) else len(texto)
        libres[m.clave] = texto[m.fin : fin].strip()
    return pares, libres


def _bloques(pares: list[tuple[str, str | None, str]], prefijo: str) -> list[dict[str, str]]:
    """Agrupa campos 'prefijo.x' en registros; empieza uno nuevo cuando un campo se repite."""
    bloques: list[dict[str, str]] = []
    actual: dict[str, str] = {}
    for clave, _, valor in pares:
        if not clave.startswith(prefijo + "."):
            continue
        k = clave.split(".", 1)[1]
        if k in actual:
            bloques.append(actual)
            actual = {}
        actual[k] = valor
    if actual:
        bloques.append(actual)
    return bloques


# ── Fuentes abiertas (texto libre) ───────────────────────────────────────────

_RE_URL = re.compile(r"https?://[^\s<>\"')]+", re.I)
_RE_CONSULTA = re.compile(r"fecha\s+y\s+hora\s+de\s+consulta\s*:?\s*([0-9/\-]+\s*[0-9:]+(?:\s*hrs?\.?)?)", re.I)
_RE_CORTE_DESC = re.compile(r"fecha\s+y\s+hora\s+de\s+consulta|link\s*:", re.I)


def _fuentes_abiertas(texto: str) -> list[FuenteAbierta]:
    fuentes = []
    for trozo in re.split(rf"(?m)^[ \t]*[{_VINETAS}][ \t]*", texto):
        trozo = trozo.strip()
        if not trozo or _sin_dato(trozo):
            continue
        link = _RE_URL.search(trozo)
        consulta = _RE_CONSULTA.search(trozo)
        corte = _RE_CORTE_DESC.search(trozo)
        descripcion = " ".join((trozo[: corte.start()] if corte else trozo).split())
        fuentes.append(
            FuenteAbierta(
                descripcion=descripcion or (link[0] if link else trozo),
                fecha_consulta=consulta[1].strip() if consulta else None,
                link=link[0].rstrip(".,;") if link else None,
            )
        )
    return fuentes


# ── Fotografías: origen de la imagen (texto libre) ───────────────────────────

_RE_ETQ_FOTO = re.compile(r"(?im)^[ \t]*(fecha|nombre|(?:numero|número|no\.?|num\.?)\s+de\s+(?:causa|casusa))\s*:\s*")


def _fotografias(texto: str) -> list[FuenteFotografia]:
    """Cada viñeta es un registro: un título (la fuente) seguido de Fecha / Nombre / Número de causa."""
    registros = []
    for trozo in re.split(rf"(?m)^[ \t]*[{_VINETAS}][ \t]*", texto):
        trozo = trozo.strip()
        if not trozo or _sin_dato(trozo):
            continue
        etiquetas = list(_RE_ETQ_FOTO.finditer(trozo))
        if not etiquetas:
            continue
        valores: dict[str, str] = {}
        for i, m in enumerate(etiquetas):
            fin = etiquetas[i + 1].start() if i + 1 < len(etiquetas) else len(trozo)
            etq = _plegar(m[1])
            clave = "fecha" if etq == "fecha" else "nombre" if etq == "nombre" else "causa"
            valores[clave] = trozo[m.end() : fin]
        registros.append(
            FuenteFotografia(
                fuente=_escalar(trozo[: etiquetas[0].start()]),
                fecha=parse_fecha(valores.get("fecha")),
                nombre=_escalar(valores.get("nombre")),
                numero_causa=_escalar(valores.get("causa")),
            )
        )
    return registros


# ── Foto principal ───────────────────────────────────────────────────────────


def _elegir_foto(imagenes: list[ImagenPdf]) -> ImagenPdf | None:
    """Retrato: primera página que tenga una imagen de proporción vertical/cuadrada.

    `leer_pdf` ya descartó membrete, pie y fondos. Aquí se ignoran además las capturas de
    pantalla (apaisadas) y, entre las candidatas de una página, se toma la más grande.
    """
    candidatas = [i for i in imagenes if 0.5 <= i.ancho / i.alto <= 1.5]
    if not candidatas:
        return None
    primera = min(i.pagina for i in candidatas)
    return max((i for i in candidatas if i.pagina == primera), key=lambda i: i.area_mostrada)


# ── Punto de entrada ─────────────────────────────────────────────────────────


def extraer_ficha(contenido: ContenidoPdf) -> Ficha:
    texto = _normalizar(contenido.texto)
    if _RE_PIWEB_MARCA.search(texto):
        return _extraer_piweb(texto, contenido.imagenes)
    pares, libres = _segmentar(texto)

    # Para campos simples gana la primera aparición (la sección de datos personales va primero).
    primero: dict[str, str] = {}
    for clave, _, valor in pares:
        if "." not in clave:
            primero.setdefault(clave, valor)

    lugar_nacimiento = _escalar(primero.get("lugar_nacimiento"))
    personales = DatosPersonales(
        nombre=_escalar(primero.get("nombre")),
        fecha_nacimiento=parse_fecha(primero.get("fecha_nacimiento")),
        lugar_nacimiento=lugar_nacimiento,
        estado=_estado_lugar_nacimiento(lugar_nacimiento),
        domicilios=_items(primero.get("domicilio")),
        telefonos=_telefonos(primero.get("telefono"))[:1],
        telefono_emergencia=next(
            iter(_telefonos(primero.get("telefono_emergencia"))), None
        ),
        ocupacion=_escalar(primero.get("ocupacion")),
        estado_civil=_escalar(primero.get("estado_civil")),
        edad=_entero(primero.get("edad")),
        alias=_sin_comillas(_escalar(primero.get("alias"))),
    )
    familiares = DatosFamiliares(
        madre=_escalar(primero.get("madre")),
        padre=_escalar(primero.get("padre")),
        hermanos=_familiares(primero.get("hermanos")),
        hermanas=_familiares(primero.get("hermanas")),
        pareja=_escalar(primero.get("pareja")),
        hijas=_familiares(primero.get("hijas")),
        hijos=_familiares(primero.get("hijos")),
    )
    carpetas = [
        CarpetaInvestigacion(
            nuc=_escalar(b.get("nuc")),
            fecha_inicio=parse_fecha(b.get("fecha_inicio")),
            delito=_escalar(b.get("delito")),
            calidad=_escalar(b.get("calidad")),
            hechos=_escalar(b.get("hechos")),
            unidad=_escalar(b.get("unidad")),
        )
        for b in _bloques(pares, "carpeta")
    ]
    vehiculos = [
        Vehiculo(**{k: _escalar(v) for k, v in b.items()})
        for b in _bloques(pares, "vehiculo")
        if any(_escalar(v) for v in b.values())
    ]
    fotografias = _fotografias(libres.get("fotografias", ""))

    # NUC del encabezado: "NUC 19-2019-26310" cerca del inicio; si no, el de la primera carpeta.
    m_nuc = re.search(r"\bNUC\b[:\s]*(\d{2}-\d{4}-\d{3,6})", texto[:1500], re.I)
    nuc = m_nuc[1] if m_nuc else next((c.nuc for c in carpetas if c.nuc), None)

    foto = _elegir_foto(contenido.imagenes)

    return Ficha(
        nuc=nuc,
        datos_personales=personales,
        datos_familiares=familiares,
        carpetas=carpetas,
        vehiculos=vehiculos,
        registro_publico=_items(libres.get("registro")),
        fuentes_abiertas=_fuentes_abiertas(libres.get("fuentes", "")),
        fotografias=fotografias,
        observaciones=_escalar(primero.get("observaciones")),
        foto_base64=base64.b64encode(foto.png).decode() if foto else None,
    )
