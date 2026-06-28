"""
Analizador único de CV — la ÚNICA fuente de verdad.

`analizar_cv(cv, vacante="")` devuelve un objeto normalizado que TODAS las vistas
(Adaptar, Análisis ATS, Checklist, 15 Métricas) proyectan sin recalcular nada.
Así el mismo CV produce los mismos números en las 4 pestañas.

Decisiones clave (lo que antes se contradecía):
- Detección de secciones (`detectar_secciones`): una sección está PRESENTE si tiene
  encabezado conocido O si hay evidencia de contenido (rango de fechas → experiencia,
  grado/institución → educación, lista de skills → habilidades, párrafo → resumen).
  Antes: Adaptar exigía encabezado (estricto) y el Checklist buscaba la palabra en
  cualquier parte (laxo) → resultados opuestos.
- Calidad (`calcular_calidad`): una sola fórmula de impacto/verbos/legibilidad.
- Score global: Σ de los 5 sub-scores con pesos de core.constantes (fórmula explícita).
"""

import re
from typing import Dict, List, Optional, Tuple

from app.core import constantes as K
from app.services.adaptador import (
    _keywords_de, _analizar_cobertura, _detectar_titulo_vacante, _titulo_en_cv,
    norm_alias, _kw_cubierta, _normalizar,
)
from app.services.parser_ats import (
    EMAIL_RE, PHONE_RE, LINKEDIN_RE, RANGO_RE, TITULO_ACAD, EMPRESA_ACAD,
    simular_parsing, _detectar_skills,
)
from app.services.mejorador_bullets import tiene_metrica


# ---------------------------------------------------------------------------
# Segmentación y detección de secciones (CANÓNICA)
# ---------------------------------------------------------------------------

def _segmentar(cv: str) -> Dict[str, List[str]]:
    """{tipo: [líneas]} por encabezados de core.HEADERS_SECCION. 'encabezado' = previo."""
    secciones: Dict[str, List[str]] = {"encabezado": []}
    actual = "encabezado"
    for linea in cv.splitlines():
        s = linea.strip().rstrip(":").strip()
        tipo = None
        if s and len(s) < 50:
            for t, pat in K.HEADERS_SECCION.items():
                if pat.match(s):
                    tipo = t
                    break
        if tipo:
            actual = tipo
            secciones.setdefault(actual, [])
        elif linea.strip():
            secciones.setdefault(actual, []).append(linea.strip())
    return secciones


def _secciones_y_seg(cv: str) -> Tuple[Dict[str, bool], Dict[str, List[str]]]:
    seg = _segmentar(cv)
    pres = {t: bool(seg.get(t)) for t in
            ("contacto", "resumen", "experiencia", "educacion", "habilidades")}

    # Inferencia por contenido cuando no hay encabezado explícito.
    if not pres["contacto"]:
        pres["contacto"] = bool(EMAIL_RE.search(cv) or PHONE_RE.search(cv) or LINKEDIN_RE.search(cv))
    if not pres["experiencia"]:
        pres["experiencia"] = any(RANGO_RE.search(l) for l in cv.splitlines())
    if not pres["educacion"]:
        pres["educacion"] = bool(TITULO_ACAD.search(cv) or EMPRESA_ACAD.search(cv))
    if not pres["habilidades"]:
        pres["habilidades"] = len(_detectar_skills(cv)) >= K.SKILLS_MIN_PARA_SECCION

    # Resumen presente si HAY un encabezado reconocido (Resumen/Perfil/Summary/…) con
    # algo de contenido —sin exigir longitud mínima— o, si no hay título, un párrafo
    # de presentación bajo el nombre con sustancia (>30 palabras).
    resumen_palabras = len(" ".join(seg.get("resumen", [])).split())
    enc_palabras = len(" ".join(seg.get("encabezado", [])).split())
    pres["resumen"] = (bool(seg.get("resumen"))
                       or resumen_palabras > K.RESUMEN_MIN_PALABRAS
                       or enc_palabras > K.RESUMEN_MIN_PALABRAS + 5)
    return pres, seg


def detectar_secciones(cv: str) -> Dict[str, bool]:
    """Presencia canónica de las 5 secciones clave (header O contenido)."""
    return _secciones_y_seg(cv)[0]


def estado_secciones(cv: str) -> Dict[str, str]:
    """
    Estado de cada sección, para dar recomendaciones DISTINTAS:
      'encabezado' — tiene un título estándar reconocible.
      'contenido'  — presente por su contenido pero SIN encabezado claro
                     (p.ej. lista de tecnologías sin el título «Habilidades»).
      'ausente'    — no se detecta ni por título ni por contenido.
    """
    pres, seg = _secciones_y_seg(cv)
    estado = {}
    for t in ("contacto", "resumen", "experiencia", "educacion", "habilidades"):
        if not pres[t]:
            estado[t] = "ausente"
        elif seg.get(t):
            estado[t] = "encabezado"
        else:
            estado[t] = "contenido"
    return estado


# ---------------------------------------------------------------------------
# Calidad de contenido (CANÓNICA)
# ---------------------------------------------------------------------------

_STOP_REP = {
    "de", "la", "el", "en", "y", "a", "que", "los", "las", "con", "por", "para",
    "un", "una", "su", "sus", "se", "es", "son", "fue", "era", "al", "del", "lo",
    "the", "and", "for", "with", "that", "this", "from", "were", "was", "have",
    "has", "had", "are", "our", "your", "their",
}


def _palabras_repetidas(cv: str) -> List[str]:
    freq: Dict[str, int] = {}
    for w in re.findall(r"[a-záéíóúñü]{4,}", cv.lower()):
        if w not in _STOP_REP:
            freq[w] = freq.get(w, 0) + 1
    rep = sorted([(w, c) for w, c in freq.items() if c >= 4], key=lambda x: -x[1])
    return [f"{w} x{c}" for w, c in rep[:6]]


def unidades_logro(cv: str, seg: Optional[Dict[str, List[str]]] = None) -> List[str]:
    """
    Segmenta el CV en 'unidades de logro' por LÍNEAS **y** por ORACIONES — funciona
    con viñetas, prosa, saltos de línea y separadores variados (no solo "-"/"•").

    Usa la sección Experiencia si existe; si no (CV en prosa sin encabezados), el
    cuerpo, excluyendo encabezados de sección y líneas de contacto. Así las métricas
    de impacto/bullets y «Mejorar bullets» dejan de devolver N/A con CVs en prosa.
    """
    if seg is None:
        seg = _segmentar(cv)
    if seg.get("experiencia"):
        fuente = list(seg["experiencia"])
    else:
        fuente = []
        for raw in cv.splitlines():
            s = raw.strip()
            if not s:
                continue
            if len(s) < 50 and any(p.match(s.rstrip(":")) for p in K.HEADERS_SECCION.values()):
                continue  # encabezado de sección
            if EMAIL_RE.search(s) or PHONE_RE.search(s) or LINKEDIN_RE.search(s):
                continue  # línea de contacto
            fuente.append(s)

    out: List[str] = []
    for linea in fuente:
        base = re.sub(r"^[\s\-–—•·*▪●○‣◦]+", "", linea).strip()
        for frag in re.split(r"(?<=[.;])\s+", base):   # partir por oraciones
            f = frag.strip(" \t-–—•·")
            if 15 <= len(f) <= 300:
                out.append(f)
    return out


def _bullets_de(cv: str, seg: Dict[str, List[str]]) -> List[str]:
    return unidades_logro(cv, seg)


def bullets_de(cv: str) -> List[str]:
    """Vista pública de las unidades de logro del CV (para otras pestañas)."""
    return unidades_logro(cv)


def _hay_keyword_stuffing(cv: str) -> bool:
    """True si hay >2 líneas que son listas de keywords sin verbo ni contexto."""
    stuffed = 0
    for linea in cv.split("\n"):
        palabras = [w for w in re.split(r"[\s,;|]+", linea.strip()) if len(w) > 2]
        if len(palabras) >= 6 and "," in linea and not K.VERBO_ACCION.match(linea.strip()):
            stuffed += 1
    return stuffed > 2


def calcular_calidad(cv: str, seg: Optional[Dict[str, List[str]]] = None) -> Dict:
    """Sub-métricas de calidad ÚNICAS para todas las vistas."""
    if seg is None:
        seg = _segmentar(cv)
    bullets = _bullets_de(cv, seg)
    n = len(bullets)
    con_metrica = sum(1 for b in bullets if tiene_metrica(b))
    con_verbo = sum(1 for b in bullets if K.VERBO_ACCION.match(b))
    relleno = len(K.FRASES_RELLENO.findall(cv))
    repetidas = _palabras_repetidas(cv)
    ratio_verbo = (con_verbo / n) if n else 0.0
    impacto = round(con_metrica / n * 100) if n else 0
    fuerza = round(ratio_verbo * 100)
    legibilidad = max(0, 100 - min(40, relleno * 8) - min(20, len(repetidas) * 4))
    return {
        "bullets_total": n,
        "con_metrica": con_metrica,
        "con_verbo": con_verbo,
        "ratio_verbo": round(ratio_verbo, 2),
        "relleno": relleno,
        "stuffing": _hay_keyword_stuffing(cv),
        "repetidas": repetidas,
        "impacto": impacto,            # % de bullets con métrica real
        "fuerza_bullets": fuerza,      # % de bullets con verbo de acción
        "legibilidad": legibilidad,    # 0-100, mayor = más claro
    }


# ---------------------------------------------------------------------------
# Formato / riesgo (CANÓNICO)
# ---------------------------------------------------------------------------

def calcular_formato(cv: str) -> Dict:
    """Señales de formato ATS + score 0-100 (mayor = más seguro) + riesgos."""
    n = len(cv.split())
    lineas_pipe = sum(1 for l in cv.splitlines() if l.count("|") >= 2)
    sin_tabla = (not K.TABLA_SIGNS.search(cv)) and lineas_pipe < 3
    long_ok = 300 <= n <= 800
    long_cerca = K.PALABRAS_MIN <= n <= 1000
    hay_fecha_buena = bool(K.FECHA_MES.search(cv))
    hay_fecha_mala = bool(K.FECHA_MALA.search(cv))
    sin_chars = not K.CHARS_RAROS.search(cv)
    sin_foto = not re.search(r"\b(foto|photo|photograph|imagen de perfil)\b", cv, re.I)

    riesgos = []
    if not sin_tabla:
        riesgos.append("tablas o columnas (el ATS las desordena)")
    if not (long_ok or long_cerca):
        riesgos.append(f"longitud fuera de rango ({n} palabras, ideal 300-800)")
    if hay_fecha_mala and not hay_fecha_buena:
        riesgos.append("fechas numéricas (usa «Mes AAAA»)")
    if not sin_chars:
        riesgos.append("caracteres especiales (•, comillas tipográficas, emojis)")
    if not sin_foto:
        riesgos.append("foto/imagen en el CV")

    return {
        "sin_tabla": sin_tabla, "long_ok": long_ok, "long_cerca": long_cerca,
        "hay_fecha_buena": hay_fecha_buena, "hay_fecha_mala": hay_fecha_mala,
        "sin_chars": sin_chars, "sin_foto": sin_foto, "lineas_pipe": lineas_pipe,
        "palabras": n, "riesgos": riesgos,
    }


# ---------------------------------------------------------------------------
# Dimensiones del score (5) — usan secciones/calidad/formato canónicos
# ---------------------------------------------------------------------------

def _empaquetar(nombre: str, checks: List[Dict], maximo: int) -> Dict:
    puntos = max(0, min(maximo, sum(c["pts"] for c in checks)))
    return {"nombre": nombre, "puntos": puntos, "max": maximo, "checks": checks}


def _peso_posicion(kw: str, seg) -> float:
    if _kw_cubierta(norm_alias(" ".join(seg.get("resumen", []))), kw):
        return 1.5
    if _kw_cubierta(norm_alias(" ".join(seg.get("experiencia", []))), kw):
        return 1.0
    if _kw_cubierta(norm_alias(" ".join(seg.get("habilidades", []))), kw):
        return 0.7
    return 1.0


def _dim_keywords(cv, vacante, cubiertas, sugeridas, kw_vacante, titulo_vacante, seg) -> Dict:
    soft_norm = {norm_alias(s) for s in K.SOFT_SKILLS}
    hard = [k for k in kw_vacante if norm_alias(k) not in soft_norm]
    soft = [k for k in kw_vacante if norm_alias(k) in soft_norm]
    hard_cub = [k for k in cubiertas if norm_alias(k) not in soft_norm]
    soft_cub = [k for k in cubiertas if norm_alias(k) in soft_norm]
    ratio_hard = min(1.0, sum(_peso_posicion(k, seg) for k in hard_cub) / len(hard)) if hard else 1.0
    ratio_soft = min(1.0, sum(_peso_posicion(k, seg) for k in soft_cub) / len(soft)) if soft else 1.0
    resumen_txt = " ".join(seg.get("resumen", []))
    cargo_en_resumen = bool(titulo_vacante) and _titulo_en_cv(titulo_vacante, resumen_txt)
    kw_en_resumen = sum(1 for k in hard_cub if _kw_cubierta(norm_alias(resumen_txt), k))

    pts_hard = round(ratio_hard * 22)
    pts_soft = round(ratio_soft * 6)
    pts_cargo = 3 if cargo_en_resumen else 0
    pts_kwres = min(4, kw_en_resumen)
    checks = [
        {"label": f"Hard skills de la vacante cubiertas ({len(hard_cub)}/{len(hard)})",
         "pts": pts_hard, "max": 22, "ok": ratio_hard >= 0.6},
        {"label": f"Soft skills cubiertas ({len(soft_cub)}/{len(soft)})",
         "pts": pts_soft, "max": 6, "ok": ratio_soft >= 0.6},
        {"label": "Cargo objetivo mencionado en el resumen",
         "pts": pts_cargo, "max": 3, "ok": cargo_en_resumen},
        {"label": "Keywords clave presentes en el resumen",
         "pts": pts_kwres, "max": 4, "ok": kw_en_resumen >= 2},
    ]
    return _empaquetar("Keywords match", checks, K.PESOS["keywords"])


def _dim_formato(cv: str) -> Dict:
    f = calcular_formato(cv)
    if f["hay_fecha_buena"] and not f["hay_fecha_mala"]:
        pts_fecha = 5
    elif f["hay_fecha_buena"] or not f["hay_fecha_mala"]:
        pts_fecha = 3
    else:
        pts_fecha = 1
    checks = [
        {"label": "Sin tablas / columnas / gráficos", "pts": 5 if f["sin_tabla"] else 0,
         "max": 5, "ok": f["sin_tabla"]},
        {"label": f"Longitud adecuada ({f['palabras']} palabras, ideal 300-800)",
         "pts": 5 if f["long_ok"] else (3 if f["long_cerca"] else 0), "max": 5, "ok": f["long_ok"]},
        {"label": "Fechas en formato estándar (Mes AAAA)", "pts": pts_fecha,
         "max": 5, "ok": pts_fecha >= 5},
        {"label": "Sin foto en el CV", "pts": 3 if f["sin_foto"] else 0, "max": 3, "ok": f["sin_foto"]},
        {"label": "Sin caracteres especiales problemáticos",
         "pts": 2 if f["sin_chars"] else 0, "max": 2, "ok": f["sin_chars"]},
    ]
    return _empaquetar("Formato ATS", checks, K.PESOS["formato"])


def _dim_estructura(cv: str, secciones: Dict[str, bool]) -> Dict:
    P = K.ESTRUCTURA_PTS
    tiene_email = bool(EMAIL_RE.search(cv))
    tiene_tel = bool(PHONE_RE.search(cv))
    checks = [
        {"label": "Sección Resumen/Perfil (>30 palabras)",
         "pts": P["resumen"] if secciones["resumen"] else 0, "max": P["resumen"], "ok": secciones["resumen"]},
        {"label": "Sección Experiencia", "pts": P["experiencia"] if secciones["experiencia"] else 0,
         "max": P["experiencia"], "ok": secciones["experiencia"]},
        {"label": "Sección Educación", "pts": P["educacion"] if secciones["educacion"] else 0,
         "max": P["educacion"], "ok": secciones["educacion"]},
        {"label": "Sección Habilidades", "pts": P["habilidades"] if secciones["habilidades"] else 0,
         "max": P["habilidades"], "ok": secciones["habilidades"]},
        {"label": "Email de contacto", "pts": P["email"] if tiene_email else 0,
         "max": P["email"], "ok": tiene_email},
        {"label": "Teléfono de contacto", "pts": P["telefono"] if tiene_tel else 0,
         "max": P["telefono"], "ok": tiene_tel},
    ]
    return _empaquetar("Estructura y secciones", checks, K.PESOS["estructura"])


def _dim_contenido(cv: str, calidad: Dict) -> Dict:
    P = K.CONTENIDO_PTS
    con_metrica = calidad["con_metrica"]
    ratio_verbo = calidad["ratio_verbo"]
    relleno = calidad["relleno"]
    pts_metrica = P["metrica"] if con_metrica >= 2 else (3 if con_metrica == 1 else 0)
    pts_verbo = P["verbo"] if ratio_verbo >= K.RATIO_VERBO_OK else (2 if ratio_verbo >= K.RATIO_VERBO_MEDIO else 0)
    pts_relleno = P["relleno"] if relleno == 0 else (2 if relleno <= 2 else 0)
    checks = [
        {"label": f"Logros con métricas numéricas ({con_metrica})", "pts": pts_metrica,
         "max": P["metrica"], "ok": con_metrica >= 2},
        {"label": "Verbos de acción al inicio de los logros", "pts": pts_verbo,
         "max": P["verbo"], "ok": ratio_verbo >= K.RATIO_VERBO_OK},
        {"label": f"Sin frases de relleno ({relleno} detectadas)", "pts": pts_relleno,
         "max": P["relleno"], "ok": relleno == 0},
    ]
    if calidad["stuffing"]:
        checks.append({"label": f"Keyword stuffing detectado (penalización -{K.STUFFING_PENALTI})",
                       "pts": -K.STUFFING_PENALTI, "max": 0, "ok": False})
    return _empaquetar("Calidad de contenido", checks, K.PESOS["contenido"])


def _dim_cargo(cv: str, titulo_vacante: str) -> Dict:
    pts, ok, label = 0, False, "Cargo objetivo no detectado en la vacante"
    if titulo_vacante:
        nucleo = re.split(r"\b(with|using|that|who|para|en|de|con)\b|,",
                          titulo_vacante, maxsplit=1, flags=re.IGNORECASE)[0].strip()
        nucleo = " ".join(nucleo.split()[:4])
        objetivo = nucleo if len(nucleo.split()) >= 2 else titulo_vacante
        if _titulo_en_cv(objetivo, cv) or _titulo_en_cv(titulo_vacante, cv):
            pts, ok, label = K.PESOS["cargo"], True, f"Título «{objetivo}» presente en el CV"
        else:
            palabras = [p for p in _normalizar(objetivo).split() if len(p) > 2]
            cv_n = _normalizar(cv)
            presentes = sum(1 for p in palabras if re.search(rf"(?<![a-z]){re.escape(p)}", cv_n))
            if palabras and presentes / len(palabras) >= 0.6:
                pts, ok, label = 5, False, f"Coincidencia parcial del cargo «{objetivo}»"
            else:
                label = f"El cargo «{objetivo}» no aparece en el CV"
    return _empaquetar("Cargo objetivo", [{"label": label, "pts": pts, "max": K.PESOS["cargo"], "ok": ok}],
                       K.PESOS["cargo"])


# ---------------------------------------------------------------------------
# Datos estructurados + score compuesto (compat con el shape previo)
# ---------------------------------------------------------------------------

def _datos_estructurados(cv, vacante, cubiertas, sugeridas, secciones, calidad) -> Dict:
    soft_norm = {norm_alias(s) for s in K.SOFT_SKILLS}
    hard_cub = [k for k in cubiertas if norm_alias(k) not in soft_norm]
    hard_fal = [k for k in sugeridas if norm_alias(k) not in soft_norm]
    cv_alias, vac_alias = norm_alias(cv), norm_alias(vacante)
    soft_cub, soft_fal, vistos = [], [], set()
    for s in sorted(K.SOFT_SKILLS):
        sn = norm_alias(s)
        if sn in vistos or not _kw_cubierta(vac_alias, s):
            continue
        vistos.add(sn)
        (soft_cub if _kw_cubierta(cv_alias, s) else soft_fal).append(s)
    n_palabras = len(cv.split())
    return {
        "hard_cubiertas": hard_cub, "soft_cubiertas": soft_cub,
        "hard_faltantes": hard_fal, "soft_faltantes": soft_fal,
        "contact_info": {
            "email_found": bool(EMAIL_RE.search(cv)),
            "phone_found": bool(PHONE_RE.search(cv)),
            "linkedin_found": bool(LINKEDIN_RE.search(cv)),
        },
        "content_signals": {
            "metrics_count": calidad["con_metrica"],
            "weak_verbs_detected": calidad["relleno"],
            "word_count": n_palabras,
            "estimated_pages": round(n_palabras / 400, 1),
            "dates_without_format": len(K.FECHA_MALA.findall(cv)),
            "repeated_words": calidad["repetidas"],
            "has_summary_section": secciones["resumen"],
            "has_experience_section": secciones["experiencia"],
            "has_education_section": secciones["educacion"],
            "has_skills_section": secciones["habilidades"],
        },
    }


def calcular_score_compuesto(cv: str, vacante: str, cubiertas: List[str],
                             sugeridas: List[str], kw_vacante: List[str],
                             titulo_vacante: str) -> Dict:
    """Mismo contrato que antes (lo usa Adaptar), ahora derivado del core."""
    secciones, seg = _secciones_y_seg(cv)
    calidad = calcular_calidad(cv, seg)
    dims = [
        _dim_keywords(cv, vacante, cubiertas, sugeridas, kw_vacante, titulo_vacante, seg),
        _dim_formato(cv),
        _dim_estructura(cv, secciones),
        _dim_contenido(cv, calidad),
        _dim_cargo(cv, titulo_vacante),
    ]
    total = sum(d["puntos"] for d in dims)
    resultado = {"total": max(0, min(100, total)), "dimensiones": dims}
    resultado.update(_datos_estructurados(cv, vacante, cubiertas, sugeridas, secciones, calidad))
    return resultado


# ---------------------------------------------------------------------------
# Densidad / recuento de keywords (estilo Jobscan) con sinónimos y tipos
# ---------------------------------------------------------------------------

def analizar_keywords(cv: str, vacante: str = "") -> Dict:
    """
    Para cada keyword de la vacante: nº de apariciones en la vacante vs. en el CV
    (con normalización por sinónimos: JS=JavaScript, K8s=Kubernetes, AWS=Amazon Web
    Services). Clasifica en title / hard / soft / tool y marca sobreoptimización
    (keyword stuffing) cuando la frecuencia en el CV es anómalamente alta.
    Reutiliza el motor único: alias, _keywords_de y la detección de cargo.
    """
    cv = cv or ""
    vacante = vacante or ""
    n_pal = max(1, len(cv.split()))
    if not vacante.strip():
        return {"items": [], "por_tipo": {}, "sobreoptimizadas": [], "n_palabras_cv": n_pal}

    from app.services.keyword_aliases import canonicalizar, canonicalizar_texto, frecuencia
    from app.services.metricas import TOOLS
    from app.services.adaptador_docx import _formato_keyword

    cv_canon = canonicalizar_texto(cv)
    vac_canon = canonicalizar_texto(vacante)
    soft_norm = {norm_alias(s) for s in K.SOFT_SKILLS}

    candidatos: Dict[str, tuple] = {}   # canon -> (display, tipo)
    titulo = _detectar_titulo_vacante(vacante)
    if titulo:
        candidatos[canonicalizar(titulo)] = (titulo, "title")

    for kw in _keywords_de(vacante):
        canon = canonicalizar(kw)
        if canon in candidatos:
            continue
        if norm_alias(kw) in soft_norm:
            tipo = "soft"
        elif any(re.search(p, kw.lower()) for p in TOOLS.values()):
            tipo = "tool"
        else:
            tipo = "hard"
        candidatos[canon] = (_formato_keyword(kw), tipo)

    # Soft skills nombradas en la vacante (el extractor técnico no las captura).
    vac_low = vacante.lower()
    for s in sorted(K.SOFT_SKILLS):
        if re.search(r"\b" + re.escape(s.lower()) + r"\b", vac_low):
            candidatos.setdefault(canonicalizar(s), (s[:1].upper() + s[1:], "soft"))

    items = []
    for canon, (display, tipo) in candidatos.items():
        fv = frecuencia(canon, vac_canon) or 1
        fc = frecuencia(canon, cv_canon)
        # Sobreoptimización: repetida 4+ veces y muy por encima de lo que pide la vacante.
        sobre = fc >= 4 and fc > max(3, fv * 2)
        items.append({
            "keyword": display, "tipo": tipo,
            "freq_vacante": fv, "freq_cv": fc, "cubierta": fc > 0,
            "densidad": round(fc / n_pal * 100, 2), "sobreoptimizada": sobre,
        })

    orden = {"title": 0, "hard": 1, "tool": 2, "soft": 3}
    items.sort(key=lambda i: (orden.get(i["tipo"], 9), -i["freq_vacante"], i["keyword"].lower()))

    por_tipo: Dict[str, list] = {}
    for it in items:
        por_tipo.setdefault(it["tipo"], []).append(it)
    return {
        "items": items, "por_tipo": por_tipo,
        "sobreoptimizadas": [i for i in items if i["sobreoptimizada"]],
        "n_palabras_cv": n_pal,
    }


# ---------------------------------------------------------------------------
# Función pública: objeto normalizado completo (lo consume /api/v1/analyze)
# ---------------------------------------------------------------------------

def analizar_cv(cv: str, vacante: str = "") -> Dict:
    """Única fuente de verdad. Todas las pestañas proyectan ESTE objeto."""
    cv = cv or ""
    vacante = vacante or ""
    from app.services.requisitos import analizar_requisitos

    parsing = simular_parsing(cv)
    secciones, seg = _secciones_y_seg(cv)
    estado_sec = {t: ("encabezado" if seg.get(t) else "contenido") if secciones[t] else "ausente"
                  for t in ("contacto", "resumen", "experiencia", "educacion", "habilidades")}
    calidad = calcular_calidad(cv, seg)
    formato = calcular_formato(cv)
    requisitos = analizar_requisitos(cv, vacante)

    kw_vacante = _keywords_de(vacante)[:30]
    cubiertas, sugeridas = _analizar_cobertura(kw_vacante, cv)
    titulo_vacante = _detectar_titulo_vacante(vacante)
    titulo_cubierto = bool(titulo_vacante) and _titulo_en_cv(titulo_vacante, cv)

    compuesto = calcular_score_compuesto(cv, vacante, cubiertas, sugeridas, kw_vacante,
                                         titulo_vacante or "")
    dims = {d["nombre"]: d for d in compuesto["dimensiones"]}
    sub_scores = {
        "keywords":   _proj(dims["Keywords match"]),
        "formato":    _proj(dims["Formato ATS"]),
        "estructura": _proj(dims["Estructura y secciones"]),
        "contenido":  _proj(dims["Calidad de contenido"]),
        "cargo":      _proj(dims["Cargo objetivo"]),
    }
    # Score global = Σ sub-scores (cada uno ya en su escala de peso). Fórmula explícita.
    score_global = max(0, min(100, sum(s["pts"] for s in sub_scores.values())))

    return {
        "score_global": score_global,
        "parse_rate": parsing["score"],
        "secciones": secciones,
        "secciones_estado": estado_sec,
        "contacto": parsing["campos"],
        "skills": parsing["skills"],
        "requisitos": requisitos,
        "keywords": {
            "cubiertas": cubiertas, "faltantes": sugeridas,
            "hard_cubiertas": compuesto["hard_cubiertas"],
            "hard_faltantes": compuesto["hard_faltantes"],
            "soft_cubiertas": compuesto["soft_cubiertas"],
            "soft_faltantes": compuesto["soft_faltantes"],
        },
        "keywords_detalle": analizar_keywords(cv, vacante),
        "seniority": requisitos.get("seniority"),
        "calidad": calidad,
        "formato": formato,
        "cargo": {"titulo_vacante": titulo_vacante or None, "cubierto": titulo_cubierto},
        "sub_scores": sub_scores,
        "dimensiones": compuesto["dimensiones"],
    }


def _proj(dim: Dict) -> Dict:
    return {"pts": dim["puntos"], "max": dim["max"], "checks": dim["checks"]}
