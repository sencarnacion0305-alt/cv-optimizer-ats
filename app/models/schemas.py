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


# --- Response ---

class AdaptarCVResponse(BaseModel):
    cv_adaptado: CVAdaptado
    score_match: int
    keywords_cubiertas: List[str]
    keywords_sugeridas: List[str]
    notas_para_usuario: List[str]
    titulo_vacante: Optional[str] = None
    titulo_cubierto: bool = True
