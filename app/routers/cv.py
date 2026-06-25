from fastapi import APIRouter, UploadFile, File, Query, Form, HTTPException
from fastapi.responses import StreamingResponse
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
from app.services.ats_checker import analizar_ats, analizar_ats_texto
from app.services.comparador_vacantes import comparar_vacantes
from app.services.parser_ats import simular_parsing
from app.services.mejorador_bullets import mejorar_bullets
from app.services.optimizador_ats import optimizar_cv
from app.services.metricas import calcular_metricas
from app.core.cv_analyzer import analizar_cv


class LimpiarVacanteRequest(BaseModel):
    texto: str


class CompararVacantesRequest(BaseModel):
    vacantes: List[str]
    cv_texto: str = ""

router = APIRouter()

MAX_UPLOAD_MB = 5
MAX_BYTES = MAX_UPLOAD_MB * 1024 * 1024


async def _leer_upload(archivo: UploadFile) -> bytes:
    """
    Lee el archivo subido de forma segura: lee como máximo MAX_BYTES+1 para NO
    cargar archivos enormes en memoria (mitiga DoS), y valida tamaño y vacío.
    """
    contenido = await archivo.read(MAX_BYTES + 1)
    if len(contenido) > MAX_BYTES:
        raise HTTPException(status_code=413,
                            detail=f"El archivo supera el límite de {MAX_UPLOAD_MB} MB.")
    if not contenido:
        raise HTTPException(status_code=400, detail="El archivo está vacío.")
    return contenido


async def _texto_de_entrada(archivo, cv_texto: str) -> str:
    """
    Entrada unificada de CV: usa el texto pegado (prioritario) o, si no hay,
    extrae el texto del archivo subido. Permite que toda pestaña acepte ambos.
    """
    if cv_texto and cv_texto.strip():
        return cv_texto.strip()
    if archivo is not None and archivo.filename:
        contenido = await _leer_upload(archivo)
        return extraer_texto(contenido, archivo.filename or "cv")
    raise HTTPException(status_code=400,
                        detail="Proporciona un CV: sube un archivo (PDF/DOCX) o pega el texto.")


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

    contenido = await _leer_upload(archivo)
    try:
        docx_adaptado = adaptar_cv_docx(contenido, vacante_texto)
        doc_adaptado   = DocxDocument(io.BytesIO(docx_adaptado))
        lineas         = _extraer_todo_texto_docx(doc_adaptado)
        texto_adaptado = _limpiar("\n".join(lineas))
    except Exception:
        raise HTTPException(status_code=422,
                            detail="No se pudo procesar el DOCX. Verifica que sea un archivo Word válido.")

    nombre = (archivo.filename or "CV").rsplit(".", 1)[0] + "_Adaptado.docx"

    return {
        "archivo_base64": base64.b64encode(docx_adaptado).decode(),
        "nombre": nombre,
        "texto": texto_adaptado,
    }


@router.post("/analizar-ats")
async def analizar_ats_endpoint(archivo: UploadFile = File(None), cv_texto: str = Form("")):
    """
    Analiza un CV y devuelve un reporte de compatibilidad ATS sin vacante.
    Acepta archivo (.docx/.pdf) o texto pegado (cv_texto).
    """
    try:
        if cv_texto and cv_texto.strip():
            return analizar_ats_texto(cv_texto.strip())
        if archivo is None or not archivo.filename:
            raise HTTPException(status_code=400,
                                detail="Proporciona un CV: sube un archivo o pega el texto.")
        contenido = await _leer_upload(archivo)
        return analizar_ats(contenido, archivo.filename or "archivo")
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=422,
                            detail="No se pudo analizar el CV. Sube un DOCX/PDF válido o pega el texto.")


@router.post("/analyze")
async def analyze_endpoint(
    archivo: UploadFile = File(None),
    cv_texto: str = Form(""),
    vacante_texto: str = Form(""),
):
    """
    Fuente ÚNICA de verdad del análisis (core.cv_analyzer.analizar_cv).
    Devuelve el objeto normalizado del que TODAS las pestañas son una vista:
    parse_rate, secciones, contacto, skills, keywords, seniority, requisitos,
    calidad, formato, cargo, sub_scores y score_global. Acepta archivo o texto.
    """
    texto = await _texto_de_entrada(archivo, cv_texto)
    try:
        return analizar_cv(texto, vacante_texto or "")
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=422,
                            detail="No se pudo analizar el CV. Revisa el archivo o el texto.")


@router.post("/metricas")
async def metricas_endpoint(
    archivo: UploadFile = File(None),
    cv_texto: str = Form(""),
    vacante_texto: str = Form(""),
):
    """
    Calcula las 15 métricas competitivas (ATS Parse Rate, Title/Experience/
    Seniority/Education/Certifications/Hard/Soft/Tools/Methodologies Match,
    Measurable Impact, Bullet Strength, Readability, Format Risk, ATS Vendor Risk)
    agrupadas en 6 categorías, cada una con score, explicación y recomendación.
    Acepta archivo (.docx/.pdf) o texto pegado; la vacante es opcional.
    """
    texto = await _texto_de_entrada(archivo, cv_texto)
    try:
        return calcular_metricas(texto, vacante_texto or "")
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=422,
                            detail="No se pudieron calcular las métricas. Revisa el CV.")


@router.post("/comparar-vacantes")
def comparar_vacantes_endpoint(request: CompararVacantesRequest):
    """
    Recibe varias vacantes del mismo rol y devuelve las keywords del mercado
    clasificadas por frecuencia. Si se aporta cv_texto, marca la cobertura.
    """
    return comparar_vacantes(request.vacantes, request.cv_texto)


@router.post("/parsing-ats")
async def parsing_ats_endpoint(archivo: UploadFile = File(None), cv_texto: str = Form("")):
    """
    Simula cómo un ATS 'lee' el CV. Acepta archivo (.docx/.pdf) o texto pegado.
    """
    texto = await _texto_de_entrada(archivo, cv_texto)
    try:
        return simular_parsing(texto)
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=422,
                            detail="No se pudo procesar el CV. Sube un DOCX/PDF válido o pega el texto.")


@router.post("/mejorar-bullets")
async def mejorar_bullets_endpoint(archivo: UploadFile = File(None), cv_texto: str = Form("")):
    """
    Reescribe bullets con verbos débiles. Acepta archivo (.docx/.pdf) o texto pegado.
    """
    texto = await _texto_de_entrada(archivo, cv_texto)
    try:
        return mejorar_bullets(texto)
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=422,
                            detail="No se pudo procesar el CV. Sube un DOCX/PDF válido o pega el texto.")


@router.post("/optimizar-cv")
@router.post("/plantilla-ats")  # alias de compatibilidad
async def optimizar_cv_endpoint(
    archivo: UploadFile = File(None),
    cv_texto: str = Form(""),
    vacante_texto: str = Form(""),
):
    """
    Optimizador ATS completo: reconstruye CUALQUIER CV en una plantilla limpia
    (una columna, secciones estándar, fechas Mes AAAA, orden cronológico inverso)
    y, si se aporta la vacante, inyecta título/keywords/acrónimos/métricas.
    Acepta archivo (.docx/.pdf) o texto pegado. Devuelve DOCX base64, cambios y score.
    """
    import base64

    # Leer la entrada UNA sola vez: el archivo se consume al leerlo, así que
    # guardamos sus bytes para reutilizarlos en el score "antes" (si lo releyéramos
    # vendría vacío y score_antes quedaría siempre en null para entrada por archivo).
    es_texto = bool(cv_texto and cv_texto.strip())
    contenido_archivo: bytes = b""
    if es_texto:
        texto = cv_texto.strip()
    elif archivo is not None and archivo.filename:
        contenido_archivo = await _leer_upload(archivo)
        texto = extraer_texto(contenido_archivo, archivo.filename or "cv")
    else:
        raise HTTPException(status_code=400,
                            detail="Proporciona un CV: sube un archivo (PDF/DOCX) o pega el texto.")

    try:
        # Score ANTES sobre el contenido original (mismo origen que la entrada).
        try:
            if es_texto:
                score_antes = analizar_ats_texto(texto)["score"]
            else:
                score_antes = analizar_ats(contenido_archivo, archivo.filename or "cv")["score"]
            score_antes_nota = None
        except Exception:
            score_antes = None
            score_antes_nota = ("No se pudo calcular el score original; se muestra "
                                "únicamente el del CV ya optimizado.")

        resultado = optimizar_cv(texto, vacante_texto or "")
        score_despues = analizar_ats(resultado["docx"], "CV_Optimizado_ATS.docx")["score"]
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=422,
            detail="No se pudo optimizar el CV. Sube un DOCX/PDF válido o pega el texto.")

    base_nombre = (archivo.filename if (archivo and archivo.filename) else "CV")
    nombre = base_nombre.rsplit(".", 1)[0] + "_Optimizado_ATS.docx"
    return {
        "archivo_base64": base64.b64encode(resultado["docx"]).decode(),
        "nombre": nombre,
        "formato_entrada": "texto" if es_texto else "archivo",
        "score_antes": score_antes,
        "score_antes_nota": score_antes_nota,
        "score_despues": score_despues,
        "cambios": resultado["cambios"],
    }


@router.post("/extraer-cv")
async def extraer_cv_endpoint(archivo: UploadFile = File(...)):
    """
    Recibe un archivo .pdf o .docx y devuelve el texto extraído.
    El frontend usa este endpoint para llenar el textarea del CV.
    """
    contenido = await _leer_upload(archivo)
    try:
        texto = extraer_texto(contenido, archivo.filename or "archivo")
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=422,
                            detail="No se pudo leer el archivo. Sube un DOCX o PDF válido.")
    return {"texto": texto, "nombre": archivo.filename}
