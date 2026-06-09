"""
Extractor de texto desde archivos PDF y DOCX.
"""

import io
import re

from fastapi import HTTPException


def extraer_texto(contenido: bytes, nombre_archivo: str) -> str:
    """
    Recibe los bytes del archivo y su nombre original.
    Devuelve el texto extraído como string limpio.
    """
    ext = nombre_archivo.rsplit(".", 1)[-1].lower()

    if ext == "pdf":
        return _desde_pdf(contenido)
    elif ext in ("docx", "doc"):
        return _desde_docx(contenido)
    else:
        raise HTTPException(
            status_code=415,
            detail=f"Formato no soportado: .{ext}. Sube un archivo .pdf o .docx",
        )


def _desde_pdf(contenido: bytes) -> str:
    try:
        import pdfplumber
    except ImportError:
        raise HTTPException(status_code=500, detail="pdfplumber no está instalado.")

    texto_paginas = []
    with pdfplumber.open(io.BytesIO(contenido)) as pdf:
        for pagina in pdf.pages:
            t = pagina.extract_text()
            if t:
                texto_paginas.append(t)

    if not texto_paginas:
        raise HTTPException(
            status_code=422,
            detail="No se pudo extraer texto del PDF. "
                   "Puede ser un PDF escaneado (imagen). Prueba pegando el texto manualmente.",
        )

    return _limpiar("\n".join(texto_paginas))


def _desde_docx(contenido: bytes) -> str:
    try:
        from docx import Document
    except ImportError:
        raise HTTPException(status_code=500, detail="python-docx no está instalado.")

    doc = Document(io.BytesIO(contenido))
    lineas = _extraer_todo_texto_docx(doc)

    if not lineas:
        raise HTTPException(
            status_code=422,
            detail="El archivo DOCX parece estar vacío.",
        )

    return _limpiar("\n".join(lineas))


def _extraer_todo_texto_docx(doc) -> list:
    """
    Extrae texto de paragrafos Y de celdas de tablas en orden de aparicion
    en el documento. Los CVs con columnas usan tablas para el layout.
    """
    from docx.oxml.ns import qn

    lineas = []

    def _texto_elemento(elem):
        """Recorre el XML del elemento y recoge texto de parrafos."""
        for p_elem in elem.iter(qn("w:p")):
            texto = "".join(
                r.text or "" for r in p_elem.iter(qn("w:t"))
            ).strip()
            if texto:
                lineas.append(texto)

    # Recorrer el body en orden: paragrafos y tablas mezclados
    body = doc.element.body
    for child in body:
        tag = child.tag.split("}")[-1] if "}" in child.tag else child.tag
        if tag == "p":
            texto = "".join(
                r.text or "" for r in child.iter(qn("w:t"))
            ).strip()
            if texto:
                lineas.append(texto)
        elif tag == "tbl":
            # Recorrer filas y celdas de la tabla
            for row in child.iter(qn("w:tr")):
                for cell in row.iter(qn("w:tc")):
                    for p_elem in cell.iter(qn("w:p")):
                        texto = "".join(
                            r.text or "" for r in p_elem.iter(qn("w:t"))
                        ).strip()
                        if texto:
                            lineas.append(texto)

    return lineas


def _limpiar(texto: str) -> str:
    """Elimina líneas vacías múltiples y espacios redundantes."""
    texto = re.sub(r"\r\n|\r", "\n", texto)          # normalizar saltos
    texto = re.sub(r"[ \t]+", " ", texto)             # espacios múltiples
    texto = re.sub(r"\n{3,}", "\n\n", texto)          # máximo 2 saltos seguidos
    return texto.strip()
