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
# "Ciudad, ST" / "Ciudad, País" sin etiqueta (típico en la línea de contacto):
# "New York, NY", "San Francisco, CA", "Madrid, España", "Lima, Perú".
CIUDAD_RE   = re.compile(
    r"\b([A-ZÁÉÍÓÚÑ][a-záéíóúñ.]+(?:\s+[A-ZÁÉÍÓÚÑ][a-záéíóúñ.]+){0,2}),\s*"
    r"([A-Z]{2}|[A-ZÁÉÍÓÚ][a-záéíóúñ]{2,})\b")

# Nombres de mes completos PRIMERO (para que "January 2021" no caiga a solo "2021").
MESES = (r"(?:january|february|march|april|june|july|august|september|october|"
         r"november|december|"
         r"enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|"
         r"setiembre|octubre|noviembre|diciembre|"
         r"jan|feb|mar|apr|may|jun|jul|aug|sept|sep|oct|nov|dec|"
         r"ene|abr|ago|dic)")
ANIO   = r"(?:19|20)\d{2}"
PRESENTE = r"(?:actualidad|presente|present|actual|currently|current|now|hoy|ongoing|to\s*date)"

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


def _es_bullet(t: str) -> bool:
    """Línea que es una responsabilidad/logro (viñeta o frase), no un dato corto."""
    t = t.strip()
    if re.match(r"^[\-\*•·▪◦]", t):
        return True
    # Frase larga o terminada en punto => responsabilidad, no nombre de empresa
    if len(t) > 55 or t.endswith("."):
        return True
    return False


def _split_titulo_empresa(cabecera: str):
    """
    Separa "Cargo - Empresa", "Cargo | Empresa", "Cargo at Empresa",
    "Cargo en Empresa" en (titulo, empresa). Si no hay separador, empresa="".
    No parte guiones internos de palabras (Co-Founder) porque exige espacios.
    """
    cab = cabecera.strip(" \t|-–—:·,")
    partes = re.split(r"\s+[-–—|]\s+|\s+(?:at|en)\s+", cab, maxsplit=1)
    titulo = partes[0].strip(" \t|-–—:·,")
    empresa = partes[1].strip(" \t|-–—:·,") if len(partes) > 1 else ""
    return titulo, empresa


def _detectar_bloques_fechados(lineas: List[str]) -> List[Dict]:
    """
    Detecta bloques con rango de fechas (experiencia o educacion).
    El texto antes del rango es el titulo (y, tras un separador, la empresa);
    si la empresa no viene en la misma línea, se busca en la siguiente línea
    que NO sea una viñeta/responsabilidad ni datos de contacto.
    """
    bloques = []
    for i, linea in enumerate(lineas):
        m = RANGO_RE.search(linea)
        if not m:
            continue
        cabecera = linea[:m.start()].strip(" \t|-–—:·,")
        periodo  = re.sub(r"\s+", " ", m.group(0)).strip()
        if not cabecera and i > 0:
            cabecera = lineas[i - 1].strip()

        titulo, organizacion = _split_titulo_empresa(cabecera)

        # Si la empresa no estaba junto al cargo, buscarla en la línea siguiente
        # que sea un nombre corto (no viñeta, no responsabilidad, no contacto).
        if not organizacion:
            for j in range(i + 1, min(i + 3, len(lineas))):
                sig = lineas[j].strip()
                if not sig or RANGO_RE.search(sig):
                    continue
                if _es_bullet(sig) or _es_linea_contacto(sig):
                    break
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
        # "Location: New York, NY | Phone: ..." -> quedarnos con la ciudad
        mc = CIUDAD_RE.search(ubicacion)
        if mc:
            ubicacion = mc.group(0).strip()
    else:
        # Ciudad sin etiqueta en la zona de contacto (primeras líneas):
        # "… | New York, NY". Solo se busca ahí para evitar falsos positivos
        # tipo "Python, FastAPI" en la línea de skills.
        for l in lineas[:6]:
            if EMAIL_RE.search(l) or LINKEDIN_RE.search(l) or PHONE_RE.search(l) or "|" in l:
                mc = CIUDAD_RE.search(l)
                if mc:
                    ubicacion = mc.group(0).strip()[:80]
                    break

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
