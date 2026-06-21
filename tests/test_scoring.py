"""SCORE-01: score compuesto de 5 dimensiones con pesos fijos."""
from app.models.schemas import AdaptarCVRequest
from app.services.adaptador import adaptar_cv

VACANTE = """Backend Developer
We are looking for a Backend Developer with Python, Django, AWS, Docker,
PostgreSQL and REST APIs experience to join our team."""

CV_BUENO = """Jane Smith
Backend Developer
jane@mail.com | +1 555 123 4567
Summary
Backend Developer with 6 years building scalable APIs and leading teams across
distributed systems, clean architecture and cloud-native platforms every day.
Experience
Backend Developer  Jan 2020 - Present
TechCorp
- Built REST APIs in Python and Django serving 1M requests/day, reducing latency by 40%
- Led a team of 5 engineers and deployed to AWS with Docker
Education
B.Sc Computer Science  2014 - 2018
University
Skills
Python, Django, AWS, Docker, PostgreSQL, REST APIs"""

CV_POBRE = "Python Django AWS Docker PostgreSQL REST APIs"


def _d(cv):
    return adaptar_cv(AdaptarCVRequest(cv_texto=cv, vacante_texto=VACANTE)).score_desglose


def test_desglose_suma_total():
    d = _d(CV_BUENO)
    assert d["total"] == min(100, sum(x["puntos"] for x in d["dimensiones"]))
    assert len(d["dimensiones"]) == 5


def test_pesos_maximos_correctos():
    maxs = {x["nombre"]: x["max"] for x in _d(CV_BUENO)["dimensiones"]}
    assert maxs["Keywords match"] == 35
    assert maxs["Formato ATS"] == 20
    assert maxs["Estructura y secciones"] == 20
    assert maxs["Calidad de contenido"] == 15
    assert maxs["Cargo objetivo"] == 10
    assert sum(maxs.values()) == 100


def test_keyword_stuffing_no_llega_a_100():
    assert _d(CV_POBRE)["total"] < 60


def test_cv_bueno_supera_al_pobre():
    assert _d(CV_BUENO)["total"] > _d(CV_POBRE)["total"]


def test_cargo_objetivo_detectado():
    cargo = [x for x in _d(CV_BUENO)["dimensiones"] if x["nombre"] == "Cargo objetivo"][0]
    assert cargo["puntos"] >= 5


def test_estructura_pobre_penalizada():
    est = [x for x in _d(CV_POBRE)["dimensiones"] if x["nombre"] == "Estructura y secciones"][0]
    assert est["puntos"] <= 5


def test_response_enriquecido():
    r = adaptar_cv(AdaptarCVRequest(cv_texto=CV_BUENO, vacante_texto=VACANTE))
    # alias y compatibilidad
    assert r.score == r.score_match
    assert r.score_desglose is not None and r.keywords_cubiertas is not None
    # score_breakdown con las 5 claves y forma {score, max}
    assert set(r.score_breakdown.keys()) == {
        "keywords_match", "formato_ats", "estructura", "calidad_contenido", "cargo_objetivo"}
    assert all(set(v.keys()) == {"score", "max"} for v in r.score_breakdown.values())
    # hard/soft + contacto + señales
    assert isinstance(r.keywords_hard_skills_cubiertas, list)
    assert "email_found" in r.contact_info
    assert "word_count" in r.content_signals
    assert r.content_signals["word_count"] > 0
