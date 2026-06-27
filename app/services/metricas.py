"""
15 métricas competitivas del análisis ATS (estilo Jobscan / Enhancv / Teal).

Cada métrica es un dict uniforme:
    {id, nombre, categoria, score (0-100 | None si no aplica),
     aplica (bool), explicacion, recomendacion}

Se agrupan en 6 categorías para la UI:
    Compatibilidad ATS · Match con Vacante · Skills y Requisitos ·
    Calidad del Contenido · Formato y Riesgo · Recomendaciones Prioritarias

El módulo reutiliza los analizadores existentes (parser, requisitos, scoring)
y añade diccionarios nuevos para herramientas, metodologías y riesgo por vendor.
"""

import re
from typing import Dict, List

from app.services.adaptador import (
    _detectar_titulo_vacante, _titulo_en_cv, _keywords_de,
    _analizar_cobertura, norm_alias, TECH_SINGLE,
)
from app.services.parser_ats import simular_parsing
from app.services.requisitos import analizar_requisitos
from app.core.constantes import SOFT_SKILLS
from app.core.cv_analyzer import calcular_calidad, bullets_de, analizar_keywords
from app.services.mejorador_bullets import tiene_metrica


# Categorías (orden de presentación en la UI)
CAT_ATS      = "Compatibilidad ATS"
CAT_MATCH    = "Match con Vacante"
CAT_SKILLS   = "Skills y Requisitos"
CAT_CALIDAD  = "Calidad del Contenido"
CAT_FORMATO  = "Formato y Riesgo"
CATEGORIAS = [CAT_ATS, CAT_MATCH, CAT_SKILLS, CAT_CALIDAD, CAT_FORMATO]


# ---------------------------------------------------------------------------
# Diccionarios nuevos
# ---------------------------------------------------------------------------

TOOLS = {
    "Jira": r"\bjira\b", "Salesforce": r"\bsalesforce\b", "HubSpot": r"\bhubspot\b",
    "SAP": r"\bsap\b", "Workday": r"\bworkday\b", "ServiceNow": r"\bservicenow\b",
    "Kubernetes": r"\bkubernetes\b|\bk8s\b", "Docker": r"\bdocker\b",
    "Terraform": r"\bterraform\b", "Jenkins": r"\bjenkins\b", "Git": r"\bgit(?:hub|lab)?\b",
    "AWS": r"\baws\b|amazon web services", "Azure": r"\bazure\b", "GCP": r"\bgcp\b|google cloud",
    "Tableau": r"\btableau\b", "Power BI": r"power\s*bi", "Looker": r"\blooker\b",
    "Snowflake": r"\bsnowflake\b", "Databricks": r"\bdatabricks\b", "Excel": r"\bexcel\b",
    "Figma": r"\bfigma\b", "Zendesk": r"\bzendesk\b", "Slack": r"\bslack\b",
    "Notion": r"\bnotion\b", "Postman": r"\bpostman\b", "Grafana": r"\bgrafana\b",
    "Splunk": r"\bsplunk\b", "Confluence": r"\bconfluence\b",
}

METHODOLOGIES = {
    "Agile": r"\bagile\b|metodolog[ií]as?\s+[áa]giles?|\b[áa]gil\b", "Scrum": r"\bscrum\b",
    "Kanban": r"\bkanban\b", "DevOps": r"\bdevops\b",
    "CI/CD": r"ci\s*/?\s*cd|continuous\s+(?:integration|delivery|deployment)",
    "ITIL": r"\bitil\b", "Lean": r"\blean\b", "Six Sigma": r"six\s*sigma|6\s*sigma",
    "Waterfall": r"\bwaterfall\b|cascada", "TDD": r"\btdd\b|test[-\s]driven",
    "SAFe": r"\bsafe\b\s+(?:framework|agile)?", "XP": r"extreme\s+programming",
}

# Sensibilidad de cada ATS comercial al formato/parseo (1.0 = el más estricto).
_VENDORS = {
    "Taleo":              (1.00, "el más estricto: evita tablas, columnas y caracteres especiales"),
    "Workday":            (0.85, "sensible a multi-columna y fechas no estándar"),
    "SAP SuccessFactors": (0.85, "sensible a tablas y columnas"),
    "iCIMS":              (0.75, "sensible a formato complejo y gráficos"),
    "BambooHR":           (0.55, "tolerancia media"),
    "Greenhouse":         (0.45, "parser moderno, bastante tolerante"),
    "Lever":              (0.45, "parser moderno, bastante tolerante"),
}

# Frases vagas que restan legibilidad/impacto profesional.
_VAGAS = (
    "responsible for", "team player", "hard worker", "results-driven",
    "go-getter", "think outside the box", "various", "etc", "stuff", "things",
    "a lot of", "many", "responsable de", "varios", "diversas", "etcétera",
    "buen ambiente", "proactivo", "orientado a resultados",
)

_STOP = {"the", "and", "for", "with", "that", "this", "from", "para", "con", "los",
         "las", "del", "una", "que", "por", "como", "the", "and", "into", "your"}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _c(n) -> int:
    return max(0, min(100, int(round(n))))


def _metric(mid, nombre, categoria, score, explicacion, recomendacion) -> Dict:
    aplica = score is not None
    return {
        "id": mid, "nombre": nombre, "categoria": categoria,
        "score": (_c(score) if aplica else None), "aplica": aplica,
        "explicacion": explicacion, "recomendacion": recomendacion,
    }


def _match_dict(dic: Dict[str, str], vacante: str, cv: str):
    """Items del diccionario pedidos en la vacante y cuáles aparecen en el CV."""
    vac, cvl = vacante.lower(), cv.lower()
    pedidos = [n for n, pat in dic.items() if re.search(pat, vac)]
    presentes = [n for n in pedidos if re.search(dic[n], cvl)]
    return pedidos, presentes


def _soft_match(vacante: str, cv: str):
    vac, cvl = vacante.lower(), cv.lower()
    pedidos, presentes, vistos = [], [], set()
    for s in sorted(SOFT_SKILLS):
        pat = r"\b" + re.escape(s.lower()) + r"\b"
        if re.search(pat, vac):
            canon = norm_alias(s)
            if canon in vistos:
                continue
            vistos.add(canon)
            pedidos.append(s)
            if re.search(pat, cvl):
                presentes.append(s)
    return pedidos, presentes


def _bullets(cv: str) -> List[str]:
    # Misma detección de viñetas que el core (fuente única) → consistencia con Adaptar.
    return bullets_de(cv)


def _faltantes(pedidos, presentes) -> str:
    falt = [p for p in pedidos if p not in presentes]
    return ", ".join(falt[:8]) if falt else ""


# ---------------------------------------------------------------------------
# Métricas individuales
# ---------------------------------------------------------------------------

def _m_parse_rate(parsing: Dict) -> Dict:
    score = parsing["score"]
    faltan = ", ".join(parsing.get("no_detectados", []))
    expl = (f"El ATS puede leer ~{score}% de tus campos clave "
            f"(contacto, experiencia, empresas, fechas, educación, skills).")
    rec = (f"Revisa estos campos que no se detectaron bien: {faltan}."
           if faltan else "Tu CV se parsea correctamente. Mantén el formato de una columna.")
    return _metric("ats_parse_rate", "ATS Parse Rate", CAT_ATS, score, expl, rec)


def _m_title(cv: str, vacante: str) -> Dict:
    titulo = _detectar_titulo_vacante(vacante)
    if not titulo:
        return _metric("title_match", "Title Match", CAT_MATCH, None,
                       "No se detectó un cargo objetivo en la vacante.",
                       "Asegúrate de que la vacante incluya el título del puesto.")
    cubierto = _titulo_en_cv(titulo, cv)
    score = 100 if cubierto else 0
    expl = (f"El cargo objetivo «{titulo}» {'aparece' if cubierto else 'NO aparece'} "
            f"como tal en tu CV.")
    rec = ("Coincide. Ideal mantenerlo en el titular y el resumen."
           if cubierto else
           f"Añade «{titulo}» textualmente en tu titular o resumen para igualar el cargo.")
    return _metric("title_match", "Title Match", CAT_MATCH, score, expl, rec)


def _m_experience(req: Dict) -> Dict:
    a = req.get("anios")
    if not a:
        return _metric("experience_match", "Experience Match", CAT_MATCH, None,
                       "La vacante no especifica años de experiencia.",
                       "Sin requisito de años: enfócate en logros relevantes.")
    det = a["detectados"]
    if det is None:
        score = 40
    elif a["cumple"]:
        score = 100
    else:
        score = _c(det / a["requeridos"] * 100)
    expl = (f"La vacante pide ~{a['requeridos']} años; en tu CV se detectan "
            f"{det if det is not None else 'indeterminados'} años.")
    rec = ("Cumples el requisito de experiencia." if a["cumple"] else
           "Resalta fechas claras (Mes AAAA) y años totales en el resumen.")
    return _metric("experience_match", "Experience Match", CAT_MATCH, score, expl, rec)


def _m_seniority(req: Dict) -> Dict:
    s = req.get("seniority")
    if not s:
        return _metric("seniority_match", "Seniority Match", CAT_MATCH, None,
                       "La vacante no especifica un nivel de seniority.",
                       "Sin nivel explícito: alinea el tono al alcance del rol.")
    score = 100 if s["coincide"] else 45
    expl = (f"Vacante: {s['vacante']}; tu CV refleja "
            f"{s['cv'] or 'sin señal clara'}.")
    rec = ("Tu seniority encaja con el rol." if s["coincide"] else
           f"Refuerza señales de nivel «{s['vacante']}» (alcance, equipo, impacto).")
    return _metric("seniority_match", "Seniority Match", CAT_MATCH, score, expl, rec)


def _m_education(req: Dict) -> Dict:
    e = req.get("educacion")
    if not e:
        return _metric("education_match", "Education Match", CAT_SKILLS, None,
                       "La vacante no especifica un requisito educativo.",
                       "Sin requisito formal: la experiencia manda.")
    score = 100 if e["cumple"] else 0
    expl = (f"La vacante pide «{e['requerido']}»; en tu CV: "
            f"{e['cv'] or 'no detectado'}.")
    rec = ("Cumples el nivel educativo." if e["cumple"] else
           f"Incluye tu formación («{e['requerido']}» o equivalente) en la sección Educación.")
    return _metric("education_match", "Education Match", CAT_SKILLS, score, expl, rec)


def _m_certs(req: Dict) -> Dict:
    certs = req.get("certificaciones", [])
    if not certs:
        return _metric("certifications_match", "Certifications Match", CAT_SKILLS, None,
                       "La vacante no pide certificaciones concretas.",
                       "Sin certificaciones requeridas. Súmalas si las tienes, dan ventaja.")
    pres = [c for c in certs if c["en_cv"]]
    score = _c(len(pres) / len(certs) * 100)
    faltan = ", ".join(c["cert"].upper() for c in certs if not c["en_cv"])
    expl = (f"Certificaciones pedidas: {len(certs)}; presentes en tu CV: {len(pres)}.")
    rec = (f"Añade o destaca: {faltan}." if faltan else
           "Tienes las certificaciones solicitadas. Mantenlas visibles.")
    return _metric("certifications_match", "Certifications Match", CAT_SKILLS, score, expl, rec)


def _m_hard(cv: str, vacante: str) -> Dict:
    kws = _keywords_de(vacante)
    soft_norm = {norm_alias(s) for s in SOFT_SKILLS}
    hard = [k for k in kws if norm_alias(k) not in soft_norm]
    if not hard:
        return _metric("hard_skills_match", "Hard Skills Match", CAT_SKILLS, None,
                       "No se detectaron hard skills en la vacante.",
                       "Verifica que la vacante liste tecnologías concretas.")
    cub, sug = _analizar_cobertura(hard, cv)
    score = _c(len(cub) / len(hard) * 100)
    expl = f"Cubres {len(cub)} de {len(hard)} hard skills de la vacante."
    rec = (f"Incorpora (si las dominas): {', '.join(sug[:8])}." if sug else
           "Cubres las hard skills clave. Excelente.")
    return _metric("hard_skills_match", "Hard Skills Match", CAT_SKILLS, score, expl, rec)


def _m_soft(cv: str, vacante: str) -> Dict:
    ped, pres = _soft_match(vacante, cv)
    if not ped:
        return _metric("soft_skills_match", "Soft Skills Match", CAT_SKILLS, None,
                       "La vacante no menciona soft skills explícitas.",
                       "Aun así, demuestra liderazgo/colaboración con ejemplos en tus logros.")
    score = _c(len(pres) / len(ped) * 100)
    faltan = _faltantes(ped, pres)
    expl = f"La vacante valora {len(ped)} soft skills; tu CV refleja {len(pres)}."
    rec = (f"Evidencia con ejemplos: {faltan}." if faltan else
           "Reflejas las soft skills pedidas.")
    return _metric("soft_skills_match", "Soft Skills Match", CAT_SKILLS, score, expl, rec)


def _m_tools(cv: str, vacante: str) -> Dict:
    ped, pres = _match_dict(TOOLS, vacante, cv)
    if not ped:
        return _metric("tools_match", "Tools / Platforms Match", CAT_SKILLS, None,
                       "La vacante no menciona herramientas/plataformas concretas.",
                       "Sin herramientas pedidas: lista igualmente las que dominas.")
    score = _c(len(pres) / len(ped) * 100)
    faltan = _faltantes(ped, pres)
    expl = f"Herramientas pedidas: {', '.join(ped)}. Presentes: {len(pres)}/{len(ped)}."
    rec = (f"Añade si las usas: {faltan}." if faltan else
           "Cubres las herramientas solicitadas.")
    return _metric("tools_match", "Tools / Platforms Match", CAT_SKILLS, score, expl, rec)


def _m_methods(cv: str, vacante: str) -> Dict:
    ped, pres = _match_dict(METHODOLOGIES, vacante, cv)
    if not ped:
        return _metric("methodologies_match", "Methodologies Match", CAT_SKILLS, None,
                       "La vacante no menciona metodologías concretas.",
                       "Sin metodologías pedidas: menciona Agile/Scrum si aplicaste.")
    score = _c(len(pres) / len(ped) * 100)
    faltan = _faltantes(ped, pres)
    expl = f"Metodologías pedidas: {', '.join(ped)}. Presentes: {len(pres)}/{len(ped)}."
    rec = (f"Menciona si trabajaste con: {faltan}." if faltan else
           "Cubres las metodologías solicitadas.")
    return _metric("methodologies_match", "Methodologies Match", CAT_SKILLS, score, expl, rec)


def _m_impact(bullets: List[str]) -> Dict:
    if not bullets:
        return _metric("measurable_impact", "Measurable Impact Score", CAT_CALIDAD, None,
                       "No se detectaron viñetas de logros para evaluar.",
                       "Escribe tus logros como viñetas que empiecen con verbo de acción.")
    con = sum(1 for b in bullets if tiene_metrica(b))
    score = _c(con / len(bullets) * 100)   # == core.calidad["impacto"] (misma fórmula)
    expl = f"{con} de {len(bullets)} viñetas incluyen una métrica real (%, $, tiempo, volumen)."
    rec = ("Buen uso de métricas." if score >= 60 else
           "Cuantifica más logros: añade %, importes, tiempos o volúmenes reales.")
    return _metric("measurable_impact", "Measurable Impact Score", CAT_CALIDAD, score, expl, rec)


def _m_bullet_strength(cv: str, bullets: List[str]) -> Dict:
    from app.services.ats_checker import _empieza_con_verbo_accion
    if not bullets:
        return _metric("bullet_strength", "Bullet Strength Score", CAT_CALIDAD, None,
                       "No se detectaron viñetas para evaluar.",
                       "Convierte tus tareas en viñetas: verbo + tarea + herramienta + resultado.")
    tech = set(TECH_SINGLE) | {t.lower() for t in TOOLS}
    total = 0
    for b in bullets:
        low = b.lower()
        pts = 0
        if _empieza_con_verbo_accion(b):
            pts += 30
        if 40 <= len(b) <= 220:
            pts += 20
        if any(re.search(rf"\b{re.escape(t)}\b", low) for t in tech) or \
           any(re.search(p, low) for p in TOOLS.values()):
            pts += 25
        if tiene_metrica(b):
            pts += 25
        total += pts
    score = _c(total / len(bullets))
    expl = ("Calidad media de tus viñetas (verbo de acción + tarea + herramienta + "
            f"resultado): {score}/100.")
    rec = ("Viñetas sólidas." if score >= 70 else
           "Mejora la estructura: empieza con verbo fuerte, nombra la herramienta y cierra con un resultado medible.")
    return _metric("bullet_strength", "Bullet Strength Score", CAT_CALIDAD, score, expl, rec)


def _m_readability(cv: str) -> Dict:
    # Legibilidad del core (fuente única) → no contradice la Calidad de «Adaptar».
    cal = calcular_calidad(cv)
    score = cal["legibilidad"]
    detalle = []
    if cal["relleno"]:
        detalle.append(f"{cal['relleno']} frases de relleno")
    if cal["repetidas"]:
        detalle.append(f"{len(cal['repetidas'])} palabras repetidas en exceso")
    expl = ("Claridad y concisión del texto: " +
            (", ".join(detalle) if detalle else "sin problemas notables") + ".")
    rec = ("Texto claro y profesional." if score >= 75 else
           "Elimina frases de relleno y evita repetir las mismas palabras.")
    return _metric("readability", "Readability Score", CAT_CALIDAD, score, expl, rec)


def _m_format_risk(cv: str) -> Dict:
    score = 100
    señales = []
    if "\t" in cv:
        score -= 15
        señales.append("tabulaciones")
    lineas_pipe = sum(1 for l in cv.splitlines() if l.count("|") >= 2)
    if lineas_pipe >= 2:
        score -= 15
        señales.append("posibles columnas/tablas (|)")
    if re.search(r"[│┃┊╎▏▕░▒▓■●▶➤◦‣]", cv):
        score -= 10
        señales.append("viñetas/caracteres no estándar")
    if re.search(r"[\U0001F300-\U0001FAFF☀-➿]", cv):
        score -= 10
        señales.append("emojis")
    no_ascii = sum(1 for ch in cv if ord(ch) > 0x2122)
    if no_ascii > 15:
        score -= 10
        señales.append("muchos caracteres especiales")
    score = _c(score)
    expl = ("Riesgo de formato para el parseo ATS (mayor score = más seguro). "
            + ("Detectado: " + ", ".join(señales) + "." if señales
               else "Sin señales de riesgo en el texto."))
    rec = ("Formato seguro (una columna, texto plano)." if score >= 80 else
           "Evita tablas, columnas, iconos y caracteres especiales; usa viñetas simples (•/-).")
    # Nota: el texto pegado no permite ver imágenes/headers/footers reales de un DOCX.
    return _metric("format_risk", "Format Risk Score", CAT_FORMATO, score, expl, rec)


def _m_vendor_risk(parse_rate: int, format_safety: int) -> Dict:
    base = (parse_rate + format_safety) / 2
    detalles, scores = [], []
    for vendor, (sens, nota) in _VENDORS.items():
        riesgo = (100 - base) * sens
        seguro = _c(100 - riesgo)
        scores.append(seguro)
        nivel = "bajo" if seguro >= 80 else ("medio" if seguro >= 60 else "alto")
        detalles.append((vendor, seguro, nivel, nota))
    detalles.sort(key=lambda x: x[1])  # peor primero
    score = _c(sum(scores) / len(scores))
    peores = [f"{v} (riesgo {n})" for v, s, n, _ in detalles if s < 80][:3]
    expl = ("Seguridad estimada frente a los ATS comerciales (mayor = mejor). "
            + ("Más exigentes con tu CV actual: " + ", ".join(peores) + "."
               if peores else "Bajo riesgo en todos los vendors evaluados."))
    rec = (("Prioriza un formato simple para superar " + ", ".join(p.split(" (")[0] for p in peores) + ".")
           if peores else "Tu formato es robusto frente a los principales ATS.")
    return _metric("ats_vendor_risk", "ATS Vendor Risk", CAT_FORMATO, score, expl, rec)


# ---------------------------------------------------------------------------
# Función pública
# ---------------------------------------------------------------------------

def calcular_metricas(cv: str, vacante: str = "") -> Dict:
    """Calcula las 15 métricas competitivas y las agrupa por categoría."""
    cv = cv or ""
    vacante = vacante or ""
    parsing = simular_parsing(cv)
    req = analizar_requisitos(cv, vacante)
    bullets = _bullets(cv)

    m_parse = _m_parse_rate(parsing)
    m_format = _m_format_risk(cv)

    metricas = [
        m_parse,
        _m_title(cv, vacante),
        _m_experience(req),
        _m_seniority(req),
        _m_education(req),
        _m_certs(req),
        _m_hard(cv, vacante),
        _m_soft(cv, vacante),
        _m_tools(cv, vacante),
        _m_methods(cv, vacante),
        _m_impact(bullets),
        _m_bullet_strength(cv, bullets),
        _m_readability(cv),
        m_format,
        _m_vendor_risk(m_parse["score"] or 0, m_format["score"] or 0),
    ]

    # ── REGLA DE N/A (manejo transparente de la agregación) ───────────────────
    # Una métrica N/A (no aplicable, p.ej. Title Match sin vacante, o Measurable
    # Impact sin viñetas) NUNCA cuenta como acierto. Se EXCLUYE del promedio: cada
    # agregado se recalcula SOLO sobre las métricas aplicables. Por eso una categoría
    # solo llega a 100 si TODAS sus métricas aplicables están realmente al máximo, y
    # cada agregado expone "aplicables/total" para que la UI explique la base.
    # Si TODAS las métricas de una categoría son N/A -> score None (pendiente), no 0 ni 100.
    aplicables = [m["score"] for m in metricas if m["aplica"]]
    score_global = _c(sum(aplicables) / len(aplicables)) if aplicables else 0

    # Recomendaciones prioritarias: métricas aplicables con menor score.
    prioritarias = sorted([m for m in metricas if m["aplica"]],
                          key=lambda m: m["score"])
    prioritarias = [
        {"nombre": m["nombre"], "score": m["score"],
         "categoria": m["categoria"], "recomendacion": m["recomendacion"]}
        for m in prioritarias if m["score"] < 80
    ][:5]

    # Agrupadas por categoría (para la UI)
    por_categoria = {cat: [m for m in metricas if m["categoria"] == cat]
                     for cat in CATEGORIAS}

    # Agregado por categoría aplicando la regla de N/A + cobertura (aplicables/total).
    def _agg(items):
        apt = [m["score"] for m in items if m["aplica"]]
        return {"score": (_c(sum(apt) / len(apt)) if apt else None),
                "aplicables": len(apt), "total": len(items)}

    resumen_categorias = {cat: _agg(por_categoria[cat]) for cat in CATEGORIAS}
    cobertura_global = {"aplicables": len(aplicables), "total": len(metricas)}

    return {
        "score_global": score_global,
        "cobertura_global": cobertura_global,
        "categorias": CATEGORIAS,
        "metricas": metricas,
        "por_categoria": por_categoria,
        "resumen_categorias": resumen_categorias,
        "prioritarias": prioritarias,
        # Densidad/recuento de keywords con sinónimos (estilo Jobscan).
        "keywords_detalle": analizar_keywords(cv, vacante),
    }
