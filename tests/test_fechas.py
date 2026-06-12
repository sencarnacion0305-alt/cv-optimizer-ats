"""P3 — normalización de fechas a 'Mes AAAA' con separador uniforme."""
import pytest

from app.services.optimizador_ats import _normalizar_fechas

# Los tres formatos del CV de prueba + el resultado esperado
CASOS = [
    ("Jan 2021 - Present", "Jan 2021 - Present"),
    ("06/2019 — 12/2020", "Jun 2019 - Dec 2020"),
    ("2014 - 2018", "2014 - 2018"),
]


@pytest.mark.parametrize("entrada,esperado", CASOS)
def test_tres_formatos(entrada, esperado):
    salida, _ = _normalizar_fechas(entrada, "en")
    assert salida == esperado


@pytest.mark.parametrize("entrada", [c[0] for c in CASOS])
def test_separador_uniforme(entrada):
    """Ninguna salida debe conservar guiones largos; todas usan ' - '."""
    salida, _ = _normalizar_fechas(entrada, "en")
    assert "—" not in salida
    assert "–" not in salida
    assert " - " in salida


def test_variantes_extra():
    assert _normalizar_fechas("Mar. 2018 – Dic 2019", "en")[0] == "Mar 2018 - Dec 2019"
    assert _normalizar_fechas("'19 - '22", "en")[0] == "2019 - 2022"
