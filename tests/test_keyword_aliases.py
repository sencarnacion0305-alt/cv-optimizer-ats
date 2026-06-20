"""P1 — matching semántico de keywords (sigla <-> forma expandida <-> variantes)."""
import pytest

from app.services.adaptador import _analizar_cobertura
from app.services.keyword_aliases import son_equivalentes

# Pares (sigla, forma expandida) que deben tratarse como la misma entidad
PARES = [
    ("aws", "amazon web services"),
    ("k8s", "kubernetes"),
    ("ml", "machine learning"),
    ("js", "javascript"),
    ("ts", "typescript"),
    ("postgres", "postgresql"),
    ("gcp", "google cloud platform"),
    ("ci/cd", "continuous integration"),
    ("siem", "security information and event management"),
    ("nlp", "natural language processing"),
]


@pytest.mark.parametrize("sigla,expandida", PARES)
def test_son_equivalentes(sigla, expandida):
    assert son_equivalentes(sigla, expandida)
    assert son_equivalentes(expandida, sigla)


@pytest.mark.parametrize("sigla,expandida", PARES)
def test_cv_sigla_jd_expandida(sigla, expandida):
    """CV usa la sigla, la vacante pide la forma expandida -> CUBIERTA (no faltante)."""
    cubiertas, sugeridas = _analizar_cobertura([expandida], f"Skilled in {sigla} and other tools.")
    assert expandida in cubiertas
    assert expandida not in sugeridas


@pytest.mark.parametrize("sigla,expandida", PARES)
def test_cv_expandida_jd_sigla(sigla, expandida):
    """CV usa la forma expandida, la vacante pide la sigla -> CUBIERTA."""
    cubiertas, sugeridas = _analizar_cobertura([sigla], f"Experience with {expandida} in production.")
    assert sigla in cubiertas
    assert sigla not in sugeridas


@pytest.mark.parametrize("variante_cv", ["node.js", "nodejs", "node"])
def test_variantes_puntuacion_node(variante_cv):
    """node.js / nodejs / node deben tratarse como la misma keyword."""
    cubiertas, _ = _analizar_cobertura(["nodejs"], f"Built backend services with {variante_cv}.")
    assert "nodejs" in cubiertas


def test_caso_critico_del_reporte():
    """CV con AWS, K8s, ML — vacante con las formas expandidas: nada debe faltar."""
    cv = "Cloud engineer with AWS, K8s and ML experience building pipelines."
    jd = ["amazon web services", "kubernetes", "machine learning"]
    cubiertas, sugeridas = _analizar_cobertura(jd, cv)
    assert sugeridas == []
    assert set(jd) == set(cubiertas)


def test_no_falso_positivo():
    """Una keyword realmente ausente sí debe aparecer como faltante."""
    cubiertas, sugeridas = _analizar_cobertura(["docker"], "Skilled in AWS and Kubernetes.")
    assert "docker" in sugeridas
    assert "docker" not in cubiertas


def test_feat07_keyword_negada_no_cubierta():
    """FEAT-07: una keyword en contexto negativo NO cuenta como cubierta."""
    cubiertas, sugeridas = _analizar_cobertura(
        ["python", "aws"], "Strong with AWS but sin experiencia en Python.")
    assert "aws" in cubiertas
    assert "python" in sugeridas
    assert "python" not in cubiertas
