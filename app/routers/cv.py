from fastapi import APIRouter, UploadFile, File, Query, Form
from fastapi.responses import JSONResponse, StreamingResponse
import io
from typing import List

from pydantic import BaseModel

from app.models.schemas import AdaptarCVRequest, AdaptarCVResponse
from app.services.adaptador import adaptar_cv
from app.services.extractor import extraer_texto, _extraer_todo_texto_docx, _limpiar
from app.services.limpiador import limpiar_vacante
from app.services.generador_cv import generar_cv_adaptado
from app.services.exportador import exportar_pdf, exportar_docx
from app.services.adaptador_docx import adaptar_cv_docx
from app.services.ats_checker import analizar_ats
from app.services.comparador_vacantes import comparar_vacantes
from app.services.parser_ats import simular_parsing
from app.services.mejorador_bullets import mejorar_bullets


class LimpiarVacanteRequest(BaseModel):
    texto: str


class CompararVacantesRequest(BaseModel):
    vacantes: List[str]
    cv_texto: str = ""

router = APIRouter()

MAX_UPLOAD_MB = 5
MAX_BYTES = MAX_UPLOAD_MB * 1024 * 1024


@router.post("/adaptar", response_model=AdaptarCVResponse)
def adaptar_cv_endpoint(request: AdaptarCVRequest):
    """
    Recibe el texto del CV y la descripción de la vacante,
    y devuelve el CV adaptado con análisis ATS.
    """
    return adaptar_cv(request)


@router.post("/generar-cv")
def generar_cv_endpoint(request: AdaptarCVRequest):
    """
    Genera un CV completo adaptado a la vacante, listo para copiar.
    Incluye resumen reescrito con keywords, experiencia y habilidades.
    """
    return generar_cv_adaptado(request.cv_texto, request.vacante_texto)


@router.post("/exportar-cv")
def exportar_cv_endpoint(
    request: AdaptarCVRequest,
    formato: str = Query(default="pdf", pattern="^(pdf|docx)$"),
):
    """
    Genera el CV adaptado y lo devuelve como archivo descargable.
    Parámetro: formato=pdf (por defecto) o formato=docx
    """
    nombre_archivo = "CV_Adaptado"

    if formato == "docx":
        contenido = exportar_docx(request.cv_texto, request.vacante_texto)
        media_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        headers = {"Content-Disposition": f'attachment; filename="{nombre_archivo}.docx"'}
    else:
        contenido = exportar_pdf(request.cv_texto, request.vacante_texto)
        media_type = "application/pdf"
        headers = {"Content-Disposition": f'attachment; filename="{nombre_archivo}.pdf"'}

    return StreamingResponse(io.BytesIO(contenido), media_type=media_type, headers=headers)


@router.post("/limpiar-vacante")
def limpiar_vacante_endpoint(request: LimpiarVacanteRequest):
    """
    Recibe la descripción completa de una vacante y devuelve
    solo la información relevante (requisitos, responsabilidades,
    habilidades), descartando beneficios, cultura, datos legales, etc.
    """
    texto_limpio = limpiar_vacante(request.texto)
    return {"texto": texto_limpio}


@router.post("/adaptar-docx-original")
async def adaptar_docx_original_endpoint(
    archivo: UploadFile = File(...),
    vacante_texto: str = Form(""),
):
    """
    Recibe el DOCX original, lo adapta a la vacante y devuelve:
    - El archivo DOCX adaptado en base64 para descarga
    - El texto extraido del DOCX adaptado para actualizar el textarea y re-analizar
    """
    import base64
    from docx import Document as DocxDocument

    contenido = await archivo.read()
    if len(contenido) > MAX_BYTES:
        return JSONResponse(status_code=413, content={"detail": "Archivo mayor a 5 MB."})

    docx_adaptado = adaptar_cv_docx(contenido, vacante_texto)

    # Extraer texto del DOCX adaptado (parrafos + tablas) para actualizar el textarea
    doc_adaptado   = DocxDocument(io.BytesIO(docx_adaptado))
    lineas         = _extraer_todo_texto_docx(doc_adaptado)
    texto_adaptado = _limpiar("\n".join(lineas))

    nombre = (archivo.filename or "CV").rsplit(".", 1)[0] + "_Adaptado.docx"

    return {
        "archivo_base64": base64.b64encode(docx_adaptado).decode(),
        "nombre": nombre,
        "texto": texto_adaptado,
    }


@router.post("/analizar-ats")
async def analizar_ats_endpoint(archivo: UploadFile = File(...)):
    """
    Analiza un CV (.docx o .pdf) y devuelve un reporte de compatibilidad ATS
    SIN necesidad de una vacante: formato, estructura, contacto y contenido.
    """
    contenido = await archivo.read()
    if len(contenido) > MAX_BYTES:
        return JSONResponse(
            status_code=413,
            content={"detail": f"El archivo supera el límite de {MAX_UPLOAD_MB} MB."},
        )
    return analizar_ats(contenido, archivo.filename or "archivo")


@router.post("/comparar-vacantes")
def comparar_vacantes_endpoint(request: CompararVacantesRequest):
    """
    Recibe varias vacantes del mismo rol y devuelve las keywords del mercado
    clasificadas por frecuencia. Si se aporta cv_texto, marca la cobertura.
    """
    return comparar_vacantes(request.vacantes, request.cv_texto)


@router.post("/parsing-ats")
async def parsing_ats_endpoint(archivo: UploadFile = File(...)):
    """
    Simula como un ATS 'lee' el CV: extrae nombre, contacto, experiencia,
    educacion y skills, y resalta lo que no pudo detectar.
    """
    contenido = await archivo.read()
    if len(contenido) > MAX_BYTES:
        return JSONResponse(
            status_code=413,
            content={"detail": f"El archivo supera el límite de {MAX_UPLOAD_MB} MB."},
        )
    texto = extraer_texto(contenido, archivo.filename or "archivo")
    return simular_parsing(texto)


@router.post("/mejorar-bullets")
async def mejorar_bullets_endpoint(archivo: UploadFile = File(...)):
    """
    Detecta bullets con verbos debiles en el CV y los reescribe con
    verbos de accion (por reglas, sin API).
    """
    contenido = await archivo.read()
    if len(contenido) > MAX_BYTES:
        return JSONResponse(
            status_code=413,
            content={"detail": f"El archivo supera el límite de {MAX_UPLOAD_MB} MB."},
        )
    texto = extraer_texto(contenido, archivo.filename or "archivo")
    return mejorar_bullets(texto)


@router.post("/extraer-cv")
async def extraer_cv_endpoint(archivo: UploadFile = File(...)):
    """
    Recibe un archivo .pdf o .docx y devuelve el texto extraído.
    El frontend usa este endpoint para llenar el textarea del CV.
    """
    contenido = await archivo.read()

    if len(contenido) > MAX_BYTES:
        return JSONResponse(
            status_code=413,
            content={"detail": f"El archivo supera el límite de {MAX_UPLOAD_MB} MB."},
        )

    texto = extraer_texto(contenido, archivo.filename or "archivo")
    return {"texto": texto, "nombre": archivo.filename}
