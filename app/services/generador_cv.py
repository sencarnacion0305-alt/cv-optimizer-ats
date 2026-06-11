"""
Generador de CV adaptado.

Estrategia: preservar el CV original intacto y modificar
SOLO las secciones que deben cambiar por vacante:
  1. Resumen / Professional Summary  -> reescrito con keywords de la vacante
  2. Skills / Habilidades            -> reordenado para poner primero las
                                        keywords que pide la vacante
Todo lo demas (experiencia, educacion, certificaciones, contacto, etc.)
se copia tal cual del CV original.
"""

import re
from typing import List, Dict

from app.services.adaptador import (
    _keywords_de,
    _analizar_cobertura,
    _normalizar,
    _kw_presente,
)


# ---------------------------------------------------------------------------
# Encabezados de seccion que reconocemos
# ---------------------------------------------------------------------------

SECCION_RESUMEN = re.compile(
    r"^(resumen\s*profesional|professional\s*summary|summary|perfil\s*profesional|"
    r"objetivo\s*profesional|career\s*objective|about\s*me|sobre\s*mi|profile)[\s:]*$",
    re.IGNORECASE,
)

SECCION_HABILIDADES = re.compile(
    r"^(habilidades?(\s*(tecnicas?|profesionales?|clave))?|"
    r"technical\s*skills?|core\s*competencies|skills?|"
    r"competencias?|conocimientos?\s*(tecnicos?)?|"
    r"technologies?|tools?\s*&?\s*technologies?)[\s:]*$",
    re.IGNORECASE,
)

SECCION_CUALQUIER = re.compile(
    r"^[A-ZÀ-Ü][A-Za-zÀ-ÿ\s/&\-]{2,50}:?\s*$"
)


# ---------------------------------------------------------------------------
# Parser: divide el CV en bloques { header, lineas[] }
# ---------------------------------------------------------------------------

def _es_encabezado(linea: str) -> bool:
    """
    Detecta si una linea es un encabezado de seccion.
    Criterios: todo mayusculas, o Title Case corto, o termina en ":",
    o coincide con patrones conocidos.
    """
    s = linea.strip()
    if not s or len(s) > 80:
        return False
    # Todo mayusculas (min 3 chars)
    if s.isupper() and len(s) >= 3:
        return True
    # Termina en ":"
    if s.endswith(":") and len(s) < 60:
        return True
    # Patrones conocidos
    if SECCION_RESUMEN.match(s) or SECCION_HABILIDADES.match(s):
        return True
    # Linea corta en Title Case sin puntuacion al final
    palabras = s.split()
    if (2 <= len(palabras) <= 5
            and s[-1] not in ".!,;)"
            and sum(1 for p in palabras if p[0].isupper()) == len(palabras)):
        return True
    return False


def _parsear_cv(cv_texto: str) -> List[Dict]:
    """
    Devuelve lista de secciones:
    [{ "header": str|None, "lineas": [str] }, ...]
    La primera seccion (header=None) es el encabezado del CV (nombre, contacto).
    """
    secciones = []
    seccion_actual = {"header": None, "lineas": []}

    for linea in cv_texto.splitlines():
        if _es_encabezado(linea):
            if seccion_actual["lineas"] or seccion_actual["header"]:
                secciones.append(seccion_actual)
            seccion_actual = {"header": linea.strip(), "lineas": []}
        else:
            seccion_actual["lineas"].append(linea)

    if seccion_actual["lineas"] or seccion_actual["header"]:
        secciones.append(seccion_actual)

    return secciones


def _tipo_seccion(header: str) -> str:
    """Clasifica el header: 'resumen', 'habilidades', u 'otro'."""
    if not header:
        return "encabezado"
    if SECCION_RESUMEN.match(header.strip()):
        return "resumen"
    if SECCION_HABILIDADES.match(header.strip()):
        return "habilidades"
    return "otro"


# ---------------------------------------------------------------------------
# Adaptadores de seccion
# ---------------------------------------------------------------------------

def _adaptar_resumen(lineas_originales: List[str],
                     cubiertas: List[str],
                     sugeridas: List[str],
                     anios: str,
                     titulo_vacante: str) -> List[str]:
    """
    Reescribe el resumen profesional incorporando las keywords de la vacante.
    Si el CV ya tiene un resumen, lo usa como base y lo enriquece.
    Si no tiene resumen, construye uno desde cero.
    """
    texto_original = " ".join(l.strip() for l in lineas_originales if l.strip())

    top_kw = (cubiertas[:3] + sugeridas[:2])[:4]

    # --- Construir resumen base ---
    if len(texto_original.split()) >= 10:
        # Usar el resumen original como base
        base = texto_original
        # Agregar keywords que faltan
        texto_n = _normalizar(base)
        faltantes = [kw for kw in cubiertas[:2] if not _kw_presente(texto_n, kw)]
        if faltantes:
            base = base.rstrip(".") + ". Experiencia demostrada en " + ", ".join(faltantes) + "."
    else:
        # Construir desde plantilla
        kw_str   = ", ".join(top_kw) if top_kw else titulo_vacante
        exp_str  = f"con {anios} anios de experiencia " if anios else ""
        base = (
            f"Profesional en ciberseguridad {exp_str}especializado en {kw_str}. "
            f"Trayectoria comprobada en deteccion, analisis y respuesta a incidentes "
            f"de seguridad en entornos criticos."
            if "cyber" in _normalizar(titulo_vacante) or "security" in _normalizar(titulo_vacante)
            else f"Profesional {exp_str}especializado en {kw_str}."
        )

    # Partir en lineas de ~80 chars para que se vea bien
    palabras = base.split()
    lineas_out = []
    linea_actual = ""
    for p in palabras:
        if len(linea_actual) + len(p) + 1 > 90:
            lineas_out.append(linea_actual)
            linea_actual = p
        else:
            linea_actual = (linea_actual + " " + p).strip()
    if linea_actual:
        lineas_out.append(linea_actual)

    return lineas_out


def _adaptar_habilidades(lineas_originales: List[str],
                         cubiertas: List[str],
                         sugeridas: List[str]) -> List[str]:
    """
    Reorganiza la seccion de habilidades:
    1. Habilidades del CV que coinciden con la vacante (al principio)
    2. El resto de habilidades originales
    3. Nota con keywords sugeridas (al final, entre corchetes)
    Sin agregar habilidades que el usuario no tiene.
    """
    # Extraer items de habilidades del texto original
    items_originales = []
    for linea in lineas_originales:
        # Separar por comas, pipes, puntos y coma, o tomar la linea entera
        partes = re.split(r"[,|;]|\s{2,}", linea)
        for p in partes:
            p = p.strip().strip("-•*").strip()
            if p and len(p) > 1:
                items_originales.append(p)

    if not items_originales:
        return lineas_originales  # sin cambios si no hay items

    cubiertas_set = set(_normalizar(c) for c in cubiertas)

    # Separar: los que coinciden con la vacante vs el resto
    primero = []
    resto   = []
    vistos  = set()
    for item in items_originales:
        key = _normalizar(item)
        if key in vistos:
            continue
        vistos.add(key)
        if any(c in key or key in c for c in cubiertas_set):
            primero.append(item)
        else:
            resto.append(item)

    ordenados = primero + resto

    # Reconstruir en grupos de 3 por linea
    lineas_out = []
    for i in range(0, len(ordenados), 3):
        grupo = ordenados[i:i+3]
        lineas_out.append("  |  ".join(grupo))


    return lineas_out


# ---------------------------------------------------------------------------
# Funcion principal
# ---------------------------------------------------------------------------

def generar_cv_adaptado(cv_texto: str, vacante_texto: str) -> dict:
    """
    Genera el CV adaptado preservando la estructura original.
    Solo modifica el resumen y la seccion de habilidades.
    """
    kw_vacante           = _keywords_de(vacante_texto)[:30]
    cubiertas, sugeridas = _analizar_cobertura(kw_vacante, cv_texto)

    # Extraer algunos metadatos del CV
    anios = ""
    m = re.search(r"(\d+)\+?\s*(anos?|years?)\s*(de\s*)?(experiencia|experience)", cv_texto, re.I)
    if m:
        anios = m.group(1)

    titulo_vacante = "el puesto"
    for linea in vacante_texto.splitlines():
        linea = linea.strip()
        if linea and len(linea) < 80:
            titulo_vacante = linea
            break

    # Parsear el CV original en secciones
    secciones = _parsear_cv(cv_texto)

    # Reconstruir el CV modificando solo lo necesario
    lineas_salida = []
    resumen_encontrado = False

    for seccion in secciones:
        header = seccion["header"]
        lineas = seccion["lineas"]
        tipo   = _tipo_seccion(header or "")

        # Agregar header
        if header:
            lineas_salida.append("")
            lineas_salida.append(header)

        if tipo == "resumen":
            resumen_encontrado = True
            nuevas_lineas = _adaptar_resumen(lineas, cubiertas, sugeridas, anios, titulo_vacante)
            lineas_salida.extend(nuevas_lineas)

        elif tipo == "habilidades":
            nuevas_lineas = _adaptar_habilidades(lineas, cubiertas, sugeridas)
            lineas_salida.extend(nuevas_lineas)

        else:
            # Seccion original intacta
            lineas_salida.extend(lineas)

    # Si el CV no tenia seccion de resumen, insertarla despues del encabezado
    if not resumen_encontrado:
        nuevo_resumen = _adaptar_resumen([], cubiertas, sugeridas, anios, titulo_vacante)
        insert_pos = 0
        # Encontrar donde termina el encabezado (primera seccion sin header)
        for j, linea in enumerate(lineas_salida):
            if _es_encabezado(linea) and j > 0:
                insert_pos = j
                break
        bloque_resumen = ["", "RESUMEN PROFESIONAL"] + nuevo_resumen
        lineas_salida = (lineas_salida[:insert_pos] + bloque_resumen
                         + lineas_salida[insert_pos:])

    texto_completo = "\n".join(lineas_salida).strip()

    texto_completo_n = _normalizar(texto_completo)
    kw_en_resumen = [kw for kw in cubiertas if _kw_presente(texto_completo_n, kw)]

    return {
        "texto_completo":        texto_completo,
        "titulo_puesto":         titulo_vacante,
        "keywords_incorporadas": kw_en_resumen[:6],
    }
