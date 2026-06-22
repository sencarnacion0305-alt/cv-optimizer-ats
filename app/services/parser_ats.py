"""
Simulador de Parsing ATS.

Reconstruye como un sistema ATS "lee" un CV: extrae los campos estructurados
que un parser intentaria volcar a su base de datos (nombre, contacto, anios de
experiencia, puestos, educacion, skills) y resalta lo que NO pudo detectar.

Objetivo: que el candidato vea, con sus propios ojos, que informacion llega
realmente al reclutador despues del parsing automatico.
"""

import re
from datetime import datetime
from typing import Dict, List, Optional

from app.services.adaptador import (
    _extraer_compuestos, TECH_SINGLE, _normalizar,
)


# ---------------------------------------------------------------------------
# Patrones
# ---------------------------------------------------------------------------

EMAIL_RE    = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
PHONE_RE    = re.compile(r"(?:\+?\d[\d\s().\-]{7,}\d)")
LINKEDIN_RE = re.compile(r"(?:linkedin\.com/in/[\w\-%]+)", re.IGNORECASE)
UBIC_RE     = re.compile(
    r"(?:location|ubicaci[oó]n|address|direcci[oó]n)\s*[:\-]\s*(.+)", re.IGNORECASE)

MESES = (r"(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec|"
         r"ene|abr|ago|dic|enero|febrero|marzo|abril|mayo|junio|julio|"
         r"agosto|septiembre|setiembre|octubre|noviembre|diciembre)")
ANIO   = r"(?:19|20)\d{2}"
PRESENTE = r"(?:present|presente|actual|current|now|hoy|ongoing|to\s*date)"

# Un "token de fecha": mes opcional + anio, o la palabra 'presente'
TOKEN_FECHA = rf"(?:{MESES}\.?\s+)?{ANIO}|{PRESENTE}"
SEP_RANGO   = r"\s*(?:[-–—]|to|hasta|al|a)\s*"
RANGO_RE    = re.compile(rf"({TOKEN_FECHA}){SEP_RANGO}({TOKEN_FECHA})", re.IGNORECASE)

# Senal academica en el NOMBRE de la institucion (muy fiable)
EMPRESA_ACAD = re.compile(
    r"(university|universidad|college|institute|instituto|escuela|"
    r"academy|academia|polytechnic|polit[eé]cnico|faculty|facultad)",
    re.IGNORECASE)

# Senal academica en el TITULO del grado
TITULO_ACAD = re.compile(
    r"(bachelor|master'?s?|m\.?b\.?a\b|mba|ph\.?\s?d|doctorate|licenciatura|"
    r"maestr[ií]a|b\.?eng|b\.?sc|b\.?a\b|m\.?sc|m\.?eng|diploma|\bdegree\b)",
    re.IGNORECASE)

# Palabras que NO son un nombre de persona
_NO_NOMBRE = re.compile(
    r"(curriculum|resume|cv|profile|summary|contact|experience|education|"
    r"skills|@|www|http|\d)", re.IGNORECASE)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _anio_de_token(token: str) -> Optional[int]:
    if re.search(PRESENTE, token, re.IGNORECASE):
        return datetime.now().year
    m = re.search(ANIO, token)
    return int(m.group(0)) if m else None


def _detectar_nombre(lineas: List[str]) -> Optional[str]:
    """El nombre suele ser la primera linea con 2-4 palabras capitalizadas."""
    for linea in lineas[:6]:
        t = linea.strip()
        if not t or len(t) > 45 or _NO_NOMBRE.search(t):
            continue
        palabras = t.split()
        if 2 <= len(palabras) <= 4:
            # Mayoria de palabras empiezan en mayuscula o todo en mayusculas
            cap = sum(1 for p in palabras if p[:1].isupper())
            if t.isupper() or cap >= max(2, len(palabras) - 1):
                return t
    return None


def _es_linea_contacto(t: str) -> bool:
    return bool(EMAIL_RE.search(t) or LINKEDIN_RE.search(t) or
                re.search(r"\b(phone|email|tel[eé]fono|location|ubicaci)", t, re.I))


def _es_academico(titulo: str, empresa: str) -> bool:
    if EMPRESA_ACAD.search(empresa or ""):
        return True
    if TITULO_ACAD.search(titulo or ""):
        return True
    return False


def _detectar_bloques_fechados(lineas: List[str]) -> List[Dict]:
    """
    Detecta bloques con rango de fechas (experiencia o educacion).
    El texto antes del rango es el titulo; la linea siguiente, la organizacion.
    """
    bloques = []
    for i, linea in enumerate(lineas):
        m = RANGO_RE.search(linea)
        if not m:
            continue
        titulo  = linea[:m.start()].strip(" \t|-–—:·")
        periodo = re.sub(r"\s+", " ", m.group(0)).strip()
        if not titulo and i > 0:
            titulo = lineas[i - 1].strip()

        organizacion = ""
        for j in range(i + 1, min(i + 3, len(lineas))):
            sig = lineas[j].strip()
            if sig and not RANGO_RE.search(sig):
                organizacion = sig
                break

        if titulo and len(titulo) < 90:
            bloques.append({
                "titulo": titulo,
                "empresa": organizacion[:90],
                "periodo": periodo,
            })

    # Deduplicar por titulo+periodo
    vistos, out = set(), []
    for b in bloques:
        clave = (b["titulo"].lower(), b["periodo"].lower())
        if clave not in vistos:
            vistos.add(clave)
            out.append(b)
    return out


def _detectar_experiencia_educacion(lineas: List[str]):
    """Devuelve (puestos, educacion) separando bloques laborales de academicos."""
    bloques = _detectar_bloques_fechados(lineas)

    puestos, educacion = [], []
    for b in bloques:
        if _es_academico(b["titulo"], b["empresa"]):
            org = f" — {b['empresa']}" if b["empresa"] else ""
            educacion.append(f"{b['titulo']}{org} ({b['periodo']})")
        else:
            puestos.append(b)

    # Educacion adicional sin fecha (lineas con grado/institucion, no contacto)
    ya = " ".join(educacion).lower()
    for linea in lineas:
        t = linea.strip()
        if not (8 <= len(t) <= 120) or _es_linea_contacto(t):
            continue
        if RANGO_RE.search(t):       # ya cubierto por bloques fechados
            continue
        if (TITULO_ACAD.search(t) or EMPRESA_ACAD.search(t)) and t.lower() not in ya:
            # Evitar agregar el nombre o titulos de seccion sueltos
            if len(t.split()) >= 3:
                educacion.append(t)
                ya += " " + t.lower()

    return puestos[:8], educacion[:6]


def _detectar_skills(texto: str) -> List[str]:
    """Skills tecnicas reconocibles presentes en el CV."""
    texto_n = _normalizar(texto)
    compuestos = _extraer_compuestos(texto)
    single = [t for t in TECH_SINGLE if re.search(rf"\b{re.escape(t)}\b", texto_n)]
    vistos = set()
    out = []
    for s in compuestos + single:
        if s not in vistos:
            vistos.add(s)
            out.append(s)
    return out[:25]


def _estimar_experiencia(texto: str, lineas: List[str]) -> Optional[str]:
    # 1. Buscar mencion explicita "X+ years"
    m = re.search(r"(\d{1,2})\s*\+?\s*(?:years|years\b|años|anios|yrs)\b",
                  texto, re.IGNORECASE)
    explicito = int(m.group(1)) if m else None

    # 2. Estimar por rangos de fechas (anio de inicio mas antiguo -> hoy)
    anios_inicio = []
    anio_fin_max = None
    for linea in lineas:
        for mr in RANGO_RE.finditer(linea):
            a1 = _anio_de_token(mr.group(1))
            a2 = _anio_de_token(mr.group(2))
            if a1:
                anios_inicio.append(a1)
            if a2:
                anio_fin_max = max(anio_fin_max or a2, a2)

    estimado = None
    rango_txt = None
    if anios_inicio:
        inicio = min(anios_inicio)
        fin = anio_fin_max or datetime.now().year
        estimado = max(0, fin - inicio)
        rango_txt = f"{inicio}–{fin if fin < datetime.now().year else 'presente'}"

    if explicito:
        base = f"~{explicito} años (declarado en el CV)"
        return base
    if estimado:
        return f"~{estimado} años (estimado de fechas: {rango_txt})"
    return None


# ---------------------------------------------------------------------------
# Funcion publica
# ---------------------------------------------------------------------------

_MES_NUM_P = {"jan": 1, "ene": 1, "feb": 2, "mar": 3, "apr": 4, "abr": 4, "may": 5,
              "jun": 6, "jul": 7, "aug": 8, "ago": 8, "sep": 9, "set": 9, "oct": 10,
              "nov": 11, "dec": 12, "dic": 12}


def _ym_de_token(tok: str):
    """Devuelve (año, mes) de un token de fecha, o None."""
    if re.search(PRESENTE, tok, re.IGNORECASE):
        now = datetime.now()
        return (now.year, now.month)
    m = re.search(ANIO, tok)
    if not m:
        return None
    mm = re.search(r"[a-záéíóú]+", tok.lower())
    mes = _MES_NUM_P.get(mm.group(0)[:3], 1) if mm else 1
    return (int(m.group(0)), mes)


def _detectar_gaps(lineas: List[str]) -> List[Dict]:
    """Huecos >= 6 meses entre periodos consecutivos del historial laboral."""
    periodos = []
    for linea in lineas:
        for m in RANGO_RE.finditer(linea):
            a, b = _ym_de_token(m.group(1)), _ym_de_token(m.group(2))
            if a and b and b >= a:
                periodos.append((a, b))
    periodos = sorted(set(periodos))
    gaps = []
    for i in range(len(periodos) - 1):
        fin, ini_sig = periodos[i][1], periodos[i + 1][0]
        meses = (ini_sig[0] - fin[0]) * 12 + (ini_sig[1] - fin[1])
        if meses >= 6:
            gaps.append({"desde": f"{fin[1]:02d}/{fin[0]}",
                         "hasta": f"{ini_sig[1]:02d}/{ini_sig[0]}", "meses": meses})
    return gaps[:4]


def simular_parsing(texto: str) -> Dict:
    lineas = [l.strip() for l in texto.splitlines() if l.strip()]
    texto_plano = "\n".join(lineas)

    email   = EMAIL_RE.search(texto_plano)
    tel     = PHONE_RE.search(texto_plano)
    linked  = LINKEDIN_RE.search(texto_plano)
    ubic_m  = UBIC_RE.search(texto_plano)

    ubicacion = None
    if ubic_m:
        ubicacion = ubic_m.group(1).strip()[:80]

    nombre     = _detectar_nombre(lineas)
    puestos, educacion = _detectar_experiencia_educacion(lineas)
    skills     = _detectar_skills(texto_plano)
    experiencia = _estimar_experiencia(texto_plano, lineas)

    campos = {
        "nombre":     nombre,
        "email":      email.group(0) if email else None,
        "telefono":   tel.group(0).strip() if tel else None,
        "linkedin":   linked.group(0) if linked else None,
        "ubicacion":  ubicacion,
        "experiencia": experiencia,
    }

    # Campos clave que el ATS NO pudo detectar
    etiquetas = {
        "nombre": "Nombre", "email": "Email", "telefono": "Teléfono",
        "linkedin": "LinkedIn", "ubicacion": "Ubicación",
        "experiencia": "Años de experiencia",
    }
    no_detectados = [etiquetas[k] for k, v in campos.items() if not v]
    if not puestos:
        no_detectados.append("Puestos / experiencia laboral")
    if not educacion:
        no_detectados.append("Educación")
    if not skills:
        no_detectados.append("Habilidades")

    # Score de parsing: % de campos clave extraidos
    bloques = [
        bool(campos["nombre"]), bool(campos["email"]), bool(campos["telefono"]),
        bool(campos["linkedin"]), bool(campos["experiencia"]),
        bool(puestos), bool(educacion), bool(skills),
    ]
    score = int(round(sum(bloques) / len(bloques) * 100))

    if score >= 85:
        resumen = "El ATS lee tu CV casi a la perfección. Tus datos llegarán completos al reclutador."
    elif score >= 60:
        resumen = "El ATS extrae lo esencial, pero faltan campos. Revisa lo marcado en rojo."
    else:
        resumen = "El ATS pierde información importante de tu CV. Corrige el formato y los encabezados."

    return {
        "score": score,
        "resumen": resumen,
        "campos": campos,
        "puestos": puestos,
        "educacion": educacion,
        "skills": skills,
        "no_detectados": no_detectados,
        "gaps": _detectar_gaps(lineas),
    }
