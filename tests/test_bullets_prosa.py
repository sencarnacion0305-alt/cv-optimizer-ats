"""
El detector de logros debe funcionar con CUALQUIER formato, no solo viñetas.
Criterio: un CV en prosa con "Trabajé en Empresa XYZ" se identifica como débil y
se propone mejora; las métricas de impacto/bullets dejan de salir N/A.
"""
from app.core.cv_analyzer import unidades_logro, calcular_calidad
from app.services.mejorador_bullets import mejorar_bullets
from app.services.metricas import calcular_metricas


CV_PROSA = (
    "Carlos Méndez\n"
    "carlos.mendez@example.com | Madrid\n\n"
    "Soy un profesional con seis años en marketing digital. "
    "Trabajé en Empresa XYZ durante tres años gestionando campañas. "
    "Fui responsable de la estrategia de redes sociales. "
    "Ayudé a incrementar el alcance de la marca en distintos canales."
)

# Prosa con UNA sola línea (sin saltos), todo en un párrafo.
CV_UNA_LINEA = (
    "Resumen profesional. Trabajé en Empresa XYZ como analista. "
    "Encargado de los reportes mensuales. Participé en la migración del sistema."
)


def test_prosa_segmenta_en_unidades():
    u = unidades_logro(CV_PROSA)
    assert len(u) >= 3
    assert any("Trabajé en Empresa XYZ" in x for x in u)


def test_prosa_caza_verbo_debil_y_propone_mejora():
    r = mejorar_bullets(CV_PROSA)
    assert r["total_mejoras"] >= 1
    debiles = [m["original"] for m in r["mejoras"]]
    assert any("Trabajé en Empresa XYZ" in d for d in debiles)
    # La mejora reescribe el inicio débil con un verbo de acción (ya no "Trabajé en").
    mejora = next(m for m in r["mejoras"] if "Trabajé en Empresa XYZ" in m["original"])
    assert not mejora["mejorado"].lower().startswith("trabajé en")
    assert mejora["mejorado"] != mejora["original"]


def test_prosa_una_sola_linea_tambien():
    r = mejorar_bullets(CV_UNA_LINEA)
    assert r["total_mejoras"] >= 1
    assert any("Trabajé en Empresa XYZ" in m["original"] for m in r["mejoras"])


def test_metricas_impacto_bullets_no_son_na_en_prosa():
    mets = {m["id"]: m for m in calcular_metricas(CV_PROSA, "")["metricas"]}
    assert mets["measurable_impact"]["aplica"] is True
    assert mets["bullet_strength"]["aplica"] is True
    # y son coherentes con el core (fuente única)
    cal = calcular_calidad(CV_PROSA)
    assert mets["measurable_impact"]["score"] == cal["impacto"]


def test_vinetas_siguen_funcionando():
    cv = ("EXPERIENCE\n"
          "- Worked on REST APIs with Python and FastAPI\n"
          "- Implemented Docker and CI/CD pipelines")
    r = mejorar_bullets(cv)
    assert r["total_mejoras"] >= 1
    assert any("Worked on" in m["original"] for m in r["mejoras"])
