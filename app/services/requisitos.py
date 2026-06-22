"""
Análisis de requisitos de la vacante vs. el CV (estilo Jobscan / EnhanceCV):
  - Brecha de años de experiencia (requeridos vs. detectados)
  - Seniority (Junior / Mid / Senior / Lead) en vacante vs. CV
  - Idiomas requeridos y si el CV los menciona
  - Nivel educativo y certificaciones requeridas vs. presentes

Módulo hoja: solo reutiliza helpers de adaptador y parser_ats.
"""

import re
from typing import Dict, List, Optional

from app.services.adaptador import norm_alias, _kw_cubierta
from app.services.parser_ats import _estimar_experiencia


# ---------------------------------------------------------------------------
# Años de experiencia
# ---------------------------------------------------------------------------

_ANIOS = re.compile(r"(\d{1,2})\s*\+?\s*(?:years?|años?|anios?|yrs?)\b", re.IGNORECASE)
_ANIOS_MIN = re.compile(
    r"(?:m[ií]nimo|al menos|at least|minimum(?:\s+of)?)\s*(?:de\s*)?(\d{1,2})",
    re.IGNORECASE)


def _anios_requeridos(vacante: str) -> Optional[int]:
    nums = [int(m.group(1)) for m in _ANIOS_MIN.finditer(vacante)]
    nums += [int(m.group(1)) for m in _ANIOS.finditer(vacante)]
    nums = [n for n in nums if 0 < n <= 40]
    return min(nums) if nums else None


def _anios_cv(cv: str, lineas: List[str]) -> Optional[int]:
    est = _estimar_experiencia(cv, lineas)
    if not est:
        return None
    m = re.search(r"(\d{1,2})", est)
    return int(m.group(1)) if m else None


# ---------------------------------------------------------------------------
# Seniority  (orden de evaluación importa: Lead → Mid → Senior → Junior)
# ---------------------------------------------------------------------------

_SENIORITY = [
    ("Lead/Principal", r"\b(lead|principal|staff|head\s+of|director|jefe|"
                       r"l[ií]der\s+t[eé]cnico)\b"),
    ("Mid",            r"\b(mid[- ]?level|semi[- ]?senior|semi[- ]?sr|\bssr\b|intermedio)\b"),
    ("Senior",         r"\b(senior|sr\.?)\b"),
    ("Junior",         r"\b(junior|jr\.?|trainee|intern(ship)?|entry[- ]?level|"
                       r"becari|practicante)\b"),
]
_ORDEN_SEN = {"Junior": 1, "Mid": 2, "Senior": 3, "Lead/Principal": 4}


def _seniority(texto: str) -> Optional[str]:
    low = texto.lower()
    for nivel, pat in _SENIORITY:
        if re.search(pat, low):
            return nivel
    return None


# ---------------------------------------------------------------------------
# Idiomas
# ---------------------------------------------------------------------------

_IDIOMAS = {
    "Inglés": r"ingl[eé]s|english", "Español": r"espa[nñ]ol|spanish",
    "Francés": r"franc[eé]s|french", "Alemán": r"alem[aá]n|german",
    "Portugués": r"portugu[eé]s|portuguese", "Italiano": r"italiano|italian",
}
_NIVEL_IDIOMA = re.compile(
    r"(nativ|native|fluid|fluent|avanzad|advanced|\bc1\b|\bc2\b|\bb2\b|biling|professional)",
    re.IGNORECASE)


def _idiomas_requeridos(vacante: str, cv: str) -> List[Dict]:
    out, vistos = [], set()
    vac_low, cv_low = vacante.lower(), cv.lower()
    for idioma, pat in _IDIOMAS.items():
        m = re.search(pat, vac_low)
        if not m or idioma in vistos:
            continue
        ctx = vac_low[max(0, m.start() - 35): m.end() + 35]
        # Solo cuenta como requisito si hay nivel o contexto de idioma
        if _NIVEL_IDIOMA.search(ctx) or "idioma" in ctx or "language" in ctx:
            vistos.add(idioma)
            out.append({"idioma": idioma, "en_cv": bool(re.search(pat, cv_low))})
    return out


# ---------------------------------------------------------------------------
# Educación y certificaciones
# ---------------------------------------------------------------------------

_NIVEL_EDU = [
    ("Doctorado", r"\bph\.?d\b|doctorad|doctorate"),
    ("Máster", r"m[aá]ster|master'?s?|\bmba\b|maestr[ií]a|m\.?sc|posgrado|postgrad"),
    ("Grado universitario", r"\bgrado\b|licenciatura|bachelor|\bdegree\b|ingenier[ií]a|"
                            r"b\.?sc|b\.?eng|t[ií]tulo\s+universitario|carrera\s+universitaria"),
]


def _nivel_educacion(texto: str) -> Optional[str]:
    low = texto.lower()
    for nivel, pat in _NIVEL_EDU:
        if re.search(pat, low):
            return nivel
    return None


_CERTS = re.compile(
    r"\b(pmp|scrum\s+master|\bcsm\b|aws\s+certified|azure\s+(?:fundamentals|administrator|"
    r"solutions)|\bccna\b|comptia|security\+|cissp|cism|\bceh\b|oscp|itil|prince2|togaf|"
    r"google\s+(?:analytics|ads)\s+certified|salesforce\s+certified|six\s+sigma)\b",
    re.IGNORECASE)


def _certificaciones(texto: str) -> List[str]:
    return sorted({re.sub(r"\s+", " ", m.group(0).strip().lower())
                   for m in _CERTS.finditer(texto)})


# ---------------------------------------------------------------------------
# Función pública
# ---------------------------------------------------------------------------

def analizar_requisitos(cv: str, vacante: str, lineas: Optional[List[str]] = None) -> Dict:
    if lineas is None:
        lineas = [l.strip() for l in cv.splitlines() if l.strip()]

    # Años
    req = _anios_requeridos(vacante)
    det = _anios_cv(cv, lineas)
    anios = None
    if req is not None:
        anios = {"requeridos": req, "detectados": det,
                 "cumple": det is not None and det >= req}

    # Seniority
    sv, sc = _seniority(vacante), _seniority(cv)
    seniority = None
    if sv:
        coincide = sc is not None and _ORDEN_SEN.get(sc, 0) >= _ORDEN_SEN.get(sv, 0)
        seniority = {"vacante": sv, "cv": sc, "coincide": coincide}

    # Idiomas
    idiomas = _idiomas_requeridos(vacante, cv)

    # Educación
    edu_req = _nivel_educacion(vacante)
    educacion = None
    if edu_req:
        edu_cv = _nivel_educacion(cv)
        educacion = {"requerido": edu_req, "cv": edu_cv, "cumple": edu_cv is not None}

    # Certificaciones
    cv_alias = norm_alias(cv)
    certs = [{"cert": c, "en_cv": _kw_cubierta(cv_alias, c)}
             for c in _certificaciones(vacante)]

    return {
        "anios": anios,
        "seniority": seniority,
        "idiomas": idiomas,
        "educacion": educacion,
        "certificaciones": certs,
    }
