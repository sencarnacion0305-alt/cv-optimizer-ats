"""
Esquema de datos del tracker de aplicaciones (listo para sincronizar en la nube).

aplicación = {puesto, empresa, estado, scoreATS, link, notas, fecha}

Acepta tanto la clave `score` (la que usa el front en localStorage) como `score_ats`,
para que el mismo objeto sirva en modo local y en modo sincronizado sin migración.
"""
from typing import List, Optional

from pydantic import BaseModel, Field, validator

ESTADOS = ("borrador", "enviado", "entrevista", "oferta", "rechazado")


class Aplicacion(BaseModel):
    id: int
    puesto: str
    empresa: str
    estado: str = "borrador"
    score_ats: Optional[int] = Field(None, alias="score")   # scoreATS (0-100)
    link: Optional[str] = ""
    notas: Optional[str] = ""
    fecha: Optional[str] = ""                                # ISO 8601

    class Config:
        allow_population_by_field_name = True               # acepta "score" o "score_ats"

    @validator("estado")
    def _estado_valido(cls, v):
        if v not in ESTADOS:
            raise ValueError(f"estado debe ser uno de {ESTADOS}")
        return v

    @validator("score_ats", pre=True)
    def _score_a_int(cls, v):
        if v in (None, "", " "):
            return None
        try:
            return max(0, min(100, int(float(v))))
        except (ValueError, TypeError):
            return None


class TrackerSync(BaseModel):
    """Cuerpo de la sincronización (subida): la lista completa de aplicaciones."""
    aplicaciones: List[Aplicacion] = []
