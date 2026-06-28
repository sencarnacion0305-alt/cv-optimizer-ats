"""
Reescribe bullets debiles del CV con verbos de accion (por reglas, sin API).

Detecta frases de bajo impacto al inicio de un bullet ("Responsible for",
"Worked on", "Helped"...) y las transforma en logros con verbo de accion.
Tambien marca los bullets que carecen de metricas cuantificables.
"""

import re
from typing import Dict, List, Optional

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
#   ~30% / 95%      -> [% estimado]
#   ~$50K / $200K   -> [$ amount]
#   100+ / 1M+ / ~5 -> [number]
# ---------------------------------------------------------------------------
# El sufijo K/M/B se agrupa con su espacio para NO consumir el espacio previo a la
# siguiente palabra (evita "[number]horas" cuando la plantilla dice "~15 horas").
_NUM_MONEY = re.compile(r"~?\$\s*\d[\d.,]*(?:\s*[KkMmBb])?")
_NUM_PCT   = re.compile(r"~?\d[\d.,]*(?:\s*[KkMmBb])?\s*%")
_NUM_PLAIN = re.compile(r"~?\d[\d.,]*(?:\s*[KkMmBb])?\+?")

ADVERTENCIA_METRICAS = ("Reemplaza los valores estimados ([number], [% estimado]) "
                        "con cifras reales antes de enviar tu CV.")


def _a_placeholder(s: str) -> str:
    """Sustituye todo número concreto por un marcador editable."""
    s = _NUM_MONEY.sub("[$ amount]", s)
    s = _NUM_PCT.sub("[% estimado]", s)
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
    "incident":   ["reduciendo el tiempo medio de respuesta en ~30%",
                   "en ~40 incidentes por trimestre", "reduciendo el MTTR en ~25%"],
    "threat":     ["identificando ~15 amenazas activas",
                   "mejorando la cobertura de amenazas en ~35%"],
    "alert":      ["clasificando 100+ alertas por semana", "monitorizando ~500 eventos al día",
                   "elevando la precisión de detección al ~95%"],
    "vuln":       ["remediando 50+ vulnerabilidades",
                   "reduciendo las ventanas de exposición en ~40%", "escaneando ~200 activos"],
    "phishing":   ["bloqueando el ~95% de correos maliciosos", "neutralizando ~20 campañas"],
    "team":       ["liderando un equipo de ~5 personas", "formando a ~4 analistas junior",
                   "coordinando ~6 interlocutores"],
    "report":     ["mejorando la visibilidad de reportes para 10+ interlocutores",
                   "reduciendo el tiempo de reporte en ~50%"],
    "ticket":     ["resolviendo 200+ tickets al mes", "manteniendo un ~98% de cumplimiento de SLA"],
    "audit":      ["mejorando la preparación para auditorías en ~40%",
                   "alineándose con ~3 marcos de referencia"],
    "automation": ["ahorrando ~15 horas de trabajo manual a la semana",
                   "automatizando el ~80% del flujo de trabajo"],
    "cloud":      ["en 50+ servidores", "cubriendo ~10 cargas de trabajo en la nube"],
    "firewall":   ["fortaleciendo ~30 dispositivos de red",
                   "reduciendo la superficie de ataque en ~35%"],
    "default":    ["mejorando la eficiencia operativa en ~25%", "dando servicio a 1M+ usuarios",
                   "logrando un ~99% de disponibilidad"],
}

# ── Métricas por SECTOR ───────────────────────────────────────────────────
# Evita aplicar jerga de IT/ciberseguridad a perfiles de otros sectores
# (p. ej. no usar "incidentes" para un Marketing Manager).
_SECTOR_PATRONES = [
    # «seguridad» va PRIMERO y separado de «tech»: así la jerga de ciberseguridad
    # (MTTR, incidentes, alertas, amenazas) solo se aplica a perfiles de seguridad,
    # nunca a un developer/devops/data genérico (bug 4.2).
    ("seguridad", r"cybersec|cyber security|ciberseg|seguridad inform|information security|"
                  r"infosec|\bsoc\b|\bsiem\b|\bsoar\b|\bedr\b|\bxdr\b|\bcsirt\b|"
                  r"incident response|respuesta a incidentes|threat|amenaza|vulnerab|"
                  r"pentest|penetration test|forensic|forense|malware|ransomware|"
                  r"phishing|blue team|red team|analista de seguridad|security analyst"),
    ("tech",      r"software|desarroll|developer|engineer|ingenier|programm|program|"
                  r"devops|cloud|backend|frontend|full\s*stack|sysadmin|network|"
                  r"\bredes\b|data scien|machine learning|\bit\b|infraestructura|"
                  r"\bqa\b|testing|\bapi\b|microservic|kubernetes|docker"),
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
    "tech":        ["reduciendo el tiempo de despliegue en ~30%",
                    "mejorando el rendimiento en ~25%", "cubriendo ~10 servicios",
                    "reduciendo los errores en producción en ~40%",
                    "automatizando el ~80% del flujo de trabajo",
                    "dando servicio a 1M+ usuarios", "logrando un ~99% de disponibilidad"],
    "marketing":   ["aumentando el engagement en ~30%", "ampliando el alcance a ~50K usuarios",
                    "mejorando la conversión en ~20%", "gestionando un presupuesto de ~$50K",
                    "mejorando el ROI en ~25%", "en ~10 campañas"],
    "ventas":      ["superando la cuota en ~20%", "cerrando ~30 acuerdos por trimestre",
                    "haciendo crecer la cartera en ~25%", "generando ~$200K en ingresos"],
    "finanzas":    ["gestionando un presupuesto de ~$1M", "reduciendo costos en ~15%",
                    "mejorando la precisión al ~99%", "en ~200 transacciones mensuales"],
    "rrhh":        ["reduciendo el tiempo de contratación en ~30%",
                    "incorporando a ~50 nuevas personas", "mejorando la retención en ~15%",
                    "en una plantilla de ~120 personas"],
    "salud":       ["atendiendo a ~200 pacientes al mes", "mejorando los resultados en ~20%",
                    "manteniendo un ~98% de cumplimiento"],
    "educacion":   ["enseñando a ~120 estudiantes", "mejorando las tasas de aprobación en ~15%",
                    "en ~6 cursos"],
    "operaciones": ["mejorando el rendimiento en ~20%", "reduciendo el tiempo de entrega en ~25%",
                    "en ~15 procesos", "reduciendo costos en ~15%"],
    "general":     ["mejorando la eficiencia en ~25%", "ahorrando ~10 horas a la semana",
                    "dando servicio a ~1000 usuarios", "reduciendo costos en ~15%"],
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


# Ejemplo de métricas APROPIADO AL SECTOR para las recomendaciones de texto
# ("Agrega cifras: …"). Evita sugerir MTTR/incidentes a un perfil no-seguridad (4.2).
_EJEMPLO_METRICAS = {
    "seguridad":   "«Reduje el MTTR un 30%», «Analicé 100+ alertas por semana»",
    "tech":        "«Reduje la latencia un 30%», «Automaticé el 80% de los despliegues»",
    "marketing":   "«Aumenté el engagement un 30%», «Generé 50K leads»",
    "ventas":      "«Superé la cuota un 20%», «Cerré 30 acuerdos por trimestre»",
    "finanzas":    "«Reduje costos un 15%», «Gestioné un presupuesto de $1M»",
    "rrhh":        "«Reduje el tiempo de contratación un 30%», «Incorporé a 50 personas»",
    "salud":       "«Atendí a 200 pacientes al mes», «Mejoré los resultados un 20%»",
    "educacion":   "«Enseñé a 120 estudiantes», «Subí la tasa de aprobación un 15%»",
    "operaciones": "«Reduje el tiempo de entrega un 25%», «Optimicé 15 procesos»",
    "general":     "«Mejoré la eficiencia un 25%», «Ahorré 10 horas a la semana»",
}


def ejemplo_metricas(cv_texto: str) -> str:
    """Ejemplo de cifras a imitar, elegido según el sector dominante del CV."""
    return _EJEMPLO_METRICAS.get(detectar_sector(cv_texto), _EJEMPLO_METRICAS["general"])


def _categoria_metrica(texto_low: str) -> str:
    for cat, patron in _CATEGORIAS_METRICA:
        if re.search(patron, texto_low):
            return cat
    return "default"


def sufijo_metrica(bullet: str, contadores: Dict[str, int], sector: str = "tech",
                   usados: Optional[set] = None) -> str:
    """
    Devuelve un sufijo de impacto cuantificado APROPIADO AL SECTOR del candidato,
    SIN repetir una plantilla ya usada en el mismo CV (`usados`): así dos bullets
    distintos no reciben la misma mejora. Si se agota el pool de la categoría, busca
    en otras categorías del sector; solo repite cuando TODAS están usadas.
    """
    if usados is None:
        usados = set()
    low = bullet.lower()
    # Solo los perfiles de SEGURIDAD usan el pool categórico con jerga de
    # ciberseguridad; el resto (tech genérico, marketing, etc.) usa su propio pool.
    es_seg = sector == "seguridad"
    pools = _PLANTILLAS_METRICA if es_seg else _PLANTILLAS_SECTOR
    cat = _categoria_metrica(low) if es_seg else sector
    opciones = pools.get(cat, _PLANTILLAS_METRICA["default"] if es_seg
                         else _PLANTILLAS_SECTOR.get(sector, _PLANTILLAS_SECTOR["general"]))

    def _repite_palabra(cand: str) -> bool:
        return any(w in low for w in re.findall(r"[a-z]{5,}", cand.lower()))

    i = contadores.get(cat, 0)
    elegido = None
    # 1ª pasada: opción NO usada en el CV y que no repita palabras del bullet.
    for k in range(len(opciones)):
        cand = opciones[(i + k) % len(opciones)]
        if cand not in usados and not _repite_palabra(cand):
            elegido, contadores[cat] = cand, i + k + 1
            break
    # 2ª: cualquier opción de la categoría aún no usada.
    if elegido is None:
        for k in range(len(opciones)):
            cand = opciones[(i + k) % len(opciones)]
            if cand not in usados:
                elegido, contadores[cat] = cand, i + k + 1
                break
    # 3ª: si la categoría está agotada, una NO usada de otra categoría del sector.
    if elegido is None:
        for pool in pools.values():
            for cand in pool:
                if cand not in usados and not _repite_palabra(cand):
                    elegido = cand
                    break
            if elegido:
                break
    # 4ª: todo usado -> rota normal (se permite repetir como último recurso).
    if elegido is None:
        elegido = opciones[i % len(opciones)]
        contadores[cat] = i + 1

    usados.add(elegido)
    return _a_placeholder(elegido)


def agregar_metrica_a_bullet(bullet: str, contadores: Dict[str, int],
                             sector: str = "tech", usados: Optional[set] = None) -> str:
    """Agrega una metrica cuantificada al final del bullet (si no tiene ya numeros)."""
    base = bullet.rstrip().rstrip(".")
    return base + ", " + sufijo_metrica(bullet, contadores, sector, usados) + "."


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


# Jerga de ciberseguridad: si la IA la usa en un perfil no-seguridad, se descarta
# su salida y se cae a reglas (mantiene la garantía de 4.2 también con IA).
_JERGA_SEG = re.compile(r"mttr|incidente|amenaza|vulnerab|phishing|siem|\bsoc\b",
                        re.IGNORECASE)


def _validar_ia_bullet(mejorado: str, sector: str) -> Optional[str]:
    """
    Sanea la salida del modelo: convierte cualquier cifra real en marcador editable
    y rechaza (None) si filtra jerga de seguridad a un perfil que no es de seguridad.
    """
    saneado = _a_placeholder(mejorado).strip()
    if not saneado:
        return None
    if sector != "seguridad" and _JERGA_SEG.search(saneado):
        return None
    return saneado


def _mejorar_con_ia(candidatos: List[str], sector: str, cv_texto: str,
                    vacante: str) -> Optional[Dict]:
    """Camino IA: una llamada batched + validación. Devuelve la respuesta o None."""
    from app.services import llm_client
    if not candidatos or not llm_client.disponible():
        return None
    datos = llm_client.generar_bullets(candidatos, rol=sector, vacante=vacante)
    if not datos:
        return None

    mejoras: List[Dict] = []
    n_metricas = 0
    for it in datos["bullets"]:
        original = it.get("original") or ""
        saneado = _validar_ia_bullet(it.get("mejorado", ""), sector)
        if saneado is None or saneado.strip() == original.strip():
            continue
        tiene_ph = bool(re.search(r"\[(number|% estimado|\$ amount)\]", saneado))
        if tiene_ph:
            n_metricas += 1
        mejoras.append({
            "original": original,
            "mejorado": saneado,
            "tipos": ["ia"],
            "metrica_agregada": tiene_ph,
        })

    if not mejoras:               # nada utilizable -> que el caller use reglas
        return None

    consejos = [c for c in datos.get("consejos", []) if c]
    resumen = (f"La IA reescribió {len(mejoras)} bullet(s) adaptados a tu perfil"
               + (" y sugirió recomendaciones." if consejos else "."))
    if n_metricas:
        resumen += " " + ADVERTENCIA_METRICAS
    return {
        "total_mejoras": len(mejoras),
        "n_verbos": len(mejoras),
        "n_metricas": n_metricas,
        "mejoras": mejoras,
        "recomendaciones": consejos,
        "resumen": resumen,
        "advertencia": ADVERTENCIA_METRICAS if n_metricas else "",
        "fuente": "ia",
        "ia_disponible": True,
    }


def mejorar_bullets(cv_texto: str, usar_ia: bool = False,
                    vacante: str = "") -> Dict:
    # Unidades de logro por LÍNEAS y ORACIONES (funciona con prosa, no solo viñetas).
    # Import diferido para evitar ciclo (core importa este módulo).
    from app.core.cv_analyzer import unidades_logro
    from app.services import llm_client
    lineas = unidades_logro(cv_texto)
    sector = detectar_sector(cv_texto)
    ia_disponible = llm_client.disponible()

    candidatos = [
        l for l in lineas
        if 20 <= len(l) <= 320 and _es_bullet_de_logro(l)
    ]

    # Camino IA (opt-in): si está activado y disponible, se intenta; ante cualquier
    # fallo o salida no válida, se cae transparentemente al motor de reglas.
    if usar_ia and ia_disponible:
        ia = _mejorar_con_ia(candidatos, sector, cv_texto, vacante)
        if ia is not None:
            return ia

    mejoras: List[Dict] = []
    contadores: Dict[str, int] = {}
    usados: set = set()          # plantillas ya usadas en este CV (evita repetición)
    n_verbos = n_metricas = 0

    for linea in candidatos:

        mejorado = linea
        tipos: List[str] = []

        # 1. Reescribir verbo debil
        if _es_bullet_debil(linea):
            reescrito = _reescribir_bullet(linea)
            if reescrito and reescrito.strip() != linea.strip():
                mejorado = reescrito
                tipos.append("verbo")

        # 2. Agregar metrica si no tiene numeros (apropiada al sector, sin repetir)
        if not tiene_metrica(mejorado):
            mejorado = agregar_metrica_a_bullet(mejorado, contadores, sector, usados)
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
        "recomendaciones": [],
        "resumen": resumen,
        # Advertencia explícita: las métricas sugeridas son marcadores, no datos reales.
        "advertencia": ADVERTENCIA_METRICAS if n_metricas else "",
        "fuente": "reglas",
        # Indica al frontend si puede ofrecer el botón "Mejorar con IA".
        "ia_disponible": ia_disponible,
    }
