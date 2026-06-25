"""
Fuente única de verdad (core.cv_analyzer): el MISMO CV debe producir los MISMOS
valores de secciones y calidad en las 4 vistas (Adaptar, Análisis ATS, Checklist,
15 Métricas). Antes cada pestaña calculaba por su cuenta y se contradecían.

Se prueban 3 estilos de CV: prosa, viñetas y mixto.
"""
import pytest

from app.core.cv_analyzer import analizar_cv, detectar_secciones, calcular_calidad
from app.services.metricas import calcular_metricas
from app.services.ats_checker import analizar_ats_texto
from app.services.adaptador import adaptar_cv
from app.models.schemas import AdaptarCVRequest


CV_PROSA = """Alex Rivera
alex.rivera@example.com | +1 555 0100 | New York, NY

Resumen
Backend developer with six years of experience designing and operating REST APIs
in Python and FastAPI. I have led small teams and improved system reliability and
delivery speed across several products in production environments.

Experiencia
At Nova Systems from January 2021 to May 2025 I developed REST APIs with Python and
FastAPI, reducing average latency by 35 percent, and I coordinated a team of four
engineers working with Scrum and Jira on AWS infrastructure.

Educación
B.S. in Computer Science, Demo University, 2018.

Habilidades
Python, FastAPI, PostgreSQL, Docker, AWS, Git, Scrum, Agile."""

CV_VINETAS = """Alex Rivera
alex.rivera@example.com | +1 555 0100 | New York, NY

EXPERIENCE
Backend Developer - Nova Systems | January 2021 - May 2025
- Developed REST APIs with Python and FastAPI, reducing latency by 35%.
- Led a team of 4 engineers using Scrum and Jira.
- Implemented Docker containers and CI/CD pipelines on AWS.

EDUCATION
B.S. Computer Science - Demo University, 2018

SKILLS
Python, FastAPI, PostgreSQL, Docker, AWS, Git, Scrum, Agile."""

CV_MIXTO = """Alex Rivera
alex.rivera@example.com | +1 555 0100 | New York, NY

SUMMARY
Senior backend developer focused on scalable REST APIs and reliable deployments,
with experience leading teams and improving delivery across multiple products.

EXPERIENCE
Backend Developer - Nova Systems | January 2021 - May 2025
- Developed REST APIs with Python and FastAPI, reducing latency by 35%.
Optimized PostgreSQL queries and coordinated a team of four engineers using Scrum.

EDUCATION
B.S. Computer Science - Demo University, 2018

SKILLS
Python, FastAPI, PostgreSQL, Docker, AWS, Git, Scrum, Agile."""

VAC = ("Senior Backend Developer. Requirements: Python, FastAPI, PostgreSQL, Docker, "
       "AWS. Methodologies: Agile, Scrum. 5 years. Bachelor degree.")

CVS = {"prosa": CV_PROSA, "vinetas": CV_VINETAS, "mixto": CV_MIXTO}


def _secciones_ats(cv: str) -> dict:
    """Presencia de secciones según la vista Análisis ATS."""
    rep = analizar_ats_texto(cv)
    estr = [c for c in rep["categorias"] if "structura" in c["nombre"]][0]
    mapa = {"Experiencia": "experiencia", "Educación": "educacion", "Habilidades": "habilidades"}
    out = {}
    for ch in estr["checks"]:
        for etiqueta, key in mapa.items():
            if etiqueta in ch["titulo"]:
                out[key] = ch["estado"] == "ok"
    return out


@pytest.mark.parametrize("estilo", list(CVS))
def test_secciones_coinciden_entre_vistas(estilo):
    cv = CVS[estilo]
    core = analizar_cv(cv, VAC)["secciones"]
    ats = _secciones_ats(cv)
    adp = adaptar_cv(AdaptarCVRequest(cv_texto=cv, vacante_texto=VAC)).content_signals

    for key in ("experiencia", "educacion", "habilidades"):
        assert core[key] == ats[key], f"[{estilo}] {key}: core={core[key]} ats={ats[key]}"
        assert core[key] == adp[f"has_{ {'experiencia':'experience','educacion':'education','habilidades':'skills'}[key] }_section"], \
            f"[{estilo}] {key}: core={core[key]} adaptar discrepa"
    # En los 3 estilos, estas 3 secciones existen → todas deben dar True
    assert all(core[k] for k in ("experiencia", "educacion", "habilidades"))


@pytest.mark.parametrize("estilo", list(CVS))
def test_calidad_coincide_entre_vistas(estilo):
    cv = CVS[estilo]
    cal = calcular_calidad(cv)
    mets = {m["id"]: m for m in calcular_metricas(cv, VAC)["metricas"]}
    # Measurable Impact (Métricas) == impacto del core
    assert mets["measurable_impact"]["score"] == cal["impacto"]
    # Readability (Métricas) == legibilidad del core
    assert mets["readability"]["score"] == cal["legibilidad"]


@pytest.mark.parametrize("estilo", list(CVS))
def test_score_global_igual_a_adaptar(estilo):
    cv = CVS[estilo]
    core = analizar_cv(cv, VAC)
    adp = adaptar_cv(AdaptarCVRequest(cv_texto=cv, vacante_texto=VAC))
    assert core["score_global"] == adp.score


@pytest.mark.parametrize("estilo", list(CVS))
def test_determinista(estilo):
    cv = CVS[estilo]
    assert detectar_secciones(cv) == detectar_secciones(cv)
    assert analizar_cv(cv, VAC)["score_global"] == analizar_cv(cv, VAC)["score_global"]
