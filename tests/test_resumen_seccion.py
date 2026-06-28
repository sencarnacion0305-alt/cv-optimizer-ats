"""
Bug 1.2: un CV con encabezado de resumen (RESUMEN, Perfil, Summary, About…) debe
contar como sección presente aunque el texto sea corto. La detección vive en el core
(fuente única) → arregla Análisis ATS y Checklist a la vez.
"""
import pytest

from app.core.cv_analyzer import detectar_secciones, estado_secciones
from app.services.ats_checker import analizar_ats_texto

VARIANTES = [
    "RESUMEN", "Resumen", "Perfil", "Perfil profesional", "Resumen profesional",
    "Sobre mí", "SUMMARY", "Profile", "Professional Summary", "About",
]


def _cv(header: str) -> str:
    return (f"Carlos Méndez\ncarlos@example.com\n{header}\n"
            "Desarrollador backend con 6 años de experiencia.\n"
            "EXPERIENCIA\nBackend Developer - Nova | 2021 - 2025\n"
            "- Construí APIs con Python.\n"
            "EDUCACIÓN\nGrado en Informática, 2019.\n"
            "HABILIDADES\nPython, Docker, AWS, Git")


@pytest.mark.parametrize("header", VARIANTES)
def test_variante_de_resumen_detectada(header):
    cv = _cv(header)
    assert detectar_secciones(cv)["resumen"] is True
    assert estado_secciones(cv)["resumen"] == "encabezado"


@pytest.mark.parametrize("header", VARIANTES)
def test_no_se_penaliza_en_analisis_ats(header):
    rep = analizar_ats_texto(_cv(header))
    estr = [c for c in rep["categorias"] if "structura" in c["nombre"]][0]
    resumen = [ch for ch in estr["checks"] if "Resumen" in ch["titulo"]][0]
    assert resumen["estado"] == "ok"
    assert "Falta" not in resumen["titulo"]


def test_resumen_corto_con_titulo_cuenta():
    # "RESUMEN" + 7 palabras: antes daba 'ausente' por el gate de >30 palabras.
    cv = _cv("RESUMEN")
    assert estado_secciones(cv)["resumen"] != "ausente"


def test_sin_resumen_sigue_ausente():
    cv = ("Carlos Méndez\ncarlos@example.com\n"
          "EXPERIENCIA\nBackend Developer - Nova | 2021 - 2025\n- APIs con Python.\n"
          "HABILIDADES\nPython, Docker")
    assert estado_secciones(cv)["resumen"] == "ausente"
