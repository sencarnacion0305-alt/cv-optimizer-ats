"""
Detección de secciones por CONTENIDO y por SINÓNIMOS de encabezado, con 3 estados:
encabezado / contenido (presente sin título) / ausente. Recomendaciones distintas.

Criterio: un CV con lista de skills pero sin la palabra «Habilidades» ya no se
marca como "falta sección Habilidades"; se sugiere añadir el encabezado estándar.
"""
import pytest

from app.core.cv_analyzer import estado_secciones, detectar_secciones
from app.services.ats_checker import analizar_ats_texto


CV_SKILLS_SIN_TITULO = (
    "Alex Rivera\n"
    "alex@example.com | New York, NY\n"
    "Experiencia\n"
    "Backend Developer - Nova | 2021 - 2025\n"
    "Construí servicios con Docker, Git, PostgreSQL, AWS y Python."
)
CV_SIN_SKILLS = (
    "Alex Rivera\n"
    "alex@example.com\n"
    "Experiencia\n"
    "Gerente de tienda 2019-2024. Atención al cliente y ventas."
)


def _check_habilidades(cv):
    rep = analizar_ats_texto(cv)
    estr = [c for c in rep["categorias"] if "structura" in c["nombre"]][0]
    return [ch for ch in estr["checks"] if "Habilidades" in ch["titulo"]][0]


# ── Acceptance: skills sin título -> NO "falta", sino "añade encabezado" ──
def test_skills_sin_titulo_no_es_falta():
    assert estado_secciones(CV_SKILLS_SIN_TITULO)["habilidades"] == "contenido"
    assert detectar_secciones(CV_SKILLS_SIN_TITULO)["habilidades"] is True
    chk = _check_habilidades(CV_SKILLS_SIN_TITULO)
    assert "Falta" not in chk["titulo"]
    assert "sin encabezado" in chk["titulo"].lower()
    assert "encabezado" in chk["detalle"].lower()


def test_sin_skills_si_es_ausente():
    assert estado_secciones(CV_SIN_SKILLS)["habilidades"] == "ausente"
    chk = _check_habilidades(CV_SIN_SKILLS)
    assert "Falta" in chk["titulo"]


@pytest.mark.parametrize("titulo", [
    "Habilidades", "Skills", "Technical Skills", "Competencias",
    "Tecnologías", "Stack técnico", "Herramientas", "Tech Stack",
])
def test_sinonimos_de_encabezado_habilidades(titulo):
    cv = (f"Alex Rivera\nalex@example.com\nExperiencia\nDev 2021-2025\n"
          f"{titulo}\nDocker, Git, PostgreSQL, AWS")
    assert estado_secciones(cv)["habilidades"] == "encabezado"


@pytest.mark.parametrize("titulo", ["Trayectoria", "Historial", "Experiencia laboral", "Career History"])
def test_sinonimos_de_encabezado_experiencia(titulo):
    cv = f"Alex Rivera\nalex@example.com\n{titulo}\nDev en Nova 2021-2025\n- Construí APIs."
    assert estado_secciones(cv)["experiencia"] == "encabezado"


def test_estado_no_penaliza_contenido_pero_si_ausente():
    # 'contenido' no debe restar puntos de estructura; 'ausente' sí.
    def pts(r):
        return [c for c in r["categorias"] if "structura" in c["nombre"]][0]["puntos"]
    assert pts(analizar_ats_texto(CV_SKILLS_SIN_TITULO)) > pts(analizar_ats_texto(CV_SIN_SKILLS))
