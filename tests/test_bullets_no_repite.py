"""
Bug 1.3: dos bullets distintos no deben recibir la misma plantilla de mejora; las
métricas se varían dentro del mismo CV (sin repetir hasta agotar el pool).
"""
import re

from app.services.mejorador_bullets import mejorar_bullets, sufijo_metrica


def _sufijo(mejorado: str) -> str:
    return mejorado.split(",", 1)[-1].strip().rstrip(".")


CV_TECH = (
    "Experiencia en desarrollo de software con Python y AWS\n"
    "- Responsable del backend de la plataforma de pagos\n"
    "- Encargado de la integración con terceros\n"
    "- Ayudé a la arquitectura de microservicios\n"
    "- Trabajé en el rediseño de la base de datos\n"
    "- A cargo de la documentación técnica"
)


def test_bullets_no_reciben_la_misma_plantilla():
    r = mejorar_bullets(CV_TECH)
    sufijos = [_sufijo(m["mejorado"]) for m in r["mejoras"] if m["metrica_agregada"]]
    assert len(sufijos) >= 4
    assert len(sufijos) == len(set(sufijos))      # todos únicos


def test_sufijo_metrica_no_repite_con_usados():
    contadores, usados = {}, set()
    vistos = []
    for _ in range(6):
        s = sufijo_metrica("logré un resultado relevante", contadores, "general", usados)
        vistos.append(s)
    # 'general' tiene 4 plantillas -> las 4 primeras deben ser distintas
    assert len(set(vistos[:4])) == 4


def test_placeholders_y_advertencia_intactos():
    r = mejorar_bullets(CV_TECH)
    assert r["advertencia"]
    for m in r["mejoras"]:
        if m["metrica_agregada"]:
            # marcador editable presente y sin números crudos pegados
            assert re.search(r"\[(number|% estimado|\$ amount)\]", m["mejorado"])
            sin_ph = re.sub(r"\[[^\]]*\]", "", m["mejorado"])
            assert not re.search(r"\d", sin_ph)
