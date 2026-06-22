from pydantic import BaseModel
from typing import List, Optional  # Pydantic v1 compatible


# --- Request ---

class AdaptarCVRequest(BaseModel):
    cv_texto: str
    vacante_texto: str


# --- Partes del CV adaptado ---

class CVAdaptado(BaseModel):
    resumen: str
    experiencia: List[str]
    habilidades: List[str]
    experiencia_estructurada: Optional[List[dict]] = None  # [{titulo, bullets:[...]}]


# --- Response ---

class AdaptarCVResponse(BaseModel):
    cv_adaptado: CVAdaptado
    score_match: int
    keywords_cubiertas: List[str]
    keywords_sugeridas: List[str]
    notas_para_usuario: List[str]
    titulo_vacante: Optional[str] = None
    titulo_cubierto: bool = True
    score_desglose: Optional[dict] = None  # 5 dimensiones: {total, dimensiones:[...]}

    # --- Campos enriquecidos (compatibilidad: todos opcionales) ---
    score: Optional[int] = None                              # alias de score_match
    score_breakdown: Optional[dict] = None                   # {dimension: {score, max}}
    keywords_hard_skills_cubiertas: Optional[List[str]] = None
    keywords_soft_skills_cubiertas: Optional[List[str]] = None
    keywords_hard_skills_faltantes: Optional[List[str]] = None
    keywords_soft_skills_faltantes: Optional[List[str]] = None
    contact_info: Optional[dict] = None
    content_signals: Optional[dict] = None
    requisitos: Optional[dict] = None  # años, seniority, idiomas, educación, certificaciones
