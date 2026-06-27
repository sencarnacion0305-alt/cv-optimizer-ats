"""
Radar de skills del sector (Comparar vacantes potenciado): cruza las keywords del
mercado con el CV → % de cobertura del mercado + gap priorizado por demanda, con
sinónimos unificados (K8s=Kubernetes) reutilizando keyword_aliases.
"""
from app.services.comparador_vacantes import comparar_vacantes

V1 = "Backend Developer. Python, Django, PostgreSQL, Kubernetes, Celery, Redis."
V2 = "Backend Engineer. Python, FastAPI, PostgreSQL, K8s, Docker, Celery."
V3 = "Software Engineer. Python, Docker, PostgreSQL, AWS, Redis."
CV = "Soy backend con Python, Django, PostgreSQL, Docker y Redis."


def test_sinonimos_unifican_en_el_mercado():
    r = comparar_vacantes([V1, V2, V3], CV)
    freq = {k["keyword"]: k["frecuencia"] for k in r["keywords"]}
    # K8s (V2) + Kubernetes (V1) = 2 vacantes, no 1
    assert freq.get("Kubernetes") == 2


def test_cobertura_de_mercado_y_gap():
    r = comparar_vacantes([V1, V2, V3], CV)
    assert isinstance(r["cobertura_mercado"], int) and 0 <= r["cobertura_mercado"] <= 100
    nombres_gap = [g["keyword"] for g in r["gap"]]
    # Falta lo que el CV no tiene
    assert "Kubernetes" in nombres_gap and "Celery" in nombres_gap
    # NO está lo que sí tiene
    assert "Python" not in nombres_gap and "Docker" not in nombres_gap
    # Gap priorizado por frecuencia desc
    frecs = [g["frecuencia"] for g in r["gap"]]
    assert frecs == sorted(frecs, reverse=True)


def test_cobertura_ponderada_por_demanda():
    # CV cubre Python y PostgreSQL (imprescindibles, 3/3) -> cobertura alta aunque
    # falten skills ocasionales.
    r = comparar_vacantes([V1, V2, V3], "Python, PostgreSQL")
    assert r["cobertura_mercado"] is not None
    # cubre 2 imprescindibles de peso 3 cada uno -> al menos algo de cobertura
    assert r["cobertura_mercado"] > 0


def test_sin_cv_no_hay_cobertura_ni_gap():
    r = comparar_vacantes([V1, V2], "")
    assert r["cobertura_mercado"] is None
    assert r["gap"] == []
    assert r["tiene_cv"] is False


def test_cobertura_total_sin_gap():
    r = comparar_vacantes(["Python, Docker", "Python, Docker"],
                          "Tengo Python y Docker.")
    assert r["cobertura_mercado"] == 100
    assert r["gap"] == []
