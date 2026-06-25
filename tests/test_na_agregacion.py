"""
Manejo transparente de N/A en la agregación de métricas (15 Métricas).

Regla: una métrica N/A se EXCLUYE del promedio (nunca cuenta como 100). Cada
categoría expone score + aplicables/total; si TODAS son N/A, score = None.
Criterio: una categoría con N/A no muestra 100 salvo que TODAS las aplicables
estén al máximo, y se informa la base del cálculo.
"""
from app.services.metricas import calcular_metricas

# CV sin unidades de logro -> Measurable Impact y Bullet Strength = N/A; Readability sí.
CV_SIN_LOGROS = "Ana López\nana@example.com | Madrid"

# CV normal con vacante (todo aplicable en match/skills/calidad).
CV_OK = (
    "Alex Rivera\nalex@example.com | New York, NY\n"
    "EXPERIENCE\nBackend Developer - Nova | 2021 - 2025\n"
    "- Developed REST APIs with Python and FastAPI, reducing latency by 35%.\n"
    "- Led a team of 4 using Scrum.\n"
    "SKILLS\nPython, FastAPI, Docker, AWS, Scrum"
)
VAC = "Senior Backend Developer Python FastAPI Docker AWS. Agile Scrum. Bachelor."


def test_categoria_totalmente_na_no_es_100_ni_0():
    # Sin vacante, "Match con Vacante" es 100% N/A.
    r = calcular_metricas(CV_SIN_LOGROS, "")
    match = r["resumen_categorias"]["Match con Vacante"]
    assert match["aplicables"] == 0
    assert match["score"] is None          # pendiente, NO 100 ni 0 engañoso


def test_categoria_con_na_no_infla_a_100_ciego():
    r = calcular_metricas(CV_SIN_LOGROS, "")
    cal = r["resumen_categorias"]["Calidad del Contenido"]
    # 2 de 3 en N/A -> el agregado se calcula solo sobre la aplicable
    assert cal["aplicables"] < cal["total"]
    # Si llega a 100 es PORQUE la única aplicable está al máximo (no por contar N/A)
    if cal["score"] == 100:
        aplicables = [m["score"] for m in r["por_categoria"]["Calidad del Contenido"] if m["aplica"]]
        assert aplicables and all(s == 100 for s in aplicables)


def test_na_excluido_del_promedio_global():
    r = calcular_metricas(CV_SIN_LOGROS, "")
    aplicables = [m["score"] for m in r["metricas"] if m["aplica"]]
    na = [m for m in r["metricas"] if not m["aplica"]]
    assert na                                   # hay métricas N/A
    assert r["cobertura_global"]["aplicables"] == len(aplicables)
    assert r["cobertura_global"]["total"] == 15
    # el global es exactamente la media de las aplicables (N/A excluido)
    esperado = round(sum(aplicables) / len(aplicables))
    assert abs(r["score_global"] - esperado) <= 1


def test_cobertura_completa_cuando_todo_aplica():
    r = calcular_metricas(CV_OK, VAC)
    cal = r["resumen_categorias"]["Calidad del Contenido"]
    assert cal["aplicables"] == cal["total"]    # 3 de 3, sin N/A
    assert cal["score"] is not None


def test_score_categoria_es_media_de_aplicables():
    r = calcular_metricas(CV_OK, VAC)
    for cat, agg in r["resumen_categorias"].items():
        apt = [m["score"] for m in r["por_categoria"][cat] if m["aplica"]]
        if apt:
            assert abs(agg["score"] - round(sum(apt) / len(apt))) <= 1
        else:
            assert agg["score"] is None
