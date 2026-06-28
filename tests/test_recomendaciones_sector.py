"""
Bug 4.2: la jerga de seguridad (MTTR, incidentes, alertas, amenazas, vulnerabilidades)
NO debe aparecer en recomendaciones/bullets de perfiles que no son de seguridad.
Se genera según el rol/keywords detectados; un perfil de seguridad sí puede recibirla.
"""
import re

import pytest

from app.services.mejorador_bullets import (
    detectar_sector,
    ejemplo_metricas,
    mejorar_bullets,
)

_JERGA_SEG = re.compile(r"mttr|incidente|alerta|amenaza|vulnerab|phishing|siem|\bsoc\b",
                        re.IGNORECASE)

CV_MARKETING = (
    "Marketing Manager\n"
    "- Responsable de las campañas de redes sociales de la marca\n"
    "- Encargado del posicionamiento SEO y la estrategia de contenido\n"
    "- Ayudé a la planificación de la publicidad digital\n"
    "- Trabajé en el análisis de engagement y conversión"
)
CV_DEV = (
    "Backend Developer\n"
    "- Responsable del backend de la plataforma de pagos en Python\n"
    "- Encargado de la integración de APIs con terceros\n"
    "- Ayudé al diseño de la arquitectura de microservicios en AWS\n"
    "- Trabajé en el despliegue continuo con Docker"
)
CV_SEGURIDAD = (
    "Analista de Seguridad (SOC)\n"
    "- Responsable del monitoreo de alertas en el SIEM\n"
    "- Encargado de la respuesta a incidentes y threat hunting\n"
    "- Ayudé a la gestión de vulnerabilidades y parcheo\n"
    "- Trabajé en la contención de campañas de phishing"
)


def test_clasificacion_de_sector():
    assert detectar_sector(CV_MARKETING) == "marketing"
    assert detectar_sector(CV_DEV) == "tech"
    assert detectar_sector(CV_SEGURIDAD) == "seguridad"


@pytest.mark.parametrize("cv", [CV_MARKETING, CV_DEV])
def test_ejemplo_metricas_sin_jerga_seguridad(cv):
    assert not _JERGA_SEG.search(ejemplo_metricas(cv))


def test_ejemplo_metricas_seguridad_si_aplica():
    assert _JERGA_SEG.search(ejemplo_metricas(CV_SEGURIDAD))


@pytest.mark.parametrize("cv", [CV_MARKETING, CV_DEV])
def test_bullets_no_seguridad_sin_jerga(cv):
    r = mejorar_bullets(cv)
    blob = " ".join(m["mejorado"] for m in r["mejoras"])
    assert r["mejoras"], "deberia sugerir mejoras para verbos debiles"
    assert not _JERGA_SEG.search(blob)


def test_bullets_seguridad_pueden_tener_jerga():
    # No exigimos que SIEMPRE aparezca, pero el perfil de seguridad debe poder
    # recibir métricas de su dominio (categorías de _PLANTILLAS_METRICA).
    r = mejorar_bullets(CV_SEGURIDAD)
    assert r["mejoras"]
    # Al menos las cifras siguen siendo placeholders editables (sin números crudos).
    for m in r["mejoras"]:
        if m["metrica_agregada"]:
            sin_ph = re.sub(r"\[[^\]]*\]", "", m["mejorado"])
            assert not re.search(r"\d", sin_ph)


def test_notas_adaptador_sin_jerga_para_no_seguridad():
    from app.services.adaptador import _generar_notas
    notas = _generar_notas(["python"], ["sql"], 75, CV_MARKETING)
    assert not _JERGA_SEG.search(" ".join(notas))


def test_ats_checker_sin_jerga_para_no_seguridad():
    from app.services.ats_checker import analizar_ats_texto
    rep = analizar_ats_texto(CV_MARKETING)
    blob = " ".join(
        ch.get("detalle", "") + " " + ch.get("titulo", "")
        for cat in rep["categorias"] for ch in cat["checks"]
    )
    assert not _JERGA_SEG.search(blob)
