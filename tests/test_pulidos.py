"""Pulidos: 'backend' no es skill en prosa, y el resumen no arranca a media frase."""
from app.models.schemas import AdaptarCVRequest
from app.services.adaptador import (
    adaptar_cv, _extraer_habilidades, _analizar_cobertura, _keywords_de, _oraciones_de,
)

CV = """Jane Roe
Full Stack Engineer

Summary
Senior engineer with 6 years building distributed systems. Familiar with
backend and frontend technologies and passionate about clean architecture.

Experience
Senior Engineer  Jan 2020 - Present
Tech Co
- Designed Node.js microservices on AWS with PostgreSQL

Skills
Node.js, SQL, AWS, Docker, K8s, ML, Git, REST APIs, Agile
"""


# ── Pulido 1: genéricos de prosa no son skills ni keywords cubiertas ──

def test_backend_no_en_habilidades():
    skills = _extraer_habilidades(CV, [])
    assert "backend" not in skills
    assert "frontend" not in skills


def test_backend_no_es_keyword():
    # 'backend'/'frontend' no deben emitirse como keywords del texto
    kws = _keywords_de("We need backend and frontend web software developers.")
    assert "backend" not in kws and "frontend" not in kws and "web" not in kws


def test_backend_no_cuenta_como_cubierta():
    cubiertas, _ = _analizar_cobertura(["backend", "aws"], CV)
    assert "backend" not in cubiertas
    assert "aws" in cubiertas  # tecnología real sí


def test_skills_reales_si_presentes():
    skills = _extraer_habilidades(CV, [])
    assert "aws" in skills
    assert "docker" in skills


# ── Pulido 2: resumen no arranca a media frase ni parte tokens ──

def test_resumen_no_arranca_cortado():
    r = adaptar_cv(AdaptarCVRequest(cv_texto=CV, vacante_texto="Node.js AWS PostgreSQL"))
    resumen = r.cv_adaptado.resumen
    # No empieza con un fragmento de lista de skills tipo "js, SQL, AWS..."
    assert not resumen.lstrip().lower().startswith(("js,", "js ", "apis,"))
    # Empieza con mayúscula (inicio de oración real)
    assert resumen[:1].isupper()


def test_no_parte_node_js():
    # El split por oraciones no debe partir 'Node.js' en 'Node' + 'js'
    oraciones = _oraciones_de("Built Node.js services. Deployed to AWS.")
    assert not any(o.strip().lower().startswith("js") for o in oraciones)
    assert any("node.js" in o.lower() for o in oraciones)


def test_resumen_es_prosa_no_lista():
    r = adaptar_cv(AdaptarCVRequest(cv_texto=CV, vacante_texto="AWS Docker"))
    resumen = r.cv_adaptado.resumen.lower()
    # Debe venir del Summary (prosa), no de la línea de Skills
    assert "senior engineer" in resumen or "distributed systems" in resumen
