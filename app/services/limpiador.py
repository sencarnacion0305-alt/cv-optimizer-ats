"""
Limpiador de descripciones de vacantes.

Estrategia:
- Divide el texto en bloques por saltos de línea / secciones con encabezado.
- Clasifica cada bloque como RELEVANTE o RUIDO según palabras clave del título
  y del contenido.
- Devuelve solo los bloques relevantes, reconstridos como texto limpio.

Sin dependencias externas — solo stdlib.
"""

import re
from typing import List

# ---------------------------------------------------------------------------
# Palabras que indican una sección RELEVANTE (requisitos, tareas, perfil)
# ---------------------------------------------------------------------------
TITULOS_RELEVANTES = re.compile(
    r"(requisit|requerim|responsabilidad|funcion|actividad|tarea|perfil|"
    r"habilidad|competencia|conocimiento|experiencia|tecnolog|stack|skill|"
    r"qualif|requirement|responsibilit|duties|what you.ll do|what we.re looking|"
    r"who you are|must.have|nice.to.have|you will|you should|we need|"
    r"esperamos|buscamos en ti|que buscamos|lo que haras|lo que esperamos|"
    r"formacion|educacion|education|degree|certificacion|idioma|language)",
    re.IGNORECASE,
)

# ---------------------------------------------------------------------------
# Palabras que indican una sección de RUIDO (beneficios, empresa, legal)
# ---------------------------------------------------------------------------
TITULOS_RUIDO = re.compile(
    r"(beneficio|benefit|ofrecemos|te ofrecemos|what we offer|we offer|"
    r"sobre nosotros|sobre la empresa|acerca de|about us|about the company|"
    r"nuestra cultura|our culture|our values|nuestros valores|"
    r"por que trabajar|why join|why work|why us|join us|"
    r"what.s in it|what we provide|what you.ll get|what.s on offer|"
    r"perks and benefit|our benefit|employee benefit|"
    r"oportunidad igual|equal opportunit|diversity|diversidad|inclusion|"
    r"como aplicar|how to apply|para aplicar|to apply|postular|"
    r"salario|sueldo|compensacion|salary|compensation|pay range|"
    r"seguro|insurance|vacaciones|vacation|pto|tiempo libre|"
    r"home office|remoto|hibrido|ubicacion|location|modalidad|"
    r"horario|schedule|jornada|turno|"
    r"prestaciones|paquete|package|perks|"
    r"contrato|contract|tipo de empleo|employment type|"
    r"about the team|about our team|our team|meet the team|"
    r"cutting.edge|collaborative environment|career advancement|"
    r"professional development|certification support|growing team)",
    re.IGNORECASE,
)

# Líneas de interfaz de portales de empleo (LinkedIn, Indeed, InfoJobs...)
# que se cuelan al copiar y pegar la página completa.
LINEA_UI_PORTAL = re.compile(
    r"^\s*[•·\-|]*\s*(save|saved|easy apply|apply now|applied|apply|promoted|"
    r"reposted|premium|message|show more|show less|see more|see less|"
    r"follow|following|connect|share|report this job|"
    r"tailor my resume|am i a good fit|how should i prepare|"
    r"meet the hiring team|about the job|about us|people you can reach|"
    r"actively reviewing applicants|x{0,3}\d*\s*applicants?|"
    r"solicitud sencilla|solicitar ahora|solicitar|inscr[ií]bete|guardar|"
    r"guardado|compartir|denunciar( este)?( empleo)?|promocionado|"
    r"publicado de nuevo|sobre el empleo|acerca del empleo|"
    r"conoce al equipo( de contrataci[oó]n)?|ver m[aá]s|ver menos|mensaje|"
    r"\d+\s*(solicitudes|candidatos)|hace\s+\d+\s*(d[ií]as?|horas?|semanas?))"
    r"\s*[•·\-|]*\s*$",
    re.IGNORECASE,
)

# Líneas de ruido independientemente de la sección (frases legales, etc.)
LINEAS_RUIDO = re.compile(
    r"(equal opportunity|employer|somos un empleador|"
    r"nos comprometemos|we are committed|we celebrate|"
    r"sin importar|regardless of|race|gender|disability|"
    r"aplica (hoy|ahora|aqui)|apply (now|today|here)|"
    r"envia tu|send your|manda tu|submit your|"
    r"cutting.edge|collaborative environment|career advancement|"
    r"certification support|professional development|"
    r"directly contributes|safeguarding critical|"
    r"you will work with|where your expertise|"
    r"growing soc team|growing team|join our|join the|"
    # Beneficios / cultura sueltos (línea por línea), aunque no tengan encabezado
    r"seguro\s+(m[eé]dico|de\s+salud|dental|de\s+vida)|health\s+insurance|"
    r"comida\s+gratis|free\s+(food|lunch|snacks)|caf[eé]\s+gratis|fruta\s+gratis|"
    r"salario\s+competitivo|competitive\s+salary|sueldo\s+competitivo|"
    r"d[ií]as?\s+de\s+vacaciones|paid\s+time\s+off|\bpto\b|vacation\s+days|"
    r"horario\s+flexible|flexible\s+(hours|schedule)|teletrabajo|home\s+office|"
    r"trabajo\s+remoto|remote\s+work|plan\s+de\s+pensiones|retirement\s+plan|"
    r"\b401k\b|stock\s+options|bonus\s+anual|annual\s+bonus|gimnasio|gym\s+membership|"
    r"eventos\s+de\s+equipo|team\s+building|ambiente\s+(joven|din[aá]mico)|gran\s+ambiente)",
    re.IGNORECASE,
)

# ---------------------------------------------------------------------------
# Marcadores de sección (pueden aparecer INLINE, no solo como encabezado)
# ---------------------------------------------------------------------------

_MARC_RUIDO = re.compile(
    r"(we\s+offer|what\s+we\s+offer|\bbenefits?\b|\bperks?\b|about\s+us|"
    r"about\s+the\s+company|our\s+culture|company\s+culture|our\s+values|"
    r"why\s+(?:join|work)|equal\s+opportunit|\bcompensation\b|salary\s+range|"
    r"\bbeneficios?\b|ofrecemos|te\s+ofrecemos|qu[eé]\s+ofrecemos|"
    r"sobre\s+nosotros|sobre\s+la\s+empresa|acerca\s+de\s+nosotros|"
    r"nuestra\s+cultura|nuestros\s+valores|por\s+qu[eé]\s+trabajar)",
    re.IGNORECASE)

_MARC_REL = re.compile(
    r"(requirements?\b|responsibilit\w*|qualifications?\b|what\s+you.ll\s+do|"
    r"who\s+you\s+are|must.have|nice.to.have|key\s+responsibilit\w*|"
    r"requisitos?\b|requerimientos?\b|responsabilidades?\b|funciones?\b|"
    r"tareas?\b|cualificaciones?\b|lo\s+que\s+har[aá]s|\bskills?\b|"
    r"habilidades\b|conocimientos\b|\bperfil\b|experience\s+required|"
    r"tech\s+stack|stack\s+t[eé]cnico)",
    re.IGNORECASE)

_MARC_TODOS = re.compile(rf"({_MARC_RUIDO.pattern}|{_MARC_REL.pattern})", re.IGNORECASE)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _es_titulo(linea: str) -> bool:
    """Detecta si una línea parece ser un encabezado de sección."""
    limpia = linea.strip()
    if not limpia:
        return False
    # Corta y termina en ":" o "?"
    if len(limpia) < 70 and limpia.endswith(":"):
        return True
    if len(limpia) < 70 and limpia.endswith("?"):
        return True
    # Todo en mayúsculas
    if limpia.isupper():
        return True
    # Empieza con # (Markdown)
    if limpia.startswith("#"):
        return True
    # Línea con bullet
    if re.match(r"^[\d\-\*•]\s*[A-ZÁÉÍÓÚÑ]", limpia):
        return True
    # Frase corta en Title Case (cada palabra capitalizada) sin puntuación final
    palabras = limpia.split()
    if (3 <= len(palabras) <= 7
            and limpia[-1] not in ".!,"
            and sum(1 for p in palabras if p[0].isupper()) >= len(palabras) - 1):
        return True
    # Línea corta que NOMBRA una sección conocida (Beneficios, Sobre nosotros,
    # Requisitos…) aunque tenga solo 1-2 palabras.
    if len(limpia) < 50 and (TITULOS_RUIDO.search(limpia) or TITULOS_RELEVANTES.search(limpia)):
        return True
    return False


def _clasificar_titulo(titulo: str) -> str:
    """'relevante', 'ruido' o 'neutro'"""
    if TITULOS_RELEVANTES.search(titulo):
        return "relevante"
    if TITULOS_RUIDO.search(titulo):
        return "ruido"
    return "neutro"


# ---------------------------------------------------------------------------
# Función principal
# ---------------------------------------------------------------------------

def _segmentar(texto: str) -> List[str]:
    """
    Parte el texto en segmentos analizables, robusto a vacantes escritas en
    una sola línea: inserta un salto antes de cada marcador de sección conocido
    (relevante o ruido) y luego divide por oraciones. Así "…snacks. Requirements:
    Python…" se separa en un segmento de ruido y uno de requisitos.
    """
    # 1. Quitar líneas de interfaz de portales (botones, contadores)
    base = "\n".join(l for l in texto.splitlines() if not LINEA_UI_PORTAL.match(l))
    # 2. Salto de línea antes de cada marcador de sección (aunque esté inline)
    base = _MARC_TODOS.sub(lambda m: "\n" + m.group(0), base)
    # 3. Cada línea, además, se parte por oraciones (. ; •) para aislar ruido
    segmentos: List[str] = []
    for linea in base.splitlines():
        for parte in re.split(r"(?<=[.;])\s+|\s+[•·]\s+", linea):
            p = (parte or "").strip(" \t-–—•·|")
            if p:
                segmentos.append(p)
    return segmentos


def limpiar_vacante(texto: str) -> str:
    """
    Recibe la descripción completa de una vacante y devuelve solo
    la información relevante para el análisis ATS.

    Rastrea la sección actual (relevante / ruido) a medida que avanza, de modo
    que las líneas que cuelgan de un encabezado heredan su clasificación. Nunca
    devuelve vacío si la entrada contiene requisitos o responsabilidades.
    """
    if not texto or not texto.strip():
        return ""

    seccion = "neutro"          # neutro | rel | ruido
    relevantes: List[str] = []  # segmentos bajo requisitos/responsabilidades…
    neutros: List[str] = []     # preámbulo / título del puesto

    for seg in _segmentar(texto):
        tiene_rel = bool(_MARC_REL.search(seg))
        tiene_ruido = bool(_MARC_RUIDO.search(seg))

        # El marcador que ABRE el segmento manda (tras la segmentación quedan al
        # inicio). Si coexisten en el mismo segmento, gana el relevante.
        if tiene_rel:
            seccion = "rel"
            relevantes.append(seg)
            continue
        if tiene_ruido:
            seccion = "ruido"
            continue

        # Segmento sin marcador: hereda la sección actual.
        if seccion == "ruido" or LINEAS_RUIDO.search(seg):
            continue
        if seccion == "rel":
            relevantes.append(seg)
        else:  # preámbulo (título del puesto, intro breve)
            neutros.append(seg)

    partes: List[str] = []
    # Conservar el preámbulo solo si es breve (suele ser el título del puesto);
    # un preámbulo largo sin marcador es marketing de empresa.
    preambulo = "\n".join(neutros).strip()
    if preambulo and len(preambulo.split()) <= 40:
        partes.append(preambulo)
    partes.extend(relevantes)

    resultado = "\n".join(p for p in partes if p).strip()

    # Garantía anti-vacío: si no se reconoció ninguna sección pero hay texto,
    # devolver el texto sin las líneas obvias de ruido/beneficios.
    if not resultado:
        resultado = _fallback(texto)
    if not resultado.strip():
        resultado = texto.strip()

    return resultado


def _fallback(texto: str) -> str:
    """
    Limpieza mínima cuando no se reconoce ninguna sección: descarta segmentos
    que son claramente ruido (beneficios/legal/empresa) y conserva el resto.
    Opera por segmentos (no por líneas) para no borrar requisitos que comparten
    línea con texto de ruido.
    """
    conservados = [
        s for s in _segmentar(texto)
        if not _MARC_RUIDO.match(s)
        and not LINEAS_RUIDO.search(s)
        and not TITULOS_RUIDO.match(s)
    ]
    return "\n".join(conservados).strip()
