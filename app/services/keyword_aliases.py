"""
Canonicalización de keywords técnicas.

Trata siglas, formas expandidas y variantes de puntuación como la MISMA entidad,
para que la comparación CV vs vacante sea semántica y no literal. Así, un CV que
dice "AWS" cubre una vacante que pide "Amazon Web Services" (y viceversa).

Diseño:
  - GRUPOS: lista de equivalencias; el primer elemento es la forma canónica.
  - norm_alias(texto): normaliza puntuación (node.js → "node js", ci/cd → "ci cd")
    preservando tokens con sentido como c++, c#, .net.
  - equivalentes(termino): todas las claves normalizadas equivalentes a un término
    (incluye forma con espacios y forma "junta": "node js" y "nodejs").
  - canonicalizar(termino): la forma canónica del grupo, o la forma normalizada.

Este módulo es independiente (no importa otros servicios) para evitar ciclos.
"""

import re
from difflib import SequenceMatcher
from typing import List, Set

# ---------------------------------------------------------------------------
# Grupos de equivalencia (forma canónica primero)
# ---------------------------------------------------------------------------

GRUPOS: List[List[str]] = [
    ["amazon web services", "aws"],
    ["google cloud platform", "gcp", "google cloud"],
    ["microsoft azure", "azure"],
    ["kubernetes", "k8s"],
    ["machine learning", "ml"],
    ["deep learning", "dl"],
    ["natural language processing", "nlp"],
    ["artificial intelligence", "ai"],
    ["javascript", "js"],
    ["typescript", "ts"],
    ["node.js", "nodejs", "node"],
    ["react.js", "reactjs", "react"],
    ["vue.js", "vuejs", "vue"],
    ["next.js", "nextjs"],
    ["continuous integration and continuous delivery",
     "ci/cd", "cicd", "continuous integration", "continuous delivery",
     "continuous deployment"],
    ["postgresql", "postgres", "postgre"],
    ["structured query language", "sql"],
    ["representational state transfer", "rest", "rest api", "restful api", "restful"],
    ["graphql", "graph ql"],
    ["object oriented programming", "oop"],
    ["infrastructure as code", "iac"],
    ["identity and access management", "iam"],
    ["role based access control", "rbac"],
    ["user interface", "ui"],
    ["user experience", "ux"],
    ["test driven development", "tdd"],
    # Seguridad (dominio principal de la app)
    ["security information and event management", "siem"],
    ["endpoint detection and response", "edr"],
    ["extended detection and response", "xdr"],
    ["security operations center", "soc"],
    ["security orchestration automation and response", "soar"],
    ["data loss prevention", "dlp"],
    ["intrusion detection system", "ids"],
    ["intrusion prevention system", "ips"],
    ["web application firewall", "waf"],
    ["indicators of compromise", "ioc", "iocs"],
    ["multi factor authentication", "mfa", "2fa", "two factor authentication"],
    ["single sign on", "sso"],
    ["virtual private network", "vpn"],
    ["open source intelligence", "osint"],
    ["governance risk and compliance", "grc"],
    ["general data protection regulation", "gdpr", "rgpd"],
    ["esquema nacional de seguridad", "ens"],
    ["incident response", "ir", "respuesta a incidentes"],
    ["vulnerability management", "gestion de vulnerabilidades"],
    ["threat intelligence", "inteligencia de amenazas"],
    ["penetration testing", "pentesting", "pentest", "pruebas de penetracion"],
]


# ---------------------------------------------------------------------------
# Normalización
# ---------------------------------------------------------------------------

def norm_alias(texto: str) -> str:
    """
    Normaliza un texto al "espacio de alias": pasa a minúsculas y convierte los
    separadores internos (node.js, ci/cd, ci-cd) en espacios, PRESERVANDO tokens
    con sentido como c++, c#, .net (donde el símbolo no separa dos palabras).
    """
    t = texto.lower()
    # separador entre dos caracteres de palabra: node.js, ci/cd, ci-cd, c_c
    t = re.sub(r"(?<=\w)[./\\_\-](?=\w)", " ", t)
    # separadores sueltos restantes
    t = re.sub(r"[/\\_\-]{1,}", " ", t)
    t = re.sub(r"\s+", " ", t)
    return t.strip()


def _variantes_clave(termino: str) -> Set[str]:
    """Formas normalizadas de un término: con espacios y 'junta'."""
    base = norm_alias(termino)
    junto = base.replace(" ", "")
    return {base, junto} - {""}


# Índices precomputados
_CLAVE_A_CANON = {}                  # clave normalizada -> forma canónica
_CANON_A_CLAVES = {}                 # forma canónica -> set de claves equivalentes
for _grupo in GRUPOS:
    _canon = norm_alias(_grupo[0])
    _claves: Set[str] = set()
    for _v in _grupo:
        _claves |= _variantes_clave(_v)
    _CANON_A_CLAVES[_canon] = _claves
    for _c in _claves:
        _CLAVE_A_CANON[_c] = _canon


def canonicalizar(termino: str) -> str:
    """Devuelve la forma canónica del término (o su forma normalizada si no hay grupo)."""
    for clave in _variantes_clave(termino):
        if clave in _CLAVE_A_CANON:
            return _CLAVE_A_CANON[clave]
    return norm_alias(termino)


def equivalentes(termino: str) -> Set[str]:
    """
    Conjunto de claves normalizadas equivalentes al término (sigla, expansión y
    variantes de puntuación). Si el término no está en ningún grupo, devuelve sus
    propias variantes.
    """
    canon = canonicalizar(termino)
    if canon in _CANON_A_CLAVES:
        return _CANON_A_CLAVES[canon]
    return _variantes_clave(termino)


def son_equivalentes(a: str, b: str) -> bool:
    return canonicalizar(a) == canonicalizar(b)


# ---------------------------------------------------------------------------
# Fallback de similitud (conservador, configurable, opcional)
# ---------------------------------------------------------------------------

def similares(a: str, b: str, umbral: float = 0.9) -> bool:
    """
    Similitud difusa para términos FUERA del diccionario (p. ej. typos
    'kubernets' vs 'kubernetes'). Umbral alto y longitud mínima para evitar
    falsos positivos. Desactivado por defecto en el matching principal.
    """
    x, y = norm_alias(a), norm_alias(b)
    if len(x) < 6 or len(y) < 6:
        return False
    return SequenceMatcher(None, x, y).ratio() >= umbral
