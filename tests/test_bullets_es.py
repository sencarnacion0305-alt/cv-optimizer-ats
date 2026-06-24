"""
Ronda final, punto 2: las métricas inyectadas en «Mejorar bullets» deben estar
en español, conservar los placeholders y no pegar el número a la palabra
siguiente ("[number]horas" -> "[number] horas").
"""
import re

from app.services.mejorador_bullets import (
    _a_placeholder, mejorar_bullets, _PLANTILLAS_METRICA, _PLANTILLAS_SECTOR,
)

# Conectores/verbos en inglés que NO deben aparecer en los sufijos.
_INGLES = re.compile(
    r"\b(improving|supporting|saving|reducing|cutting|across|by|users|hours|"
    r"team|budget|deals|patients|students|servers|of|the|per|weekly|monthly)\b",
    re.IGNORECASE)


def test_plantillas_en_espanol():
    for dic in (_PLANTILLAS_METRICA, _PLANTILLAS_SECTOR):
        for cat, opciones in dic.items():
            for s in opciones:
                assert not _INGLES.search(s), f"Sufijo en inglés en {cat!r}: {s!r}"


def test_placeholder_no_pega_palabra():
    # El espacio antes de la palabra debe conservarse al sustituir el número.
    assert _a_placeholder("ahorrando ~15 horas a la semana") == \
        "ahorrando [number] horas a la semana"
    assert _a_placeholder("dando servicio a 1M+ usuarios") == "dando servicio a [number] usuarios"
    assert _a_placeholder("en ~200 transacciones") == "en [number] transacciones"
    # Nada de "[number]horas" / "[number]usuarios"
    for t in ("ahorrando ~15 horas", "1000 usuarios", "~120 estudiantes"):
        assert not re.search(r"\][A-Za-zÁÉÍÓÚáéíóúñ]", _a_placeholder(t))


def test_placeholders_se_conservan():
    assert _a_placeholder("en ~25%") == "en [estimated %]"
    assert _a_placeholder("de ~$50K") == "de [$ amount]"


def test_bullets_es_integracion():
    cv = ("Experiencia\nBackend Developer\n"
          "- Responsable de los despliegues con Docker y CI/CD\n"
          "- Automaticé scripts de monitorización del sistema")
    r = mejorar_bullets(cv)
    assert r["advertencia"]  # advertencia anterior intacta
    for m in r["mejoras"]:
        if m["metrica_agregada"]:
            assert not _INGLES.search(m["mejorado"]), m["mejorado"]
            assert not re.search(r"\][A-Za-zÁÉÍÓÚáéíóúñ]", m["mejorado"])  # sin pegar
