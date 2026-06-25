"""
Constantes del analizador único de CV (`core.cv_analyzer`).

TODO peso, umbral y patrón de sección vive AQUÍ — una sola definición que
comparten las 4 vistas (Adaptar, Análisis ATS, Checklist, 15 Métricas). Si dos
pestañas alguna vez se contradicen, es porque NO leyeron de aquí.
"""

import re

# ---------------------------------------------------------------------------
# Pesos del SCORE GLOBAL — 5 dimensiones, suman 100.
# Fórmula:  score_global = Σ sub_score_i   (cada sub_score ya viene en su escala)
# Se conservan los pesos del score compuesto previo para no alterar su significado.
# ---------------------------------------------------------------------------
PESOS = {
    "keywords":   35,   # match de keywords de la vacante (hard+soft, ponderado por posición)
    "formato":    20,   # legibilidad ATS (sin tablas/columnas, fechas, caracteres)
    "estructura": 20,   # presencia de secciones clave + contacto
    "contenido":  15,   # calidad de logros (métricas, verbos de acción, sin relleno)
    "cargo":      10,   # coincidencia del cargo objetivo con el CV
}
assert sum(PESOS.values()) == 100

# Reparto interno de ESTRUCTURA (suma = PESOS["estructura"] = 20)
ESTRUCTURA_PTS = {
    "resumen": 5, "experiencia": 4, "educacion": 3,
    "habilidades": 3, "email": 3, "telefono": 2,
}
assert sum(ESTRUCTURA_PTS.values()) == PESOS["estructura"]

# Reparto interno de CONTENIDO (suma = PESOS["contenido"] = 15)
CONTENIDO_PTS = {"metrica": 6, "verbo": 5, "relleno": 4}
assert sum(CONTENIDO_PTS.values()) == PESOS["contenido"]
STUFFING_PENALTI = 5            # penalización si hay keyword stuffing

# Reparto interno de FORMATO (suma = PESOS["formato"] = 20)
FORMATO_PTS = {"tabla": 6, "longitud": 5, "fechas": 4, "chars": 5}
assert sum(FORMATO_PTS.values()) == PESOS["formato"]

# ---------------------------------------------------------------------------
# Umbrales de calidad / longitud
# ---------------------------------------------------------------------------
RESUMEN_MIN_PALABRAS = 30       # un resumen "real" tiene > 30 palabras
RATIO_VERBO_OK = 0.6            # ≥60% de bullets con verbo de acción = bien
RATIO_VERBO_MEDIO = 0.3
PALABRAS_MIN = 250             # CV demasiado corto
PALABRAS_MAX = 900            # CV demasiado largo (≈2+ páginas)
SKILLS_MIN_PARA_SECCION = 4    # nº de skills sueltas que infieren "sección Habilidades"

# ---------------------------------------------------------------------------
# Encabezados de sección (EN + ES) — UNA sola definición.
# Combina los patrones que antes estaban dispersos en adaptador, ats_checker y
# el checklist JS. Se anclan al inicio de línea (^) porque son encabezados.
# ---------------------------------------------------------------------------
HEADERS_SECCION = {
    "contacto": re.compile(
        r"^(contact|datos\s*de\s*contacto|informaci[oó]n\s*de\s*contacto)", re.I),
    "resumen": re.compile(
        r"^(professional\s*summary|summary|profile|resumen(\s*profesional)?|"
        r"perfil(\s*profesional)?|objetivo|sobre\s*m[ií]|acerca\s*de\s*m[ií]|about(\s*me)?)", re.I),
    "experiencia": re.compile(
        r"^(work\s*experience|professional\s*experience|experience|"
        r"experiencia(\s*(profesional|laboral))?|employment(\s*history)?|"
        r"trayectoria|historial\s*laboral)", re.I),
    "educacion": re.compile(
        r"^(education|educaci[oó]n|formaci[oó]n(\s*acad[eé]mica)?|estudios|academic)", re.I),
    "habilidades": re.compile(
        r"^(technical\s*skills?|core\s*skills?|skills?|habilidades|competencias?|"
        r"conocimientos|aptitudes|tech\s*stack)", re.I),
}

# ---------------------------------------------------------------------------
# Primitivas de calidad (regex) — compartidas por todas las vistas.
# ---------------------------------------------------------------------------
FRASES_RELLENO = re.compile(
    r"\b(responsable de|encargad[oa] de|ayud[eé] a|particip[eé]|colabor[eé] en|"
    r"responsible for|helped(\s+to)?\b|assisted (with|in)|worked on|in charge of|"
    r"tareas (como|de)|funciones de|duties includ|a cargo de)",
    re.IGNORECASE)

VERBO_ACCION = re.compile(
    r"^\s*[-•*–·]?\s*(led|managed|built|created|designed|developed|implemented|"
    r"reduced|increased|improved|launched|delivered|drove|optimized|achieved|"
    r"resolved|analyzed|coordinated|automated|spearheaded|streamlined|executed|"
    r"detected|mitigated|investigated|deployed|configured|engineered|orchestrated|"
    r"lider[eé]|gestion[eé]|desarroll[eé]|implement[eé]|dise[ñn][eé]|reduj|"
    r"aument[eé]|mejor[eé]|cre[eé]|coordin[eé]|logr[eé]|optimic[eé]|automatic[eé]|"
    r"dirig[ií]|ejecut[eé]|analic[eé]|construi)",
    re.IGNORECASE)

# Fecha estándar "Mes AAAA" (buena) vs numérica (mala) para ATS
FECHA_MES = re.compile(
    r"\b(jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec|ene|abr|ago|dic)\.?\s+\d{4}",
    re.IGNORECASE)
FECHA_MALA = re.compile(r"\b(0?[1-9]|1[0-2])[/-](19|20)\d{2}\b|'\d{2}\b")
# Caracteres problemáticos para ATS
CHARS_RAROS = re.compile(r"[‘’“”•▪●—\U0001F300-\U0001FAFF]")
# Tablas/columnas en texto plano (box-drawing y tabs múltiples). El pipe ASCII
# se mide aparte por nº de líneas, no aquí (una línea de contacto no es tabla).
TABLA_SIGNS = re.compile(r"[│┃]|[─━]{3,}|\t{2,}")

# ---------------------------------------------------------------------------
# Soft skills (única definición; antes vivía en scoring.py).
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
