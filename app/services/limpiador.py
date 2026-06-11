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
from typing import List, Tuple

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
    r"growing soc team|growing team|join our|join the)",
    re.IGNORECASE,
)

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

def limpiar_vacante(texto: str) -> str:
    """
    Recibe la descripción completa de una vacante y devuelve solo
    la información relevante para el análisis ATS.
    """
    # Pre-filtro: quitar lineas de interfaz de portales (botones, contadores)
    lineas = [l for l in texto.splitlines() if not LINEA_UI_PORTAL.match(l)]
    bloques: List[Tuple[str, List[str]]] = []  # (clasificacion, lineas)

    seccion_actual: str = "neutro"
    contenido_actual: List[str] = []

    for linea in lineas:
        if _es_titulo(linea):
            # Guardar bloque anterior
            if contenido_actual:
                bloques.append((seccion_actual, contenido_actual))
            seccion_actual = _clasificar_titulo(linea)
            contenido_actual = [linea]
        else:
            contenido_actual.append(linea)

    if contenido_actual:
        bloques.append((seccion_actual, contenido_actual))

    # ── Seleccionar bloques relevantes ───────────────────────────────
    partes_finales: List[str] = []

    for clasificacion, lineas_bloque in bloques:
        if clasificacion == "ruido":
            continue

        # Filtrar líneas de ruido dentro de bloques neutros/relevantes
        lineas_limpias = [
            l for l in lineas_bloque
            if not LINEAS_RUIDO.search(l)
        ]

        texto_bloque = "\n".join(lineas_limpias).strip()
        if not texto_bloque:
            continue

        # Para bloques neutros al inicio (introducción), conservar solo si
        # son cortos (probablemente el título del puesto o intro breve)
        if clasificacion == "neutro":
            palabras = len(texto_bloque.split())
            # Intro larga sin sección relevante = probablemente marketing de empresa
            if palabras > 60 and not TITULOS_RELEVANTES.search(texto_bloque):
                continue

        partes_finales.append(texto_bloque)

    resultado = "\n\n".join(partes_finales).strip()

    # Si el filtro fue demasiado agresivo (eliminó casi todo), devolver original limpio
    if len(resultado.split()) < 30:
        resultado = _fallback(texto)

    return resultado


def _fallback(texto: str) -> str:
    """
    Limpieza mínima cuando el filtrado elimina demasiado:
    quita líneas claramente de beneficios/legal y devuelve el resto.
    """
    lineas = [
        l for l in texto.splitlines()
        if not LINEAS_RUIDO.search(l) and not TITULOS_RUIDO.search(l)
    ]
    return "\n".join(lineas).strip()
