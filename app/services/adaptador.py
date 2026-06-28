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
from app.services.keyword_aliases import equivalentes, norm_alias


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
    "api rest", "restful api",
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
    # Seguridad en español (con y sin acentos — el texto pegado varía)
    "respuesta a incidentes", "gestion de vulnerabilidades",
    "gestión de vulnerabilidades", "inteligencia de amenazas",
    "hacking etico", "hacking ético", "seguridad informatica",
    "seguridad informática", "seguridad de la informacion",
    "seguridad de la información", "analisis forense", "análisis forense",
    "esquema nacional de seguridad", "centro de operaciones de seguridad",
    "pruebas de penetracion", "pruebas de penetración",
    "concienciacion de seguridad", "concienciación de seguridad",
    "iso 27001", "iso 22301", "iso 27017",
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
    # Seguridad — normativa y términos en español
    "ciberseguridad", "rgpd", "lopd", "ens", "nis2", "dora", "enisa",
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
# Ruido que NUNCA es una habilidad — bloquea falsos positivos de la detección
# de nombres propios/siglas: botones de portales de empleo, ubicaciones,
# nombres de personas y jerga de reclutamiento (ES + EN).
# ---------------------------------------------------------------------------

RUIDO_PORTAL_EMPLEO: Set[str] = {
    # Interfaz de LinkedIn / Indeed / InfoJobs (inglés)
    "save", "saved", "easy", "apply", "applied", "applicants", "applicant",
    "show", "more", "less", "premium", "promoted", "sponsored", "featured",
    "tailor", "meet", "message", "messages", "connect", "connections",
    "follow", "followers", "following", "share", "report", "repost",
    "reposted", "posted", "hiring", "recruiter", "recruiters", "sign",
    "signin", "login", "notified", "notifications", "click", "view", "views",
    "profile", "insights", "actively", "reviewing", "learn", "jobs", "job",
    "alumni", "employees", "interview", "interviews", "resume", "resumes",
    "get", "see", "people", "company", "companies", "industry",
    # Interfaz en español
    "solicitar", "solicitud", "sencilla", "inscribete", "inscríbete",
    "inscripcion", "inscripción", "inscrito", "guardar", "guardado",
    "compartir", "denunciar", "empleo", "empleos", "anuncio", "anuncios",
    "candidatura", "candidaturas", "candidato", "candidatos", "postular",
    "postulate", "postúlate", "seguir", "seguidores", "conectar", "mensaje",
    "mensajes", "promocionado", "destacado", "patrocinado", "solicitantes",
    "activamente", "revisando", "ver", "vista", "perfil", "publicado",
    "republicado", "entrevista", "entrevistas", "contratacion", "contratación",
}

RUIDO_RECLUTAMIENTO: Set[str] = {
    # Marketing / RRHH en español
    "somos", "compromiso", "comprometida", "comprometido", "comprometidos",
    "talento", "seleccion", "selección", "igualdad", "diversidad",
    "inclusion", "inclusión", "oportunidades", "beneficios", "salario",
    "retribucion", "retribución", "vacaciones", "teletrabajo", "hibrido",
    "híbrido", "hibrida", "híbrida", "remoto", "remota", "jornada",
    "contrato", "indefinido", "flexible", "flexibilidad", "cultura",
    "valores", "mision", "misión", "vision", "visión", "crecimiento",
    "desarrollo", "formacion", "formación", "carrera", "unete", "únete",
    "cliente", "clientes", "cuenta", "cuentas", "tecnologia", "tecnología",
    "tecnologias", "tecnologías", "informacion", "información", "gerente",
    "lider", "líder", "lideres", "líderes", "personas", "gente", "ambiente",
    "entorno", "sector", "sectores", "ibex35", "ibex", "multinacional",
    "consultora", "consultor", "consultores", "analista", "analistas",
    "ingeniero", "ingeniera", "tecnico", "técnico", "especialista",
    "responsable", "coordinador", "coordinadora", "tech", "conoce",
    "consultoria", "consultoría",
    # Marketing / RRHH en inglés
    "benefits", "salary", "compensation", "perks", "culture", "mission",
    "vision", "values", "growth", "insurance", "vacation", "holidays",
    "equity", "bonus", "diversity", "inclusion", "equal", "employer",
    "sponsorship", "visa", "onboarding", "welcome", "package", "remote",
    "hybrid", "onsite", "office", "offices", "consulting", "acquisition",
    "talent", "group", "solutions", "services", "partners", "global",
}

APELLIDOS_COMUNES: Set[str] = {
    # Español
    "garcia", "garcía", "rodriguez", "rodríguez", "martinez", "martínez",
    "lopez", "lópez", "gonzalez", "gonzález", "hernandez", "hernández",
    "perez", "pérez", "sanchez", "sánchez", "ramirez", "ramírez", "torres",
    "flores", "rivera", "gomez", "gómez", "diaz", "díaz", "cruz", "morales",
    "reyes", "gutierrez", "gutiérrez", "ortiz", "jimenez", "jiménez",
    "ruiz", "alvarez", "álvarez", "mendoza", "castillo", "vasquez",
    "vazquez", "vázquez", "fernandez", "fernández", "romero", "herrera",
    "medina", "aguilar", "castro", "vargas", "ramos", "molina", "navarro",
    "dominguez", "domínguez", "gil", "serrano", "blanco", "suarez", "suárez",
    # Inglés
    "smith", "johnson", "williams", "brown", "jones", "miller", "davis",
    "wilson", "taylor", "moore", "jackson", "martin", "lee", "walker",
    "hall", "allen", "young", "king", "wright", "scott", "green", "baker",
    "adams", "nelson", "hill", "campbell", "mitchell", "roberts", "carter",
    "phillips", "evans", "turner", "parker", "collins", "edwards",
    "stewart", "morris", "murphy", "cook", "rogers", "morgan", "peterson",
    "cooper", "reed", "bailey", "bell", "kelly", "howard", "ward", "cox",
}

UBICACIONES: Set[str] = {
    "madrid", "barcelona", "valencia", "sevilla", "bilbao", "malaga",
    "málaga", "zaragoza", "españa", "espana", "spain", "portugal", "lisboa",
    "lisbon", "mexico", "méxico", "guadalajara", "monterrey", "colombia",
    "bogota", "bogotá", "medellin", "medellín", "argentina", "chile",
    "santiago", "peru", "perú", "lima", "ecuador", "quito", "venezuela",
    "caracas", "uruguay", "montevideo", "paraguay", "bolivia", "panama",
    "panamá", "guatemala", "honduras", "nicaragua", "dominicana",
    "latam", "latinoamerica", "latinoamérica", "europa", "europe",
    "london", "londres", "paris", "parís", "berlin", "berlín", "amsterdam",
    "dublin", "dublín", "francia", "france", "alemania", "germany",
    "italia", "italy", "miami", "texas", "florida", "california",
    "york", "usa", "eeuu",
}

NOMBRES_PILA: Set[str] = {
    # Español
    "maria", "maría", "marta", "beatriz", "carmen", "laura", "ana", "lucia",
    "lucía", "sara", "paula", "claudia", "cristina", "patricia", "raquel",
    "silvia", "elena", "irene", "alba", "andrea", "natalia", "monica",
    "mónica", "rocio", "rocío", "sandra", "sonia", "teresa", "veronica",
    "verónica", "julia", "eva", "ines", "inés", "nuria", "alicia", "angela",
    "ángela", "isabel", "sofia", "sofía", "valentina", "camila", "daniela",
    "gabriela", "alejandra", "fernanda", "jose", "josé", "juan", "carlos",
    "luis", "antonio", "javier", "david", "daniel", "miguel", "alejandro",
    "manuel", "francisco", "pablo", "sergio", "jorge", "alberto", "fernando",
    "diego", "raul", "raúl", "ivan", "iván", "ruben", "rubén", "oscar",
    "óscar", "adrian", "adrián", "alvaro", "álvaro", "marcos", "victor",
    "víctor", "hugo", "mario", "gonzalo", "andres", "andrés", "ricardo",
    "eduardo", "roberto", "pedro",
    # Inglés
    "john", "michael", "james", "robert", "william", "mary", "jennifer",
    "linda", "elizabeth", "susan", "jessica", "karen", "emily", "emma",
    "olivia", "peter", "thomas", "richard", "charles", "christopher",
    "matthew", "anthony", "mark", "steven", "paul", "andrew", "joshua",
    "kevin", "brian", "george", "kelly", "amy", "anna", "rachel", "sophie",
}

RUIDO_NO_SKILL: Set[str] = (RUIDO_PORTAL_EMPLEO | RUIDO_RECLUTAMIENTO
                            | UBICACIONES | NOMBRES_PILA | APELLIDOS_COMUNES)

# Términos demasiado genéricos para contar como skill/keyword por sí solos.
# Son palabras de prosa, no tecnologías. Se filtran tanto en la extracción de
# keywords (no aparecen como cubiertas/sugeridas) como en la de habilidades.
GENERICO_NO_SKILL: Set[str] = {
    "backend", "frontend", "fullstack", "full stack", "web", "software",
    "developer", "development", "developers", "technologies", "technology",
    "tecnologias", "tecnologías", "tecnologia", "tecnología", "desarrollo",
    "sistemas", "sistema", "programador", "programacion", "programación",
    "informatica", "informática", "tecnico", "técnico", "ingenieria", "ingeniería",
}
_GEN_NORM: Set[str] = {norm_alias(_g) for _g in GENERICO_NO_SKILL}


# ---------------------------------------------------------------------------
# Utilidades de texto
# ---------------------------------------------------------------------------

def _normalizar(texto: str) -> str:
    return re.sub(r"[^\w\sáéíóúüñ.#+]", " ", texto.lower())


def _kw_presente(texto_n: str, kw: str) -> bool:
    """
    True si la keyword aparece como palabra/frase COMPLETA en el texto
    normalizado. Evita falsos positivos por substring: «get» no debe
    coincidir dentro de «targeted», ni «ens» dentro de «citizens».
    """
    kw_n = _normalizar(kw).strip()
    if not kw_n:
        return False
    patron = re.escape(kw_n).replace("\\ ", " ")
    patron = re.sub(r"\s+", r"\\s+", patron)
    patron = r"(?<![a-z0-9áéíóúüñ])" + patron + r"(?![a-z0-9áéíóúüñ])"
    return re.search(patron, texto_n) is not None


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
        if w not in STOPWORDS and w not in RUIDO_NO_SKILL:
            propios.add(w)

    # Nombres propios a mitad de oración: precedidos por minúscula o coma
    # EN LA MISMA LÍNEA (un salto de línea indica inicio de oración/título,
    # donde las mayúsculas no implican producto/tecnología).
    for m in re.finditer(r"[a-z,][ \t]+([A-Z][a-z]{2,15})\b", texto):
        w = m.group(1).lower()
        if (w not in STOPWORDS and w not in _NO_PROPIOS
                and w not in RUIDO_NO_SKILL):
            propios.add(w)

    return propios


def _nombres_empresa(texto: str) -> Set[str]:
    """
    Detecta posibles nombres de empresa en el texto para excluirlos de keywords.
    Busca palabras que siguen a patrones como 'at Empresa', 'join Empresa',
    'Empresa is', 'Empresa,'.
    """
    patron = re.compile(
        r"\b(?:at|join|for|company|empresa|en|para|trabajar[aá]s en|[uú]nete a)\s+"
        r"([A-Z][a-zA-Z0-9&.\-]{1,18})\b|"
        r"\b([A-Z][a-zA-Z0-9&.\-]{1,18})\s+(?:is |are |was |provides |offers |seeks |"
        r"hiring |es una |es la |somos |ofrece |busca |necesita |requiere |"
        r"l[ií]der en |se dedica )",
        re.MULTILINE,
    )
    nombres: Set[str] = set()
    for m in patron.finditer(texto):
        nombre = (m.group(1) or m.group(2) or "").lower().strip(".-&")
        # No descartar términos técnicos reales (python, aws…) aunque sigan a 'en/for'
        if (nombre and nombre not in STOPWORDS and nombre not in TECH_SINGLE
                and nombre not in UBICACIONES):
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

# Cargos conocidos (EN y ES). Permite detectar el título aunque venga en una
# línea larga junto a skills: "Backend Developer Python FastAPI Docker …".
_SEN = r"(?:senior|sr\.?|junior|jr\.?|lead|principal|staff|mid|semi[\s-]?senior|ssr)"
_DOM_EN = (r"(?:back[\s-]?end|front[\s-]?end|full[\s-]?stack|data|software|web|mobile|"
           r"cloud|dev\s?ops|qa|q\.a\.|security|machine\s+learning|ml|ai|product|"
           r"project|business|systems?|network|database|platform|site\s+reliability)")
_ROL_EN = (r"(?:developer|engineer|analyst|manager|specialist|coordinator|architect|"
           r"consultant|administrator|scientist|programmer|designer|director)")
_ROL_ES = (r"(?:desarrollador(?:a)?|ingenier[oa]|analista|gerente|especialista|"
           r"coordinador(?:a)?|arquitect[oa]|consultor(?:a)?|administrador(?:a)?|"
           r"cient[ií]fic[oa]|programador(?:a)?|dise[nñ]ador(?:a)?|responsable|jefe)")
_DOM_ES = (r"(?:back[\s-]?end|front[\s-]?end|full[\s-]?stack|datos|software|web|"
           r"sistemas?|proyectos?|producto|seguridad|dev\s?ops|qa|cloud|nube|"
           r"m[oó]viles?|redes?|calidad)")
_TITULO_CARGO = re.compile(
    r"\b("
    rf"(?:{_SEN}\s+)?(?:{_DOM_EN}\s+)?{_ROL_EN}"                      # EN: Backend Developer
    r"|"
    rf"{_ROL_ES}(?:\s+(?:de\s+|en\s+)?{_DOM_ES})?(?:\s+{_SEN})?"      # ES: Ingeniero de Software
    r")\b",
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

    # 3. Cargo conocido cerca del inicio, aunque venga junto a skills en la
    #    misma línea ("Backend Developer Python FastAPI …" / "Desarrollador Backend …").
    cabecera = re.sub(r"\s+", " ", " ".join(lineas[:3]))[:160]
    m = _TITULO_CARGO.search(cabecera)
    if m:
        cand = m.group(1).strip(" .-")
        # Exigir ≥2 palabras para no capturar roles sueltos ambiguos ("Developer").
        if len(cand.split()) >= 2:
            return cand

    # 4. Primera linea corta que parezca un cargo
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
        return False
    cv_n = _normalizar(cv_texto)
    titulo_n = re.sub(r"\s+", " ", _normalizar(titulo)).strip()
    if not titulo_n:
        return False
    # 1. Frase exacta presente (como frase completa, no substring)
    if _kw_presente(cv_n, titulo_n):
        return True
    # 2. Sin palabras de seniority
    nucleo = re.sub(r"\b(senior|sr|junior|jr|lead|principal|staff|mid|semi\s*senior|ssr)\b",
                    "", titulo_n)
    nucleo = re.sub(r"\s+", " ", nucleo).strip()
    if nucleo and nucleo != titulo_n and _kw_presente(cv_n, nucleo):
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
    resultado = compuestos + simples_ordenados
    # Filtrar términos genéricos de prosa que no son skills reales
    return [k for k in resultado if norm_alias(k) not in _GEN_NORM]


# ---------------------------------------------------------------------------
# Análisis principal
# ---------------------------------------------------------------------------

def _kw_cubierta(cv_alias: str, kw: str) -> bool:
    """
    True si la keyword (o cualquiera de sus equivalentes — sigla, forma expandida
    o variante de puntuación) aparece en el CV. `cv_alias` debe venir de
    `norm_alias(cv)`. Esto hace el matching SEMÁNTICO: «aws» cubre «Amazon Web
    Services», «k8s» cubre «Kubernetes», «node.js» cubre «nodejs», etc.
    """
    for variante in equivalentes(kw):
        if _kw_presente(cv_alias, variante):
            return True
    return False


_NEGACION = (r"(?:no|sin|nunca|carece de|falta de|desconozco|without|"
             r"lack of|no experience(?: in)?|sin experiencia(?: en)?)")


def _kw_negada(cv_alias: str, kw: str) -> bool:
    """
    True si la keyword aparece en CONTEXTO NEGATIVO (precedida por una negación a
    ≤3 palabras): «sin experiencia en Python», «no domino AWS». Evita marcar como
    cubierta una skill que el CV declara NO tener.
    """
    for var in equivalentes(kw):
        patron = re.compile(
            rf"\b{_NEGACION}\s+(?:\w+\s+){{0,3}}{re.escape(var)}\b", re.IGNORECASE)
        if patron.search(cv_alias):
            return True
    return False


def _keywords_negadas(kw_vacante: List[str], texto_cv: str) -> List[str]:
    """Keywords que aparecen pero en contexto negativo (no cuentan como cubiertas)."""
    cv_alias = norm_alias(texto_cv)
    return [kw for kw in kw_vacante
            if norm_alias(kw) not in _GEN_NORM
            and _kw_cubierta(cv_alias, kw) and _kw_negada(cv_alias, kw)]


def _analizar_cobertura(
    kw_vacante: List[str], texto_cv: str
) -> Tuple[List[str], List[str]]:
    """
    Compara keywords de la vacante contra el CV usando formas canónicas: una
    keyword cuenta como CUBIERTA si el CV contiene ella o cualquier equivalente.
    Las SUGERIDAS excluyen, por tanto, todo lo que ya está cubierto por sinónimo.
    """
    cv_alias = norm_alias(texto_cv)
    cubiertas, sugeridas = [], []
    for kw in kw_vacante:
        if norm_alias(kw) in _GEN_NORM:
            continue  # término genérico de prosa: ni cubierta ni sugerida
        if _kw_cubierta(cv_alias, kw) and not _kw_negada(cv_alias, kw):
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
    """
    Divide en oraciones por salto de línea, ';' o fin de oración REAL
    (.!? seguido de espacio y mayúscula). No parte tokens como «Node.js»,
    «3.5» o «REST APIs», cuyo punto está entre caracteres.
    """
    partes = re.split(r"(?<=[.!?])\s+(?=[A-ZÁÉÍÓÚÑ¿¡])|[\n;]+", texto)
    return [o.strip() for o in partes if len(o.strip()) > 20]


def _es_lista_o_contacto(oracion: str) -> bool:
    """Una 'oración' que en realidad es una lista de skills o datos de contacto."""
    if re.search(r"@|linkedin|github\.com|\+\d|\bphone\b|\bemail\b|\btel[eé]fono\b",
                 oracion, re.IGNORECASE):
        return True
    comas = oracion.count(",")
    palabras = oracion.split()
    # Muchas comas con items cortos = enumeración de skills, no prosa
    return comas >= 4 and len(palabras) / (comas + 1) < 3.0


def _unir_oraciones(oraciones: List[str]) -> str:
    """Une oraciones con un único punto y espacio (sin puntos dobles)."""
    limpias = [o.strip().rstrip(".").strip() for o in oraciones if o.strip()]
    return (". ".join(limpias) + ".") if limpias else ""


def _mejor_resumen(cv_texto: str, kw_vacante: List[str], n: int = 3) -> str:
    # 1. Preferir la sección de resumen/perfil del CV (prosa real, oración completa)
    secciones = _segmentar_secciones(cv_texto)
    base = " ".join(secciones.get("resumen", [])).strip()
    if len(base.split()) >= 12:
        oraciones = _oraciones_de(base)
        if oraciones:
            return _unir_oraciones(oraciones[:n])

    # 2. Respaldo: oraciones de prosa, excluyendo listas de skills y contacto
    todas = _oraciones_de(cv_texto)
    oraciones = [o for o in todas if not _es_lista_o_contacto(o)] or todas
    if not oraciones:
        corte = cv_texto.strip()[:200]
        return corte.rsplit(" ", 1)[0] if len(cv_texto.strip()) > 200 else corte

    kw_set = {_normalizar(k) for k in kw_vacante}

    def relevancia(oracion: str) -> int:
        n_o = _normalizar(oracion)
        return sum(1 for kw in kw_set if kw in n_o)

    elegidas = sorted(oraciones, key=relevancia, reverse=True)[:n]
    elegidas = sorted(elegidas, key=oraciones.index)  # conservar orden narrativo
    return _unir_oraciones(elegidas)


# ---------------------------------------------------------------------------
# Segmentacion de secciones (para no mezclar resumen/experiencia/skills)
# ---------------------------------------------------------------------------

_HEADERS_SECCION = {
    "resumen": re.compile(
        r"^(professional\s+summary|summary|profile|perfil(\s+profesional)?|"
        r"resumen(\s+profesional)?|objetivo(\s+profesional)?|about\s+me|sobre\s+m[ií])$", re.I),
    "experiencia": re.compile(
        r"^(work\s+experience|professional\s+experience|experience|"
        r"experiencia(\s+(laboral|profesional))?|employment(\s+history)?|"
        r"trayectoria(\s+profesional)?|historial\s+laboral)$", re.I),
    "educacion": re.compile(
        r"^(education|educaci[oó]n|formaci[oó]n(\s+acad[eé]mica)?|academic\s+background)$", re.I),
    "habilidades": re.compile(
        r"^(technical\s+skills?|core\s+competencies|skills?|"
        r"habilidades(\s+(t[eé]cnicas?|clave))?|competencias?|"
        r"conocimientos(\s+t[eé]cnicos?)?|technologies|tech\s+stack)$", re.I),
    "idiomas": re.compile(r"^(languages?|idiomas?)$", re.I),
    "certificaciones": re.compile(r"^(certifications?|certificaciones?|licenses?)$", re.I),
    "proyectos": re.compile(r"^(projects?|proyectos?)$", re.I),
    "logros": re.compile(r"^(key\s+achievements?|achievements?|logros|awards?|reconocimientos?)$", re.I),
    "contacto": re.compile(
        r"^(contact(\s+information)?|contacto|informaci[oó]n\s+de\s+contacto|datos\s+personales)$", re.I),
}


def _limpiar_bullet(linea: str) -> str:
    """Quita prefijos de viñeta ('- ', '• ', '* ', '– ', '·', etc.) del inicio."""
    return re.sub(r"^\s*[-–—•·*▪●○‣◦]+\s+", "", linea.strip())


def _segmentar_secciones(cv_texto: str) -> dict:
    """
    Divide el CV en secciones por encabezados conocidos. Devuelve
    {tipo: [lineas]} sin arrastrar contenido de una sección a otra.
    'encabezado' contiene lo previo a la primera sección (nombre/contacto).
    """
    secciones: dict = {"encabezado": []}
    actual = "encabezado"
    for linea in cv_texto.splitlines():
        s = linea.strip().rstrip(":").strip()
        tipo = None
        if s and len(s) < 50:
            for t, pat in _HEADERS_SECCION.items():
                if pat.match(s):
                    tipo = t
                    break
        if tipo:
            actual = tipo
            secciones.setdefault(actual, [])
        elif linea.strip():
            secciones.setdefault(actual, []).append(linea.strip())
    return secciones


def _extraer_experiencias(cv_texto: str) -> List[str]:
    """
    Extrae bullets de la sección de EXPERIENCIA respetando los encabezados, sin
    arrastrar frases del resumen y limpiando los prefijos de viñeta. Si el CV no
    tiene encabezados reconocibles, usa una heurística de respaldo.
    """
    secciones = _segmentar_secciones(cv_texto)
    lineas_exp = secciones.get("experiencia", [])
    if lineas_exp:
        exp = [_limpiar_bullet(l) for l in lineas_exp if len(_limpiar_bullet(l)) > 15]
        if exp:
            return exp[:6]

    # Respaldo: CV sin encabezados claros → heurística por verbos/fechas
    patrones_exp = re.compile(
        r"(20\d{2}|19\d{2}|empresa|company|trabaj|desarrollé|lideré|"
        r"gestioné|implementé|diseñé|coordiné|worked|developed|led|"
        r"managed|built|created|launched|analyst|engineer|specialist|"
        r"coordinator|manager|director)",
        re.IGNORECASE,
    )
    lineas = re.split(r"[\n;]", cv_texto)
    exp = [_limpiar_bullet(l.strip()) for l in lineas
           if patrones_exp.search(l) and len(l.strip()) > 15]
    return exp[:5] if exp else _oraciones_de(cv_texto)[:3]


_TIENE_RANGO = re.compile(r"((19|20)\d{2}|'\d{2})\s*[-–—a]\s*|present|presente|actual",
                          re.IGNORECASE)

# Una línea que EMPIEZA con verbo de acción es un logro, no un título ni empresa
_VERBO_INICIO = re.compile(
    r"^(constru|lider|gestion|desarroll|implement|dise[nñ]|cre[ée]|coordin|analic|"
    r"logr|aument|reduj|mejor|dirig|ejecut|optimic|automatic|mantuv|realic|monitor|"
    r"led|managed|built|developed|created|designed|implemented|reduced|increased|"
    r"improved|launched|delivered|drove|optimized|achieved|resolved|analyzed|"
    r"coordinated|automated|maintained|spearheaded|streamlined|oversaw|administered)",
    re.IGNORECASE)


def _experiencia_estructurada(cv_texto: str) -> List[dict]:
    """
    Agrupa la sección de experiencia en bloques puesto → logros, preservando la
    jerarquía (cargo como encabezado, tareas como viñetas). Devuelve
    [{"titulo": str, "bullets": [str]}]. Vacío si no hay sección reconocible.
    """
    lineas = _segmentar_secciones(cv_texto).get("experiencia", [])
    puestos: List[dict] = []
    actual = None
    empresa_capturada = False
    for raw in lineas:
        l = _limpiar_bullet(raw)
        if len(l) < 3:
            continue
        empieza_verbo = bool(_VERBO_INICIO.match(l))
        es_titulo = (not empieza_verbo and
                     ((len(l) < 75 and _PALABRAS_TITULO.search(l))
                      or (len(l) < 80 and _TIENE_RANGO.search(l))))
        if es_titulo:
            actual = {"titulo": l, "bullets": []}
            puestos.append(actual)
            empresa_capturada = False
        elif actual is None:
            actual = {"titulo": l, "bullets": []}
            puestos.append(actual)
            empresa_capturada = False
        elif (not actual["bullets"] and not empresa_capturada
              and len(l) < 55 and not empieza_verbo and not _TIENE_RANGO.search(l)):
            actual["titulo"] += " — " + l   # nombre de empresa / ubicación (una sola)
            empresa_capturada = True
        else:
            actual["bullets"].append(l)
    return puestos[:6]


_CASING_SKILL = {
    "python": "Python", "java": "Java", "javascript": "JavaScript",
    "typescript": "TypeScript", "docker": "Docker", "kubernetes": "Kubernetes",
    "postgresql": "PostgreSQL", "postgres": "PostgreSQL", "mysql": "MySQL",
    "mongodb": "MongoDB", "fastapi": "FastAPI", "django": "Django", "flask": "Flask",
    "react": "React", "angular": "Angular", "vue": "Vue.js", "nodejs": "Node.js",
    "node": "Node.js", "nosql": "NoSQL", "php": "PHP", "ruby": "Ruby", "golang": "Go",
    "github": "GitHub", "gitlab": "GitLab", "jenkins": "Jenkins", "terraform": "Terraform",
    "ansible": "Ansible", "kafka": "Kafka", "redis": "Redis", "graphql": "GraphQL",
    "elasticsearch": "Elasticsearch", "splunk": "Splunk", "wazuh": "Wazuh",
    "metasploit": "Metasploit", "wireshark": "Wireshark", "power bi": "Power BI",
    "powerbi": "Power BI", "tableau": "Tableau", "excel": "Excel", "google analytics":
    "Google Analytics", "fortinet": "Fortinet", "sophos": "Sophos",
}
_SIGLAS_UP = {"aws", "gcp", "sql", "html", "css", "api", "rest", "siem", "edr", "soc",
              "ids", "ips", "waf", "dlp", "ceh", "oscp", "cissp", "cism", "seo", "sem",
              "iam", "vpn", "ai", "ml", "nlp", "qa", "ci", "cd", "it", "ux", "ui", "rgpd",
              "ens", "nmap"}


def _formato_skill(s: str) -> str:
    """Capitalización canónica de una skill (docker -> Docker, aws -> AWS)."""
    sl = s.lower().strip()
    if sl in _CASING_SKILL:
        return _CASING_SKILL[sl]
    if sl in _SIGLAS_UP:
        return sl.upper()
    return s[:1].upper() + s[1:] if s else s


def _extraer_habilidades(cv_texto: str, kw_vacante: List[str]) -> List[str]:
    """
    Extrae habilidades reales (TECH_SINGLE o compuestos técnicos). Prioriza la
    SECCIÓN de habilidades si existe — así una palabra como «backend» que aparece
    en prosa del resumen no se cuenta como skill. Usa matching por palabra
    completa para evitar falsos positivos por substring.
    """
    secciones = _segmentar_secciones(cv_texto)
    lineas_skills = secciones.get("habilidades", [])
    fuente = "\n".join(lineas_skills) if lineas_skills else cv_texto
    texto_n = _normalizar(fuente)

    # Términos técnicos de una palabra presentes (palabra completa, sin genéricos)
    tech_en_cv = [t for t in TECH_SINGLE
                  if norm_alias(t) not in _GEN_NORM and _kw_presente(texto_n, t)]

    # Compuestos técnicos presentes (excluyendo los demasiado genéricos)
    compuestos_en_cv = [c for c in _extraer_compuestos(fuente)
                        if norm_alias(c) not in _GEN_NORM]

    # Ordenar: primero los que coincidan con la vacante
    kw_vac_set = set(kw_vacante)
    prioridad = [h for h in compuestos_en_cv + tech_en_cv if h in kw_vac_set]
    resto     = [h for h in compuestos_en_cv + tech_en_cv if h not in kw_vac_set]

    # Deduplicar manteniendo orden y aplicar capitalización canónica
    vistos: Set[str] = set()
    resultado = []
    for h in prioridad + resto:
        if h not in vistos:
            vistos.add(h)
            resultado.append(_formato_skill(h))
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
            "(%, tiempos, escala de proyectos/usuarios, etc.)."
        )

    if not re.search(r"\d+\s*%|\d+\s*(usuarios|clientes|incidentes|alerts|tickets|casos)",
                     cv_texto, re.IGNORECASE):
        # Ejemplo acorde al sector del CV (no jerga de seguridad si no aplica, 4.2).
        from app.services.mejorador_bullets import ejemplo_metricas
        notas.append(
            f"Agrega métricas concretas: {ejemplo_metricas(cv_texto)}."
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

    from app.services.scoring import calcular_score_compuesto
    from app.services.requisitos import analizar_requisitos

    # Limitar a las 30 keywords más relevantes para que el score sea justo
    kw_vacante             = _keywords_de(vacante)[:30]
    cubiertas, sugeridas   = _analizar_cobertura(kw_vacante, cv)

    # Job title match — sin cargo detectado en la vacante NO se marca cubierto.
    titulo_vacante = _detectar_titulo_vacante(vacante)
    titulo_cubierto = bool(titulo_vacante) and _titulo_en_cv(titulo_vacante, cv)

    # Score compuesto de 5 dimensiones (keywords, formato, estructura, contenido, cargo)
    desglose = calcular_score_compuesto(cv, vacante, cubiertas, sugeridas,
                                        kw_vacante, titulo_vacante or "")
    score = desglose["total"]

    requisitos = analizar_requisitos(cv, vacante)

    resumen                = _mejor_resumen(cv, kw_vacante)
    experiencias           = _extraer_experiencias(cv)
    experiencia_estruct    = _experiencia_estructurada(cv)
    habilidades            = _extraer_habilidades(cv, kw_vacante)
    notas                  = _generar_notas(cubiertas, sugeridas, score, cv)
    if titulo_vacante and not titulo_cubierto:
        notas.insert(0, (
            f"El título del puesto «{titulo_vacante}» no aparece en tu CV. "
            "Inclúyelo en tu titular profesional o resumen — los ATS ponderan "
            "mucho la coincidencia de cargo."))
        notas = notas[:6]

    # Keywords en contexto negativo (SCORE-EX-02)
    negadas = _keywords_negadas(kw_vacante, cv)
    if negadas:
        notas.insert(0, (
            f"Contexto negativo detectado en: {', '.join(negadas[:3])} "
            "(p. ej. «sin experiencia en…»). No cuentan como cubiertas; si dominas "
            "esas habilidades, reformula para no negarlas."))
        notas = notas[:6]

    _sb_map = {
        "Keywords match": "keywords_match", "Formato ATS": "formato_ats",
        "Estructura y secciones": "estructura", "Calidad de contenido": "calidad_contenido",
        "Cargo objetivo": "cargo_objetivo",
    }
    score_breakdown = {
        _sb_map[d["nombre"]]: {"score": d["puntos"], "max": d["max"]}
        for d in desglose["dimensiones"] if d["nombre"] in _sb_map
    }

    return AdaptarCVResponse(
        cv_adaptado=CVAdaptado(
            resumen=resumen,
            experiencia=experiencias,
            habilidades=habilidades,
            experiencia_estructurada=experiencia_estruct or None,
        ),
        score_match=score,
        keywords_cubiertas=cubiertas[:15],
        keywords_sugeridas=sugeridas[:10],
        notas_para_usuario=notas,
        titulo_vacante=titulo_vacante or None,
        titulo_cubierto=titulo_cubierto,
        score_desglose=desglose,
        score=score,
        score_breakdown=score_breakdown,
        keywords_hard_skills_cubiertas=desglose.get("hard_cubiertas", [])[:15],
        keywords_soft_skills_cubiertas=desglose.get("soft_cubiertas", []),
        keywords_hard_skills_faltantes=desglose.get("hard_faltantes", [])[:10],
        keywords_soft_skills_faltantes=desglose.get("soft_faltantes", []),
        contact_info=desglose.get("contact_info"),
        content_signals=desglose.get("content_signals"),
        requisitos=requisitos,
    )
