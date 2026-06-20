"""BLOQUE 6 — mejoras al scoring: peso por posición, negación, keyword stuffing."""
from app.models.schemas import AdaptarCVRequest
from app.services.adaptador import adaptar_cv, _keywords_negadas
from app.services.scoring import _peso_posicion, _hay_keyword_stuffing

VACANTE = """Backend Developer
We need a Backend Developer with Python, Django and AWS experience."""


def _kw_dim(cv):
    d = adaptar_cv(AdaptarCVRequest(cv_texto=cv, vacante_texto=VACANTE)).score_desglose
    return [x for x in d["dimensiones"] if x["nombre"] == "Keywords match"][0]["puntos"]


# ── SCORE-EX-01: peso por posición ──
def test_peso_resumen_mayor_que_skills():
    secciones_resumen = {"resumen": ["Expert in Python and Django"], "experiencia": [], "habilidades": []}
    secciones_skills = {"resumen": [], "experiencia": [], "habilidades": ["Python, Django"]}
    assert _peso_posicion("python", secciones_resumen) == 1.5
    assert _peso_posicion("python", secciones_skills) == 0.7
    assert _peso_posicion("python", {"resumen": [], "experiencia": ["Built Python APIs"], "habilidades": []}) == 1.0


def test_keyword_en_resumen_puntua_mas():
    cv_resumen = """Ana
Summary
Backend Developer expert in Python, Django and AWS building APIs.
Experience
Engineer Jan 2020 - Present
- Built services
Skills
Git"""
    cv_skills = """Ana
Summary
Professional seeking new roles.
Experience
Engineer Jan 2020 - Present
- Built services
Skills
Python, Django, AWS, Git"""
    assert _kw_dim(cv_resumen) >= _kw_dim(cv_skills)


# ── SCORE-EX-02: contexto negativo ──
def test_keywords_negadas_detectadas():
    negadas = _keywords_negadas(["python", "aws"], "Strong with AWS but sin experiencia en Python.")
    assert "python" in negadas
    assert "aws" not in negadas


def test_nota_contexto_negativo():
    cv = "Ana\nSummary\nEngineer with AWS. Sin experiencia en Python.\nSkills\nAWS"
    r = adaptar_cv(AdaptarCVRequest(cv_texto=cv, vacante_texto=VACANTE))
    assert any("contexto negativo" in n.lower() for n in r.notas_para_usuario)


# ── SCORE-EX-03: keyword stuffing ──
def test_detecta_stuffing():
    cv = ("Python, Java, AWS, Docker, Git, SQL, React\n"
          "Vue, Angular, Node, PHP, Ruby, Go, Rust\n"
          "MongoDB, Redis, Kafka, Nginx, Linux, Bash, C++")
    assert _hay_keyword_stuffing(cv) is True


def test_no_stuffing_en_prosa():
    cv = "Built scalable Python APIs on AWS and led the backend team to deliver features."
    assert _hay_keyword_stuffing(cv) is False
