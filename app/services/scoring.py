"""
Score compuesto CV vs vacante — 5 dimensiones con pesos fijos (total 100).

A diferencia del score anterior (casi 100% % de keywords), este reparte el
puntaje en áreas accionables, de modo que el candidato vea QUÉ mejorar y no
pueda obtener 100 solo listando keywords sin contexto.

  1. Keywords match        35   (hard %, soft %, cargo en resumen, kw en resumen)
  2. Formato ATS           20   (sin tablas, longitud, fechas, sin foto, chars)
  3. Estructura/secciones  20   (resumen, experiencia, educación, skills, email, tel)
  4. Calidad de contenido  15   (métricas, verbos de acción, sin relleno)
  5. Cargo objetivo        10   (título exacto / parcial)

Devuelve {"total": int, "dimensiones": [ {nombre, puntos, max, checks:[...]} ]}.
"""

import re
from typing import Dict, List

from app.services.adaptador import (
    _segmentar_secciones, _titulo_en_cv, norm_alias, _kw_cubierta, _normalizar,
)
from app.services.parser_ats import EMAIL_RE, PHONE_RE, LINKEDIN_RE
from app.services.mejorador_bullets import tiene_metrica


# ---------------------------------------------------------------------------
# Diccionarios auxiliares
# ---------------------------------------------------------------------------

SOFT_SKILLS = {
    "communication", "comunicacion", "comunicación", "leadership", "liderazgo",
    "teamwork", "trabajo en equipo", "problem solving", "resolucion de problemas",
    "resolución de problemas", "adaptability", "adaptabilidad", "creativity",
    "creatividad", "time management", "gestion del tiempo", "gestión del tiempo",
    "collaboration", "colaboracion", "colaboración", "critical thinking",
    "pensamiento critico", "pensamiento crítico", "negotiation", "negociacion",
    "negociación", "empathy", "empatia", "empatía", "organization", "organizacion",
    "organización", "proactividad", "proactive", "flexibility", "flexibilidad",
    "analytical", "analitico", "analítico", "attention to detail", "detail oriented",
    "interpersonal", "presentation", "mentoring", "mentoria", "mentoría",
    "autonomia", "autonomía", "self-motivated", "resiliencia", "resilience",
    "gestion del cambio", "gestión del cambio", "change management",
    "toma de decisiones", "decision making", "resolucion de conflictos",
    "resolución de conflictos", "conflict resolution", "orientacion a resultados",
    "orientación a resultados", "results oriented", "atencion al cliente",
    "atención al cliente", "customer service", "pensamiento estrategico",
    "pensamiento estratégico", "strategic thinking", "trabajo bajo presion",
    "trabajo bajo presión", "gestion de equipos", "gestión de equipos",
    "team management", "stakeholder management",
}

_FRASES_RELLENO = re.compile(
    r"\b(responsable de|encargad[oa] de|ayud[eé] a|particip[eé]|colabor[eé] en|"
    r"responsible for|helped(\s+to)?\b|assisted (with|in)|worked on|in charge of|"
    r"tareas (como|de)|funciones de|duties includ|a cargo de)",
    re.IGNORECASE)

_VERBO_ACCION = re.compile(
    r"^\s*[-•*–·]?\s*(led|managed|built|created|designed|developed|implemented|"
    r"reduced|increased|improved|launched|delivered|drove|optimized|achieved|"
    r"resolved|analyzed|coordinated|automated|spearheaded|streamlined|executed|"
    r"detected|mitigated|investigated|deployed|configured|engineered|orchestrated|"
    r"lider[eé]|gestion[eé]|desarroll[eé]|implement[eé]|dise[ñn][eé]|reduj|"
    r"aument[eé]|mejor[eé]|cre[eé]|coordin[eé]|logr[eé]|optimic[eé]|automatic[eé]|"
    r"dirig[ií]|ejecut[eé]|analic[eé]|construi)",
    re.IGNORECASE)

# Fecha en formato estándar "Mes AAAA"
_FECHA_MES = re.compile(
    r"\b(jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec|ene|abr|ago|dic)\.?\s+\d{4}",
    re.IGNORECASE)
_FECHA_MALA = re.compile(r"\b(0?[1-9]|1[0-2])[/-](19|20)\d{2}\b|'\d{2}\b")

# Caracteres problemáticos para ATS
_CHARS_RAROS = re.compile(r"[‘’“”•▪●—"
                          r"\U0001F300-\U0001FAFF]")
# Señales de tablas/columnas en texto plano (box-drawing y tabs múltiples).
# El pipe ASCII '|' NO se incluye aquí: una sola línea de contacto
# "Email | Tel | Ciudad" no es una tabla — eso se mide por nº de líneas con pipes.
_TABLA_SIGNS = re.compile(r"[│┃]|[─━]{3,}|\t{2,}")


def _bullets_de(cv_texto: str, secciones: Dict[str, List[str]]) -> List[str]:
    """Líneas de la sección Experiencia (o líneas con pinta de logro como respaldo)."""
    exp = secciones.get("experiencia", [])
    if exp:
        return [l for l in exp if len(l.strip()) > 20]
    return [l.strip() for l in cv_texto.splitlines() if len(l.strip()) > 30]


# ---------------------------------------------------------------------------
# Dimensiones
# ---------------------------------------------------------------------------

def _peso_posicion(kw: str, secciones) -> float:
    """
    Peso de una keyword según DÓNDE aparece (los ATS ponderan la posición):
    en el resumen/título 1.5x, en experiencia 1.0x, solo en habilidades 0.7x.
    """
    if _kw_cubierta(norm_alias(" ".join(secciones.get("resumen", []))), kw):
        return 1.5
    if _kw_cubierta(norm_alias(" ".join(secciones.get("experiencia", []))), kw):
        return 1.0
    if _kw_cubierta(norm_alias(" ".join(secciones.get("habilidades", []))), kw):
        return 0.7
    return 1.0


def _dim_keywords(cv: str, vacante: str, cubiertas, sugeridas, kw_vacante,
                  titulo_vacante: str, secciones) -> Dict:
    todas = cubiertas + sugeridas
    hard = [k for k in todas if norm_alias(k) not in {norm_alias(s) for s in SOFT_SKILLS}]
    soft = [k for k in todas if norm_alias(k) in {norm_alias(s) for s in SOFT_SKILLS}]
    hard_cub = [k for k in cubiertas if k in hard]
    soft_cub = [k for k in cubiertas if k in soft]

    # Cobertura PONDERADA por posición: una keyword en el resumen vale más.
    ratio_hard = min(1.0, sum(_peso_posicion(k, secciones) for k in hard_cub) / len(hard)) if hard else 1.0
    ratio_soft = min(1.0, sum(_peso_posicion(k, secciones) for k in soft_cub) / len(soft)) if soft else 1.0
    pts_hard = round(22 * ratio_hard)
    pts_soft = round(8 * ratio_soft)

    resumen_txt = " ".join(secciones.get("resumen", []))
    resumen_alias = norm_alias(resumen_txt)
    cargo_en_resumen = bool(titulo_vacante) and _titulo_en_cv(titulo_vacante, resumen_txt)
    kw_en_resumen = sum(1 for k in cubiertas if _kw_cubierta(resumen_alias, k))

    pts_cargo = 3 if cargo_en_resumen else 0
    pts_kw_res = 2 if kw_en_resumen >= 2 else (1 if kw_en_resumen == 1 else 0)

    checks = [
        {"label": f"Hard skills cubiertas ({len(hard_cub)}/{len(hard)})",
         "pts": pts_hard, "max": 22, "ok": ratio_hard >= 0.6},
        {"label": f"Soft skills cubiertas ({len(soft_cub)}/{len(soft)})",
         "pts": pts_soft, "max": 8, "ok": ratio_soft >= 0.6},
        {"label": "Cargo objetivo mencionado en el resumen",
         "pts": pts_cargo, "max": 3, "ok": cargo_en_resumen},
        {"label": "Keywords presentes en el resumen (no solo en habilidades)",
         "pts": pts_kw_res, "max": 2, "ok": kw_en_resumen >= 2},
    ]
    return _empaquetar("Keywords match", checks, 35)


def _dim_formato(cv: str) -> Dict:
    n_palabras = len(cv.split())
    # Tabla real = box-drawing/tabs, o pipes en 3+ líneas (no solo el contacto)
    lineas_pipe = sum(1 for l in cv.splitlines() if l.count("|") >= 2)
    sin_tabla = (not _TABLA_SIGNS.search(cv)) and lineas_pipe < 3
    long_ok = 300 <= n_palabras <= 800
    long_cerca = 200 <= n_palabras <= 1000
    hay_fecha_buena = bool(_FECHA_MES.search(cv))
    hay_fecha_mala = bool(_FECHA_MALA.search(cv))
    sin_foto = not re.search(r"\b(foto|photo|photograph|imagen de perfil)\b", cv, re.I)
    sin_chars = not _CHARS_RAROS.search(cv)

    if hay_fecha_buena and not hay_fecha_mala:
        pts_fecha = 5
    elif hay_fecha_buena:
        pts_fecha = 3
    elif not hay_fecha_mala:
        pts_fecha = 3   # no hay fechas detectables: neutral
    else:
        pts_fecha = 1

    checks = [
        {"label": "Sin tablas / columnas / gráficos", "pts": 5 if sin_tabla else 0,
         "max": 5, "ok": sin_tabla},
        {"label": f"Longitud adecuada ({n_palabras} palabras, ideal 300-800)",
         "pts": 5 if long_ok else (3 if long_cerca else 0), "max": 5, "ok": long_ok},
        {"label": "Fechas en formato estándar (Mes AAAA)", "pts": pts_fecha,
         "max": 5, "ok": pts_fecha >= 5},
        {"label": "Sin foto en el CV", "pts": 3 if sin_foto else 0, "max": 3, "ok": sin_foto},
        {"label": "Sin caracteres especiales problemáticos",
         "pts": 2 if sin_chars else 0, "max": 2, "ok": sin_chars},
    ]
    return _empaquetar("Formato ATS", checks, 20)


def _dim_estructura(cv: str, secciones) -> Dict:
    resumen_palabras = len(" ".join(secciones.get("resumen", [])).split())
    tiene_resumen = resumen_palabras > 30
    tiene_exp = bool(secciones.get("experiencia"))
    tiene_edu = bool(secciones.get("educacion"))
    tiene_hab = bool(secciones.get("habilidades"))
    tiene_email = bool(EMAIL_RE.search(cv))
    tiene_tel = bool(PHONE_RE.search(cv))

    checks = [
        {"label": "Sección Resumen/Perfil (>30 palabras)", "pts": 5 if tiene_resumen else 0,
         "max": 5, "ok": tiene_resumen},
        {"label": "Sección Experiencia", "pts": 4 if tiene_exp else 0, "max": 4, "ok": tiene_exp},
        {"label": "Sección Educación", "pts": 3 if tiene_edu else 0, "max": 3, "ok": tiene_edu},
        {"label": "Sección Habilidades", "pts": 3 if tiene_hab else 0, "max": 3, "ok": tiene_hab},
        {"label": "Email de contacto", "pts": 3 if tiene_email else 0, "max": 3, "ok": tiene_email},
        {"label": "Teléfono de contacto", "pts": 2 if tiene_tel else 0, "max": 2, "ok": tiene_tel},
    ]
    return _empaquetar("Estructura y secciones", checks, 20)


def _hay_keyword_stuffing(cv: str) -> bool:
    """True si hay >2 líneas que son listas de keywords sin verbo ni contexto."""
    verbo_ini = re.compile(
        r"^\s*(lider|gest|desar|implement|optim|dise|constru|analiz|coordin|"
        r"led|managed|built|developed|created|designed)", re.IGNORECASE)
    stuffed = 0
    for linea in cv.split("\n"):
        palabras = [w for w in re.split(r"[\s,;|]+", linea.strip()) if len(w) > 2]
        if len(palabras) >= 6 and "," in linea and not verbo_ini.match(linea.strip()):
            stuffed += 1
    return stuffed > 2


def _dim_contenido(cv: str, secciones) -> Dict:
    bullets = _bullets_de(cv, secciones)
    con_metrica = sum(1 for b in bullets if tiene_metrica(b))
    con_verbo = sum(1 for b in bullets if _VERBO_ACCION.match(b))
    rellenos = len(_FRASES_RELLENO.findall(cv))
    ratio_verbo = con_verbo / len(bullets) if bullets else 0
    stuffing = _hay_keyword_stuffing(cv)

    pts_metrica = 6 if con_metrica >= 2 else (3 if con_metrica == 1 else 0)
    pts_verbo = 5 if ratio_verbo >= 0.6 else (2 if ratio_verbo >= 0.3 else 0)
    pts_relleno = 4 if rellenos == 0 else (2 if rellenos <= 2 else 0)

    checks = [
        {"label": f"Logros con métricas numéricas ({con_metrica})", "pts": pts_metrica,
         "max": 6, "ok": con_metrica >= 2},
        {"label": "Verbos de acción al inicio de los logros", "pts": pts_verbo,
         "max": 5, "ok": ratio_verbo >= 0.6},
        {"label": f"Sin frases de relleno ({rellenos} detectadas)", "pts": pts_relleno,
         "max": 4, "ok": rellenos == 0},
    ]
    if stuffing:
        checks.append({"label": "Keyword stuffing detectado (penalización -5)",
                       "pts": -5, "max": 0, "ok": False})
    return _empaquetar("Calidad de contenido", checks, 15)


def _dim_cargo(cv: str, titulo_vacante: str) -> Dict:
    pts, ok, label = 0, False, "Cargo objetivo no detectado en la vacante"
    if titulo_vacante:
        # Núcleo del rol: corta en conectores (with/para/de…) y deja máx. 4 palabras
        nucleo = re.split(r"\b(with|using|that|who|para|en|de|con)\b|,",
                          titulo_vacante, maxsplit=1, flags=re.IGNORECASE)[0].strip()
        nucleo = " ".join(nucleo.split()[:4])
        objetivo = nucleo if len(nucleo.split()) >= 2 else titulo_vacante
        if _titulo_en_cv(objetivo, cv) or _titulo_en_cv(titulo_vacante, cv):
            pts, ok, label = 10, True, f"Título «{objetivo}» presente en el CV"
        else:
            palabras = [p for p in _normalizar(objetivo).split() if len(p) > 2]
            cv_n = _normalizar(cv)
            presentes = sum(1 for p in palabras if re.search(rf"(?<![a-z]){re.escape(p)}", cv_n))
            if palabras and presentes / len(palabras) >= 0.6:
                pts, ok, label = 5, False, f"Coincidencia parcial del cargo «{objetivo}»"
            else:
                label = f"El cargo «{objetivo}» no aparece en el CV"
    checks = [{"label": label, "pts": pts, "max": 10, "ok": ok}]
    return _empaquetar("Cargo objetivo", checks, 10)


def _empaquetar(nombre: str, checks: List[Dict], maximo: int) -> Dict:
    puntos = max(0, min(maximo, sum(c["pts"] for c in checks)))
    return {"nombre": nombre, "puntos": puntos, "max": maximo, "checks": checks}


# ---------------------------------------------------------------------------
# Datos estructurados para el response del API
# ---------------------------------------------------------------------------

_STOP_REP = {
    "de", "la", "el", "en", "y", "a", "que", "los", "las", "con", "por", "para",
    "un", "una", "su", "sus", "se", "es", "son", "fue", "era", "al", "del", "lo",
    "the", "and", "for", "with", "that", "this", "from", "were", "was", "have",
}


def _palabras_repetidas(cv: str) -> List[str]:
    freq: Dict[str, int] = {}
    for w in re.findall(r"[a-záéíóúñü]{4,}", cv.lower()):
        if w not in _STOP_REP:
            freq[w] = freq.get(w, 0) + 1
    rep = sorted([(w, c) for w, c in freq.items() if c >= 4], key=lambda x: -x[1])
    return [f"{w} x{c}" for w, c in rep[:6]]


def _datos_estructurados(cv: str, vacante: str, cubiertas: List[str],
                         sugeridas: List[str], secciones) -> Dict:
    soft_norm = {norm_alias(s) for s in SOFT_SKILLS}
    hard_cub = [k for k in cubiertas if norm_alias(k) not in soft_norm]
    hard_fal = [k for k in sugeridas if norm_alias(k) not in soft_norm]

    # Soft skills: las que pide la vacante, clasificadas por presencia en el CV
    # (el extractor de keywords solo captura skills técnicas, no soft).
    cv_alias, vac_alias = norm_alias(cv), norm_alias(vacante)
    soft_cub, soft_fal, vistos = [], [], set()
    for s in sorted(SOFT_SKILLS):
        sn = norm_alias(s)
        if sn in vistos or not _kw_cubierta(vac_alias, s):
            continue
        vistos.add(sn)
        (soft_cub if _kw_cubierta(cv_alias, s) else soft_fal).append(s)

    bullets = _bullets_de(cv, secciones)
    n_palabras = len(cv.split())
    return {
        "hard_cubiertas": hard_cub,
        "soft_cubiertas": soft_cub,
        "hard_faltantes": hard_fal,
        "soft_faltantes": soft_fal,
        "contact_info": {
            "email_found": bool(EMAIL_RE.search(cv)),
            "phone_found": bool(PHONE_RE.search(cv)),
            "linkedin_found": bool(LINKEDIN_RE.search(cv)),
        },
        "content_signals": {
            "metrics_count": sum(1 for b in bullets if tiene_metrica(b)),
            "weak_verbs_detected": len(_FRASES_RELLENO.findall(cv)),
            "word_count": n_palabras,
            "estimated_pages": round(n_palabras / 400, 1),
            "dates_without_format": len(_FECHA_MALA.findall(cv)),
            "repeated_words": _palabras_repetidas(cv),
            "has_summary_section": bool(secciones.get("resumen")),
            "has_experience_section": bool(secciones.get("experiencia")),
            "has_education_section": bool(secciones.get("educacion")),
            "has_skills_section": bool(secciones.get("habilidades")),
        },
    }


# ---------------------------------------------------------------------------
# Función pública
# ---------------------------------------------------------------------------

def calcular_score_compuesto(cv: str, vacante: str, cubiertas: List[str],
                             sugeridas: List[str], kw_vacante: List[str],
                             titulo_vacante: str) -> Dict:
    secciones = _segmentar_secciones(cv)
    dims = [
        _dim_keywords(cv, vacante, cubiertas, sugeridas, kw_vacante, titulo_vacante, secciones),
        _dim_formato(cv),
        _dim_estructura(cv, secciones),
        _dim_contenido(cv, secciones),
        _dim_cargo(cv, titulo_vacante),
    ]
    total = sum(d["puntos"] for d in dims)
    resultado = {"total": max(0, min(100, total)), "dimensiones": dims}
    resultado.update(_datos_estructurados(cv, vacante, cubiertas, sugeridas, secciones))
    return resultado
