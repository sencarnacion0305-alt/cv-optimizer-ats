"""Métricas 10-13: brecha de años, seniority, idiomas, educación, certificaciones."""
from app.services.requisitos import analizar_requisitos


def test_anios_requeridos_y_detectados():
    cv = "Backend Engineer 2017 - Present\n- Built scalable APIs"
    vac = "Senior Backend Developer with at least 5 years of experience."
    r = analizar_requisitos(cv, vac)
    assert r["anios"]["requeridos"] == 5
    assert r["anios"]["detectados"] is not None
    assert r["anios"]["cumple"] is True


def test_anios_no_cumple():
    cv = "Junior Developer 2024 - Present"
    vac = "Developer con mínimo 8 años de experiencia."
    r = analizar_requisitos(cv, vac)
    assert r["anios"]["requeridos"] == 8
    assert r["anios"]["cumple"] is False


def test_seniority_coincide_y_no():
    r = analizar_requisitos("Senior Engineer with 6 years", "Senior Backend Developer")
    assert r["seniority"]["vacante"] == "Senior"
    assert r["seniority"]["coincide"] is True
    r2 = analizar_requisitos("Junior Developer", "Senior Backend Developer")
    assert r2["seniority"]["coincide"] is False


def test_idioma_requerido():
    r = analizar_requisitos("Python developer. Inglés avanzado.",
                            "Backend con inglés fluido requerido.")
    ing = [i for i in r["idiomas"] if i["idioma"] == "Inglés"]
    assert ing and ing[0]["en_cv"] is True


def test_educacion():
    r = analizar_requisitos("B.Sc Computer Science",
                            "Se requiere grado universitario en informática.")
    assert r["educacion"]["requerido"] == "Grado universitario"
    assert r["educacion"]["cumple"] is True


def test_certificaciones():
    r = analizar_requisitos("Certified Scrum Master and PMP holder.",
                            "Buscamos PMP y Scrum Master.")
    certs = {c["cert"] for c in r["certificaciones"]}
    assert "pmp" in certs
    assert any(c["en_cv"] for c in r["certificaciones"])


def test_sin_requisitos_vacante_vacia():
    r = analizar_requisitos("Mi CV", "Buscamos a alguien.")
    assert r["anios"] is None
    assert r["seniority"] is None
    assert r["idiomas"] == []
