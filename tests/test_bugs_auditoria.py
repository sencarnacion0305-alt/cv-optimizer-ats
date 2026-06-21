"""Lote de auditoría en producción — bugs 1, 3, 5, 6."""
from app.services.adaptador import (
    _keywords_de, _formato_skill, _extraer_habilidades,
)
from app.services.mejorador_bullets import mejorar_bullets
from app.services.scoring import _dim_formato

CV_EXP = """Juan Perez
Experiencia
Backend Engineer Jan 2020 - Present
- Responsable de la infraestructura cloud del equipo de desarrollo
- Ayudé a migrar 20 servicios críticos a contenedores en producción"""


# ── Bug 1: línea de contacto con | no es tabla ──
def test_contacto_con_pipes_no_es_tabla():
    cv = ("Ana Garcia\nana@mail.com | +34 600 123 | Madrid\nResumen\n"
          "Ingeniera con experiencia en sistemas distribuidos y liderazgo.\n"
          "Experiencia\n- Construi APIs escalables")
    tabla = [c for c in _dim_formato(cv)["checks"] if "tabla" in c["label"].lower()][0]
    assert tabla["ok"] is True


def test_pipes_en_muchas_lineas_si_es_tabla():
    cv = "col a | col b | col c\nx1 | y1 | z1\nx2 | y2 | z2\nx3 | y3 | z3"
    tabla = [c for c in _dim_formato(cv)["checks"] if "tabla" in c["label"].lower()][0]
    assert tabla["ok"] is False


# ── Bug 3: nombre de empresa no es keyword ──
def test_empresa_no_es_keyword():
    vac = "Backend Developer en Acme. Acme es una empresa líder. Buscamos Python, Docker, AWS."
    kws = _keywords_de(vac)
    assert "acme" not in kws
    assert "python" in kws  # la skill real sí


# ── Bug 5: verbos débiles en español (con viñetas) ──
def test_verbos_debiles_espanol():
    r = mejorar_bullets(CV_EXP)
    assert r["n_verbos"] >= 1
    textos = " ".join(m["mejorado"].lower() for m in r["mejoras"])
    assert "responsable de" not in textos
    assert "ayudé a" not in textos


# ── Bug 6: casing canónico de skills ──
def test_casing_skills():
    assert _formato_skill("docker") == "Docker"
    assert _formato_skill("postgresql") == "PostgreSQL"
    assert _formato_skill("aws") == "AWS"
    assert _formato_skill("python") == "Python"


def test_habilidades_con_casing():
    skills = _extraer_habilidades("Ana\nHabilidades\nDocker, Python, AWS, PostgreSQL", [])
    assert "Docker" in skills and "Python" in skills and "AWS" in skills
