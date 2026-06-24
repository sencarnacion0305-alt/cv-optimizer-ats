"""
Reescribe bullets debiles del CV con verbos de accion (por reglas, sin API).

Detecta frases de bajo impacto al inicio de un bullet ("Responsible for",
"Worked on", "Helped"...) y las transforma en logros con verbo de accion.
Tambien marca los bullets que carecen de metricas cuantificables.
"""

import re
from typing import Dict, List

# Frase debil inicial -> verbo de accion por defecto (si no hay gerundio detras)
MAPEO_DEBIL = {
    "responsibilities included": "",
    "responsible for the": "Managed the",
    "responsible for": "Managed",
    "responsible of": "Managed",
    "in charge of": "Led",
    "duties included": "",
    "tasked with": "",
    "worked on": "Developed",
    "worked with": "Leveraged",
    "worked as": "Served as",
    "helped to": "Helped",          # se procesa como gerundio/infinitivo abajo
    "helped with": "Supported",
    "helped": "Supported",
    "assisted with": "Supported",
    "assisted in": "Supported",
    "assisted": "Supported",
    "participated in": "Contributed to",
    "involved in": "Drove",
    "responsable de": "Gestioné",
    "responsable por": "Gestioné",
    "encargado de": "Lideré",
    "encargada de": "Lideré",
    "fui responsable de": "Lideré",
    "me encargué de": "Lideré",
    "me encargue de": "Lideré",
    "a cargo de": "Lideré",
    "ayudé a": "Impulsé",
    "ayude a": "Impulsé",
    "ayudé en": "Apoyé",
    "ayude en": "Apoyé",
    "apoyé en": "Apoyé",
    "trabajé en": "Desarrollé",
    "trabaje en": "Desarrollé",
    "trabajé con": "Utilicé",
    "trabaje con": "Utilicé",
    "participé en": "Contribuí a",
    "participe en": "Contribuí a",
    "colaboré en": "Contribuí a",
    "colabore en": "Contribuí a",
    "fui parte de": "Integré",
    "estuve involucrado en": "Impulsé",
    "realicé tareas de": "Ejecuté",
    "realice tareas de": "Ejecuté",
    "me ocupé de": "Gestioné",
}

# Gerundios comunes -> pasado (irregulares y de consonante doblada)
GERUNDIOS = {
    "managing": "Managed", "developing": "Developed", "leading": "Led",
    "creating": "Created", "designing": "Designed", "building": "Built",
    "implementing": "Implemented", "maintaining": "Maintained",
    "supporting": "Supported", "coordinating": "Coordinated",
    "handling": "Handled", "monitoring": "Monitored", "analyzing": "Analyzed",
    "testing": "Tested", "writing": "Wrote", "running": "Ran",
    "providing": "Provided", "ensuring": "Ensured", "performing": "Performed",
    "overseeing": "Oversaw", "administering": "Administered",
    "configuring": "Configured", "deploying": "Deployed", "resolving": "Resolved",
    "troubleshooting": "Troubleshot", "improving": "Improved",
    "planning": "Planned", "setting": "Set",
}

METRICA_RE = re.compile(r"\d+\s*%|\d[\d,.]*\s*\+|\b\d{2,}\b|\$\s*\d")

# ---------------------------------------------------------------------------
# Sanitizado a PLACEHOLDERS: nunca presentar cifras inventadas como reales.
# Convierte cualquier número de las plantillas en un marcador editable.
#   ~30% / 95%      -> [estimated %]
#   ~$50K / $200K   -> [$ amount]
#   100+ / 1M+ / ~5 -> [number]
# ---------------------------------------------------------------------------
_NUM_MONEY = re.compile(r"~?\$\s*\d[\d.,]*\s*[KkMmBb]?")
_NUM_PCT   = re.compile(r"~?\d[\d.,]*\s*[KkMmBb]?\s*%")
_NUM_PLAIN = re.compile(r"~?\d[\d.,]*\s*[KkMmBb]?\+?")

ADVERTENCIA_METRICAS = ("Reemplaza los valores estimados ([number], [estimated %]) "
                        "con cifras reales antes de enviar tu CV.")


def _a_placeholder(s: str) -> str:
    """Sustituye todo número concreto por un marcador editable."""
    s = _NUM_MONEY.sub("[$ amount]", s)
    s = _NUM_PCT.sub("[estimated %]", s)
    s = _NUM_PLAIN.sub("[number]", s)
    return s

# ---------------------------------------------------------------------------
# Generador de metricas contextuales (placeholders editables marcados con ~)
# ---------------------------------------------------------------------------

# Categoria del bullet segun palabras clave -> sufijos de impacto cuantificado.
# Los numeros llevan «~» para indicar que el usuario debe ajustarlos a su realidad.
_CATEGORIAS_METRICA = [
    ("incident",   r"incident|response|breach|intrusion|attack|malware|ransomware"),
    ("threat",     r"threat|hunt|ioc|adversary|compromise"),
    ("alert",      r"alert|monitor|siem|log|event|\bsoc\b|detect|correlat"),
    ("vuln",       r"vulnerab|patch|scan|remediat|nessus|qualys|\bcve\b|exposure"),
    ("phishing",   r"phishing|email|spam|campaign|harmony"),
    ("team",       r"\bteam\b|mentor|train|junior|coordinat|stakeholder|cross-functional"),
    ("report",     r"report|document|dashboard|executive|visibility"),
    ("ticket",     r"ticket|support|help\s*desk|end users|\busers?\b"),
    ("audit",      r"audit|complian|policy|\biso\b|nist|risk|framework|control"),
    ("automation", r"automat|script|playbook|orchestrat|runbook"),
    ("cloud",      r"cloud|\baws\b|azure|\bgcp\b|server|infrastructure|virtual"),
    ("firewall",   r"firewall|network|fortinet|sophos|checkpoint|harden"),
]

_PLANTILLAS_METRICA = {
    "incident":   ["cutting average response time by ~30%", "across ~40 incidents per quarter",
                   "reducing MTTR by ~25%"],
    "threat":     ["identifying ~15 active threats", "improving threat coverage by ~35%"],
    "alert":      ["triaging 100+ alerts per week", "monitoring ~500 events daily",
                   "raising detection accuracy to ~95%"],
    "vuln":       ["remediating 50+ vulnerabilities", "reducing exposure windows by ~40%",
                   "scanning ~200 assets"],
    "phishing":   ["blocking ~95% of malicious emails", "neutralizing ~20 campaigns"],
    "team":       ["leading a team of ~5", "mentoring ~4 junior analysts",
                   "coordinating ~6 stakeholders"],
    "report":     ["improving reporting visibility for 10+ stakeholders",
                   "cutting reporting time by ~50%"],
    "ticket":     ["resolving 200+ tickets per month", "sustaining ~98% SLA compliance"],
    "audit":      ["improving audit readiness by ~40%", "aligning with ~3 frameworks"],
    "automation": ["saving ~15 hours of manual work weekly", "automating ~80% of the workflow"],
    "cloud":      ["across 50+ servers", "covering ~10 cloud workloads"],
    "firewall":   ["hardening ~30 network devices", "reducing attack surface by ~35%"],
    "default":    ["improving operational efficiency by ~25%", "supporting 1M+ users",
                   "achieving ~99% uptime"],
}

# ── Métricas por SECTOR ───────────────────────────────────────────────────
# Evita aplicar jerga de IT/ciberseguridad a perfiles de otros sectores
# (p. ej. no usar "incidentes" para un Marketing Manager).
_SECTOR_PATRONES = [
    ("tech",      r"software|desarroll|developer|engineer|ingenier|programm|program|"
                  r"cyber|ciberseg|security|seguridad inform|\bsoc\b|siem|devops|"
                  r"cloud|backend|frontend|sysadmin|network|\bredes\b|data scien|"
                  r"machine learning|\bit\b|infraestructura|\bqa\b|testing"),
    ("marketing", r"marketing|\bbrand\b|marca|\bseo\b|\bsem\b|social media|"
                  r"redes sociales|content|contenido|community|campaign|campañ|"
                  r"publicidad|comunicaci|growth|engagement"),
    ("ventas",    r"\bsales\b|ventas|account executive|business development|comercial|"
                  r"\bkam\b|retail|cuota|portafolio"),
    ("finanzas",  r"finance|financ|account|contab|\baudit|\btax\b|impuesto|tesorer|"
                  r"presupuesto|\bcfo\b|controller|banca|inversi"),
    ("rrhh",      r"human resources|recursos humanos|\brrhh\b|talent|talento|recruit|"
                  r"selecci[oó]n de personal|onboarding|\bhr\b"),
    ("salud",     r"\bhealth\b|salud|nurse|enfermer|m[eé]dic|cl[ií]nic|patient|"
                  r"paciente|hospital|farmac"),
    ("educacion", r"teacher|profesor|docente|education|educaci|maestr|tutor|acad[eé]mic"),
    ("operaciones", r"operations|operaciones|log[ií]stic|supply chain|"
                    r"cadena de suministro|almac[eé]n|producci[oó]n|manufactur"),
]

_PLANTILLAS_SECTOR = {
    "marketing":   ["increasing engagement by ~30%", "growing reach to ~50K users",
                    "boosting conversion by ~20%", "managing a ~$50K budget",
                    "improving ROI by ~25%", "across ~10 campaigns"],
    "ventas":      ["exceeding quota by ~20%", "closing ~30 deals per quarter",
                    "growing the portfolio by ~25%", "generating ~$200K in revenue"],
    "finanzas":    ["managing a ~$1M budget", "reducing costs by ~15%",
                    "improving accuracy to ~99%", "across ~200 monthly transactions"],
    "rrhh":        ["reducing time-to-hire by ~30%", "onboarding ~50 new hires",
                    "improving retention by ~15%", "across ~120 employees"],
    "salud":       ["serving ~200 patients monthly", "improving outcomes by ~20%",
                    "maintaining ~98% compliance"],
    "educacion":   ["teaching ~120 students", "improving pass rates by ~15%",
                    "across ~6 courses"],
    "operaciones": ["improving throughput by ~20%", "cutting delivery time by ~25%",
                    "across ~15 processes", "reducing costs by ~15%"],
    "general":     ["improving efficiency by ~25%", "saving ~10 hours weekly",
                    "supporting ~1000 users", "reducing costs by ~15%"],
}


def detectar_sector(texto: str) -> str:
    """Sector dominante del CV, para elegir métricas apropiadas al perfil."""
    low = texto.lower()
    mejor, maximo = "general", 0
    for sector, patron in _SECTOR_PATRONES:
        n = len(re.findall(patron, low))
        if n > maximo:
            mejor, maximo = sector, n
    return mejor


def _categoria_metrica(texto_low: str) -> str:
    for cat, patron in _CATEGORIAS_METRICA:
        if re.search(patron, texto_low):
            return cat
    return "default"


def sufijo_metrica(bullet: str, contadores: Dict[str, int], sector: str = "tech") -> str:
    """
    Devuelve un sufijo de impacto cuantificado APROPIADO AL SECTOR del candidato,
    rotando entre variantes y evitando las que repiten palabras del bullet.
    Para sectores no técnicos no se usa jerga de IT/ciberseguridad.
    """
    low = bullet.lower()
    if sector == "tech":
        cat = _categoria_metrica(low)
        opciones = _PLANTILLAS_METRICA.get(cat, _PLANTILLAS_METRICA["default"])
    else:
        cat = sector
        opciones = _PLANTILLAS_SECTOR.get(sector, _PLANTILLAS_SECTOR["general"])
    i = contadores.get(cat, 0)
    for k in range(len(opciones)):
        cand = opciones[(i + k) % len(opciones)]
        palabras = re.findall(r"[a-z]{5,}", cand.lower())
        if not any(w in low for w in palabras):  # evita repetir palabras del bullet
            contadores[cat] = i + k + 1
            return _a_placeholder(cand)
    contadores[cat] = i + 1
    return _a_placeholder(opciones[i % len(opciones)])


def agregar_metrica_a_bullet(bullet: str, contadores: Dict[str, int],
                             sector: str = "tech") -> str:
    """Agrega una metrica cuantificada al final del bullet (si no tiene ya numeros)."""
    base = bullet.rstrip().rstrip(".")
    return base + ", " + sufijo_metrica(bullet, contadores, sector) + "."


def tiene_metrica(texto: str) -> bool:
    return bool(METRICA_RE.search(texto))


def _gerundio_a_pasado(g: str) -> str:
    """Convierte un gerundio en -ing a su forma pasada (heuristica)."""
    if g in GERUNDIOS:
        return GERUNDIOS[g]
    raiz = g[:-3] if g.endswith("ing") else g
    if not raiz:
        return g.capitalize()
    if len(raiz) >= 2 and raiz[-1] == raiz[-2]:   # doblado: planning->plann->plan
        raiz = raiz[:-1]
    return (raiz + "ed").capitalize()


def _reescribir_bullet(bullet: str) -> str:
    low = bullet.lower().strip()
    for frase in sorted(MAPEO_DEBIL, key=len, reverse=True):
        if low.startswith(frase):
            verbo = MAPEO_DEBIL[frase]
            resto = bullet.strip()[len(frase):].strip(" ,:;-")

            if not resto:
                return bullet

            primera = resto.split()[0].lower()

            # Caso 1: lo que sigue es un gerundio -> usar su pasado
            if primera.endswith("ing") and len(primera) > 4:
                pasado = _gerundio_a_pasado(primera)
                cola = resto.split(" ", 1)[1] if " " in resto else ""
                nuevo = (pasado + (" " + cola if cola else "")).strip()
            # Caso 2: infinitivo "to X" -> convertir X a pasado
            elif primera == "to" and len(resto.split()) > 1:
                verbo2 = resto.split()[1]
                pasado = _gerundio_a_pasado(verbo2 + "ing") if not verbo2.endswith("ed") else verbo2.capitalize()
                cola = resto.split(" ", 2)[2] if len(resto.split(" ", 2)) > 2 else ""
                nuevo = (pasado + (" " + cola if cola else "")).strip()
            # Caso 3: anteponer verbo por defecto (o solo quitar la frase)
            else:
                nuevo = (verbo + " " + resto).strip() if verbo else resto

            return nuevo[:1].upper() + nuevo[1:]
    return bullet


def _es_bullet_debil(linea: str) -> bool:
    low = linea.lower().strip()
    return any(low.startswith(f) for f in MAPEO_DEBIL)


# Lineas que parecen logro pero NO lo son (certificaciones, cursos, grados)
_NO_LOGRO_INICIO = (
    "certified", "certificate", "certification", "relevant coursework",
    "coursework", "b.eng", "b.sc", "b.s.", "m.sc", "bachelor", "master",
    "licenciatura", "ingenier", "tecnolog", "diploma", "associate",
)


def _es_bullet_de_logro(linea: str) -> bool:
    """Bullet de experiencia: empieza con verbo de accion o con frase debil."""
    from app.services.ats_checker import _empieza_con_verbo_accion, _es_titulo_seccion
    low = linea.lower().strip()
    if any(low.startswith(x) for x in _NO_LOGRO_INICIO):
        return False
    if _es_titulo_seccion(linea):
        return False
    return _empieza_con_verbo_accion(linea) or _es_bullet_debil(linea)


def mejorar_bullets(cv_texto: str) -> Dict:
    # Quitar prefijos de viñeta para que la detección de verbos débiles funcione
    lineas = [re.sub(r"^[\s\-–—•·*▪●○‣◦]+", "", l).strip()
              for l in cv_texto.splitlines() if l.strip()]
    sector = detectar_sector(cv_texto)

    mejoras: List[Dict] = []
    contadores: Dict[str, int] = {}
    n_verbos = n_metricas = 0

    for linea in lineas:
        if len(linea) < 25 or len(linea) > 400:
            continue
        if not _es_bullet_de_logro(linea):
            continue

        mejorado = linea
        tipos: List[str] = []

        # 1. Reescribir verbo debil
        if _es_bullet_debil(linea):
            reescrito = _reescribir_bullet(linea)
            if reescrito and reescrito.strip() != linea.strip():
                mejorado = reescrito
                tipos.append("verbo")

        # 2. Agregar metrica si no tiene numeros (apropiada al sector)
        if not tiene_metrica(mejorado):
            mejorado = agregar_metrica_a_bullet(mejorado, contadores, sector)
            tipos.append("metrica")

        if tipos and mejorado.strip() != linea.strip():
            if "verbo" in tipos:
                n_verbos += 1
            if "metrica" in tipos:
                n_metricas += 1
            mejoras.append({
                "original": linea,
                "mejorado": mejorado,
                "tipos": tipos,
                "metrica_agregada": "metrica" in tipos,
            })

    if mejoras:
        partes = []
        if n_verbos:
            partes.append(f"{n_verbos} con verbos débiles reescritos")
        if n_metricas:
            partes.append(f"{n_metricas} con métricas de impacto sugeridas")
        resumen = "Mejoramos " + " y ".join(partes) + "."
        if n_metricas:
            resumen += " " + ADVERTENCIA_METRICAS
    else:
        resumen = ("Tus bullets ya usan verbos de acción y métricas. ¡Excelente! "
                   "No hay cambios que sugerir.")

    return {
        "total_mejoras": len(mejoras),
        "n_verbos": n_verbos,
        "n_metricas": n_metricas,
        "mejoras": mejoras,
        "resumen": resumen,
        # Advertencia explícita: las métricas sugeridas son marcadores, no datos reales.
        "advertencia": ADVERTENCIA_METRICAS if n_metricas else "",
    }
