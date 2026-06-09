"""
Motor ATS local — sin API externa.

Estrategia:
1. Extrae keywords relevantes de la vacante (técnicas, de dominio, habilidades).
2. Las busca en el CV (cobertura).
3. Calcula score_match basado en cobertura ponderada.
4. Reescribe el resumen del CV priorizando los términos de la vacante.
5. Genera notas de mejora accionables.
"""

import re
from typing import List, Set, Tuple

from app.models.schemas import AdaptarCVRequest, AdaptarCVResponse, CVAdaptado


# ---------------------------------------------------------------------------
# Stopwords — español + inglés ampliado
# ---------------------------------------------------------------------------
STOPWORDS: Set[str] = {
    # Español — funcionales
    "de", "la", "el", "en", "y", "a", "los", "las", "un", "una", "con",
    "por", "para", "que", "se", "su", "del", "al", "lo", "más", "como",
    "pero", "sus", "le", "ya", "o", "fue", "este", "ha", "si", "sobre",
    "ser", "tiene", "años", "también", "hay", "era", "muy", "sin", "entre",
    "nos", "mis", "mi", "tu", "es", "son", "están", "fue", "ser", "tener",
    "hacer", "poder", "parte", "vez", "cada", "todo", "todos", "todas",
    "este", "esta", "estos", "estas", "ese", "esa", "esos", "esas",
    # Español — genéricos de vacantes
    "trabajo", "empresa", "área", "equipo", "proyecto", "proyectos",
    "experiencia", "conocimiento", "conocimientos", "buscamos",
    "requerimos", "ofrecemos", "cargo", "puesto", "perfil", "requisitos",
    "funciones", "responsabilidades", "habilidades", "nivel", "grado",
    "titulo", "título", "licenciatura", "carrera", "egresado", "graduado",
    "mínimo", "minimo", "deseable", "indispensable", "preferente",
    "capacidad", "manejo", "buenas", "bueno", "buena", "excelente",
    "alta", "alto", "mediante", "través", "traves", "tanto", "bien",

    # Inglés — funcionales
    "the", "of", "and", "to", "in", "is", "it", "you", "that", "he",
    "was", "for", "on", "are", "with", "as", "at", "this", "have",
    "from", "or", "an", "will", "be", "has", "but", "not", "what",
    "all", "were", "we", "when", "your", "can", "said", "there",
    "they", "she", "his", "her", "its", "our", "their", "which",
    "who", "whom", "how", "why", "where", "been", "being", "had",
    "do", "did", "does", "would", "could", "should", "may", "might",
    "shall", "must", "about", "above", "after", "before", "between",
    "into", "through", "during", "including", "without", "such",
    "also", "than", "then", "both", "each", "more", "most", "other",
    "some", "these", "those", "if", "so", "by", "up", "out", "no",
    "any", "only", "same", "very", "just", "over", "own",

    # Inglés — genéricos de vacantes
    "use", "experience", "skills", "knowledge", "team", "work",
    "looking", "required", "requirements", "responsibilities",
    "information", "location", "using", "years", "year", "key",
    "detail", "details", "professional", "ability", "provide",
    "support", "ensure", "maintain", "manage", "include", "including",
    "related", "relevant", "following", "strong", "excellent",
    "good", "great", "help", "need", "needs", "like", "make",
    "within", "across", "multiple", "various", "different",
    "large", "small", "new", "high", "low", "full", "part",
    "time", "based", "plus", "well", "highly", "least",
    "minimum", "preferred", "desirable", "required",
    "seeking", "candidate", "candidates", "position", "role",
    "join", "apply", "opportunities", "opportunity", "growing",
    "fast", "analytical", "proactive", "dynamic", "collaborative",
    "motivated", "organized", "oriented", "driven",
    "pressure", "environment", "environments", "conduct", "update",
    "updates", "improvements", "improvement", "exploratory",
    "effective", "efficient", "quality", "critical",
    "focus", "focused", "abilities", "communication",
    "written", "verbal", "interpersonal", "organizational",
    "problem", "solving", "thinking", "learning",
    "understanding", "demonstrate", "demonstrated",
    "proven", "track", "record", "hands", "working", "day",
    "daily", "weekly", "monthly", "ongoing", "current", "previous",
    # Verbos genéricos en inglés que no son habilidades
    "analyse", "analyze", "research", "contribute", "centre", "center",
    "global", "virtual", "dedicated", "experienced", "timely", "ideal",
    "honest", "solid", "background", "operate", "involves", "conducting",
    "reporting", "response", "investigation", "operation",
    "develop", "deliver", "execute", "perform", "report", "review",
    "identify", "assess", "create", "design", "build", "test", "deploy",
    "implement", "integrate", "configure", "install", "setup", "define",
    "document", "coordinate", "lead", "drive", "own", "handle", "serve",
    # Demasiado genéricos
    "tasks", "task", "platform", "platforms", "solutions", "solution",
    "tools", "tool", "systems", "system", "process", "processes",
    "infrastructure", "services", "service", "data", "access",
    "manner", "manager", "management", "education", "documentation",
    "development", "alerts", "alert", "timely", "review",
    "available", "procedures", "procedure", "escalating", "escalation",
    "initial", "assessments", "assessment", "activities", "activity",
    "incidents", "policies", "policy", "standards", "standard",
    "practices", "practice", "including", "ensure", "across",
    "within", "through", "against", "following", "based",
}

# ---------------------------------------------------------------------------
# Frases técnicas compuestas — se detectan antes de tokenizar
# ---------------------------------------------------------------------------
COMPOUND_TERMS = [
    # Seguridad
    "incident response", "threat hunting", "threat intelligence",
    "vulnerability management", "penetration testing", "security operations",
    "security operations center", "intrusion detection", "intrusion prevention",
    "endpoint detection", "endpoint response", "edr", "xdr",
    "security information", "security event management", "siem",
    "zero trust", "identity access management", "iam",
    "privileged access management", "pam", "data loss prevention", "dlp",
    "cloud security", "network security", "application security",
    "security awareness", "red team", "blue team", "purple team",
    "malware analysis", "forensic analysis", "digital forensics",
    "security assessment", "risk assessment", "compliance",
    # Cloud
    "amazon web services", "google cloud platform", "microsoft azure",
    "cloud computing", "cloud native", "infrastructure as code",
    "site reliability", "platform engineering",
    # Dev / Backend
    "machine learning", "deep learning", "natural language processing",
    "data science", "data engineer", "data analyst", "business intelligence",
    "full stack", "frontend", "backend", "api rest", "restful api",
    "microservices", "event driven", "domain driven design",
    "continuous integration", "continuous delivery", "continuous deployment",
    "devops", "mlops", "gitops", "devsecops",
    # Frameworks / tecnologías comunes
    "react native", "node.js", "next.js", "spring boot",
    "kubernetes", "docker", "terraform", "ansible",
    "power bi", "tableau", "looker",
    "active directory", "microsoft 365", "office 365",
    # Metodologías
    "agile methodology", "metodología ágil", "scrum master",
    "project management", "gestión de proyectos",
    # Certificaciones cibersec
    "comptia security", "certified ethical hacker", "ceh",
    "certified information systems security", "cissp",
    "certified information security manager", "cism",
    "offensive security", "oscp", "giac",
]

# Términos técnicos de una sola palabra que SÍ deben considerarse habilidades
TECH_SINGLE = {
    # Lenguajes
    "python", "java", "javascript", "typescript", "golang", "rust", "scala",
    "kotlin", "swift", "php", "ruby", "perl", "bash", "powershell",
    "sql", "nosql", "graphql", "html", "css", "r",
    # Cloud / Infra
    "aws", "azure", "gcp", "kubernetes", "docker", "terraform", "ansible",
    "jenkins", "gitlab", "github", "bitbucket", "prometheus", "grafana",
    "elasticsearch", "kibana", "logstash", "splunk", "suricata", "snort",
    # Bases de datos
    "postgresql", "mysql", "mongodb", "redis", "cassandra", "dynamodb",
    "oracle", "mssql", "mariadb", "sqlite",
    # Seguridad
    "siem", "soar", "edr", "xdr", "ids", "ips", "waf", "dlp", "soc",
    "nmap", "wireshark", "metasploit", "burpsuite", "kali", "nessus",
    "qualys", "crowdstrike", "sentinelone", "carbonblack", "defender",
    "palo alto", "fortinet", "checkpoint", "cisco", "firewall",
    "mitre", "att&ck", "owasp", "iso27001", "nist", "pci", "hipaa",
    "gdpr", "sox", "cis",
    # Frameworks / librerías
    "react", "angular", "vue", "fastapi", "django", "flask", "spring",
    "express", "nestjs", "laravel", "rails",
    # Metodologías / certs
    "scrum", "kanban", "agile", "devops", "devsecops", "mlops",
    "cissp", "cism", "ceh", "oscp", "giac", "comptia",
    # Herramientas genéricas tech
    "git", "linux", "unix", "windows", "macos", "nginx", "apache",
    "kafka", "rabbitmq", "airflow", "spark", "hadoop",
    "tableau", "powerbi", "looker", "dbt",
    # Conceptos tech válidos como keyword
    "api", "rest", "oauth", "jwt", "tls", "ssl", "vpn", "dns", "ldap",
    "tcp", "udp", "http", "https", "smtp", "ftp", "ssh",
    "blockchain", "kubernetes", "serverless", "microservices",
    "ransomware", "malware", "phishing", "forensics", "forensic",
    "playbooks", "runbooks", "automation", "orchestration",
    "monitoring", "alerting", "logging", "tracing",
    "hunting", "triage", "remediation", "mitigation", "hardening",
    "pentest", "pentesting", "vulnerability", "exploit", "patch",
    "azure", "sentinel", "defender", "chronicle", "qradar",
    # Productos SIEM / seguridad comunes (para detectarlos aunque vengan en minúscula)
    "wazuh", "logrhythm", "logscale", "elastic", "graylog", "opensearch",
    "fortianalyzer", "fortinet", "sophos", "tenable", "harmony",
    "okta", "cloudflare", "zscaler", "proofpoint", "mimecast",
}

# Palabras que pueden aparecer Capitalizadas (inicio de oración / títulos)
# pero NO son tecnologías ni habilidades — evita falsos positivos como nombre propio
_NO_PROPIOS: Set[str] = {
    "must", "strong", "good", "great", "nice", "key", "main", "essential",
    "preferred", "required", "desirable", "responsibilities", "requirements",
    "experience", "knowledge", "ability", "candidate", "role", "about",
    "join", "why", "what", "who", "how", "when", "where", "this", "that",
    "they", "you", "our", "the", "your", "their", "cybersecurity", "security",
    "information", "support", "analyst", "engineer", "manager", "team",
    "work", "working", "company", "looking", "seeking", "position",
    "responsible", "including", "ensure", "provide", "perform", "develop",
    "manage", "lead", "monitor", "investigate", "respond", "detect",
    "education", "skills", "summary", "profile", "objective", "contact",
    "location", "phone", "email", "languages", "certifications", "references",
    "please", "apply", "send", "contact", "note", "duties", "tasks",
}


# ---------------------------------------------------------------------------
# Utilidades de texto
# ---------------------------------------------------------------------------

def _normalizar(texto: str) -> str:
    return re.sub(r"[^\w\sáéíóúüñ.#+]", " ", texto.lower())


def _extraer_compuestos(texto: str) -> List[str]:
    texto_n = _normalizar(texto)
    return [t for t in COMPOUND_TERMS if t in texto_n]


def _tokenizar(texto: str) -> List[str]:
    tokens = re.findall(r"\b[a-záéíóúüña-z0-9][a-záéíóúüña-z0-9+#.\-]{2,}\b",
                        _normalizar(texto))
    return [t for t in tokens if t not in STOPWORDS and not t.isdigit()]


def _tokens_propios(texto: str) -> Set[str]:
    """
    Detecta tokens que aparecen como tecnología/producto en el texto original:
    - Siglas en mayúsculas (AWS, OSCP, SIEM, EDR, XDR, GCP, SOC, IAM).
    - Nombres propios capitalizados a mitad de oración (Splunk, Wazuh, Sentinel,
      Elastic, LogScale) — precedidos por palabra en minúscula o coma, lo que
      descarta las palabras capitalizadas por inicio de oración o título.
    Devuelve los tokens en minúscula.
    """
    propios: Set[str] = set()

    # Siglas: 2-6 caracteres en mayúsculas/dígitos
    for m in re.finditer(r"\b([A-Z][A-Z0-9]{1,5})\b", texto):
        w = m.group(1).lower()
        if w not in STOPWORDS:
            propios.add(w)

    # Nombres propios a mitad de oración: precedidos por minúscula o coma
    for m in re.finditer(r"[a-z,]\s+([A-Z][a-z]{2,15})\b", texto):
        w = m.group(1).lower()
        if w not in STOPWORDS and w not in _NO_PROPIOS:
            propios.add(w)

    return propios


def _nombres_empresa(texto: str) -> Set[str]:
    """
    Detecta posibles nombres de empresa en el texto para excluirlos de keywords.
    Busca palabras que siguen a patrones como 'at Empresa', 'join Empresa',
    'Empresa is', 'Empresa,'.
    """
    patron = re.compile(
        r"\b(?:at|join|for|company|empresa)\s+([A-Z][a-z]{2,15})\b|"
        r"\b([A-Z][a-z]{2,15})\s+(?:is |are |was |provides |offers |seeks )",
        re.MULTILINE,
    )
    nombres: Set[str] = set()
    for m in patron.finditer(texto):
        nombre = (m.group(1) or m.group(2) or "").lower()
        if nombre and nombre not in STOPWORDS:
            nombres.add(nombre)
    return nombres


# Títulos de puesto comunes (para validar la deteccion)
_PALABRAS_TITULO = re.compile(
    r"(analyst|engineer|developer|manager|specialist|coordinator|administrator|"
    r"architect|consultant|lead|director|officer|technician|designer|scientist|"
    r"analista|ingenier|desarrollador|gerente|especialista|coordinador|"
    r"administrador|arquitecto|consultor|tecnico|t[eé]cnico|dise[nñ]ador|"
    r"responsable|jefe|director)",
    re.IGNORECASE)

_LIMPIEZA_TITULO = re.compile(
    r"^\s*(we\s+are\s+)?(currently\s+)?(looking|hiring|seeking|searching|"
    r"buscamos|busca|requerimos|solicitamos|necesitamos)\s+"
    r"(for\s+)?(an?\s+|una?\s+|un\s+)?",
    re.IGNORECASE)


def _detectar_titulo_vacante(vacante: str) -> str:
    """
    Intenta extraer el titulo del puesto de una vacante.
    Busca patrones explicitos y, si no, la primera linea corta con pinta de cargo.
    """
    lineas = [l.strip() for l in vacante.splitlines() if l.strip()]
    if not lineas:
        return ""

    # 1. Patrones explicitos: "Puesto: X", "Position: X", "Role: X", "Vacante: X"
    for l in lineas[:15]:
        m = re.match(r"(?:puesto|cargo|position|role|job\s*title|t[ií]tulo|vacante)"
                     r"\s*[:\-]\s*(.+)", l, re.IGNORECASE)
        if m:
            titulo = m.group(1).strip(" .-")
            if 2 <= len(titulo.split()) <= 8:
                return titulo

    # 2. "We are looking for a <titulo>" / "Buscamos un/una <titulo>"
    for l in lineas[:15]:
        m = re.search(r"(?:looking for|hiring|seeking|buscamos|busca|"
                      r"solicitamos|requerimos|necesitamos)\s+(?:an?\s+|una?\s+|un\s+)?"
                      r"([A-Za-zÁ-úÑñ /&-]{3,50})", l, re.IGNORECASE)
        if m:
            cand = m.group(1).strip(" .-,")
            cand = re.split(r"\b(?:with|who|to|that|para|con|que)\b", cand, 1, re.IGNORECASE)[0].strip()
            if _PALABRAS_TITULO.search(cand) and 1 <= len(cand.split()) <= 6:
                return cand

    # 3. Primera linea corta que parezca un cargo
    for l in lineas[:5]:
        limpia = _LIMPIEZA_TITULO.sub("", l).strip(" .-")
        if _PALABRAS_TITULO.search(limpia) and len(limpia) <= 60 and len(limpia.split()) <= 8:
            # quitar sufijos tipo "(Remote)", "- Madrid"
            limpia = re.split(r"[\(\-–—|]| at | en ", limpia)[0].strip()
            if limpia:
                return limpia

    return ""


def _titulo_en_cv(titulo: str, cv_texto: str) -> bool:
    """
    True si el titulo del puesto aparece como FRASE en el CV (no palabras sueltas).
    Tolera variaciones de seniority (Senior/Junior/Lead...).
    """
    if not titulo:
        return True
    cv_n = _normalizar(cv_texto)
    titulo_n = re.sub(r"\s+", " ", _normalizar(titulo)).strip()
    if not titulo_n:
        return True
    # 1. Frase exacta presente
    if titulo_n in cv_n:
        return True
    # 2. Sin palabras de seniority
    nucleo = re.sub(r"\b(senior|sr|junior|jr|lead|principal|staff|mid|semi\s*senior|ssr)\b",
                    "", titulo_n)
    nucleo = re.sub(r"\s+", " ", nucleo).strip()
    if nucleo and nucleo != titulo_n and nucleo in cv_n:
        return True
    return False


def _keywords_de(texto: str) -> List[str]:
    """
    Keywords únicas del texto: compuestos técnicos primero, luego tokens simples.
    Un token simple solo se acepta si es técnico conocido (TECH_SINGLE) o si
    aparece como nombre propio / sigla en el original (tecnología o producto).
    Esto evita el ruido de palabras genéricas (issues, hypothesis, resources…).
    """
    compuestos = _extraer_compuestos(texto)
    tokens     = _tokenizar(texto)
    excluir    = _nombres_empresa(texto)
    propios    = _tokens_propios(texto)

    cubiertos = set()
    for comp in compuestos:
        for parte in comp.split():
            cubiertos.add(parte)

    simples = []
    freq: dict = {}
    for t in tokens:
        if t in cubiertos or t in excluir:
            continue
        freq[t] = freq.get(t, 0) + 1
        # Solo aceptar términos técnicos conocidos o nombres propios/siglas reales
        if t in TECH_SINGLE or t in propios:
            if t not in simples:
                simples.append(t)

    simples_ordenados = sorted(simples, key=lambda x: -freq.get(x, 1))
    return compuestos + simples_ordenados


# ---------------------------------------------------------------------------
# Análisis principal
# ---------------------------------------------------------------------------

def _analizar_cobertura(
    kw_vacante: List[str], texto_cv: str
) -> Tuple[List[str], List[str]]:
    texto_cv_n = _normalizar(texto_cv)
    cubiertas, sugeridas = [], []
    for kw in kw_vacante:
        if kw in texto_cv_n:
            cubiertas.append(kw)
        else:
            sugeridas.append(kw)
    return cubiertas, sugeridas


def _calcular_score(cubiertas: List[str], total_vacante_kw: int) -> int:
    if total_vacante_kw == 0:
        return 0
    base = len(cubiertas) / total_vacante_kw
    score = int(base * 100)
    if base >= 0.6:
        score = min(100, score + 5)
    return max(0, min(100, score))


def _oraciones_de(texto: str) -> List[str]:
    oraciones = re.split(r"[.\n;]+", texto)
    return [o.strip() for o in oraciones if len(o.strip()) > 20]


def _mejor_resumen(cv_texto: str, kw_vacante: List[str], n: int = 3) -> str:
    oraciones = _oraciones_de(cv_texto)
    if not oraciones:
        return cv_texto[:200]
    kw_set = set(kw_vacante)

    def relevancia(oracion: str) -> int:
        text_n = _normalizar(oracion)
        return sum(1 for kw in kw_set if kw in text_n)

    mejores = sorted(oraciones, key=relevancia, reverse=True)[:n]
    return ". ".join(mejores).strip().rstrip(".") + "."


def _extraer_experiencias(cv_texto: str) -> List[str]:
    patrones_exp = re.compile(
        r"(20\d{2}|19\d{2}|empresa|company|trabaj|desarrollé|lideré|"
        r"gestioné|implementé|diseñé|coordiné|worked|developed|led|"
        r"managed|built|created|launched|analyst|engineer|specialist|"
        r"coordinator|manager|director)",
        re.IGNORECASE,
    )
    lineas = re.split(r"[\n;.]", cv_texto)
    exp = [l.strip() for l in lineas if patrones_exp.search(l) and len(l.strip()) > 15]
    return exp[:5] if exp else _oraciones_de(cv_texto)[:3]


def _extraer_habilidades(cv_texto: str, kw_vacante: List[str]) -> List[str]:
    """
    Extrae habilidades reales: solo términos en TECH_SINGLE o compuestos técnicos
    presentes en el CV. Prioriza los que también aparecen en la vacante.
    """
    texto_n = _normalizar(cv_texto)

    # Términos técnicos de una palabra presentes en el CV
    tech_en_cv = [t for t in TECH_SINGLE if t in texto_n]

    # Compuestos técnicos presentes en el CV
    compuestos_en_cv = _extraer_compuestos(cv_texto)

    # Ordenar: primero los que coincidan con la vacante
    kw_vac_set = set(kw_vacante)
    prioridad = [h for h in compuestos_en_cv + tech_en_cv if h in kw_vac_set]
    resto     = [h for h in compuestos_en_cv + tech_en_cv if h not in kw_vac_set]

    # Deduplicar manteniendo orden
    vistos: Set[str] = set()
    resultado = []
    for h in prioridad + resto:
        if h not in vistos:
            vistos.add(h)
            resultado.append(h)
    return resultado[:12]


def _generar_notas(
    cubiertas: List[str],
    sugeridas: List[str],
    score: int,
    cv_texto: str,
) -> List[str]:
    notas: List[str] = []

    if sugeridas:
        top = ", ".join(sugeridas[:4])
        notas.append(
            f"Incorpora estas palabras clave de la vacante en tu CV si las dominas: {top}."
        )

    if score < 40:
        notas.append(
            "Compatibilidad baja. Reescribe el resumen profesional usando el mismo "
            "vocabulario técnico que usa la vacante."
        )
    elif score < 70:
        notas.append(
            "Compatibilidad media. Agrega ejemplos concretos de cómo aplicaste "
            "las tecnologías que pide la vacante."
        )
    else:
        notas.append(
            "Buena compatibilidad. Refuerza el impacto con métricas cuantificables "
            "(%, tiempos, escala de incidentes manejados, etc.)."
        )

    if not re.search(r"\d+\s*%|\d+\s*(usuarios|clientes|incidentes|alerts|tickets|casos)",
                     cv_texto, re.IGNORECASE):
        notas.append(
            "Agrega métricas concretas: «Respondí X incidentes por semana», "
            "«Reduje el MTTR en un 30%», «Analicé Y alertas diarias»."
        )

    if len(cubiertas) < 3:
        notas.append(
            "Usa el mismo vocabulario técnico que la vacante — los ATS hacen "
            "búsqueda exacta de términos."
        )

    if len(cv_texto.split()) < 100:
        notas.append(
            "El CV es muy corto. Desarrolla cada experiencia: contexto, "
            "herramientas usadas y resultado obtenido."
        )

    return notas[:6]


# ---------------------------------------------------------------------------
# Función pública
# ---------------------------------------------------------------------------

def adaptar_cv(request: AdaptarCVRequest) -> AdaptarCVResponse:
    cv      = request.cv_texto
    vacante = request.vacante_texto

    # Limitar a las 30 keywords más relevantes para que el score sea justo
    kw_vacante             = _keywords_de(vacante)[:30]
    cubiertas, sugeridas   = _analizar_cobertura(kw_vacante, cv)
    score                  = _calcular_score(cubiertas, len(kw_vacante))
    resumen                = _mejor_resumen(cv, kw_vacante)
    experiencias           = _extraer_experiencias(cv)
    habilidades            = _extraer_habilidades(cv, kw_vacante)
    notas                  = _generar_notas(cubiertas, sugeridas, score, cv)

    # Job title match
    titulo_vacante = _detectar_titulo_vacante(vacante)
    titulo_cubierto = _titulo_en_cv(titulo_vacante, cv)
    if titulo_vacante and not titulo_cubierto:
        notas.insert(0, (
            f"El título del puesto «{titulo_vacante}» no aparece en tu CV. "
            "Inclúyelo en tu titular profesional o resumen — los ATS ponderan "
            "mucho la coincidencia de cargo."))
        notas = notas[:6]

    return AdaptarCVResponse(
        cv_adaptado=CVAdaptado(
            resumen=resumen,
            experiencia=experiencias,
            habilidades=habilidades,
        ),
        score_match=score,
        keywords_cubiertas=cubiertas[:15],
        keywords_sugeridas=sugeridas[:10],
        notas_para_usuario=notas,
        titulo_vacante=titulo_vacante or None,
        titulo_cubierto=titulo_cubierto,
    )
