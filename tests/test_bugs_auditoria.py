"""Lote de auditoría en producción — bugs 1, 3, 5, 6."""
from app.services.adaptador import (
    _keywords_de, _formato_skill, _extraer_habilidades, _experiencia_estructurada,
)
from app.services.mejorador_bullets import mejorar_bullets
from app.services.scoring import _dim_formato
from app.services.limpiador import limpiar_vacante
from app.services.ats_checker import analizar_ats_texto

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


# ── Bug 2: limpiar vacante quita beneficios y 'sobre nosotros' ──
_VAC = """Backend Developer
Requisitos
- Python y Django
- Docker y AWS
Sobre nosotros
Somos una startup con gran ambiente.
Beneficios
- Seguro médico privado
- Comida gratis en la oficina
- Salario competitivo
- 25 días de vacaciones"""


def test_limpiar_quita_beneficios():
    limpio = limpiar_vacante(_VAC).lower()
    assert "python" in limpio                      # conserva requisitos
    assert "seguro" not in limpio                  # quita beneficios
    assert "comida gratis" not in limpio
    assert "salario competitivo" not in limpio
    assert "startup" not in limpio                 # quita 'sobre nosotros'


# ── Bug 4: jerarquía puesto → logros ──
def test_experiencia_estructurada():
    cv = ("Juan\nExperiencia\nBackend Developer  Jan 2020 - Present\nTechCorp\n"
          "- Construí APIs REST en Python\n- Lideré un equipo de 5 ingenieros\n"
          "Junior Developer  2017 - 2019\nAcme Startup\n- Mantuve servicios legacy")
    est = _experiencia_estructurada(cv)
    assert len(est) == 2
    assert "Backend Developer" in est[0]["titulo"]
    assert len(est[0]["bullets"]) == 2
    # los logros NO deben quedar como títulos
    assert not any("Construí" in p["titulo"] for p in est)


# ── Bug 7: análisis ATS también acepta texto plano ──
def test_analizar_ats_texto():
    cv = ("Ana Garcia\nana@mail.com | +34 600 123\nResumen\n"
          "Ingeniera con 5 años en sistemas distribuidos y liderazgo de equipos.\n"
          "Experiencia\nEngineer 2020 - Present\n- Construí APIs reduciendo latencia 40%\n"
          "Educación\nB.Sc 2014 - 2018\nHabilidades\nPython, AWS, Docker")
    r = analizar_ats_texto(cv)
    assert r["tipo_archivo"] == "texto"
    assert len(r["categorias"]) == 5
    assert 0 <= r["score"] <= 100
    # contacto y estructura se evalúan aunque no haya archivo
    assert any(c["nombre"] == "Estructura" and c["puntos"] > 0 for c in r["categorias"])
