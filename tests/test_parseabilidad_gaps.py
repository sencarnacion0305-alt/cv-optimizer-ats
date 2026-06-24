"""Métricas 14 (parseabilidad PDF) y 15 (gaps en el historial)."""
from app.services.ats_checker import analizar_ats
from app.services.parser_ats import _detectar_gaps


# ── #14: PDF con casi nada de texto = escaneado ──
def test_pdf_escaneado_detectado():
    from fpdf import FPDF
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("helvetica", size=12)
    pdf.cell(40, 10, "Hi")  # < 150 caracteres
    contenido = bytes(pdf.output())
    r = analizar_ats(contenido, "cv.pdf")
    textos = [ch["titulo"].lower() for c in r["categorias"] for ch in c["checks"]]
    assert any("escaneado" in t or "sin texto" in t for t in textos)
    assert r["score"] == 0


# ── #15: huecos en el historial ──
def test_gap_detectado():
    lineas = ["Engineer Jan 2018 - Dec 2019", "Developer Jun 2021 - Present"]
    gaps = _detectar_gaps(lineas)
    assert len(gaps) == 1
    assert gaps[0]["meses"] >= 6


def test_sin_gap_si_continuo():
    lineas = ["Engineer 2018 - 2020", "Developer 2020 - 2023"]
    assert _detectar_gaps(lineas) == []


def test_gap_corto_no_cuenta():
    lineas = ["Engineer Jan 2020 - Mar 2022", "Developer Jun 2022 - Present"]
    # 3 meses de hueco -> no se reporta
    assert _detectar_gaps(lineas) == []
