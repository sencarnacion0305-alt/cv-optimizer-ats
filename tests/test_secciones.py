"""P2 — separación de secciones, limpieza de viñetas y skills sin ruido."""
from app.services.adaptador import (
    _extraer_experiencias, _extraer_habilidades, _limpiar_bullet, _segmentar_secciones,
)

CV = """John Doe
Senior Developer

Summary
Backend specialist. Looking for new opportunities in a backend role.

Experience
- Responsible for maintaining payment services
- Built REST APIs with Python and PostgreSQL
- Led a team of 5 engineers

Skills
Python, Docker, PostgreSQL, AWS

Education
B.Sc Computer Science 2014 - 2018
"""


def test_experiencia_no_arrastra_resumen():
    exp = _extraer_experiencias(CV)
    assert not any("Looking for new opportunities" in e for e in exp)
    assert not any("specialist" in e.lower() for e in exp)


def test_experiencia_sin_guiones_crudos():
    exp = _extraer_experiencias(CV)
    assert all(not e.lstrip().startswith(("-", "•", "*", "–")) for e in exp)


def test_experiencia_contiene_bullets_reales():
    exp = _extraer_experiencias(CV)
    assert any("payment services" in e for e in exp)
    assert any("REST APIs" in e for e in exp)


def test_limpiar_bullet():
    assert _limpiar_bullet("- Responsible for X") == "Responsible for X"
    assert _limpiar_bullet("• Built Y") == "Built Y"
    assert _limpiar_bullet("* Designed Z") == "Designed Z"
    assert _limpiar_bullet("– Managed W") == "Managed W"


def test_backend_no_es_skill_en_prosa():
    skills = _extraer_habilidades(CV, [])
    assert "backend" not in skills
    assert "frontend" not in skills


def test_skills_reales_si_extraidos():
    skills = _extraer_habilidades(CV, [])
    assert "python" in skills
    assert "docker" in skills
    assert ("postgresql" in skills or "postgres" in skills)


def test_segmentacion_separa_secciones():
    secciones = _segmentar_secciones(CV)
    assert "experiencia" in secciones
    assert "habilidades" in secciones
    exp_texto = " ".join(secciones["experiencia"])
    assert "Looking for new opportunities" not in exp_texto
