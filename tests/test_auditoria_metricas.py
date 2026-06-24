"""
Auditoría: páginas legales, cabeceras de seguridad y las 15 métricas.
"""
from fastapi.testclient import TestClient

from app.main import app
from app.services.metricas import calcular_metricas, CATEGORIAS

client = TestClient(app)

CV = """Alex Rivera
alex.rivera@example.com | +1 555 0100 | linkedin.com/in/alexrivera | New York, NY
SUMMARY
Senior Backend Developer with 6 years building REST APIs.
EXPERIENCE
Backend Developer - Nova Systems | January 2021 - May 2025
- Developed REST APIs with Python and FastAPI, reducing latency by 35%.
- Led a team of 4 engineers using Scrum and Jira.
- Implemented Docker and CI/CD on AWS.
EDUCATION
B.S. Computer Science - Demo University, 2018
SKILLS
Python, FastAPI, PostgreSQL, Docker, AWS, Git, Scrum, Agile, leadership."""

VAC = """Senior Backend Developer. Requirements: 5+ years Python, FastAPI, PostgreSQL,
Docker, AWS, Kubernetes. Methodologies: Agile, Scrum, CI/CD. Tools: Jira, AWS.
Strong leadership and communication. Bachelor degree required. AWS Certified preferred."""


# ── Problema 4: páginas legales 200 ──
def test_privacy_responde_200():
    r = client.get("/privacy")
    assert r.status_code == 200
    assert "Privacidad" in r.text


def test_terms_responde_200():
    r = client.get("/terms")
    assert r.status_code == 200
    assert "Términos" in r.text


# ── Problema 5: seguridad ──
def test_hsts_solo_en_https():
    # Sin https declarado -> no HSTS
    r = client.get("/")
    assert "strict-transport-security" not in {k.lower() for k in r.headers}
    # Con X-Forwarded-Proto: https (como en Render) -> sí HSTS
    r2 = client.get("/", headers={"X-Forwarded-Proto": "https"})
    assert r2.headers.get("Strict-Transport-Security")


def test_cabeceras_seguridad_presentes():
    h = client.get("/").headers
    assert h.get("Content-Security-Policy")
    assert h.get("X-Content-Type-Options") == "nosniff"
    assert h.get("X-Frame-Options") == "SAMEORIGIN"


# ── 15 métricas: modelo de datos completo ──
def test_metricas_quince_con_score_expl_recomendacion():
    r = calcular_metricas(CV, VAC)
    assert len(r["metricas"]) == 15
    for m in r["metricas"]:
        assert {"id", "nombre", "categoria", "score", "aplica",
                "explicacion", "recomendacion"} <= set(m)
        assert m["explicacion"] and m["recomendacion"]
        assert m["categoria"] in CATEGORIAS
        if m["aplica"]:
            assert 0 <= m["score"] <= 100


def test_metricas_ids_esperados():
    ids = {m["id"] for m in calcular_metricas(CV, VAC)["metricas"]}
    esperados = {
        "ats_parse_rate", "title_match", "experience_match", "seniority_match",
        "education_match", "certifications_match", "hard_skills_match",
        "soft_skills_match", "tools_match", "methodologies_match",
        "measurable_impact", "bullet_strength", "readability",
        "format_risk", "ats_vendor_risk",
    }
    assert ids == esperados


def test_metricas_agrupadas_y_prioritarias():
    r = calcular_metricas(CV, VAC)
    assert r["categorias"] == CATEGORIAS
    # cada métrica está en su grupo
    total = sum(len(v) for v in r["por_categoria"].values())
    assert total == 15
    # prioritarias: ordenadas por score ascendente y con recomendación
    scores = [p["score"] for p in r["prioritarias"]]
    assert scores == sorted(scores)
    assert all(p["recomendacion"] for p in r["prioritarias"])


def test_metricas_matches_detectados():
    r = {m["id"]: m for m in calcular_metricas(CV, VAC)["metricas"]}
    assert r["title_match"]["score"] == 100            # Backend Developer en CV
    assert r["education_match"]["score"] == 100        # B.S. ahora detectado
    assert r["tools_match"]["aplica"]                  # Jira/AWS pedidos
    assert r["methodologies_match"]["score"] == 100    # Agile/Scrum/CI-CD presentes
    assert r["seniority_match"]["score"] == 100        # Senior == Senior


def test_metricas_endpoint_texto():
    r = client.post("/api/v1/metricas", data={"cv_texto": CV, "vacante_texto": VAC})
    assert r.status_code == 200
    j = r.json()
    assert len(j["metricas"]) == 15
    assert 0 <= j["score_global"] <= 100


def test_metricas_sin_vacante_no_rompe():
    # Sin vacante, los matches no aplican pero las métricas de CV sí.
    r = calcular_metricas(CV, "")
    by = {m["id"]: m for m in r["metricas"]}
    assert by["ats_parse_rate"]["aplica"]
    assert by["readability"]["aplica"]
    assert by["title_match"]["aplica"] is False        # no hay cargo en vacante vacía
